import json
from unittest.mock import AsyncMock
import pytest
from app.schemas import PolicyDocument
from app.engine import inspect_text, calculate_compliance_score
from app.config import settings
from app.providers import ProviderUnavailable


# Publish a real policy through every lifecycle gate for integration tests.
def activate(client, changes=None):
    document = PolicyDocument(name="Test policy").model_dump()
    if changes:
        for category, action in changes.items():
            document["rules"][category]["action"] = action
    response = client.post("/api/policies", json=document)
    assert response.status_code == 201, response.text
    policy_id = response.json()["id"]
    for operation in ("submit", "approve", "publish", "activate"):
        response = client.post(f"/api/policies/{policy_id}/{operation}")
        assert response.status_code == 200, response.text
    return policy_id, document


# Safe requests pass both gates and persist sanitized metadata.
def test_safe_end_to_end(client):
    activate(client)
    response = client.post("/api/governance/generate", json={"text": "Explain data governance."})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["decision"] == "ALLOW" and result["model_invoked"]
    assert result["output"]["decision"] == "ALLOW" and result["safe_response"]
    history = client.get("/api/audit/executions").json()
    assert len(history) == 1
    assert "safe_text" not in history[0]["metadata_json"]
    assert "Explain data" not in json.dumps(client.get("/api/audit/events").json())


# Secrets never reach generation or ordinary audit records.
def test_secret_blocks_before_provider(client, monkeypatch):
    activate(client)
    provider = AsyncMock()
    monkeypatch.setattr("app.providers.generate_ai_response", provider)
    secret = "sk-test-" + "A" * 30
    result = client.post("/api/governance/generate", json={"text": secret}).json()
    assert result["decision"] == "BLOCK" and not result["model_invoked"]
    provider.assert_not_called()
    assert secret not in json.dumps(client.get("/api/audit/executions").json())


# Redacted input is inspected again and only sanitized text reaches the model.
def test_pii_redaction_revalidation(client, monkeypatch):
    activate(client)
    provider = AsyncMock(return_value="Approved response")
    monkeypatch.setattr("app.providers.generate_ai_response", provider)
    result = client.post("/api/governance/generate", json={"text": "Email test.person@example.com"}).json()
    assert result["input"]["decision"] == "REDACT"
    assert result["input"]["revalidated"]
    provider.assert_awaited_once_with("Email [REDACTED]")
    assert "test.person@example.com" not in json.dumps(client.get("/api/audit/executions").json())


# Unvalidated model output is withheld even after successful input inspection.
def test_output_blocking(client):
    activate(client)
    result = client.post("/api/governance/generate", json={"text": "[OUTPUT_SECRET]"}).json()
    assert result["model_invoked"] and result["output"]["decision"] == "BLOCK"
    assert result["safe_response"] is None


# Missing and disabled active policies cannot silently allow requests.
def test_missing_disabled_policy(client):
    assert client.post("/api/governance/generate", json={"text": "safe"}).status_code == 409
    policy_id, _ = activate(client)
    client.post(f"/api/policies/{policy_id}/disable")
    assert client.post("/api/governance/generate", json={"text": "safe"}).status_code == 409
    client.post(f"/api/policies/{policy_id}/enable")
    assert client.post("/api/governance/generate", json={"text": "safe"}).json()["decision"] == "ALLOW"


# Editing published documents creates a draft without mutating active versions.
def test_lifecycle_immutable_history(client):
    policy_id, document = activate(client)
    before = client.get(f"/api/policies/{policy_id}/versions").json()
    document["name"] = "New draft"
    assert client.put(f"/api/policies/{policy_id}", json=document).json()["status"] == "DRAFT"
    assert client.get(f"/api/policies/{policy_id}/versions").json() == before
    assert client.post(f"/api/policies/{policy_id}/publish").status_code == 409
    assert client.delete(f"/api/policies/{policy_id}").status_code == 409
    assert client.post(f"/api/policies/{policy_id}/archive").status_code == 409


# Never-published drafts can be edited and deleted with an audit trail.
def test_draft_crud(client):
    document = PolicyDocument(name="Draft").model_dump()
    policy_id = client.post("/api/policies", json=document).json()["id"]
    document["name"] = "Changed"
    assert client.put(f"/api/policies/{policy_id}", json=document).status_code == 200
    assert client.delete(f"/api/policies/{policy_id}").status_code == 200
    assert client.get(f"/api/policies/{policy_id}").status_code == 404
    assert len(client.get("/api/audit/events").json()) == 3


# Tenant identities cannot discover, change, or refer to another tenant's data.
def test_tenant_isolation(client):
    policy_id, _ = activate(client)
    client.headers["Authorization"] = "Bearer foreign"
    assert client.get("/api/policies").json() == []
    for method, suffix in [("get", ""), ("post", "/activate"), ("post", "/disable"), ("delete", "")]:
        assert getattr(client, method)(f"/api/policies/{policy_id}{suffix}").status_code == 404
    assert client.get("/api/audit/events").json() == []
    assert client.post("/api/governance/generate", json={"text": "safe"}).status_code == 409


# A frontend-selected or forged role has no authority.
def test_role_and_authentication(client):
    policy_id, document = activate(client)
    client.headers["Authorization"] = "Bearer developer"
    assert client.put(f"/api/policies/{policy_id}", json=document).status_code == 403
    assert client.post("/api/reports/export", json={}).status_code == 403
    assert client.get("/api/reviews").status_code == 403
    client.headers["Authorization"] = "Bearer fake-admin"
    assert client.get("/api/policies").status_code == 401


# Review approval never calls the provider or releases the held text.
def test_human_review_hold_and_disposition(client, monkeypatch):
    activate(client, {"blocked_keywords": "HUMAN_REVIEW"})
    provider = AsyncMock()
    monkeypatch.setattr("app.providers.generate_ai_response", provider)
    result = client.post("/api/governance/generate", json={"text": "internal-only"}).json()
    assert result["decision"] == "HUMAN_REVIEW" and result["safe_response"] is None
    review_id = result["review_id"]
    assert client.post(f"/api/reviews/{review_id}/approve").json()["status"] == "APPROVED_RESUBMIT_REQUIRED"
    assert client.post(f"/api/reviews/{review_id}/reject").status_code == 409
    assert client.post("/api/governance/generate", json={"text": "internal-only"}).json()["decision"] == "HUMAN_REVIEW"
    provider.assert_not_called()


# Required moderation fails closed, with an explicit unknown contribution.
@pytest.mark.parametrize("text,expected", [("[MODERATION_FLAG]", "FAILED"), ("[MODERATION_UNAVAILABLE]", "UNKNOWN")])
def test_moderation_controls(client, text, expected):
    activate(client)
    result = client.post("/api/governance/generate", json={"text": text}).json()
    assert result["decision"] == "BLOCK" and not result["model_invoked"]
    assert result["input"]["breakdown"]["moderation"] == expected


# Generation outages do not return a fabricated or unsafe response.
def test_generation_failure(client, monkeypatch):
    activate(client)
    monkeypatch.setattr("app.providers.generate_ai_response", AsyncMock(side_effect=ProviderUnavailable()))
    result = client.post("/api/governance/generate", json={"text": "safe"}).json()
    assert result["decision"] == "BLOCK" and result["safe_response"] is None


# Unknown controls do not contribute success to a score.
def test_score_independent_of_decision():
    statuses = {"secret_detection": "SATISFIED", "pii_detection": "FAILED", "moderation": "UNKNOWN", "blocked_keywords": "NOT_APPLICABLE"}
    score, contributions = calculate_compliance_score(statuses)
    assert score == 37.5 and contributions["moderation"] == 0


# Invalid schemas and potentially sensitive errors do not echo submitted values.
def test_policy_validation_and_body_limits(client):
    secret = "sensitive-value"
    response = client.post("/api/policies", json={"name": "Bad", "unknown": secret})
    assert response.status_code == 422 and secret not in response.text
    assert client.post("/api/governance/generate", json={"text": "a" * 65000}).status_code == 413
    document = PolicyDocument(name="Invalid").model_dump()
    document["rules"]["moderation"]["action"] = "REDACT"
    assert client.post("/api/policies", json=document).status_code == 422


# Unavailable export infrastructure is recorded as a failure, never fake success.
def test_export_feedback_analytics(client, monkeypatch):
    activate(client)
    execution = client.post("/api/governance/generate", json={"text": "safe"}).json()
    assert client.post("/api/feedback", json={"execution_id": execution["request_id"], "rating": 4}).status_code == 201
    assert client.get("/api/feedback/summary").json()["average"] == 4
    monkeypatch.setattr("app.providers.upload_report", lambda *args: (_ for _ in ()).throw(ProviderUnavailable()))
    assert client.post("/api/reports/export", json={"format": "csv"}).json()["status"] == "FAILED"
    assert client.get("/api/analytics/overview").json()["total_validations"] == 1
    client.headers["Authorization"] = "Bearer foreign"
    assert client.post("/api/feedback", json={"execution_id": execution["request_id"], "rating": 4}).status_code == 404


# If audit persistence fails, the gateway must not return approved content.
def test_database_failure_prevents_release(client, monkeypatch):
    activate(client)
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", lambda *args: (_ for _ in ()).throw(OperationalError("failed", {}, Exception())))
    response = client.post("/api/governance/generate", json={"text": "safe"})
    assert response.status_code == 503 and "local fixture" not in response.text


# PII detector exceptions are unknown and block the request.
@pytest.mark.asyncio
async def test_detector_failure(client, monkeypatch):
    monkeypatch.setattr(settings, "pii_mode", "presidio")
    monkeypatch.setattr("app.engine.get_pii_analyzer", lambda: (_ for _ in ()).throw(RuntimeError()))
    result = await inspect_text("safe", PolicyDocument(name="Test"))
    assert result["decision"] == "BLOCK" and result["breakdown"]["pii_detection"] == "UNKNOWN"


# Held sensitive text is never transmitted to the moderation provider before review.
def test_review_sensitive_content_not_sent_to_moderation(client, monkeypatch):
    activate(client, {"secret_detection": "HUMAN_REVIEW"})
    moderator = AsyncMock(return_value=[])
    monkeypatch.setattr("app.engine.moderate_user_prompt", moderator)
    result = client.post("/api/governance/generate", json={"text": "sk-test-" + "Z" * 30}).json()
    assert result["decision"] == "HUMAN_REVIEW"
    moderator.assert_not_called()


# Sanitized exports contain only the documented metadata allowlist.
def test_export_allowlist(client, monkeypatch):
    activate(client)
    client.post("/api/governance/generate", json={"text": "Email test.person@example.com"})
    captured = []
    monkeypatch.setattr("app.providers.upload_report", lambda path, content: captured.append(content))
    response = client.post("/api/reports/export", json={"format": "json"})
    assert response.json()["status"] == "SUCCEEDED"
    rows = json.loads(captured[0])
    assert set(rows[0]) == {"request_id", "timestamp", "decision", "policy_id", "version"}
    assert "test.person@example.com" not in captured[0]
