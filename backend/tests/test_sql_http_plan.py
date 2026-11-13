"""Phase 5 safety review: synthetic credentials, disposable SQLite, no cloud calls."""

import copy
import fcntl
import importlib.util
import json
import os
import signal
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update

SPEC = importlib.util.spec_from_file_location("sql_http_driver", Path(__file__).resolve().parents[2] / "scripts/test_azure_sql_http.py")
driver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(driver)


def manifest():
    run = str(uuid4())
    return {
        "run_id": run,
        "tenant": "http-sql-test-" + run,
        "tokens": {"Admin": "fixture_admin", "Developer": "fixture_developer", "Foreign Admin": "fixture_foreign"},
        "record_ids": {},
    }


def private_file(tmp_path, data=None):
    path = tmp_path / "governance-sql-http-fixture.json"
    path.write_text(json.dumps(data if data is not None else manifest()))
    path.chmod(0o600)
    return path


def test_default_is_offline(monkeypatch, capsys):
    monkeypatch.setattr(driver, "ManifestStore", lambda *_: pytest.fail("File access"))
    monkeypatch.setattr(driver, "sql_check", lambda *_: pytest.fail("SQL connection"))
    monkeypatch.setattr(driver.httpx, "Client", lambda **_: pytest.fail("HTTP connection"))
    assert driver.main([]) == 0
    assert json.loads(capsys.readouterr().out)["connection_attempted"] is False


@pytest.mark.parametrize("mode", [0o644, 0o660, 0o400, 0o700])
def test_manifest_permissions(tmp_path, mode):
    path = private_file(tmp_path)
    path.chmod(mode)
    with pytest.raises((driver.SafetyStop, OSError)), driver.ManifestStore(path):
        pass


def test_manifest_owner(tmp_path, monkeypatch):
    path = private_file(tmp_path)
    monkeypatch.setattr(driver.os, "getuid", lambda: path.stat().st_uid + 1)
    with pytest.raises(driver.SafetyStop), driver.ManifestStore(path):
        pass


@pytest.mark.parametrize("kind", ["symlink", "parent_symlink", "hardlink"])
def test_manifest_link_rejection(tmp_path, kind):
    path = private_file(tmp_path)
    if kind == "parent_symlink":
        parent = tmp_path / "parent"
        parent.symlink_to(tmp_path, target_is_directory=True)
        path = parent / path.name
    else:
        link = tmp_path / "link"
        if kind == "symlink":
            link.symlink_to(path)
        else:
            os.link(path, link)
        path = link
    with pytest.raises((OSError, driver.SafetyStop)), driver.ManifestStore(path):
        pass


@pytest.mark.parametrize("status", [None, {}, "", {"status": "INCOMPLETE"}, {"status": "HTTP_SQL_TEST_PASSED"}])
def test_any_previous_run_is_rejected(tmp_path, status):
    data = manifest()
    data["http_test"] = status
    path = private_file(tmp_path, data)
    with driver.ManifestStore(path) as store, pytest.raises(driver.SafetyStop):
        store.load()


def test_manifest_empty_provenance_and_unique_tokens(tmp_path):
    data = manifest()
    data["record_ids"] = {"id": [str(uuid4())]}
    with pytest.raises(driver.SafetyStop):
        driver.validate_manifest(data)
    data = manifest()
    data["tokens"]["Foreign Admin"] = data["tokens"]["Admin"]
    with pytest.raises(driver.SafetyStop):
        driver.validate_manifest(data)


def test_manifest_lock_and_path_replacement(tmp_path):
    path = private_file(tmp_path)
    with driver.ManifestStore(path) as first:
        with pytest.raises(BlockingIOError), driver.ManifestStore(path):
            pass
        data = first.load()
        replacement = tmp_path / "replacement"
        replacement.write_text(json.dumps(data))
        replacement.chmod(0o600)
        replacement.replace(path)
        with pytest.raises(driver.SafetyStop):
            first.save(data)
        assert first.poisoned


def test_manifest_checkpoint_failure_poisoned(tmp_path, monkeypatch):
    path = private_file(tmp_path)
    with driver.ManifestStore(path) as store:
        data = store.load()
        data["http_test"] = {"status": "INCOMPLETE"}
        monkeypatch.setattr(driver.os, "fsync", Mock(side_effect=OSError("fixture_private_message")))
        with pytest.raises(OSError):
            store.save(data)
        assert store.poisoned
        with pytest.raises(driver.SafetyStop):
            store.save(data)
    with driver.ManifestStore(path) as store, pytest.raises(driver.SafetyStop):
        store.load()


def test_no_repository_manifests(tmp_path, monkeypatch):
    path = private_file(tmp_path)
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    with pytest.raises(driver.SafetyStop), driver.ManifestStore(path):
        pass
    ignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text()
    assert "governance-sql-http-*.json" in ignore


@pytest.fixture
def local_workflow(client, monkeypatch):
    from app import main
    from app.config import settings
    from app.models import Audit, Base, Policy
    from app.providers import ProviderUnavailable
    import app.azure_sql
    import inventory_azure_sql
    import test_azure_sql_writes

    data = manifest()
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(driver.demo_accounts(data["run_id"], data["tokens"])))
    monkeypatch.setattr(settings, "adls_account_url", "")
    monkeypatch.setattr(main.providers, "upload_report", Mock(side_effect=ProviderUnavailable("fixture disabled")))
    dependency = main.app.dependency_overrides[main.get_database]()
    session = next(dependency)
    engine = session.bind
    session.add_all(
        [
            Policy(id=str(uuid4()), tenant="preexisting", name="Existing fixture", draft="{}"),
            Audit(id=str(uuid4()), tenant="preexisting", actor="fixture", action="fixture", resource="fixture"),
        ]
    )
    session.commit()
    session.close()
    dependency.close()

    def existing_rows():
        with engine.connect() as connection:
            return {
                model.__tablename__: [
                    dict(row)
                    for row in connection.execute(select(*model.__table__.columns).where(model.tenant == "preexisting")).mappings()
                ]
                for model in test_azure_sql_writes.MODELS
            }

    baseline = existing_rows()

    class LocalTransport:
        def request(self, method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            if path == "/api/settings" and response.status_code == 200:
                content = response.json()
                content.update(database="mssql", azure_generation="NOT_CONFIGURED", moderation="NOT_CONFIGURED")
                return driver.httpx.Response(200, json=content)
            return response

    monkeypatch.setattr(app.azure_sql, "create_azure_sql_engine", lambda *_: engine)
    monkeypatch.setattr(engine, "dispose", lambda: None)
    monkeypatch.setattr(test_azure_sql_writes, "preflight", lambda *_: None)
    monkeypatch.setattr(inventory_azure_sql, "install_query_timeout", lambda *_: None)
    assert all(value == 0 for value in driver.sql_check(data, before=True).values())
    data["http_test"] = {"operations": []}
    snapshots = []
    runner = driver.Driver(LocalTransport(), data, lambda: snapshots.append(copy.deepcopy(data)))
    runner.workflows()
    assert driver.sql_check(data, before=False) == driver.EXPECTED_COUNTS
    yield data, engine, test_azure_sql_writes.MODELS, snapshots
    assert existing_rows() == baseline
    assert len(Base.metadata.tables) == 19


def test_http_sequence_and_persisted_counts(local_workflow):
    data, _, _, snapshots = local_workflow
    assert len(data["http_test"]["versions"]) == 2
    assert all(op["outcome"] == "RECEIVED" for op in data["http_test"]["operations"])
    assert len(snapshots) > len(data["http_test"]["operations"])
    assert not any(op["path"].startswith("/api/policies/") and "preexisting" in op["path"] for op in data["http_test"]["operations"])


def test_core_mapping_matches_api_while_session_mapping_is_orm(local_workflow):
    from app.models import Version
    from sqlalchemy.orm import Session

    data, engine, _, _ = local_workflow
    version = data["http_test"]["versions"][0]
    with engine.connect() as connection:
        core_row = connection.execute(select(Version).where(Version.id == version["id"])).mappings().one()
        assert dict(core_row) == version  # Proves the original Core comparison was valid.
        explicit = connection.execute(select(*Version.__table__.columns).where(Version.id == version["id"])).mappings().one()
        driver.verify_version(explicit, version, data["tenant"], version["policy_id"], 2, version["document"])
    with Session(engine) as session:
        orm_row = session.execute(select(Version).where(Version.id == version["id"])).mappings().one()
        assert list(orm_row) == ["Version"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("document", "{}"),
        ("number", 1),
        ("number", "2"),
        ("number", True),
        ("policy_id", "00000000-0000-0000-0000-000000000000"),
        ("id", "00000000-0000-0000-0000-000000000000"),
        ("tenant", "foreign"),
        ("created", "changed"),
    ],
)
def test_version_mismatch_rejected(local_workflow, field, value):
    data, _, _, _ = local_workflow
    version = data["http_test"]["versions"][0]
    changed = dict(version, **{field: value})
    with pytest.raises((driver.SafetyStop, ValidationError)):
        driver.verify_version(changed, version, data["tenant"], version["policy_id"], 2, version["document"])


@pytest.mark.parametrize(
    "table,field,value",
    [
        ("policy_versions", "document", "{}"),
        ("policy_versions", "number", 9),
        ("policy_versions", "policy_id", "foreign-policy"),
        ("active_policy_assignments", "version_id", "foreign-version"),
        ("validation_executions", "policy_id", "foreign-policy"),
        ("validation_executions", "version", 9),
        ("human_review_cases", "execution_id", "foreign-execution"),
        ("human_review_cases", "row_version", 9),
        ("feedback_records", "execution_id", "foreign-execution"),
        ("feedback_records", "rating", 4),
        ("evaluation_exports", "status", "SUCCEEDED"),
        ("audit_events", "resource", "foreign-resource"),
        ("audit_events", "tenant", "foreign-tenant"),
    ],
)
def test_changed_database_records_rejected(local_workflow, table, field, value):
    data, engine, models, _ = local_workflow
    model = next(model for model in models if model.__tablename__ == table)
    with engine.begin() as connection:
        row = connection.execute(select(*model.__table__.columns).where(model.tenant == data["tenant"])).mappings().first()
        key = "tenant" if table == "active_policy_assignments" else "id"
        connection.execute(update(model).where(getattr(model, key) == row[key]).values(**{field: value}))
    with pytest.raises((driver.SafetyStop, KeyError)):
        driver.sql_check(data, before=False)


def test_unexpected_audit_api_field_rejected(local_workflow):
    data, engine, models, _ = local_workflow
    corrupted = copy.deepcopy(data)
    corrupted["http_test"]["records"]["audit_events"][0]["unexpected_field"] = "synthetic"
    with engine.connect() as connection, pytest.raises(driver.SafetyStop):
        driver.verify_retained(connection, corrupted, models)


@pytest.mark.parametrize("table", list(driver.EXPECTED_COUNTS))
def test_missing_expected_record_rejected(local_workflow, table):
    data, engine, models, _ = local_workflow
    corrupted = copy.deepcopy(data)
    corrupted["http_test"]["records"][table].pop()
    with engine.connect() as connection, pytest.raises(driver.SafetyStop):
        driver.verify_retained(connection, corrupted, models)


def test_wrong_relationship_even_if_api_and_sql_agree(local_workflow):
    from app.models import Feedback

    data, engine, models, _ = local_workflow
    wrong = data["http_test"]["created"]["validation_executions"][-1]
    with engine.begin() as connection:
        connection.execute(update(Feedback).where(Feedback.tenant == data["tenant"]).values(execution_id=wrong))
    for row in data["http_test"]["records"]["feedback_records"]:
        row["execution_id"] = wrong
    with engine.connect() as connection, pytest.raises(driver.SafetyStop):
        driver.verify_retained(connection, data, models)


@pytest.mark.parametrize("where", ["before", "after"])
def test_checkpoint_failure_stops_transmission_and_future_calls(where):
    data = manifest()
    data["http_test"] = {"operations": []}
    client = Mock()
    client.request.return_value = driver.httpx.Response(201, json={"id": str(uuid4()), "tenant": data["tenant"]})
    checkpoint = Mock(side_effect=OSError("fixture_private_message") if where == "before" else [None, OSError("fixture_private_message")])
    runner = driver.Driver(client, data, checkpoint)
    with pytest.raises(OSError):
        runner.call("POST", "/api/policies", {})
    with pytest.raises(driver.SafetyStop):
        runner.call("POST", "/api/policies", {})
    assert client.request.call_count == (0 if where == "before" else 1)
    assert data["http_test"]["operations"][0]["outcome"] == ("UNKNOWN" if where == "before" else "RECEIVED")


def test_timeout_records_unknown_without_retry():
    data = manifest()
    data["http_test"] = {"operations": []}
    client = Mock()
    client.request.side_effect = driver.httpx.ReadTimeout("fixture_private_message")
    checkpoints = []
    runner = driver.Driver(client, data, lambda: checkpoints.append(copy.deepcopy(data)))
    with pytest.raises(driver.httpx.ReadTimeout):
        runner.call("POST", "/api/policies", {})
    with pytest.raises(driver.SafetyStop):
        runner.call("POST", "/api/policies", {})
    assert client.request.call_count == 1
    assert checkpoints[0]["http_test"]["operations"] == [{"method": "POST", "path": "/api/policies", "outcome": "UNKNOWN"}]


@pytest.mark.parametrize("failure", ["exception", "sigterm", "deadline", "keyboard", "checkpoint"])
def test_main_failure_is_sanitized_and_not_reusable(tmp_path, monkeypatch, capsys, failure):
    path = private_file(tmp_path)
    original = driver.ManifestStore.save

    def fail(*_, **__):
        if failure == "sigterm":
            signal.raise_signal(signal.SIGTERM)
        if failure == "deadline":
            signal.raise_signal(signal.SIGALRM)
        if failure == "keyboard":
            raise KeyboardInterrupt()
        raise RuntimeError("fixture_private_message")

    if failure == "checkpoint":

        def failing_save(self, data):
            original(self, data)
            self.poisoned = True
            raise OSError("fixture_private_message")

        monkeypatch.setattr(driver.ManifestStore, "save", failing_save)
    monkeypatch.setattr(driver, "sql_check", fail)
    monkeypatch.setattr(driver.httpx, "Client", lambda **_: pytest.fail("Unexpected HTTP client"))
    assert driver.main(["--execute-approved-http-test", "--manifest", str(path)]) == 2
    output = capsys.readouterr()
    assert "fixture_private_message" not in output.out + output.err
    assert all(value not in output.out + output.err for value in manifest()["tokens"].values())
    report = json.loads(path.read_text())
    assert report["http_test"]["status"] in ("INCOMPLETE", "FAILED_OR_INCOMPLETE")
    with driver.ManifestStore(path) as store, pytest.raises(driver.SafetyStop):
        store.load()


def test_foreign_identity_and_hashes():
    data = manifest()
    accounts = driver.demo_accounts(data["run_id"], data["tokens"])
    assert accounts[0]["tenant"] == accounts[1]["tenant"] == data["tenant"]
    assert accounts[2]["tenant"] == data["tenant"] + "-foreign"
    assert [account["role"] for account in accounts] == ["Admin", "Developer", "Admin"]
    assert not any(token in json.dumps(accounts) for token in data["tokens"].values())


def test_manifest_lock_uses_same_descriptor(tmp_path):
    path = private_file(tmp_path)
    with driver.ManifestStore(path) as store:
        data = store.load()
        data["http_test"] = {"status": "INCOMPLETE"}
        store.save(data)
        fd = os.open(path, os.O_RDONLY)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)


@pytest.mark.parametrize("mismatch", ["foreign_tenant", "developer_role", "missing_auth"])
def test_authentication_mismatch_stops_before_http_mutations(mismatch):
    data = manifest()
    data["http_test"] = {"operations": []}
    methods = []

    class Diagnostics:
        def request(self, method, path, **kwargs):
            methods.append(method)
            if path == "/health":
                return driver.httpx.Response(200, json={"status": "ok"})
            if path == "/ready":
                return driver.httpx.Response(200, json={"status": "ready"})
            bearer = kwargs["headers"]["Authorization"]
            tenant, role = data["tenant"], "Admin"
            if bearer.endswith(data["tokens"]["Developer"]):
                role = "Admin" if mismatch == "developer_role" else "Developer"
            elif bearer.endswith(data["tokens"]["Foreign Admin"]):
                tenant += "" if mismatch == "foreign_tenant" else "-foreign"
            elif not bearer and mismatch != "missing_auth":
                return driver.httpx.Response(401, json={"detail": "fixture"})
            return driver.httpx.Response(
                200,
                json={
                    "database": "mssql",
                    "provider_mode": "fixture",
                    "pii_mode": "regex",
                    "adls": "NOT_CONFIGURED",
                    "moderation": "NOT_CONFIGURED",
                    "azure_generation": "NOT_CONFIGURED",
                    "tenant": tenant,
                    "role": role,
                },
            )

    runner = driver.Driver(Diagnostics(), data, lambda: None)
    with pytest.raises(driver.SafetyStop):
        runner.workflows()
    assert set(methods) == {"GET"}


def test_local_invalid_authentication_is_401(client):
    assert client.get("/api/settings", headers={"Authorization": "Bearer invalid_fixture"}).status_code == 401
    assert client.get("/api/settings", headers={"Authorization": ""}).status_code == 401


def test_main_never_promotes_failed_independent_verification(tmp_path, monkeypatch, capsys):
    path = private_file(tmp_path)
    checks = Mock(side_effect=[{name: 0 for name in driver.EXPECTED_COUNTS}, driver.SafetyStop("fixture_private_message")])
    monkeypatch.setattr(driver, "sql_check", checks)
    monkeypatch.setattr(driver.Driver, "workflows", lambda _: None)  # Never run the approved driver here.
    fake_client = Mock()
    fake_client.__enter__ = Mock(return_value=fake_client)
    fake_client.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(driver.httpx, "Client", lambda **_: fake_client)
    assert driver.main(["--execute-approved-http-test", "--manifest", str(path)]) == 2
    assert checks.call_count == 2
    assert "HTTP_SQL_TEST_PASSED" not in capsys.readouterr().out
    assert json.loads(path.read_text())["http_test"]["status"] == "FAILED_OR_INCOMPLETE"


def test_snapshot_agreement_does_not_hide_wrong_immutable_document(local_workflow):
    from app.models import Version

    data, engine, models, _ = local_workflow
    version = data["http_test"]["records"]["policy_versions"][0]
    with engine.begin() as connection:
        connection.execute(update(Version).where(Version.id == version["id"]).values(document="{}"))
    version["document"] = "{}"
    with engine.connect() as connection, pytest.raises(driver.SafetyStop):
        driver.verify_retained(connection, data, models)


def test_private_manifest_creation_is_exclusive_and_0600(tmp_path, capsys):
    data = manifest()
    path = tmp_path / "governance-sql-http-created.json"
    driver.create_manifest(path, data["run_id"], data["tokens"])
    assert path.stat().st_mode & 0o777 == 0o600
    with driver.ManifestStore(path) as store:
        assert store.load() == data
    with pytest.raises(FileExistsError):
        driver.create_manifest(path, data["run_id"], data["tokens"])
    link = tmp_path / "governance-sql-http-link.json"
    link.symlink_to(path)
    with pytest.raises(driver.SafetyStop):
        driver.create_manifest(link, data["run_id"], data["tokens"])
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_bearers_absent_from_http_logs(local_workflow, caplog, capsys):
    data, _, _, _ = local_workflow
    logs = "\n".join(record.getMessage() for phase in ("setup", "call") for record in caplog.get_records(phase))
    output = capsys.readouterr()
    for token in data["tokens"].values():
        assert token not in logs + output.out + output.err


def test_swapped_review_dispositions_even_if_api_and_sql_agree(local_workflow):
    from app.models import Review

    data, engine, models, _ = local_workflow
    reviews = data["http_test"]["records"]["human_review_cases"]
    with engine.begin() as connection:
        for row in reviews:
            row["status"] = "REJECTED" if row["status"] == "APPROVED_RESUBMIT_REQUIRED" else "APPROVED_RESUBMIT_REQUIRED"
            connection.execute(update(Review).where(Review.id == row["id"]).values(status=row["status"]))
    with engine.connect() as connection, pytest.raises(driver.SafetyStop):
        driver.verify_retained(connection, data, models)


@pytest.mark.parametrize("key", ["adls", "moderation", "azure_generation"])
@pytest.mark.parametrize("state", ["CONFIGURED_NOT_VERIFIED", "VERIFIED", "FAILED", "BLOCKED", None])
def test_provider_configuration_stops_before_any_http_write(key, state):
    data = manifest()
    data["http_test"] = {"operations": []}
    methods = []

    class Diagnostics:
        def request(self, method, path, **kwargs):
            methods.append(method)
            if path == "/health":
                return driver.httpx.Response(200, json={"status": "ok"})
            if path == "/ready":
                return driver.httpx.Response(200, json={"status": "ready"})
            content = {"database": "mssql", "provider_mode": "fixture", "pii_mode": "regex",
                       "adls": "NOT_CONFIGURED", "moderation": "NOT_CONFIGURED",
                       "azure_generation": "NOT_CONFIGURED", "tenant": data["tenant"], "role": "Admin"}
            content[key] = state
            return driver.httpx.Response(200, json=content)

    with pytest.raises(driver.SafetyStop):
        driver.Driver(Diagnostics(), data, lambda: None).workflows()
    assert methods == ["GET", "GET", "GET"]
