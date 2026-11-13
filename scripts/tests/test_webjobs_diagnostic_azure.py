"""Azure integration tests use fake CLI, HTTP and secret-store backends only."""

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webjobs_diagnostic import Diagnostic, Drift, FLAG, IDENTITY, Journal, RELEASE, SafetyError, Snapshot, TARGET
import webjobs_diagnostic_azure as a
from test_webjobs_diagnostic import FakeClock, KEY, ORIGINAL


@pytest.fixture(autouse=True)
def deny_real_io(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("REAL_NETWORK_OR_CLI_FORBIDDEN")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(subprocess, "run", denied)


class Token:
    def __init__(self):
        self.calls = 0

    def token(self, limit):
        limit.left()
        self.calls += 1
        return "synthetic-token-no-log"


def evidence():
    return a.ConditionalEvidence(TARGET, a.API, True, "mock-CAS-proof-only")


class Wire:
    def __init__(self, clock):
        self.clock, self.values, self.version = clock, dict(ORIGINAL), 1
        self.calls = []
        self.hook = None
        self.etag = True
        self.corrupt_host = False
        self.fail_health = False

    @contextmanager
    def open(self, req, timeout):
        assert 0 < timeout <= 10
        headers = dict(req.header_items())
        self.calls.append((req.method, req.full_url, headers, req.data))
        if self.hook:
            self.hook(self, req)
        body, response_headers = {}, {}
        if req.full_url == a.ARM + TARGET + a.QUERY:
            body = {"id": TARGET, "name": a.APP, "kind": "app,linux", "identity": {"principalId": IDENTITY},
                    "properties": {"defaultHostName": "wrong" if self.corrupt_host else a.APP + ".azurewebsites.net", "reserved": True}}
        elif req.full_url == a.ARM + TARGET + "/config/web" + a.QUERY:
            body = {"properties": {"linuxFxVersion": "PYTHON|3.13", "alwaysOn": True, "numberOfWorkers": 1}}
        elif req.full_url.endswith("/config/appsettings/list" + a.QUERY):
            assert req.method == "POST"
            body = {"id": TARGET + "/config/appsettings", "properties": dict(self.values)}
            response_headers = {"ETag": f'"{self.version}"'} if self.etag else {}
        elif req.full_url.endswith("/config/appsettings" + a.QUERY):
            assert req.method == "PUT"
            if headers.get("If-match") != f'"{self.version}"':
                raise HTTPError(req.full_url, 412, "secret-must-not-log", {}, io.BytesIO(b"secret"))
            self.values = json.loads(req.data)["properties"]
            self.version += 1
            body = {"id": TARGET + "/config/appsettings", "properties": dict(self.values)}
        elif req.full_url == a.WEB + "/health":
            if self.fail_health and FLAG in self.values:
                raise URLError(TimeoutError("synthetic-secret-never-print"))
            body = {"status": "ok"}
        elif req.full_url == a.WEB + "/ready":
            body = {"status": "ready", "database_revision": "005", "release": {"build_version": RELEASE, **a.HASHES}}
        elif req.full_url == a.SCM + "/api/vfs/LogFiles/":
            body = [{"name": "2026_11_08_worker_docker.log", "mtime": "2026-11-08T09:00:00Z"},
                    {"name": "../environment", "mtime": "9999"}]
        elif req.full_url == a.SCM + "/api/vfs/LogFiles/2026_11_08_worker_docker.log":
            stamp = datetime.fromtimestamp(self.clock.wall(), timezone.utc).isoformat().replace("+00:00", "Z")
            body = "\n".join([stamp + " Starting container: abc_app-governance-validator-atiya-1026.",
                               stamp + " Site startup probe succeeded after 1.0 seconds.", stamp + " Site started."])
        elif req.full_url == a.SCM + "/api/continuouswebjobs":
            body = []
        else:
            raise AssertionError("UNEXPECTED_ADAPTER_REQUEST")
        raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        stream = io.BytesIO(raw)
        stream.status, stream.headers = 200, response_headers
        yield stream


def setup(tmp_path, proof=True):
    clock = FakeClock()
    wire = Wire(clock)
    transport = a.AzureTransport(Token(), evidence() if proof else None, wire, clock.mono, clock.wall)
    journal = Journal(tmp_path / "secure" / "state", KEY)
    return clock, wire, transport, journal, Diagnostic(transport, journal, clock)


def jwt(**overrides):
    claims = {"tid": a.TENANT, "oid": a.OPERATOR, "aud": a.ARM + "/", "exp": 5000, **overrides}
    return "synthetic." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".signature"


def cli_runner(token=None, account=None):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        result = account or {"id": a.SUB, "tenantId": a.TENANT, "state": "Enabled"}
        if "get-access-token" in command:
            result = {"accessToken": token or jwt()}
        return SimpleNamespace(returncode=0, stdout=json.dumps(result), stderr="")

    return runner, calls


def test_cli_pins_subscription_tenant_subject_and_audience():
    runner, calls = cli_runner()
    credential = a.CliCredential(runner, wall=lambda: 1000)
    assert credential.token(a.Limit(10)) == jwt()
    assert len(calls) == 2
    assert all(a.SUB in command and "capture_output" in opts for command, opts in calls)
    assert a.TENANT in calls[1][0] and a.ARM + "/" in calls[1][0]
    assert credential.token(a.Limit(10)) == jwt() and len(calls) == 2
    assert jwt() not in repr(calls)


@pytest.mark.parametrize("claims", [{"tid": "wrong"}, {"oid": "wrong"}, {"aud": "wrong"}, {"exp": 1001}])
def test_cli_rejects_wrong_or_expired_token_without_disclosure(claims):
    runner, calls = cli_runner(token=jwt(**claims))
    with pytest.raises(SafetyError, match="AZURE_TOKEN_IDENTITY_MISMATCH") as caught:
        a.CliCredential(runner, wall=lambda: 1000).token(a.Limit(10))
    assert jwt(**claims) not in str(caught.value)


def test_cli_timeout_or_wrong_account_is_sanitized():
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("az", 1, output="synthetic-secret-never-print")

    with pytest.raises(SafetyError, match="AZURE_CLI_AUTH_FAILURE") as caught:
        a.CliCredential(timeout).token(a.Limit(10))
    assert "synthetic-secret" not in str(caught.value)
    runner, calls = cli_runner(account={"id": "wrong"})
    with pytest.raises(SafetyError, match="AZURE_ACCOUNT_MISMATCH"):
        a.CliCredential(runner).token(a.Limit(10))
    assert len(calls) == 1


def test_complete_mock_azure_flow_and_conditional_rollback(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    assert run.run(1000, 1900)["overall"] == "PASS"
    assert wire.values == ORIGINAL
    puts = [x for x in wire.calls if x[0] == "PUT"]
    assert len(puts) == 2 and all("If-match" in x[2] for x in puts)
    assert len([x for x in wire.calls if x[1].endswith("/api/continuouswebjobs")]) == 1
    assert not any("Authorization" in h for method, url, h, body in wire.calls if url.startswith(a.WEB))
    assert b"synthetic-secret" not in journal.path.read_bytes()
    assert "synthetic-secret" not in json.dumps(journal.load()["audit"])


def test_default_conditional_write_blocked_even_if_mock_returns_etag(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path, proof=False)
    result = run.run(1000, 1900)
    assert result["overall"] == "PARTIAL" and result["flag_restored"]
    assert not any(x[0] == "PUT" for x in wire.calls)
    assert not adapter.listing_sent


@pytest.mark.parametrize("version", ["", "*", 'W/"1"', '"bad\r\nheader"'])
def test_missing_weak_or_injectable_etag_cannot_write(tmp_path, version):
    clock, wire, adapter, journal, run = setup(tmp_path)
    with pytest.raises(SafetyError, match="STRONG_ETAG_REQUIRED"):
        adapter.replace(TARGET, Snapshot(dict(ORIGINAL), version), {**ORIGINAL, FLAG: "false"}, 10)
    assert wire.calls == []


def test_concurrent_change_before_put_is_not_overwritten(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    snapshot = adapter.settings(TARGET, 10)
    wire.values["OTHER"] = "keep"
    wire.version += 1
    with pytest.raises(Drift):
        adapter.replace(TARGET, snapshot, {**ORIGINAL, FLAG: "false"}, 10)
    assert not any(x[0] == "PUT" for x in wire.calls)


def test_concurrent_change_during_put_is_rejected_by_cas(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    snapshot = adapter.settings(TARGET, 10)

    def collision(w, req):
        if req.method == "PUT":
            w.version += 1
            w.values["OTHER"] = "keep"

    wire.hook = collision
    with pytest.raises(Drift):
        adapter.replace(TARGET, snapshot, {**ORIGINAL, FLAG: "false"}, 10)
    assert FLAG not in wire.values and wire.values["OTHER"] == "keep"


def test_timeout_after_applied_enablement_uses_durable_recovery(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    get_count = 0

    def lost_ack(w, req):
        nonlocal get_count
        if FLAG in w.values and req.full_url.endswith("/config/appsettings/list" + a.QUERY):
            get_count += 1
            if get_count == 1:
                raise URLError(TimeoutError("synthetic-secret"))

    wire.hook = lost_ack
    result = run.run(1000, 1900)
    assert result["flag_restored"] and wire.values == ORIGINAL
    assert not adapter.listing_sent


def test_fresh_adapter_cleanup_only_after_interruption_and_expiry(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    original_replace = adapter.replace

    class SimulatedTermination(BaseException):
        pass

    def interrupted(*args, **kwargs):
        original_replace(*args, **kwargs)
        if FLAG in wire.values:
            raise SimulatedTermination()

    # The original core suite additionally tests os._exit, where finally cannot run.
    adapter.replace = interrupted
    with pytest.raises(SimulatedTermination):
        run.run(1000, 1900)
    clock.utc = 9000
    fresh = a.AzureTransport(Token(), evidence(), wire, clock.mono)
    before = len(wire.calls)
    assert Diagnostic(fresh, Journal(journal.path, KEY), clock).recover()["flag_restored"]
    assert not any(x[1].endswith("/api/continuouswebjobs") for x in wire.calls[before:])
    assert not any("LogFiles" in x[1] for x in wire.calls[before:])


def test_target_url_and_unrelated_mutations_are_blocked_locally(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    with pytest.raises(SafetyError):
        adapter.identity("wrong-target", 10)
    with pytest.raises(SafetyError):
        adapter._request(a.SCM, "/api/continuouswebjobs/job/start", a.Limit(10), "POST")
    with pytest.raises(SafetyError):
        adapter._request("https://unapproved.invalid", "/", a.Limit(10))
    with pytest.raises(SafetyError):
        adapter.replace(TARGET, Snapshot(dict(ORIGINAL), '"1"'), {**ORIGINAL, "OTHER": "bad", FLAG: "false"}, 10)
    assert wire.calls == []


def test_listing_network_failure_cannot_be_retried(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    wire.hook = lambda w, req: (_ for _ in ()).throw(URLError(TimeoutError()))
    with pytest.raises(URLError):
        adapter.listing(TARGET, 10)
    with pytest.raises(SafetyError, match="LISTING_ALREADY_ATTEMPTED"):
        adapter.listing(TARGET, 10)
    assert len(wire.calls) == 1


def test_health_normalization_and_asset_hash_drift(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    assert adapter.health(TARGET, "/ready", 10).body == {"status": "ready", "release": RELEASE, "revision": "005"}
    wire.corrupt_host = True
    with pytest.raises(SafetyError, match="TARGET_IDENTITY_MISMATCH"):
        adapter.identity(TARGET, 10)
    assert "synthetic-secret" not in repr(Snapshot(ORIGINAL, '"1"'))


class SecretBackend:
    COLLECTION_DEFAULT = "default"
    ServiceFlags = SimpleNamespace(OPEN_SESSION=1, LOAD_COLLECTIONS=2)
    CollectionFlags = SimpleNamespace(NONE=0)
    SchemaFlags = SimpleNamespace(NONE=0)
    SchemaAttributeType = SimpleNamespace(STRING=1)

    def __init__(self):
        self.locked, self.value, self.stores = False, None, 0
        self.Service = SimpleNamespace(get_sync=lambda *args: object())
        self.Collection = SimpleNamespace(for_alias_sync=lambda *args: SimpleNamespace(get_locked=lambda: self.locked))
        self.Schema = SimpleNamespace(new=lambda *args: object())

    def password_lookup_sync(self, *args):
        return self.value

    def password_store_sync(self, schema, attributes, collection, label, value, cancel):
        assert schema and attributes["app"] == a.APP
        self.value, self.stores = value, self.stores + 1
        return True


def test_durable_key_backend_create_then_recover_without_rotation():
    backend = SecretBackend()
    key = a.DesktopKeys(backend).key("synthetic-op", create=True)
    assert len(key) == 32 and backend.stores == 1
    assert a.DesktopKeys(backend).key("synthetic-op", create=False) == key and backend.stores == 1


def test_recovery_never_creates_a_missing_or_locked_key():
    backend = SecretBackend()
    with pytest.raises(SafetyError, match="RECOVERY_KEY_UNAVAILABLE"):
        a.DesktopKeys(backend).key("missing", create=False)
    backend.locked = True
    with pytest.raises(SafetyError, match="RECOVERY_KEY_UNAVAILABLE"):
        a.DesktopKeys(backend).key("locked", create=True)
    assert backend.stores == 0


def test_supervisor_must_survive_host_loss_not_merely_restart():
    document = {"target": TARGET, "verified": True, "different_host": True,
                "survives_initiator_termination": True, "survives_host_unavailability": False,
                "journal_access_verified": True, "key_access_verified": True,
                "azure_restore_access_verified": True, "coverage_until": 1900, "evidence_reference": "mock"}
    with pytest.raises(SafetyError, match="INDEPENDENT_SUPERVISOR_UNVERIFIED"):
        a.require_supervisor(document, 1900)
    document["survives_host_unavailability"] = True
    a.require_supervisor(document, 1900)


def test_cli_entry_refuses_unverified_writes_without_cli_or_key_access(tmp_path, capsys):
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps({"target": TARGET, "api_version": a.API, "verified": False, "reference": "review-only"}))
    assert a.main(["run", "--journal", str(tmp_path / "state"), "--operation-id", "op",
                   "--conditional-evidence", str(proof)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"
    assert not (tmp_path / "state").exists()


def test_redirects_never_forward_credentials():
    assert a.NoRedirect().redirect_request(None, None, 302, "", {}, "https://unapproved.invalid") is None


def test_adapter_subrequest_deadline_detects_host_pause_without_monotonic_progress(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    snapshot = adapter.settings(TARGET, 10)

    def suspend_during_read(w, req):
        if req.full_url.endswith("/config/appsettings/list" + a.QUERY):
            clock.utc += 3600

    wire.hook = suspend_during_read
    with pytest.raises(TimeoutError):
        adapter.replace(TARGET, snapshot, {**ORIGINAL, FLAG: "false"}, 10)
    assert not any(x[0] == "PUT" for x in wire.calls)


def test_real_missing_etag_response_blocks_put_with_reviewed_mock_proof(tmp_path):
    clock, wire, adapter, journal, run = setup(tmp_path)
    wire.etag = False
    result = run.run(1000, 1900)
    assert result["flag_restored"] and result["overall"] == "PARTIAL"
    assert not any(x[0] == "PUT" for x in wire.calls)


def test_cli_entry_requires_independent_supervisor_before_any_key_access(tmp_path, capsys):
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps({"target": TARGET, "api_version": a.API, "verified": True, "reference": "mock-proof"}))
    assert a.main(["run", "--journal", str(tmp_path / "state"), "--operation-id", "op",
                   "--conditional-evidence", str(proof)]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "LIVE_APPROVAL_AND_SUPERVISOR_REQUIRED"


def test_cli_entry_rejects_expired_approval_before_key_or_cli_access(tmp_path, capsys):
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps({"target": TARGET, "api_version": a.API, "verified": True, "reference": "mock-proof"}))
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"target": TARGET, "operation_id": "op", "scope": "ONE_FLAG_ONE_LISTING_THEN_RESTORE",
                                    "approved_at": 1000, "expires": 1900}))
    supervisor = tmp_path / "not-read.json"
    assert a.main(["run", "--journal", str(tmp_path / "state"), "--operation-id", "op", "--approval", str(approval),
                   "--supervisor-evidence", str(supervisor), "--conditional-evidence", str(proof)]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_AUTHORIZATION"
