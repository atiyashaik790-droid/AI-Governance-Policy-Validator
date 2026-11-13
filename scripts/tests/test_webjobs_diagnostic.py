"""Local mock-only regression tests, including a real abrupt child-process exit."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
from urllib.error import URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webjobs_diagnostic import (
    Budget, Diagnostic, Drift, Expired, FLAG, IDENTITY, Journal, RELEASE,
    Response, SafetyError, Snapshot, TARGET, actual_startup,
)

KEY = bytes(range(32))  # Synthetic journal key only, never a production key.
ORIGINAL = {"EXAMPLE_SECRET": "synthetic-secret-never-print", "SSO_ENABLED": "true"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("NETWORK_FORBIDDEN_IN_LOCAL_TEST")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)


class FakeClock:
    def __init__(self, wall=1000):
        self.utc, self.elapsed = wall, 0

    def wall(self):
        return self.utc

    def mono(self):
        return self.elapsed

    def sleep(self, seconds):
        self.utc += seconds
        self.elapsed += seconds


class FakeIO:
    def __init__(self, clock, cloud_file=None):
        self.clock, self.cloud_file = clock, cloud_file
        if cloud_file and cloud_file.exists():
            data = json.loads(cloud_file.read_text())
            self.values, self.version = data["values"], data["version"]
        else:
            self.values, self.version = deepcopy(ORIGINAL), 0
        self.calls, self.hooks, self.counts = [], {}, {}
        self.after_replace = None
        self.list_status = 200
        self.startup_ready = True
        self.wrong_identity = False

    def event(self, method, target, timeout, *args):
        assert target == TARGET and 0 < timeout <= 10
        self.counts[method] = self.counts.get(method, 0) + 1
        self.calls.append((method, self.clock.wall(), args))
        if method in self.hooks:
            self.hooks[method](self, self.counts[method], *args)

    def identity(self, target, timeout):
        self.event("identity", target, timeout)
        return {"id": "wrong" if self.wrong_identity else TARGET,
                "identity": IDENTITY, "runtime": "PYTHON|3.13"}

    def settings(self, target, timeout):
        self.event("settings", target, timeout)
        return Snapshot(deepcopy(self.values), str(self.version))

    def replace(self, target, expected, desired, timeout):
        self.event("replace", target, timeout, desired)
        if expected != Snapshot(self.values, str(self.version)):
            raise Drift("CAS_FAILED")
        assert {k: v for k, v in desired.items() if k != FLAG} == {
            k: v for k, v in self.values.items() if k != FLAG
        }
        self.values, self.version = deepcopy(desired), self.version + 1
        if self.cloud_file:
            self.cloud_file.write_text(json.dumps({"values": self.values, "version": self.version}))
        if self.after_replace:
            self.after_replace(self)

    def startup_lines(self, target, since, timeout):
        self.event("startup_lines", target, timeout)
        if not self.startup_ready:
            return []
        stamp = datetime.fromtimestamp(self.clock.wall(), timezone.utc).isoformat().replace("+00:00", "Z")
        return [stamp + " Starting container: abc_app-governance-validator-atiya-1026.",
                stamp + " Site startup probe succeeded after 35.0 seconds.",
                stamp + " Site started."]

    def health(self, target, route, timeout):
        self.event("health", target, timeout, route)
        return Response(200, {"status": "ok"} if route == "/health" else
                        {"status": "ready", "release": RELEASE, "revision": "005"})

    def listing(self, target, timeout):
        self.event("listing", target, timeout)
        return Response(self.list_status, [])


def setup(tmp_path):
    clock = FakeClock()
    io = FakeIO(clock)
    journal = Journal(tmp_path / "secure" / "recovery.aesgcm", KEY)
    return clock, io, journal, Diagnostic(io, journal, clock)


def test_normal_success_and_three_spaced_pairs(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    result = run.run(1000, 1900)
    assert result["overall"] == "PASS" and result["status"] == "RESTORED"
    assert io.values == ORIGINAL and io.counts["listing"] == 1
    audit = journal.load()["audit"]
    pairs = [x for x in audit if x["event"] == "HEALTH_PAIR" and x["phase"] == "diagnostic"]
    assert [x["consecutive"] for x in pairs] == [1, 2, 3]
    assert all(b["utc_epoch"] - a["utc_epoch"] == 10 for a, b in zip(pairs, pairs[1:]))
    assert "ACTUAL_STARTUP_COMPLETE" in [x["event"] for x in audit]


def test_expiry_before_mutation_never_calls_transport(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    clock.utc = 1900
    with pytest.raises(Expired):
        run.run(1000, 1900)
    assert io.calls == [] and not journal.path.exists()


def test_expiry_between_intent_and_mutation(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    save = journal.save

    def expire_on_intent(state):
        save(state)
        if state["audit"][-1:][0]["event"] == "MUTATION_INTENT":
            clock.utc = 2000

    # PREPARED has no events.
    def guarded_save(state):
        if state["audit"]:
            expire_on_intent(state)
        else:
            save(state)

    journal.save = guarded_save
    result = run.run(1000, 1900)
    assert result["flag_restored"] and result["overall"] == "BLOCKED_WINDOW_EXCEEDED"
    assert not io.counts.get("replace") and not io.counts.get("listing")


def test_expiry_after_mutation_does_not_block_cleanup(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def suspend(transport):
        if FLAG in transport.values:
            clock.utc += 5 * 3600  # Host suspension: monotonic need not advance.

    io.after_replace = suspend
    result = run.run(1000, 1900)
    assert result["flag_restored"] and result["cleanup_overdue"]
    assert result["overall"] == "BLOCKED_WINDOW_EXCEEDED"
    assert io.values == ORIGINAL and io.counts["replace"] == 2
    assert not io.counts.get("listing")
    assert any(x["event"] == "RESTORATION_STARTED" and x["overdue"] for x in journal.load()["audit"])


def test_real_process_termination_then_fresh_process_state_recovery(tmp_path):
    cloud = tmp_path / "mock-cloud.json"
    journal_path = tmp_path / "secure" / "recovery.aesgcm"
    code = """
import os, sys, socket
sys.path.insert(0, sys.argv[1])
from test_webjobs_diagnostic import FakeClock, FakeIO, KEY
from webjobs_diagnostic import Diagnostic, Journal
from pathlib import Path
socket.create_connection=lambda *a,**kw: (_ for _ in ()).throw(AssertionError('NO_NETWORK'))
clock=FakeClock();io=FakeIO(clock,Path(sys.argv[2]))
io.after_replace=lambda io: os._exit(42)
Diagnostic(io,Journal(Path(sys.argv[3]),KEY),clock).run(1000,1900)
"""
    child = subprocess.run([sys.executable, "-c", code, str(Path(__file__).parent),
                            str(cloud), str(journal_path)], capture_output=True, timeout=10)
    assert child.returncode == 42
    assert FLAG in json.loads(cloud.read_text())["values"]
    clock = FakeClock(3000)
    io = FakeIO(clock, cloud)
    result = Diagnostic(io, Journal(journal_path, KEY), clock).recover()
    assert result["flag_restored"] and io.values == ORIGINAL
    assert result["overall"] == "BLOCKED_WINDOW_EXCEEDED"
    assert not io.counts.get("startup_lines") and not io.counts.get("listing")


def test_repeated_restoration_is_idempotent_and_no_diagnostic_resume(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    run.run(1000, 1900)
    writes = io.counts["replace"]
    clock.utc = 5000
    assert Diagnostic(io, Journal(journal.path, KEY), clock).recover()["flag_restored"]
    assert run.recover()["flag_restored"]
    assert io.counts["replace"] == writes and io.counts["listing"] == 1
    with pytest.raises(SafetyError, match="EXISTING_STATE_RECOVER_ONLY"):
        run.run(5000, 5900)


def test_unrelated_drift_is_detected_and_preserved(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def drift(transport):
        if FLAG in transport.values:
            transport.values["OTHER_OPERATOR_SETTING"] = "preserve-me"

    io.after_replace = drift
    result = run.run(1000, 1900)
    assert result["status"] == "RESTORED_WITH_DRIFT" and result["unrelated_drift"]
    assert io.values == {**ORIGINAL, "OTHER_OPERATOR_SETTING": "preserve-me"}
    assert not io.counts.get("listing")


def test_same_flag_drift_fails_closed_without_overwrite(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def drift(transport):
        transport.values[FLAG] = "other-operator-value"

    io.after_replace = drift
    result = run.run(1000, 1900)
    assert result["status"] == "BLOCKED_RESTORATION_UNVERIFIED"
    assert io.values[FLAG] == "other-operator-value" and io.counts["replace"] == 1
    assert not io.counts.get("listing")


def test_timeout_resets_streak_and_sanitizes_underlying_exception(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def timeout_once(transport, n, route):
        if n == 5:  # baseline pair, first successful pair, then timeout
            clock.sleep(10)
            raise URLError(TimeoutError("synthetic-secret-never-print"))

    io.hooks["health"] = timeout_once
    assert run.run(1000, 1900)["overall"] == "PASS"
    state = journal.load()
    reset = next(x for x in state["audit"] if x["event"] == "HEALTH_RESET")
    assert reset["underlying_type"] == "TimeoutError"
    assert reset["route"] == "/health"
    audit = json.dumps(state["audit"])
    assert "synthetic-secret" not in audit
    pairs = [x["consecutive"] for x in state["audit"] if x["event"] == "HEALTH_PAIR" and x["phase"] == "diagnostic"]
    assert pairs == [1, 1, 2, 3] and io.counts["listing"] == 1


def test_fixed_readiness_deadline_and_failure_no_listing(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def unavailable(transport, n, route):
        if 3 <= n <= 100 and FLAG in transport.values:
            clock.sleep(10)
            raise URLError(TimeoutError())

    io.hooks["health"] = unavailable
    result = run.run(1000, 1900)
    assert result["flag_restored"] and not io.counts.get("listing")
    assert all(t < 1300 for method, t, args in io.calls if method in ("startup_lines", "listing"))


def test_no_listing_before_real_warmup(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    io.startup_ready = False
    result = run.run(1000, 1900)
    assert result["flag_restored"] and not io.counts.get("listing")
    assert clock.wall() >= 1300


def test_ambiguous_enablement_timeout_restores_durable_intent(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def uncertain(transport):
        if FLAG in transport.values:
            raise URLError(TimeoutError())  # PUT applied but acknowledgement lost

    io.after_replace = uncertain
    result = run.run(1000, 1900)
    assert result["flag_restored"] and io.values == ORIGINAL
    assert journal.load()["intent"] and not io.counts.get("listing")


def test_listing_timeout_is_never_replayed_even_on_recovery(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    io.hooks["listing"] = lambda *args: (_ for _ in ()).throw(URLError(TimeoutError()))
    assert run.run(1000, 1900)["flag_restored"]
    run.recover()
    assert io.counts["listing"] == 1 and journal.load()["listing_intent"]


def test_wrong_target_blocks_recovery_writes(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    run.run(1000, 1900)
    writes = io.counts["replace"]
    io.wrong_identity = True
    assert run.recover()["status"] == "BLOCKED_RESTORATION_UNVERIFIED"
    assert io.counts["replace"] == writes


def test_conditional_write_collision_reloads_instead_of_losing_changes(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def collision(transport, n, desired):
        if n == 2:  # race during cleanup, after its settings read
            transport.values["CONCURRENT"] = "retained"
            transport.version += 1

    io.hooks["replace"] = collision
    result = run.run(1000, 1900)
    assert result["flag_restored"] and result["unrelated_drift"]
    assert io.values == {**ORIGINAL, "CONCURRENT": "retained"}


def test_encrypted_original_is_durable_not_plaintext(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    run.run(1000, 1900)
    raw = journal.path.read_bytes()
    assert b"synthetic-secret" not in raw and b"EXAMPLE_SECRET" not in raw
    assert Journal(journal.path, KEY).load()["original"] == ORIGINAL
    assert journal.path.stat().st_mode & 0o077 == 0
    with pytest.raises(SafetyError, match="INVALID_RECOVERY_JOURNAL"):
        Journal(journal.path, bytes(reversed(KEY))).load()


def test_tampered_scope_cannot_authorize_other_cleanup(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    run.run(1000, 1900)
    state = journal.load()
    state["flag"] = "DIFFERENT_SETTING"
    journal.save(state)
    writes = io.counts["replace"]
    with pytest.raises(SafetyError, match="INVALID_RECOVERY_JOURNAL"):
        run.recover()
    assert io.counts["replace"] == writes


def test_clock_rollback_does_not_extend_authorization():
    clock = FakeClock()
    budget = Budget(clock, 1900)
    clock.elapsed = 901
    clock.utc = 500
    with pytest.raises(Expired):
        budget.timeout()


def test_deadline_during_pair_does_not_start_second_request(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def expired_response(transport, n, route):
        if n == 3:
            clock.utc = 2000

    io.hooks["health"] = expired_response
    assert run.run(1000, 1900)["flag_restored"]
    assert not io.counts.get("listing")
    # No diagnostic /ready is started after the expired /health response.
    failed = [x for x in journal.load()["audit"] if x["event"] == "DIAGNOSTIC_FAILED"]
    assert failed[0]["exception_type"] == "Expired"


def test_restore_after_audit_disk_failure_still_removes_flag(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    save = journal.save

    def fail_only_cleanup(state):
        if any(x["event"] == "RESTORATION_STARTED" for x in state["audit"]):
            raise OSError("disk full")
        save(state)

    journal.save = fail_only_cleanup
    result = run.run(1000, 1900)
    assert FLAG not in io.values and result["flag_restored"]
    assert result["overall"] == "BLOCKED_AUDIT_PERSISTENCE"


def test_recovery_failure_reports_blocked_and_state_remains_recoverable(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def deny_cleanup(transport, n, desired):
        if FLAG not in desired:
            raise URLError(TimeoutError())

    io.hooks["replace"] = deny_cleanup
    result = run.run(1000, 1900)
    assert result["status"] == "BLOCKED_RESTORATION_UNVERIFIED" and FLAG in io.values
    io.hooks.clear()
    clock.utc = 5000
    assert Diagnostic(io, Journal(journal.path, KEY), clock).recover()["flag_restored"]


def test_premature_warmup_marker_never_passes():
    since = datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc).timestamp()
    lines = [
        "2026-11-08T09:18:20Z Starting container: abc_app-governance-validator-atiya-1026.",
        "2026-11-08T09:18:21Z State: Starting, Action: WaitingForSiteWarmUpProbeSuccess, Details: Pinging warmup path to ensure container is ready to receive requests.",
        "2026-11-08T09:18:22Z State: Started, Details: Site started at earlier time.",
    ]
    assert not actual_startup(lines, since)
    assert actual_startup(lines + ["2026-11-08T09:18:55Z Site startup probe succeeded after 35.0 seconds.",
                                   "2026-11-08T09:18:56Z Site started."], since)


def test_http200_with_unexpected_jobs_is_not_pass(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def unexpected(target, timeout):
        io.event("listing", target, timeout)
        return Response(200, [{"name": "unexpected-job"}])

    io.listing = unexpected
    assert run.run(1000, 1900)["overall"] == "PARTIAL"
    assert not journal.load()["diagnostic_passed"] and FLAG not in io.values


def test_certificate_failure_is_fatal_not_retried(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def certificate(transport, n, route):
        if FLAG in transport.values:
            raise URLError(ssl.SSLCertVerificationError("do not log this"))

    io.hooks["health"] = certificate
    assert run.run(1000, 1900)["flag_restored"]
    assert not io.counts.get("listing")
    assert not any(x["event"] == "HEALTH_RESET" for x in journal.load()["audit"])
    fatal = next(x for x in journal.load()["audit"] if x["event"] == "DIAGNOSTIC_FAILED")
    assert fatal["code"] == "CERTIFICATE_VERIFICATION_FAILED"


def test_wrong_target_before_mutation(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    io.wrong_identity = True
    with pytest.raises(SafetyError, match="TARGET_IDENTITY_MISMATCH"):
        run.run(1000, 1900)
    assert io.counts.get("replace", 0) == 0


def test_no_mutation_if_durable_original_cannot_be_written(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def full_disk(state):
        raise OSError("disk full")

    journal.save = full_disk
    with pytest.raises(OSError):
        run.run(1000, 1900)
    assert io.counts.get("replace", 0) == 0


def test_cross_process_lock_prevents_concurrent_recovery(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    run.run(1000, 1900)
    with journal.lock():
        with pytest.raises(BlockingIOError):
            Diagnostic(io, Journal(journal.path, KEY), clock).recover()


def test_reject_symlink_and_insecure_state_directory(tmp_path):
    directory = tmp_path / "unsafe"
    directory.mkdir(mode=0o755)
    with pytest.raises(SafetyError, match="INSECURE_STATE_DIRECTORY"):
        Journal(directory / "state", KEY)
    link = tmp_path / "link"
    link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(SafetyError, match="SYMLINK_STATE_PATH"):
        Journal(link / "state", KEY)


def test_phase_cannot_extend_expired_parent_when_wall_clock_moves_back(tmp_path):
    clock, io, journal, run = setup(tmp_path)
    save = journal.save

    def jump_at_intent(state):
        save(state)
        if state["audit"] and state["audit"][-1]["event"] == "MUTATION_INTENT":
            clock.utc = 500
            clock.elapsed = 901

    journal.save = jump_at_intent
    result = run.run(1000, 1900)
    assert io.counts.get("replace", 0) == 0
    assert result["overall"] == "BLOCKED_WINDOW_EXCEEDED"
    assert result["flag_restored"]


def test_monotonic_expiry_after_mutation_is_audited_when_wall_time_moves_back(tmp_path):
    clock, io, journal, run = setup(tmp_path)

    def clock_jump(transport):
        if FLAG in transport.values:
            clock.utc = 500
            clock.elapsed = 901

    io.after_replace = clock_jump
    result = run.run(1000, 1900)
    assert result["overall"] == "BLOCKED_WINDOW_EXCEEDED"
    assert result["flag_restored"] and journal.load()["authorization_expired"]
    assert io.counts["replace"] == 2 and not io.counts.get("listing")
