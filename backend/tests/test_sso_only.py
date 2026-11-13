"""SSO-only enforcement with synthetic credentials and disposable SQL only."""

import pytest
from app.config import settings
from test_entra_sso import browser, sign_in, ORIGIN  # noqa: F401

LEGACY_ROUTES = [
    ("POST", "/api/auth/session"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/sessions"),
    ("POST", "/api/auth/sessions/synthetic/revoke"),
]


@pytest.mark.parametrize("legacy_enabled", [False, True])
def test_disabled_demo_rejects_credentials_and_existing_sessions(client, monkeypatch, legacy_enabled):
    monkeypatch.setattr(settings, "demo_browser_login_enabled", True)
    issued = client.post("/api/auth/session")
    assert issued.status_code == 201
    token = issued.json()["access_token"]
    monkeypatch.setattr(settings, "demo_browser_login_enabled", False)
    monkeypatch.setattr(settings, "allow_legacy_api_credentials", legacy_enabled)
    for credential in ("admin", token):
        client.headers["Authorization"] = "Bearer " + credential
        assert client.get("/api/policies").status_code == 401
        assert client.get("/api/settings").status_code == 401
        for method, path in LEGACY_ROUTES:
            response = client.request(method, path)
            assert response.status_code == 403
            assert response.json()["detail"] == "Demonstration authentication is disabled"
    client.headers.pop("Authorization")
    assert client.get("/api/policies").status_code == 401
    for method, path in LEGACY_ROUTES:
        assert client.request(method, path).status_code == 403


def test_disabled_demo_preserves_sso_and_blocks_cookie_on_legacy_routes(browser, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "demo_browser_login_enabled", False)
    assert sign_in(browser).status_code == 303
    me = browser.get("/api/sso/me")
    assert me.status_code == 200
    assert me.json()["role"] == "Admin" and me.json()["tenant"] == "one"
    assert browser.get("/api/policies").status_code == 200
    headers = {"Origin": ORIGIN, "X-CSRF-Token": me.json()["csrf_token"]}
    for method, path in LEGACY_ROUTES:
        assert browser.request(method, path, headers=headers).status_code == 403
    assert browser.post("/api/sso/logout", headers=headers).status_code == 200
    assert browser.get("/api/policies").status_code == 401
