"""Existing HTTP/SSO contracts exercised on disposable revision 006."""

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_database
from app.main import app
from app.models import Execution, InferenceUsage, SsoMembership, Review
from app.models_multi_policy import Execution006
from app.services import policy_sets as domain
from test_multi_policy_phase_b import engine006, templates, legacy, ADMIN  # noqa: F401


@pytest.fixture
def bridge(client, engine006, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    monkeypatch.setattr(settings, "pii_mode", "regex")
    monkeypatch.setattr(settings, "sso_enabled", False)
    monkeypatch.setattr(settings, "demo_browser_login_enabled", True)

    def dependency():
        with Session(engine006, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_database] = dependency
    return client


def test_legacy_generate_on_006_keeps_original_contract(bridge, engine006):  # noqa: F811
    with Session(engine006, expire_on_commit=False) as db:
        policy, version = legacy(db)
        policy_id = policy.id
    result = bridge.post("/api/governance/generate", json={"text": "Explain governance"})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["policy_id"] == policy_id and body["policy_version"] == 1
    assert body["decision"] == "ALLOW" and body["safe_response"]
    assert "execution_mode" not in body and "mode" not in body
    with Session(engine006) as db:
        assert db.scalar(select(Execution.policy_id)) == policy_id
        assert db.scalar(select(InferenceUsage.status)) == "SUCCEEDED"
    assert bridge.get("/ready").json()["database_revision"] == "006"


def test_multimode_http_guards_before_provider_work(bridge, engine006, monkeypatch):  # noqa: F811
    from app import providers
    with Session(engine006, expire_on_commit=False) as db:
        policy, version = legacy(db)
        pid = policy.id
        domain.change_mode(db, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=True)
    generate = AsyncMock(side_effect=AssertionError("Provider must not run"))
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    for path in ["/api/governance/generate", "/api/governance/validate-input", "/api/governance/validate-output", f"/api/policies/{pid}/simulate"]:
        result = bridge.post(path, json={"text": "Do not release"})
        assert result.status_code == 409 and result.json()["detail"] == "USE_API_V2"
    assert bridge.post(f"/api/policies/{pid}/activate").status_code == 409
    assert bridge.post(f"/api/policies/{pid}/disable").status_code == 409
    assert bridge.post(f"/api/policies/{pid}/archive").status_code == 409
    assert bridge.delete(f"/api/policies/{pid}").status_code == 409
    generate.assert_not_awaited()


def test_expired_worker_cannot_return_generated_text(bridge, engine006, monkeypatch):  # noqa: F811
    from app import providers
    with Session(engine006, expire_on_commit=False) as db:
        legacy(db)

    async def expire_then_return(_text):
        with Session(engine006) as db:
            row = db.scalar(select(InferenceUsage).where(InferenceUsage.status == "RESERVED"))
            row.expires = "2000-01-01T00:00:00+00:00"
            db.commit()
        return "Generated text that must be withheld"

    monkeypatch.setattr(providers, "generate_ai_response", expire_then_return)
    result = bridge.post("/api/governance/generate", json={"text": "Explain governance"})
    assert result.status_code == 409 and result.json()["detail"] == "RESERVATION_FENCED"
    assert "Generated text" not in result.text
    with Session(engine006) as db:
        assert db.scalar(select(Execution)) is None


def test_legacy_draft_simulation_still_works_without_active_policy(bridge):
    policy = bridge.post("/api/policies", json={"name": "Draft simulation"}).json()
    result = bridge.post(f"/api/policies/{policy['id']}/simulate", json={"text": "Explain governance"})
    assert result.status_code == 200 and result.json()["decision"] == "ALLOW"


def test_sso_csrf_and_role_protection_on_006(bridge, engine006, monkeypatch):  # noqa: F811
    from app import sso
    directory = "11111111-1111-4111-8111-111111111111"
    object_id = "33333333-3333-4333-8333-333333333333"
    for key, value in {
        "sso_enabled": True, "demo_browser_login_enabled": False,
        "entra_tenant_id": directory, "entra_client_id": "22222222-2222-4222-8222-222222222222",
        "entra_client_secret": "synthetic-only", "sso_public_origin": "https://testserver",
    }.items():
        monkeypatch.setattr(settings, key, value)
    with Session(engine006) as db:
        db.add(SsoMembership(directory_tenant=directory, object_id=object_id, tenant="one", actor="reviewer", role="Reviewer"))
        db.commit()
    monkeypatch.setattr(sso, "metadata", AsyncMock(return_value={"authorization_endpoint": f"https://login.microsoftonline.com/{directory}/oauth2/v2.0/authorize"}))
    monkeypatch.setattr(sso, "exchange_code", AsyncMock(return_value={"tid": directory, "oid": object_id}))
    bridge.headers.pop("Authorization")
    bridge.base_url = httpx.URL("https://testserver")
    response = bridge.get("/api/sso/login", follow_redirects=False)
    assert response.status_code == 302
    state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    assert bridge.get("/api/sso/callback", params={"state": state, "code": "synthetic"}, follow_redirects=False).status_code == 303
    me = bridge.get("/api/sso/me")
    assert me.status_code == 200 and me.json()["role"] == "Reviewer"
    assert bridge.get("/ready").json()["sso_available"] is True
    assert bridge.post("/api/policies", json={"name": "Denied"}).status_code == 403
    headers = {"Origin": "https://testserver", "X-CSRF-Token": me.json()["csrf_token"]}
    assert bridge.post("/api/policies", json={"name": "Denied"}, headers=headers).status_code == 403
    assert bridge.get("/api/policies").status_code == 200
    assert bridge.post("/api/sso/logout", headers=headers).status_code == 200
    assert bridge.get("/api/policies").status_code == 401


def test_v2_exposes_only_workspace_management_routes():
    assert {path for path in app.openapi()["paths"] if path.startswith("/api/v2/workspace/")} == {
        "/api/v2/workspace/policy-state", "/api/v2/workspace/policy-mode",
        "/api/v2/workspace/policy-assignments", "/api/v2/workspace/policy-assignments/{policy_id}",
        "/api/v2/workspace/policy-assignment-events",
    }


def test_v1_cannot_flatten_multi_history_after_return_to_legacy(bridge, engine006):  # noqa: F811
    with Session(engine006, expire_on_commit=False) as db:
        _, version = legacy(db)
        revision = domain.change_mode(db, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=False)
        execution = Execution006(tenant="one", actor="admin", execution_mode="MULTI", policy_id=None,
                                 version=None, model="fixture", decision="HUMAN_REVIEW", metadata_json="{}")
        db.add(execution)
        db.flush()
        review = Review(tenant="one", execution_id=execution.id)
        db.add(review)
        db.commit()
        rid = review.id
        domain.change_mode(db, ADMIN, "LEGACY", expected_revision=revision, legacy_version_id=version.id)
    for path in ["/api/audit/executions", "/api/analytics/overview", f"/api/reviews/{rid}"]:
        result = bridge.get(path)
        assert result.status_code == 409 and result.json()["detail"] == "USE_API_V2"
    result = bridge.post("/api/reports/export", json={})
    assert result.status_code == 409 and result.json()["detail"] == "USE_API_V2"


@pytest.mark.parametrize("operation", ["archive", "delete"])
def test_deactivation_permits_lifecycle_despite_dormant_legacy_pointer(bridge, engine006, operation):  # noqa: F811
    with Session(engine006, expire_on_commit=False) as db:
        p, v = legacy(db)
        pid = p.id
        revision = domain.change_mode(db, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=True)
        domain.change_assignment(db, ADMIN, pid, active=False, expected_revision=revision)
    assert bridge.post(f"/api/policies/{pid}/disable").status_code == 200
    if operation == "archive":
        result = bridge.post(f"/api/policies/{pid}/archive")
    else:
        row_version = bridge.get(f"/api/policies/{pid}").json()["row_version"]
        result = bridge.delete(f"/api/policies/{pid}", headers={"If-Match": str(row_version)})
    assert result.status_code == 200, result.text


def test_disabled_legacy_policy_keeps_original_error_contract(bridge, engine006):  # noqa: F811
    with Session(engine006, expire_on_commit=False) as db:
        p, _ = legacy(db)
        pid = p.id
    assert bridge.post(f"/api/policies/{pid}/disable").status_code == 200
    result = bridge.post("/api/governance/generate", json={"text": "Explain governance"})
    assert result.status_code == 409
    assert result.json() == {"detail": "No enabled active policy; request withheld"}
