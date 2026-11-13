"""Exercise actual migrations in disposable SQLite databases at each reviewed head."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_database
from app.config import settings
from app.schema_compatibility import inspect_schema


@pytest.fixture(params=["004", "005"])
def migrated(request, tmp_path, client, monkeypatch):
    path = tmp_path / "compatibility.db"
    environment = {**os.environ, "DATABASE_URL": "sqlite:///" + str(path)}
    subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "upgrade", request.param],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        check=True,
    )
    engine = create_engine("sqlite:///" + str(path), connect_args={"check_same_thread": False})

    def dependency():
        with Session(engine, expire_on_commit=False) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_database] = dependency
    monkeypatch.setattr(settings, "sso_enabled", False)
    monkeypatch.setattr(settings, "demo_browser_login_enabled", True)
    monkeypatch.setattr(settings, "allow_legacy_api_credentials", False)
    with TestClient(app) as browser:
        yield browser, engine, request.param
    engine.dispose()


def test_supported_revision_demo_workflow(migrated):
    browser, engine, revision = migrated
    assert browser.get("/health").status_code == 200
    response = browser.get("/ready")
    assert response.status_code == 200, response.text
    assert response.json()["database_revision"] == revision and response.json()["sso_available"] is False
    assert browser.get("/api/sso/status").json() == {"sso_enabled": False, "configured": False, "demo_login_enabled": True}
    assert browser.get("/api/sso/login", follow_redirects=False).status_code == 503
    assert browser.get("/api/policies").status_code == 401
    session = browser.post("/api/auth/session", headers={"Authorization": "Bearer admin"})
    assert session.status_code == 201
    headers = {"Authorization": "Bearer " + session.json()["access_token"]}
    assert browser.get("/api/policies", headers=headers).status_code == 200
    created = browser.post("/api/policies", headers=headers, json={"name": "Compatibility policy"})
    assert created.status_code == 201
    auditor = browser.post("/api/auth/session", headers={"Authorization": "Bearer auditor"}).json()["access_token"]
    assert browser.post("/api/policies", headers={"Authorization": "Bearer " + auditor}, json={"name": "Denied"}).status_code == 403
    foreign = browser.post("/api/auth/session", headers={"Authorization": "Bearer foreign"}).json()["access_token"]
    assert browser.get("/api/policies/" + created.json()["id"], headers={"Authorization": "Bearer " + foreign}).status_code == 404
    assert browser.post("/api/auth/logout", headers=headers).status_code == 200
    assert browser.get("/api/policies", headers=headers).status_code == 401
    with engine.connect() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == revision


def test_sso_requires_reviewed_schema(migrated, monkeypatch):
    browser, _, revision = migrated
    monkeypatch.setattr(settings, "sso_enabled", True)
    monkeypatch.setattr(settings, "entra_tenant_id", "11111111-1111-4111-8111-111111111111")
    monkeypatch.setattr(settings, "entra_client_id", "22222222-2222-4222-8222-222222222222")
    monkeypatch.setattr(settings, "entra_client_secret", "synthetic-only")
    monkeypatch.setattr(settings, "sso_public_origin", "https://testserver")
    assert browser.get("/ready").status_code == (503 if revision == "004" else 200)
    assert browser.get("/api/sso/status").json()["configured"] is (revision == "005")
    # Unknown callback cannot create a session; revision 004 stops before SSO SQL.
    assert browser.get("/api/sso/callback", follow_redirects=False).status_code == (503 if revision == "004" else 303)


@pytest.mark.parametrize("drift", ["revision", "multiple_revisions", "missing_table", "missing_index", "missing_trigger", "partial_sso"])
def test_drift_is_not_ready(migrated, drift):
    browser, engine, revision = migrated
    with engine.begin() as c:
        if drift == "revision":
            c.execute(text("UPDATE alembic_version SET version_num='999'"))
        if drift == "multiple_revisions":
            c.execute(text("INSERT INTO alembic_version VALUES ('003')"))
        if drift == "missing_table":
            c.execute(text("DROP TABLE demo_sessions"))
        if drift == "missing_index":
            c.execute(text("DROP INDEX ix_demo_sessions_expires"))
        if drift == "missing_trigger":
            c.execute(text("DROP TRIGGER immutable_audit_events_delete"))
        if drift == "partial_sso":
            c.execute(text("CREATE TABLE sso_sessions (id TEXT)" if revision == "004" else "DROP TABLE sso_sessions"))
    assert browser.get("/health").status_code == 200
    assert browser.get("/ready").status_code == 503


def test_inspection_never_mutates_schema_or_records(migrated):
    _, engine, _ = migrated
    with Session(engine) as db:
        before = list(db.execute(text("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")))
        inspect_schema(db)
        after = list(db.execute(text("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")))
        assert before == after


@pytest.mark.parametrize(
    "permission_case", ["allowed", "missing_base", "missing_sso", "disabled_index", "disabled_trigger", "untrusted_fk"]
)
def test_sql_server_runtime_contract(migrated, monkeypatch, permission_case):
    """Actual migrated object reflection, with SQL Server-only metadata/permissions mocked."""
    from types import SimpleNamespace
    from sqlalchemy import inspect
    from fastapi import HTTPException
    from app import schema_compatibility as compatibility

    _, engine, revision = migrated
    with engine.connect() as connection:
        actual = inspect(connection)

        class Metadata:
            def get_indexes(self, name, **kwargs):
                # MSSQL exposes UNIQUE constraints as backing indexes; SQLite
                # reports them separately. Model that dialect contract faithfully.
                indexes = actual.get_indexes(name)
                return indexes + [
                    {"name": constraint["name"], "column_names": constraint["column_names"], "unique": True}
                    for constraint in actual.get_unique_constraints(name)
                ]

            def __getattr__(self, name):
                method = getattr(actual, name)
                return lambda *args, **kwargs: method(*args, **{k: v for k, v in kwargs.items() if k != "schema"})

        class Connection:
            dialect = SimpleNamespace(name="mssql")

            def execute(self, statement):
                return connection.execute(text(str(statement).replace("dbo.alembic_version", "alembic_version")))

            def scalar(self, statement, params=None):
                query = str(statement)
                if "HAS_PERMS" in query:
                    if permission_case == "missing_base" and "dbo.demo_sessions" in params.values():
                        return 0
                    if permission_case == "missing_sso" and "dbo.sso_sessions" in params.values():
                        return 0
                    return 1
                if "sys.triggers" in query:
                    return 0 if permission_case == "disabled_trigger" else 1
                if "sys.foreign_keys" in query:
                    return int(permission_case == "untrusted_fk")
                if "sys.indexes" in query:
                    return int(permission_case == "disabled_index")
                raise AssertionError("Unexpected SQL")

        monkeypatch.setattr(compatibility, "inspect", lambda _: Metadata())
        monkeypatch.setattr(compatibility, "BatchedKeys", lambda connection, inspector: inspector)
        db = SimpleNamespace(connection=lambda: Connection())
        should_fail = permission_case in {"missing_base", "disabled_index", "disabled_trigger", "untrusted_fk"}
        if should_fail:
            with pytest.raises(HTTPException):
                compatibility.inspect_schema(db)
        else:
            assert compatibility.inspect_schema(db)["revision"] == revision
            if revision == "005" and permission_case == "missing_sso":
                with pytest.raises(HTTPException):
                    compatibility.inspect_schema(db, require_sso=True)
            elif revision == "005":
                assert compatibility.inspect_schema(db, require_sso=True)["sso_schema"]


def test_existing_demo_session_survives_local_additive_upgrade(migrated):
    browser, engine, revision = migrated
    response = browser.post("/api/auth/session", headers={"Authorization": "Bearer admin"})
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    with engine.connect() as c:
        before = list(c.execute(text("SELECT id,tenant,actor,action,resource,created FROM audit_events ORDER BY id")))
    environment = {**os.environ, "DATABASE_URL": str(engine.url)}
    subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "upgrade", "005"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        check=True,
    )
    assert browser.get("/ready").status_code == 200
    assert browser.get("/ready").json()["database_revision"] == "005"
    assert browser.get("/api/policies", headers=headers).status_code == 200
    assert browser.get("/api/sso/status").json()["configured"] is False
    with engine.connect() as c:
        assert list(c.execute(text("SELECT id,tenant,actor,action,resource,created FROM audit_events ORDER BY id"))) == before


def test_oidc_session_on_actual_migrated_005(migrated, monkeypatch):
    import httpx
    from unittest.mock import AsyncMock
    from urllib.parse import urlsplit, parse_qs
    from app import sso
    from app.models import SsoMembership

    browser, engine, revision = migrated
    if revision == "004":
        assert browser.get("/api/sso/login", follow_redirects=False).status_code == 503
        return
    directory = "11111111-1111-4111-8111-111111111111"
    object_id = "33333333-3333-4333-8333-333333333333"
    for key, value in {
        "sso_enabled": True,
        "entra_tenant_id": directory,
        "entra_client_id": "22222222-2222-4222-8222-222222222222",
        "entra_client_secret": "synthetic-only",
        "sso_public_origin": "https://testserver",
    }.items():
        monkeypatch.setattr(settings, key, value)
    with Session(engine) as db:
        db.add(SsoMembership(directory_tenant=directory, object_id=object_id, tenant="one", actor="authorized-user", role="Auditor"))
        db.commit()
    monkeypatch.setattr(
        sso,
        "metadata",
        AsyncMock(return_value={"authorization_endpoint": f"https://login.microsoftonline.com/{directory}/oauth2/v2.0/authorize"}),
    )
    monkeypatch.setattr(sso, "exchange_code", AsyncMock(return_value={"tid": directory, "oid": object_id}))
    browser.base_url = httpx.URL("https://testserver")
    response = browser.get("/api/sso/login", follow_redirects=False)
    state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    assert browser.get("/api/sso/callback", params={"state": state, "code": "synthetic"}, follow_redirects=False).status_code == 303
    me = browser.get("/api/sso/me")
    assert me.json()["role"] == "Auditor"
    assert browser.get("/api/policies").status_code == 200
    assert (
        browser.post(
            "/api/policies", json={"name": "Denied"}, headers={"Origin": "https://testserver", "X-CSRF-Token": me.json()["csrf_token"]}
        ).status_code
        == 403
    )
    assert (
        browser.post("/api/sso/logout", headers={"Origin": "https://testserver", "X-CSRF-Token": me.json()["csrf_token"]}).status_code
        == 200
    )
    assert browser.get("/api/policies").status_code == 401
