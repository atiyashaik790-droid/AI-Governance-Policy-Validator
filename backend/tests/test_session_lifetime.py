"""Absolute Entra app-session lifetime; synthetic OIDC and isolated databases."""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import sso
from app.config import Settings, settings
from app.models import SsoSession
from test_entra_sso import browser, sign_in, db_session, ORIGIN  # noqa: F401


@pytest.fixture(params=[60, 120], ids=["explicit-60", "default-120"])
def clock(monkeypatch, request):
    value = [datetime(2035, 1, 2, 12, 30, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(sso, "now", lambda: value[0].isoformat())
    if request.param == 120:
        monkeypatch.delenv("SSO_SESSION_MINUTES", raising=False)
        minutes = Settings(_env_file=None).sso_session_minutes
    else:
        minutes = Settings(_env_file=None, sso_session_minutes=60).sso_session_minutes
    monkeypatch.setattr(settings, "sso_session_minutes", minutes)
    return value


def test_default_and_cap_preserve_shorter_security_configuration():
    assert Settings.model_fields["sso_session_minutes"].default == 120
    assert Settings(_env_file=None, sso_session_minutes=60).sso_session_minutes == 60
    assert Settings.model_fields["demo_session_minutes"].default == 60
    assert Settings(_env_file=None, sso_session_minutes=15).sso_session_minutes == 15
    with pytest.raises(ValidationError):
        Settings(_env_file=None, sso_session_minutes=121)


def test_successful_signin_aligns_database_cookie_and_server_clock(browser, clock):  # noqa: F811
    response = sign_in(browser)
    assert response.status_code == 303
    cookies = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookies.load(header)
    cookie = cookies[sso.COOKIE]
    assert cookie["max-age"] == str(settings.sso_session_minutes * 60)
    assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "lax" and cookie["path"] == "/"
    expected = clock[0] + timedelta(minutes=settings.sso_session_minutes)
    with db_session() as db:
        session = db.scalar(select(SsoSession))
        assert datetime.fromisoformat(session.expires) == expected
        assert datetime.fromisoformat(session.expires).utcoffset() == timedelta(0)
    assert parsedate_to_datetime(cookie["expires"]) == expected
    me = browser.get("/api/sso/me").json()
    assert datetime.fromisoformat(me["expires_at"]) == expected
    assert datetime.fromisoformat(me["server_now"]) == clock[0]
    assert "session_id" not in me and "access_token" not in me


def test_activity_and_refresh_do_not_shorten_or_extend_session(browser, clock):  # noqa: F811
    sign_in(browser)
    with db_session() as db:
        original = db.scalar(select(SsoSession.expires))
    for minutes in (3, 6, 30, settings.sso_session_minutes - 1):
        clock[0] = datetime.fromisoformat(original) - timedelta(minutes=settings.sso_session_minutes - minutes)
        assert browser.get("/api/sso/me").status_code == 200
        assert browser.get("/api/policies").status_code == 200
        with db_session() as db:
            assert db.scalar(select(SsoSession.expires)) == original
    clock[0] = datetime.fromisoformat(original) - timedelta(microseconds=1)
    assert browser.get("/api/sso/me").status_code == 200
    clock[0] += timedelta(microseconds=1)
    response = browser.get("/api/sso/me")
    assert response.status_code == 401 and response.headers["X-Session-Reason"] == "expired"
    assert browser.get("/api/policies").status_code == 401


def test_offset_timestamp_compares_instants_not_iso_strings(browser, clock):  # noqa: F811
    sign_in(browser)
    end = clock[0] + timedelta(minutes=settings.sso_session_minutes)
    with db_session() as db:
        session = db.scalar(select(SsoSession))
        session.expires = end.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
        db.commit()
    clock[0] = end - timedelta(seconds=1)
    assert browser.get("/api/sso/me").status_code == 200
    clock[0] = end
    response = browser.get("/api/sso/me")
    assert response.status_code == 401 and response.headers["X-Session-Reason"] == "expired"


@pytest.mark.parametrize("invalid", ["2035-01-02T15:30:00", "not-a-date"])
def test_invalid_expiry_fails_closed(browser, clock, invalid):  # noqa: F811
    sign_in(browser)
    with db_session() as db:
        db.scalar(select(SsoSession)).expires = invalid
        db.commit()
    response = browser.get("/api/sso/me")
    assert response.status_code == 401 and response.headers["X-Session-Reason"] == "ended"


def test_anonymous_logout_and_explicit_revocation_are_distinct(browser, clock):  # noqa: F811
    anonymous = browser.get("/api/sso/me")
    assert anonymous.status_code == 401 and anonymous.headers["X-Session-Reason"] == "anonymous"
    sign_in(browser)
    me = browser.get("/api/sso/me").json()
    headers = {"Origin": ORIGIN, "X-CSRF-Token": me["csrf_token"]}
    response = browser.post("/api/sso/logout", headers=headers)
    assert response.status_code == 200 and "Max-Age=0" in response.headers["set-cookie"]
    assert browser.get("/api/sso/me").headers["X-Session-Reason"] == "anonymous"
    sign_in(browser)
    me = browser.get("/api/sso/me").json()
    with db_session() as db:
        sid = db.scalar(select(SsoSession.id).where(SsoSession.revoked == 0))
    headers["X-CSRF-Token"] = me["csrf_token"]
    assert browser.post(f"/api/sso/sessions/{sid}/revoke", headers=headers).status_code == 200
    revoked = browser.get("/api/sso/me")
    assert revoked.status_code == 401 and revoked.headers["X-Session-Reason"] == "ended"


def test_fresh_signin_rotates_without_reviving_previous_session(browser, clock):  # noqa: F811
    sign_in(browser)
    with db_session() as db:
        old_id = db.scalar(select(SsoSession.id))
    old_cookie = browser.cookies.get(sso.COOKIE)
    assert sign_in(browser).status_code == 303
    assert browser.cookies.get(sso.COOKIE) != old_cookie
    with db_session() as db:
        assert db.get(SsoSession, old_id).revoked == 1
    assert browser.get("/api/sso/me").status_code == 200
