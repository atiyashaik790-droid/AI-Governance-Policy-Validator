"""Public v2 end-to-end contracts: fixture providers and disposable schemas only."""

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import providers
from app.config import settings
from app.models import InferenceUsage, Version
from app.models_multi_policy import Execution006, ExecutionPolicyEvidence as Evidence
import test_multi_policy_bridge as phase_b_bridge
import test_multi_policy_phase_b as phase_b
import test_multi_policy_phase_d as phase_d

templates = phase_b.templates
template010 = phase_b.template010
engine006 = phase_b.engine010
bridge = phase_b_bridge.bridge


def tag(client):
    return client.get("/api/v2/workspace/policy-state").headers["etag"]


def documents():
    return [phase_d.document(keyword="review-term", action="HUMAN_REVIEW"), phase_d.document(keyword="redact-term", action="REDACT"),
            phase_d.document(keyword="block-term"), *[phase_d.document(name=f"Extra {i}") for i in range(3)]]


@pytest.mark.parametrize("text,expected,calls", [("public", "ALLOW", 1), ("redact-term", "REDACT", 1),
    ("review-term redact-term", "HUMAN_REVIEW", 0), ("block-term review-term redact-term", "BLOCK", 0)])
def test_public_six_policy_precedence_persistence_and_counts(bridge, engine006, monkeypatch, text, expected, calls):
    with Session(engine006, expire_on_commit=False) as db:
        pairs, _ = phase_d.setup_workspace(db, documents())
    generate = AsyncMock(return_value="public reply")
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    response = bridge.post("/api/v2/governance/generate", json={"text": text}, headers={"If-Match": tag(bridge)})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["schema_version"] == "2.0" and result["execution_mode"] == "MULTI"
    assert result["decision"] == expected and len(result["input"]["policies"]) == 6
    assert {p["version_id"] for p in result["input"]["policies"]} == {v for _, v in pairs}
    assert generate.await_count == calls
    assert (result["safe_response"] is not None) == (calls == 1)
    if calls:
        assert result["output"]["policy_count"] == 6
    summary = bridge.get("/api/v2/analytics/overview").json()
    assert summary["request_count"] == 1 and summary["policy_evaluation_count"] == summary["active_policy_count"] == 6
    assert summary["compliance"]["scored_requests"] == 1
    assert summary["compliance"]["findings_available"] is True
    assert summary["compliance"]["score"] is not None
    assert summary["compliance"]["violations"]["blocked_keywords"] == (1 if "term" in text else 0)
    bridge.headers["Authorization"] = "Bearer foreign"
    other = bridge.get("/api/v2/analytics/overview").json()
    assert other["request_count"] == 0 and other["compliance"]["score"] is None
    assert all(count == 0 for count in other["compliance"]["violations"].values())
    bridge.headers["Authorization"] = "Bearer admin"
    assert bridge.get("/api/v2/audit/events?category=governance").json()["total"] == 1
    with Session(engine006) as db:
        assert db.scalar(select(func.count()).select_from(Evidence)) == 6
        assert db.scalar(select(func.count()).select_from(Execution006)) == 1


@pytest.mark.parametrize("operation", ["validate-input", "validate-output"])
def test_public_validation_never_dispatches_generation(bridge, engine006, monkeypatch, operation):
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, documents())
    generate = AsyncMock(side_effect=AssertionError("Validation cannot generate"))
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    response = bridge.post("/api/v2/governance/" + operation, json={"text": "public"}, headers={"If-Match": tag(bridge)})
    assert response.status_code == 200 and response.json()["decision"] == "ALLOW"
    stage = "output" if operation == "validate-output" else "input"
    assert response.json()[stage]["policy_count"] == 6
    generate.assert_not_awaited()


def test_public_output_gate_and_ambiguous_generation_no_retry(bridge, engine006, monkeypatch):
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, documents())
    generate = AsyncMock(return_value="block-term")
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    response = bridge.post("/api/v2/governance/generate", json={"text": "public"}, headers={"If-Match": tag(bridge)})
    assert response.json()["decision"] == "BLOCK" and response.json()["safe_response"] is None
    assert response.json()["output"]["policy_count"] == 6 and generate.await_count == 1
    generate.reset_mock()
    generate.side_effect = providers.ProviderUnavailable("synthetic ambiguous result")
    response = bridge.post("/api/v2/governance/generate", json={"text": "public"}, headers={"If-Match": tag(bridge)})
    assert response.json()["decision"] == "BLOCK" and response.json()["generation_status"] == "FAILED"
    assert generate.await_count == 1


@pytest.mark.parametrize("header,status", [(None, 428), ('"999"', 412), ('W/"1"', 412), ("*", 412)])
def test_public_preconditions_fail_before_admission_or_provider(bridge, engine006, monkeypatch, header, status):
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, documents())
    generate = AsyncMock()
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    response = bridge.post("/api/v2/governance/generate", json={"text": "public"}, headers={"If-Match": header} if header else {})
    assert response.status_code == status
    generate.assert_not_awaited()
    with Session(engine006) as db:
        assert db.scalar(select(func.count()).select_from(InferenceUsage)) == 0


def test_public_pins_and_cross_tenant_scope_and_v1_guards(bridge, engine006, monkeypatch):
    with Session(engine006, expire_on_commit=False) as db:
        pairs, _ = phase_d.setup_workspace(db, documents())
        db.add(Version(tenant="one", policy_id=pairs[0][0], number=2, document=phase_d.document(keyword="public").model_dump_json()))
        db.commit()
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(return_value="public reply"))
    result = bridge.post("/api/v2/governance/generate", json={"text": "public"}, headers={"If-Match": tag(bridge)}).json()
    assert result["decision"] == "ALLOW" and {p["version_id"] for p in result["input"]["policies"]} == {v for _, v in pairs}
    assignment = bridge.get("/api/v2/workspace/policy-assignments").json()["items"][0]
    assert assignment["version"] == 1
    assert bridge.post("/api/governance/generate", json={"text": "public"}).status_code == 409
    assert bridge.post(f"/api/policies/{pairs[0][0]}/activate").status_code == 409
    bridge.headers["Authorization"] = "Bearer foreign"
    assert bridge.post("/api/v2/governance/generate", json={"text": "public"}, headers={"If-Match": tag(bridge)}).status_code == 409
    assert bridge.get("/api/v2/audit/executions/" + result["request_id"]).status_code == 404
    bridge.headers["Authorization"] = "Bearer reviewer"
    assert bridge.post("/api/v2/governance/generate", json={"text": "public"}, headers={"If-Match": '"1"'}).status_code == 403
    bridge.headers.pop("Authorization")
    assert bridge.post("/api/v2/governance/generate", json={"text": "public"}).status_code == 401


def test_legacy_policy_owner_activation_preserved_but_multi_management_denied(bridge, engine006, monkeypatch):
    with Session(engine006, expire_on_commit=False) as db:
        p, _ = phase_b.legacy(db)
        pid = p.id
    accounts = json.loads(settings.demo_accounts_json)
    for account in accounts:
        if account["user"] == "admin":
            account["role"] = "Policy Owner"
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    assert bridge.post(f"/api/policies/{pid}/activate").status_code == 200
    assert bridge.put("/api/v2/workspace/policy-mode", json={"mode": "MULTI", "seed_legacy_assignment": False}, headers={"If-Match": tag(bridge)}).status_code == 403


def test_public_payload_forbids_client_tenant(bridge, engine006):
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, documents())
    assert bridge.post("/api/v2/governance/generate", json={"text": "public", "tenant": "two"}, headers={"If-Match": tag(bridge)}).status_code == 422


def test_policy_owner_cannot_bypass_multi_assignments_through_v1(bridge, engine006, monkeypatch):
    with Session(engine006, expire_on_commit=False) as db:
        pairs, _ = phase_d.setup_workspace(db, documents())
    accounts = json.loads(settings.demo_accounts_json)
    for account in accounts:
        if account["user"] == "admin":
            account["role"] = "Policy Owner"
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    assert bridge.post(f"/api/policies/{pairs[0][0]}/activate").status_code == 409
    assert bridge.put(f"/api/v2/workspace/policy-assignments/{pairs[0][0]}",
                      json={"active": False}, headers={"If-Match": tag(bridge)}).status_code == 403
