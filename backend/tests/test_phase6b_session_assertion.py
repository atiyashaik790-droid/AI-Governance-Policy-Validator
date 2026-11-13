"""Actual revision-005 fixtures; deterministic request delay, no native SQL/SSO network."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import sso, schema_compatibility
from app.config import Settings, settings
from app.database import get_database
from app.main import app
from app.models import SsoSession
from test_entra_sso import browser, begin  # noqa: F401
from test_session_lifetime import clock  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/tests"))
from session_contract import observe_issuance, verify_session  # noqa: E402


@pytest.fixture(scope="module")
def template005(tmp_path_factory):
    directory = tmp_path_factory.mktemp("phase6b-a1-005")
    path = directory / "template.db"
    subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "upgrade", "005"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "DATABASE_URL": "sqlite:///" + str(path), "PROVIDER_MODE": "fixture", "PII_MODE": "regex"},
        check=True,
        capture_output=True,
        timeout=60,
    )
    return path


@pytest.fixture
def revision005(client, template005, tmp_path):
    path = tmp_path / "session005.db"
    shutil.copyfile(template005, path)
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
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "005"
    yield engine
    engine.dispose()


def callback(browser_client):
    state = begin(browser_client)
    with observe_issuance(sso, settings.sso_session_minutes) as issued:
        response = browser_client.get("/api/sso/callback", params={"state": state, "code": "synthetic"}, follow_redirects=False)
        assert response.status_code == 303
    return response, issued


@pytest.mark.parametrize("delay", [0, 107.20794])
def test_005_delay_reproduces_old_failure_and_correct_contract_survives(revision005, browser, clock, monkeypatch, delay):  # noqa: F811
    response, issued = callback(browser)
    raw = browser.cookies.get(sso.COOKIE)
    sid = sso.digest(raw)
    with Session(revision005) as db:
        persisted = db.get(SsoSession, sid).expires
    # Simulate measured schema-check latency with virtual UTC time, without sleeping.
    original = schema_compatibility.inspect_schema

    def delayed(*args, **kwargs):
        result = original(*args, **kwargs)
        clock[0] += timedelta(seconds=delay)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(schema_compatibility, "inspect_schema", delayed)
        me = browser.get("/api/sso/me")
    assert me.status_code == 200
    actual = (datetime.fromisoformat(me.json()["expires_at"]) - datetime.fromisoformat(me.json()["server_now"])).total_seconds()
    expected = settings.sso_session_minutes * 60 - delay
    assert actual == pytest.approx(expected)
    if settings.sso_session_minutes == 120 and delay:
        assert not 7100 < actual <= 7200
        assert actual == 7092.79206  # Reproduction, not a recovered historical measurement.
    evidence = verify_session(sso, issued, response, persisted, me.json())
    assert evidence["issued_duration_lower_seconds"] == settings.sso_session_minutes * 60
    assert evidence["remaining_seconds"] == actual
    # A separate client and fresh ORM session restore the same persisted session.
    with TestClient(app, base_url="https://testserver") as restored:
        restored.cookies.set(sso.COOKIE, raw)
        again = restored.get("/api/sso/me")
        assert again.status_code == 200
        assert again.json()["expires_at"] == persisted
    with Session(revision005) as db:
        assert db.get(SsoSession, sid).expires == persisted
    print("SESSION_REPRODUCTION " + json.dumps(evidence, sort_keys=True))


@pytest.mark.parametrize("fault", ["shortened", "extended", "cookie", "database", "renewed", "naive", "offset"])
def test_corrected_contract_rejects_real_duration_and_consistency_defects(revision005, browser, clock, fault):  # noqa: F811
    response, issued = callback(browser)
    expires = issued[0]["expires"].isoformat()
    me = {"expires_at": expires, "server_now": clock[0].isoformat()}
    persisted = expires
    if fault in ("shortened", "extended"):
        issued[0]["expires"] += timedelta(minutes=-60 if fault == "shortened" else 60)
    elif fault == "cookie":
        response.headers["set-cookie"] = f"{sso.COOKIE}=synthetic; Max-Age=1; Secure; HttpOnly; SameSite=lax; Path=/"
    elif fault == "database":
        persisted = (clock[0] + timedelta(minutes=1)).isoformat()
    elif fault == "renewed":
        me["expires_at"] = (issued[0]["expires"] + timedelta(seconds=1)).isoformat()
    elif fault == "naive":
        me["server_now"] = clock[0].replace(tzinfo=None).isoformat()
    else:
        me["server_now"] = clock[0].astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
    with pytest.raises(AssertionError):
        verify_session(sso, issued, response, persisted, me)


def test_default_and_explicit_configuration_do_not_inherit_hosted_override(monkeypatch):
    monkeypatch.delenv("SSO_SESSION_MINUTES", raising=False)
    monkeypatch.delenv("DEMO_SESSION_MINUTES", raising=False)
    assert Settings(_env_file=None).sso_session_minutes == 120
    monkeypatch.setenv("SSO_SESSION_MINUTES", "60")
    assert Settings(_env_file=None).sso_session_minutes == 60
    assert Settings(_env_file=None).demo_session_minutes == 60
    monkeypatch.setenv("DEMO_SESSION_MINUTES", "120")
    assert Settings(_env_file=None).sso_session_minutes == 60
    assert Settings(_env_file=None).demo_session_minutes == 120


def test_issuance_observer_rejects_wrong_configured_duration(revision005, browser, clock, monkeypatch):  # noqa: F811
    original = sso.expiry
    monkeypatch.setattr(sso, "expiry", lambda minutes: original(minutes - 1))
    with pytest.raises(AssertionError, match="Incorrect issued duration"):
        callback(browser)


def test_demo_session_duration_is_independent_and_absolute(client, clock, monkeypatch):  # noqa: F811
    from app import sessions, security
    from app.models import DemoSession
    from test_entra_sso import db_session

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0] if tz else clock[0].replace(tzinfo=None)

    minutes = settings.sso_session_minutes  # Exercise demo duration 60 and 120 too.
    monkeypatch.setattr(settings, "demo_session_minutes", minutes)
    monkeypatch.setattr(settings, "demo_browser_login_enabled", True)
    monkeypatch.setattr(settings, "sso_enabled", False)
    monkeypatch.setattr(sessions, "datetime", FrozenDateTime)
    monkeypatch.setattr(security, "now", lambda: clock[0].isoformat())
    issued_at = clock[0]
    response = client.post("/api/auth/session")
    assert response.status_code == 201
    data = response.json()
    expires = issued_at + timedelta(minutes=minutes)
    assert datetime.fromisoformat(data["expires"]) == expires
    assert not response.headers.get("set-cookie")  # Bearer demo session has no SSO cookie.
    sid = sso.digest(data["access_token"])
    auth = {"Authorization": "Bearer " + data["access_token"]}
    clock[0] = expires - timedelta(microseconds=1)
    assert client.get("/api/policies", headers=auth).status_code == 200
    with db_session() as db:
        assert datetime.fromisoformat(db.get(DemoSession, sid).expires) == expires
    clock[0] = expires
    assert client.get("/api/policies", headers=auth).status_code == 401
    clock[0] = issued_at + timedelta(seconds=1)
    assert client.post("/api/auth/logout", headers=auth).status_code == 200
    assert client.get("/api/policies", headers=auth).status_code == 401
