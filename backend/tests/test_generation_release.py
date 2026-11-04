"""Synthetic provider diagnostics and input/output release gates; no live cloud calls."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app import providers
from app.config import settings
from app.schemas import PolicyDocument

REQUEST_ID = "11111111-2222-4333-8444-555555555555"


def http_fixture(monkeypatch, payload, status=200):
    http = AsyncMock()
    http.__aenter__.return_value = http
    http.post.return_value = httpx.Response(
        status, json=payload, headers={"apim-request-id": REQUEST_ID}, request=httpx.Request("POST", "https://synthetic.openai.azure.com")
    )
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **_: http)
    for key, value in {
        "provider_mode": "live",
        "azure_openai_endpoint": "https://synthetic.openai.azure.com",
        "azure_openai_deployment": "gpt-5-mini",
        "azure_openai_api_key": "synthetic-private-key",
        "azure_openai_api_version": "v1",
    }.items():
        monkeypatch.setattr(settings, key, value)
    return http


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (400, "INVALID_REQUEST"),
        (401, "AUTHENTICATION_FAILED"),
        (403, "PERMISSION_DENIED"),
        (404, "DEPLOYMENT_NOT_FOUND"),
        (429, "RATE_LIMITED"),
        (503, "PROVIDER_ERROR"),
    ],
)
async def test_provider_status_is_safe_and_actionable(monkeypatch, status, code):
    http = http_fixture(monkeypatch, {"error": {"message": "synthetic-private-prompt-and-key"}}, status)
    with pytest.raises(providers.ProviderUnavailable) as captured:
        await providers.generate_ai_response("synthetic-private-input")
    assert captured.value.diagnostics == {"code": "GENERATION_" + code, "http_status": status, "request_id": REQUEST_ID}
    assert "private" not in str(captured.value) + json.dumps(captured.value.diagnostics)
    assert http.post.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,code",
    [
        (httpx.ReadTimeout("private"), "READ_TIMEOUT"),
        (httpx.ConnectTimeout("private"), "CONNECT_TIMEOUT"),
        (httpx.ConnectError("private"), "TRANSPORT_ERROR"),
    ],
)
async def test_transport_failures_are_distinguished(monkeypatch, error, code):
    http = http_fixture(monkeypatch, {})
    http.post.side_effect = error
    with pytest.raises(providers.ProviderUnavailable) as captured:
        await providers.generate_ai_response("safe synthetic text")
    assert captured.value.diagnostics == {"code": "GENERATION_" + code}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "finish,code", [("length", "TOKEN_LIMIT"), ("content_filter", "CONTENT_FILTERED"), ("tool_calls", "INCOMPLETE"), (None, "INCOMPLETE")]
)
async def test_incomplete_generated_content_cannot_be_released(monkeypatch, finish, code):
    http_fixture(monkeypatch, {"choices": [{"finish_reason": finish, "message": {"content": "Partial synthetic answer"}}]})
    with pytest.raises(providers.ProviderUnavailable) as captured:
        await providers.generate_ai_response("safe synthetic text")
    assert captured.value.diagnostics["code"] == "GENERATION_" + code


@pytest.mark.asyncio
async def test_original_gpt5_budget_is_bounded_and_minimal(monkeypatch):
    http = http_fixture(monkeypatch, {"choices": [{"finish_reason": "stop", "message": {"content": "Complete inspected candidate"}}]})
    assert await providers.generate_ai_response("Safe synthetic input") == "Complete inspected candidate"
    payload = http.post.call_args.kwargs["json"]
    assert payload["reasoning_effort"] == "minimal" and payload["max_completion_tokens"] == 700
    assert "temperature" not in payload and "max_tokens" not in payload
    monkeypatch.setattr(settings, "azure_openai_deployment", "custom-deployment")
    await providers.generate_ai_response("Safe synthetic input")
    assert "reasoning_effort" not in http.post.call_args.kwargs["json"]


@pytest.mark.asyncio
async def test_empty_content_is_not_success_and_headers_are_untrusted(monkeypatch):
    http = http_fixture(monkeypatch, {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]})
    http.post.return_value.headers["apim-request-id"] = "synthetic-private-token"
    with pytest.raises(providers.ProviderUnavailable) as captured:
        await providers.generate_ai_response("safe synthetic text")
    assert captured.value.diagnostics == {"code": "GENERATION_INVALID_RESPONSE", "http_status": 200}


def publish(client, action="REDACT"):
    document = PolicyDocument(name="Synthetic enterprise protection").model_dump()
    document["rules"]["pii_detection"]["action"] = action
    document["rules"]["blocked_keywords"]["values"] = ["confidential project", "internal-only", "customer database", "company secret"]
    response = client.post("/api/policies", json=document)
    assert response.status_code == 201
    identifier = response.json()["id"]
    for operation in ("submit", "approve", "publish", "activate"):
        assert client.post(f"/api/policies/{identifier}/{operation}").status_code == 200
    return identifier


@pytest.mark.parametrize(
    "text,expected",
    [("Explain three advantages of FastAPI.", "ALLOW"), ("Write to priya@example.com.", "REDACT"), ("Call +91 9876543210.", "REDACT")],
)
def test_real_presidio_sanitizes_before_mock_generation(client, monkeypatch, text, expected):
    monkeypatch.setattr(settings, "pii_mode", "presidio")
    publish(client)
    generation = AsyncMock(return_value="Here are the requested professional recommendations.")
    monkeypatch.setattr(providers, "generate_ai_response", generation)
    result = client.post("/api/governance/generate", json={"text": text}).json()
    assert result["decision"] == expected and result["generation_status"] == "SUCCEEDED"
    assert result["output"]["decision"] == "ALLOW" and result["safe_response"]
    assert result["policy_name"] == "Synthetic enterprise protection"
    if expected == "REDACT":
        assert result["input"]["revalidated"] and result["input"]["breakdown"]["pii_detection"] == "FAILED"
        sent = generation.call_args.args[0]
        assert "priya@example.com" not in sent and "9876543210" not in sent and "[REDACTED]" in sent
        assert text not in client.get("/api/audit/executions").text


@pytest.mark.parametrize("action", ["REDACT", "BLOCK", "HUMAN_REVIEW"])
def test_generated_pii_is_inspected_before_release(client, monkeypatch, action):
    publish(client, action)
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(return_value="Contact synthetic.person@example.com for details."))
    result = client.post("/api/governance/generate", json={"text": "Give me safe guidance."}).json()
    assert result["output"]["decision"] == action and result["decision"] == action
    assert result["generation_status"] == "SUCCEEDED"
    if action == "REDACT":
        assert result["output"]["revalidated"] and "synthetic.person@example.com" not in result["safe_response"]
    else:
        assert result["safe_response"] is None
    if action == "HUMAN_REVIEW":
        assert client.post(f"/api/reviews/{result['review_id']}/approve").json()["status"] == "APPROVED_RESUBMIT_REQUIRED"
    assert "synthetic.person@example.com" not in client.get("/api/audit/executions").text


@pytest.mark.parametrize(
    "text",
    ["confidential project", "internal-only", "customer database", "company secret", "api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345"],
)
def test_prohibited_inputs_never_dispatch(client, monkeypatch, text):
    publish(client)
    generation = AsyncMock()
    monkeypatch.setattr(providers, "generate_ai_response", generation)
    result = client.post("/api/governance/generate", json={"text": text}).json()
    assert result["decision"] == "BLOCK" and result["generation_status"] == "NOT_INVOKED"
    assert result["safe_response"] is None and result["output"] is None
    generation.assert_not_called()


def test_failed_generation_persists_safe_failure_category(client, monkeypatch):
    publish(client)
    error = providers.ProviderUnavailable("private upstream message", code="GENERATION_READ_TIMEOUT")
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(side_effect=error))
    response = client.post("/api/governance/generate", json={"text": "Safe synthetic prompt"})
    result = response.json()
    assert response.status_code == 200 and result["decision"] == "BLOCK" and result["generation_status"] == "FAILED"
    assert result["output"] is None and result["safe_response"] is None
    assert result["provider_diagnostics"]["code"] == "GENERATION_READ_TIMEOUT" and "private" not in response.text
    assert "GENERATION_READ_TIMEOUT" in client.get("/api/audit/executions").text


@pytest.mark.parametrize("field", ["email_detection", "phone_detection", "moderation_categories", "natural_language_policy"])
def test_unsupported_policy_fields_rejected(client, field):
    document = PolicyDocument(name="Unsupported field").model_dump()
    document["rules"][field] = {"enabled": True, "action": "BLOCK"}
    response = client.post("/api/policies", json=document)
    assert response.status_code == 422 and any(item["type"] == "extra_forbidden" for item in response.json()["detail"])


def test_active_snapshot_is_used_after_unpublished_draft_edit(client, monkeypatch):
    identifier = publish(client)
    edited = PolicyDocument(name="Unpublished replacement").model_dump()
    edited["rules"]["blocked_keywords"]["values"] = ["different-draft-keyword"]
    assert (
        client.put(
            f"/api/policies/{identifier}",
            json=edited,
            headers={"If-Match": str(client.get(f"/api/policies/{identifier}").json()["row_version"])},
        ).status_code
        == 200
    )
    provider = AsyncMock()
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    result = client.post("/api/governance/generate", json={"text": "confidential project"}).json()
    assert result["decision"] == "BLOCK"
    assert result["policy_name"] == "Synthetic enterprise protection" and result["policy_version"] == 1
    provider.assert_not_called()


def test_output_redaction_reinspection_failure_withholds_content(client, monkeypatch):
    from app import engine

    publish(client)
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(return_value="Contact synthetic.person@example.com."))
    original = engine.detect_sensitive_information

    def detect(text, category, policy):
        if "[REDACTED]" in text and category == "pii_detection":
            raise RuntimeError("synthetic-private-detector-error")
        return original(text, category, policy)

    monkeypatch.setattr(engine, "detect_sensitive_information", detect)
    result = client.post("/api/governance/generate", json={"text": "Safe guidance please."}).json()
    assert result["decision"] == "BLOCK" and result["output"]["decision"] == "BLOCK"
    assert not result["output"]["revalidated"] and result["safe_response"] is None


def test_output_moderation_failure_withholds_generated_content(client, monkeypatch):
    from app import engine

    publish(client)
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(return_value="Synthetic generated candidate"))

    async def moderate(text):
        if text == "Synthetic generated candidate":
            raise providers.ProviderUnavailable("synthetic moderation outage")
        return []

    monkeypatch.setattr(engine, "moderate_user_prompt", moderate)
    result = client.post("/api/governance/generate", json={"text": "Safe synthetic input"}).json()
    assert result["generation_status"] == "SUCCEEDED" and result["output"]["breakdown"]["moderation"] == "UNKNOWN"
    assert result["decision"] == "BLOCK" and result["safe_response"] is None
