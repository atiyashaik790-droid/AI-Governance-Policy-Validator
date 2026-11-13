"""Synthetic OIDC responses and disposable DB only; no Microsoft network calls."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from sqlalchemy import select

from app import sso
from app.config import settings
from app.database import get_database
from app.main import app
from app.models import SsoMembership, SsoSession, SsoTransaction

DIRECTORY = "11111111-1111-4111-8111-111111111111"
CLIENT = "22222222-2222-4222-8222-222222222222"
OBJECT = "33333333-3333-4333-8333-333333333333"
ORIGIN = "https://testserver"
ISSUER = f"https://login.microsoftonline.com/{DIRECTORY}/v2.0"
META = {
    "issuer": ISSUER,
    "authorization_endpoint": ISSUER + "/authorize",
    "token_endpoint": ISSUER + "/token",
    "jwks_uri": ISSUER + "/keys",
    "end_session_endpoint": ISSUER + "/logout",
}


@pytest.fixture
def browser(client, monkeypatch):
    for name, value in {
        "sso_enabled": True,
        "demo_browser_login_enabled": False,
        "entra_tenant_id": DIRECTORY,
        "entra_client_id": CLIENT,
        "entra_client_secret": "synthetic-test-only",
        "sso_public_origin": ORIGIN,
    }.items():
        monkeypatch.setattr(settings, name, value)
    client.headers.pop("Authorization")
    client.base_url = httpx.URL(ORIGIN)
    monkeypatch.setattr(sso, "metadata", AsyncMock(return_value=META))
    monkeypatch.setattr(sso, "exchange_code", AsyncMock(return_value={"tid": DIRECTORY, "oid": OBJECT}))
    with next(app.dependency_overrides[get_database]()) as db:
        db.add(
            SsoMembership(id="member", directory_tenant=DIRECTORY, object_id=OBJECT, tenant="one", actor="authorized-user", role="Admin")
        )
        db.commit()
    return client


def db_session():
    return next(app.dependency_overrides[get_database]())


def begin(browser, path="/policies"):
    response = browser.get("/api/sso/login", params={"return_to": path}, follow_redirects=False)
    assert response.status_code == 302
    params = parse_qs(urlsplit(response.headers["location"]).query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["scope"] == ["openid profile"]
    assert params["redirect_uri"] == [ORIGIN + "/api/sso/callback"]
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    return params["state"][0]


def sign_in(browser):
    state = begin(browser)
    return browser.get("/api/sso/callback", params={"state": state, "code": "synthetic-code"}, follow_redirects=False)


def test_login_session_restore_logout(browser):
    response = sign_in(browser)
    assert response.status_code == 303 and response.headers["location"] == ORIGIN + "/policies"
    assert "HttpOnly" in response.headers["set-cookie"] and "Secure" in response.headers["set-cookie"]
    me = browser.get("/api/sso/me")
    assert me.json()["role"] == "Admin" and me.json()["tenant"] == "one"
    assert browser.get("/api/policies").status_code == 200
    assert browser.post("/api/sso/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": me.json()["csrf_token"]}).status_code == 200
    assert browser.get("/api/sso/me").status_code == 401
    assert browser.get("/api/policies").status_code == 401
    assert sign_in(browser).status_code == 303
    assert browser.get("/api/sso/me").status_code == 200


@pytest.mark.parametrize(
    "path", ["https://evil.example", "//evil.example", "/\\evil", "/%2f/evil", "/policies/../settings", "/unknown", "/?code=secret"]
)
def test_open_redirect_rejected(browser, path):
    assert browser.get("/api/sso/login", params={"return_to": path}).status_code == 400


@pytest.mark.parametrize("failure", ["state", "binding", "provider", "code", "unknown", "foreign", "disabled", "expired_transaction"])
def test_callback_fail_closed(browser, monkeypatch, failure):
    state = begin(browser)
    params = {"state": state, "code": "synthetic-code"}
    if failure == "state":
        params["state"] = "wrong"
    if failure == "binding":
        browser.cookies.clear()
    if failure == "provider":
        params["error"] = "access_denied"
    if failure == "code":
        monkeypatch.setattr(sso, "exchange_code", AsyncMock(side_effect=ValueError("must never appear")))
    if failure in {"unknown", "foreign"}:
        monkeypatch.setattr(
            sso, "exchange_code", AsyncMock(return_value={"tid": DIRECTORY if failure == "unknown" else CLIENT, "oid": CLIENT})
        )
    if failure in {"disabled", "expired_transaction"}:
        with db_session() as db:
            if failure == "disabled":
                db.get(SsoMembership, "member").enabled = 0
            else:
                db.get(SsoTransaction, sso.digest(state)).expires = "2000-01-01T00:00:00+00:00"
            db.commit()
    response = browser.get("/api/sso/callback", params=params, follow_redirects=False)
    assert "auth_error=" in response.headers["location"]
    assert "must never appear" not in response.text
    with db_session() as db:
        assert db.scalar(select(SsoSession)) is None


def test_replayed_response_rejected(browser):
    state = begin(browser)
    binding = browser.cookies.get(sso.TRANSACTION_COOKIE)
    response = browser.get("/api/sso/callback", params={"state": state, "code": "synthetic"}, follow_redirects=False)
    assert "auth_error" not in response.headers["location"]
    browser.cookies.set(sso.TRANSACTION_COOKIE, binding, domain="testserver.local", path="/")
    response = browser.get("/api/sso/callback", params={"state": state, "code": "synthetic"}, follow_redirects=False)
    assert "authentication_failed" in response.headers["location"]
    assert sso.exchange_code.await_count == 1


@pytest.mark.parametrize("change", ["disabled", "role", "expired", "revoked"])
def test_membership_and_session_changes_take_effect(browser, change):
    sign_in(browser)
    with db_session() as db:
        if change == "disabled":
            db.get(SsoMembership, "member").enabled = 0
        elif change == "role":
            db.get(SsoMembership, "member").role = "Auditor"
        else:
            session = db.scalar(select(SsoSession))
            if change == "expired":
                session.expires = "2000-01-01T00:00:00+00:00"
            else:
                session.revoked = 1
        db.commit()
    response = browser.get("/api/sso/me")
    if change == "role":
        assert response.json()["role"] == "Auditor"
    else:
        assert response.status_code == 401


@pytest.mark.parametrize("csrf,origin", [("", ORIGIN), ("bad", ORIGIN), ("valid", "https://evil.example"), ("valid", "")])
def test_csrf_rejected(browser, csrf, origin):
    sign_in(browser)
    actual = browser.get("/api/sso/me").json()["csrf_token"]
    assert (
        browser.post("/api/sso/logout", headers={"X-CSRF-Token": actual if csrf == "valid" else csrf, "Origin": origin}).status_code == 403
    )
    assert browser.get("/api/sso/me").status_code == 200


@pytest.mark.parametrize("role", sorted(sso.ROLES))
def test_existing_rbac_and_tenant_isolation(browser, role):
    with db_session() as db:
        db.get(SsoMembership, "member").role = role
        db.commit()
    sign_in(browser)
    assert browser.get("/api/sso/me").json()["role"] == role
    assert browser.get("/api/policies").status_code == (403 if role == "User" else 200)
    csrf = browser.get("/api/sso/me").json()["csrf_token"]
    response = browser.post("/api/policies", json={"name": "SSO isolated policy"}, headers={"X-CSRF-Token": csrf, "Origin": ORIGIN})
    if role in {"Admin", "Policy Owner"}:
        assert response.status_code == 201
        policy_id = response.json()["id"]
        with db_session() as db:
            db.get(SsoMembership, "member").tenant = "two"
            db.commit()
        assert browser.get(f"/api/policies/{policy_id}").status_code == 404
    else:
        assert response.status_code == 403


def test_no_cookie_and_ambiguous_credentials(browser):
    assert browser.get("/api/policies").status_code == 401
    sign_in(browser)
    assert browser.get("/api/policies", headers={"Authorization": "Bearer admin"}).status_code == 401


def test_session_rotation(browser):
    sign_in(browser)
    old = browser.cookies.get(sso.COOKIE)
    sign_in(browser)
    assert browser.cookies.get(sso.COOKIE) != old
    with db_session() as db:
        assert db.get(SsoSession, sso.digest(old)).revoked == 1


@pytest.mark.parametrize(
    "invalid", [None, "issuer", "audience", "signature", "expiry", "nonce", "missing_nonce", "tenant", "algorithm", "azp"]
)
@pytest.mark.asyncio
async def test_real_library_token_validation(monkeypatch, invalid):
    for name, value in {
        "sso_enabled": True,
        "demo_browser_login_enabled": False,
        "entra_tenant_id": DIRECTORY,
        "entra_client_id": CLIENT,
        "entra_client_secret": "synthetic-test-only",
        "sso_public_origin": ORIGIN,
    }.items():
        monkeypatch.setattr(settings, name, value)
    key = RSAKey.generate_key(2048, parameters={"kid": "synthetic"})
    claims = {
        "iss": ISSUER,
        "aud": CLIENT,
        "sub": "synthetic-subject",
        "oid": OBJECT,
        "tid": DIRECTORY,
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "nonce": "synthetic-nonce",
    }
    if invalid == "issuer":
        claims["iss"] = "https://evil.example"
    if invalid == "audience":
        claims["aud"] = "wrong"
    if invalid == "expiry":
        claims["exp"] = int(time.time()) - 120
    if invalid == "nonce":
        claims["nonce"] = "wrong"
    if invalid == "missing_nonce":
        del claims["nonce"]
    if invalid == "tenant":
        claims["tid"] = CLIENT
    if invalid == "azp":
        claims["azp"] = "wrong"
    signing_key = RSAKey.generate_key(2048, parameters={"kid": "synthetic"}) if invalid == "signature" else key
    encoded = jwt.encode(
        {"alg": "RS512" if invalid == "algorithm" else "RS256", "kid": "synthetic"}, claims, signing_key, algorithms=["RS256", "RS512"]
    )
    monkeypatch.setattr(sso, "metadata", AsyncMock(return_value=META))
    monkeypatch.setattr(sso.AsyncOAuth2Client, "fetch_token", AsyncMock(return_value={"id_token": encoded}))
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"keys": [key.as_dict(private=False)]}))
    monkeypatch.setattr(sso, "HttpClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    tx = SimpleNamespace(nonce="synthetic-nonce", verifier="synthetic-verifier")
    if invalid:
        with pytest.raises(Exception):
            await sso.exchange_code("synthetic-code", tx)
    else:
        result = await sso.exchange_code("synthetic-code", tx)
        assert result["oid"] == OBJECT


def test_admin_session_listing_and_revocation(browser):
    sign_in(browser)
    csrf = browser.get("/api/sso/me").json()["csrf_token"]
    rows = browser.get("/api/sso/sessions").json()
    assert len(rows) == 1 and rows[0]["actor"] == "authorized-user"
    assert browser.post(f"/api/sso/sessions/{rows[0]['id']}/revoke", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}).status_code == 200
    assert browser.get("/api/policies").status_code == 401


def test_non_admin_cannot_manage_sessions(browser):
    with db_session() as db:
        db.get(SsoMembership, "member").role = "Developer"
        db.commit()
    sign_in(browser)
    assert browser.get("/api/sso/sessions").status_code == 403


@pytest.mark.parametrize("reviewer_state", ["enabled", "disabled", "foreign", "demo_only"])
def test_sso_reviewer_assignment_uses_authorized_memberships(browser, reviewer_state):
    from app.models import Execution, Review

    with db_session() as db:
        execution = Execution(
            tenant="one",
            actor="authorized-user",
            policy_id="synthetic",
            version=1,
            model="fixture",
            decision="HUMAN_REVIEW",
            metadata_json="{}",
        )
        db.add(execution)
        db.flush()
        review = Review(tenant="one", execution_id=execution.id)
        db.add(review)
        if reviewer_state != "demo_only":
            db.add(
                SsoMembership(
                    directory_tenant=DIRECTORY,
                    object_id=CLIENT,
                    tenant="two" if reviewer_state == "foreign" else "one",
                    actor="reviewer",
                    role="Reviewer",
                    enabled=int(reviewer_state != "disabled"),
                )
            )
        db.commit()
        review_id = review.id
    sign_in(browser)
    csrf = browser.get("/api/sso/me").json()["csrf_token"]
    response = browser.put(
        f"/api/reviews/{review_id}/assignment", json={"assigned_reviewer": "reviewer"}, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}
    )
    assert response.status_code == (200 if reviewer_state == "enabled" else 422)


def test_operator_membership_provisioning_is_audited(browser):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from manage_sso_membership import apply_mapping, validate_mapping
    from app.models import Audit

    mapping = validate_mapping(
        {"directory_tenant": DIRECTORY, "object_id": CLIENT, "tenant": "one", "actor": "new-reviewer", "role": "Reviewer", "enabled": True}
    )
    with db_session() as db:
        apply_mapping(db, mapping, "approved-operator", "synthetic-approval")
        db.commit()
        member = db.scalar(select(SsoMembership).where(SsoMembership.object_id == CLIENT))
        assert member.role == "Reviewer"
        assert db.scalar(select(Audit).where(Audit.action == "sso.membership.provisioned")) is not None
        mapping["actor"] = "different-actor"
        with pytest.raises(ValueError):
            apply_mapping(db, mapping, "approved-operator", "synthetic-approval")


@pytest.mark.parametrize("changed", ["issuer", "jwks_uri", "token_endpoint"])
@pytest.mark.asyncio
async def test_untrusted_discovery_rejected(browser, monkeypatch, changed):
    # Call actual discovery validation, using a synthetic HTTPS response.
    data = {**META, changed: "https://evil.example/endpoint"}
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=data))
    monkeypatch.setattr(sso, "HttpClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    actual = sso.metadata
    # Fixture replaced the function; retrieve the real implementation saved below.
    with pytest.raises(ValueError):
        await REAL_METADATA()
    assert actual.await_count == 0


REAL_METADATA = sso.metadata


def test_chat_return_route_preserves_local_bookmark():
    assert sso.safe_return_path("/chat") == "/chat"
