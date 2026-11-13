"""Offline worker, durable-restart and real subprocess-hang tests; no Azure."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "deployment/sql-expiry-watchdog/watchdog.py"
spec = importlib.util.spec_from_file_location("webapp_watchdog", SOURCE)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
CREATED = datetime(2026, 11, 7, 10, tzinfo=timezone.utc)


def policy(mode="armed"):
    return dict(mode=mode, target=w.TARGET, approval_id="WATCHDOG-NEW-local-only",
                creation_not_before=CREATED.isoformat(),
                creation_not_after=(CREATED + timedelta(minutes=30)).isoformat(),
                cleanup_after_seconds=10800, maximum_lifetime_seconds=14400)


class Arm:
    def __init__(self):
        self.status = 200
        self.deleted = 0
        self.result = 202
        self.document = dict(id=w.TARGET, tags={"purpose": "phase6b-approval-a-synthetic", "watchdogApproval": policy()["approval_id"]},
                             properties={"creationDate": CREATED.isoformat()})

    def get(self):
        return self.status, self.document

    def delete(self):
        self.deleted += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_disabled_package_makes_no_network_calls(tmp_path):
    p = json.loads(SOURCE.with_name("policy.json").read_text())
    assert p["mode"] == "disabled"
    assert "--permit-delete" not in SOURCE.with_name("run.sh").read_text()
    assert w.tick(p, w.Store(tmp_path), None, CREATED) == "DISABLED"
    result = subprocess.run([sys.executable, "-I", str(SOURCE), "--policy", str(SOURCE.with_name("policy.json")), "--state-dir", str(tmp_path)], capture_output=True, text=True, timeout=5,
                            env={"PATH": "/usr/bin:/bin"})
    assert result.returncode == 0 and "DISABLED" in result.stdout


def test_actual_creation_time_and_three_hour_margin(tmp_path):
    arm, store = Arm(), w.Store(tmp_path)
    assert w.tick(policy(), store, arm, CREATED + timedelta(seconds=10799), True) == "WAIT"
    assert arm.deleted == 0
    assert w.tick(policy(), store, arm, CREATED + timedelta(hours=3), True) == "DELETE_PENDING"
    assert arm.deleted == 1
    state = store.load()
    assert state["deadline_utc"] == (CREATED + timedelta(hours=4)).isoformat()


@pytest.mark.parametrize("mode,permit", [("observe", True), ("armed", False)])
def test_two_activation_gates(tmp_path, mode, permit):
    arm = Arm()
    assert w.tick(policy(mode), w.Store(tmp_path), arm, CREATED + timedelta(hours=3), permit) == "OBSERVE"
    assert arm.deleted == 0


def test_restart_and_failed_delete_resume_without_deadline_extension(tmp_path):
    arm = Arm()
    now = CREATED + timedelta(hours=3)
    arm.result = OSError("private-token-never-log")
    with pytest.raises(OSError):
        w.tick(policy(), w.Store(tmp_path), arm, now, True)
    first = w.Store(tmp_path).load()
    assert first["phase"] == "DELETE_PENDING"
    arm.result = 202
    assert w.tick(policy(), w.Store(tmp_path), arm, now + timedelta(seconds=1), True) == "RETRY_WAIT"
    assert w.tick(policy(), w.Store(tmp_path), arm, now + timedelta(seconds=61), True) == "DELETE_PENDING"
    second = w.Store(tmp_path).load()
    assert second["attempts"] == 2 and second["deadline_utc"] == first["deadline_utc"]
    assert "private-token" not in (tmp_path / "audit.jsonl").read_text()


@pytest.mark.parametrize("status", [200, 202, 204, 403, 409, 429, 500, 503])
def test_delete_response_never_counts_as_confirmation(tmp_path, status):
    arm = Arm()
    arm.result = status
    assert w.tick(policy(), w.Store(tmp_path), arm, CREATED + timedelta(hours=3), True) == "DELETE_PENDING"
    assert w.Store(tmp_path).load()["phase"] != "CONFIRMED"


def test_independent_absence_confirmation_and_expired_restart(tmp_path):
    arm = Arm()
    w.tick(policy(), w.Store(tmp_path), arm, CREATED + timedelta(hours=3), True)
    arm.status = 404
    late = CREATED + timedelta(hours=5)
    assert w.tick(policy(), w.Store(tmp_path), arm, late, True) == "UNCONFIRMED"
    assert w.tick(policy(), w.Store(tmp_path), arm, late, True, inventory=lambda _: False) == "UNCONFIRMED"
    assert w.tick(policy(), w.Store(tmp_path), arm, late, True, inventory=lambda _: True) == "CONFIRMED"
    logs = (tmp_path / "audit.jsonl").read_text()
    assert "LIMIT_BREACH" in logs and '"late": true' in logs


def test_expired_database_is_deleted_immediately(tmp_path):
    arm = Arm()
    assert w.tick(policy(), w.Store(tmp_path), arm, CREATED + timedelta(hours=6), True) == "DELETE_PENDING"
    assert arm.deleted == 1 and "LIMIT_BREACH" in (tmp_path / "audit.jsonl").read_text()


@pytest.mark.parametrize("bad", ["production", "tag", "incarnation", "future", "clock", "approval"])
def test_target_and_state_guards(tmp_path, bad):
    arm, store, p = Arm(), w.Store(tmp_path), policy()
    now = CREATED + timedelta(hours=3)
    if bad in {"incarnation", "clock"}:
        w.tick(p, store, arm, CREATED + timedelta(hours=2), True)
    if bad == "production":
        arm.document["id"] = w.SERVER + "/databases/sqldb-governance-validator-dev"
    elif bad == "tag":
        arm.document["tags"]["watchdogApproval"] = "consumed-approval"
    elif bad == "incarnation":
        arm.document["properties"]["creationDate"] = (CREATED + timedelta(minutes=1)).isoformat()
    elif bad == "future":
        now = CREATED - timedelta(seconds=1)
    elif bad == "clock":
        now = CREATED + timedelta(hours=1)
    elif bad == "approval":
        p["approval_id"] = "PHASE6B-APPROVAL-A-RETRY9-20261107"
    with pytest.raises(w.SafeFailure):
        w.tick(p, store, arm, now, True)
    assert arm.deleted == 0


def test_resource_reappearance_and_permission_denial_are_not_absence(tmp_path):
    arm, store = Arm(), w.Store(tmp_path)
    w.tick(policy(), store, arm, CREATED + timedelta(hours=3), True)
    arm.status = 403
    assert w.tick(policy(), store, arm, CREATED + timedelta(hours=3, seconds=61), True) == "UNCONFIRMED"
    arm.status = 404
    assert w.tick(policy(), store, arm, CREATED + timedelta(hours=3, seconds=62), True) == "UNCONFIRMED"
    arm.status = 200
    with pytest.raises(w.SafeFailure, match="RESOURCE_REAPPEARED"):
        w.tick(policy(), store, arm, CREATED + timedelta(hours=3, seconds=63), True)


def test_corrupt_state_and_log_disk_failure(tmp_path, monkeypatch):
    store, arm = w.Store(tmp_path), Arm()
    (tmp_path / "state.json").write_text("broken")
    with pytest.raises(ValueError):
        w.tick(policy(), store, arm, CREATED, True)
    assert arm.deleted == 0
    (tmp_path / "state.json").unlink()
    # Persistent state remains usable, but audit disk write fails at deletion.
    def fail(*args, **kwargs):
        raise OSError("private-path")
    monkeypatch.setattr(store, "log", fail)
    with pytest.raises(OSError):
        w.tick(policy(), store, arm, CREATED + timedelta(hours=3), True)
    assert arm.deleted == 1


def test_real_hung_child_is_killed_and_crash_is_observed(tmp_path):
    assert w.run_bounded([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.15) == 124
    assert w.run_bounded([sys.executable, "-c", "raise SystemExit(7)"], timeout=3) == 7
    assert w.run_bounded([sys.executable, "-c", "pass"], timeout=3) == 0


def test_identity_endpoint_and_fixed_arm_target(monkeypatch):
    for value in ["https://evil.example/token", "http://192.0.2.1/token", "http://127.0.0.1/token?redirect=evil"]:
        monkeypatch.setenv("IDENTITY_ENDPOINT", value)
        monkeypatch.setenv("IDENTITY_HEADER", "never-log-this")
        with pytest.raises(w.SafeFailure):
            w.identity_token()
    calls = []
    monkeypatch.setattr(w, "identity_token", lambda: "synthetic-token")
    monkeypatch.setattr(w, "request", lambda url, headers, method="GET": (calls.append((url, method)) or (202, {})))
    assert w.Arm().delete() == 202
    assert calls == [("https://management.azure.com" + w.TARGET + w.API, "DELETE")]


@pytest.mark.parametrize("get_error,inventory,expected", [
    ('Not Found({"error":{"code":"ResourceNotFound"}})', [w.SERVER + "/databases/master"], True),
    ('Forbidden({"error":{"code":"AuthorizationFailed"}})', [w.SERVER + "/databases/master"], False),
    ('Not Found({"error":{"code":"ResourceNotFound"}})', [w.TARGET], False),
    ('Not Found({"error":{"code":"ResourceNotFound"}})', [], False),
])
def test_separate_read_only_inventory_observer(get_error, inventory, expected, monkeypatch):
    monkeypatch.setitem(sys.modules, "watchdog", w)
    observer_spec = importlib.util.spec_from_file_location("absence_observer", SOURCE.with_name("confirm_absence.py"))
    observer = importlib.util.module_from_spec(observer_spec)
    observer_spec.loader.exec_module(observer)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert "delete" not in command and "create" not in command
        from types import SimpleNamespace
        return SimpleNamespace(returncode=1, stderr=get_error, stdout="") if len(calls) == 1 else SimpleNamespace(returncode=0, stdout=json.dumps(inventory))

    assert observer.confirm(run)["confirmed"] is expected
    assert len(calls) == 2


def test_review_permission_and_configuration_scopes():
    directory = SOURCE.parent
    role = json.loads((directory / "role-definition.REVIEW_ONLY.json").read_text())
    assignment = json.loads((directory / "role-assignment.REVIEW_ONLY.json").read_text())
    changes = json.loads((directory / "azure-changes.REVIEW_ONLY.json").read_text())
    assert role["Actions"] == ["Microsoft.Sql/servers/databases/read", "Microsoft.Sql/servers/databases/delete"]
    assert role["DataActions"] == []
    assert assignment["scope"] == w.TARGET and not assignment["broader_scope_fallback_permitted"]
    assert not assignment["inventory_permissions_granted"]
    assert changes["configuration_delta"]["set_only"] == {"WEBSITE_SKIP_RUNNING_KUDUAGENT": "false"}
    assert changes["next_setup_only_approval"]["permission_changes"] == []
    assert changes["job"]["policy_mode"] == "disabled" and not changes["job"]["permit_delete"]


def test_breach_logging_does_not_depend_on_successful_arm_read(tmp_path):
    arm, store = Arm(), w.Store(tmp_path)
    w.tick(policy(), store, arm, CREATED, True)

    def failed_read():
        raise OSError("synthetic-network-failure")

    arm.get = failed_read
    with pytest.raises(OSError):
        w.tick(policy(), store, arm, CREATED + timedelta(hours=5), True)
    assert "LIMIT_BREACH" in (tmp_path / "audit.jsonl").read_text()
