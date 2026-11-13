"""HTTP contract tests are adapter tests, not claims of live cloud access."""

from unittest.mock import AsyncMock
import httpx
import pytest
from app.config import settings
from app.providers import moderate_user_prompt, generate_ai_response, ProviderUnavailable, upload_report
from app.engine import inspect_text
from app.schemas import PolicyDocument


# Replace only HTTP transport; exercise real request construction and parsing.
def mock_http(monkeypatch, payload, status=200):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = httpx.Response(status, json=payload, request=httpx.Request("POST", "https://example.com"))
    monkeypatch.setattr("app.providers.httpx.AsyncClient", lambda **kwargs: client)
    monkeypatch.setattr(settings, "provider_mode", "live")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    return client


# Normalize only the category names actually provided by the moderation API.
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flagged,categories,expected", [(False, {"violence": False}, []), (True, {"hate": False, "violence": True}, ["violence"])]
)
async def test_live_moderation_contract(monkeypatch, flagged, categories, expected):
    client = mock_http(monkeypatch, {"results": [{"flagged": flagged, "categories": categories}]})
    assert await moderate_user_prompt("safe synthetic text") == expected
    assert client.post.call_args.kwargs["json"]["model"] == "omni-moderation-latest"


# Errors, rate limits and malformed JSON structures cannot become successful inspection.
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,payload",
    [
        (401, {}),
        (429, {}),
        (500, {}),
        (200, {}),
        (200, {"results": [{"flagged": True, "categories": {}}]}),
        (200, {"results": [{"flagged": False, "categories": {"violence": "no"}}]}),
    ],
)
async def test_moderation_failure_contract(monkeypatch, status, payload):
    mock_http(monkeypatch, payload, status)
    with pytest.raises(ProviderUnavailable):
        await moderate_user_prompt("safe")


# Azure v1 request construction and response parsing are exercised without network access.
@pytest.mark.asyncio
async def test_azure_generation_contract(monkeypatch):
    client = mock_http(monkeypatch, {"choices": [{"finish_reason": "stop", "message": {"content": "Safe answer"}}]})
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "test-deployment")
    monkeypatch.setattr(settings, "azure_openai_api_key", "synthetic-key")
    monkeypatch.setattr(settings, "azure_openai_api_version", "v1")
    assert await generate_ai_response("approved") == "Safe answer"
    assert client.post.call_args.args[0].endswith("/openai/v1/chat/completions")
    assert client.post.call_args.kwargs["json"]["messages"][0]["content"] == "approved"


@pytest.mark.asyncio
async def test_live_generation_forwards_distinct_approved_prompts(monkeypatch):
    client = mock_http(monkeypatch, {"choices": [{"finish_reason": "stop", "message": {"content": "Mock answer"}}]})
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "test-deployment")
    monkeypatch.setattr(settings, "azure_openai_api_key", "synthetic-key")
    monkeypatch.setattr(settings, "azure_openai_api_version", "v1")
    assert await generate_ai_response("first approved prompt") == "Mock answer"
    assert await generate_ai_response("second approved prompt") == "Mock answer"
    sent = [call.kwargs["json"]["messages"][0]["content"] for call in client.post.call_args_list]
    assert sent == ["first approved prompt", "second approved prompt"]


# Invalid provider responses and transport errors always withhold the generated output.
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,status", [({}, 200), ({"choices": [{"finish_reason": "stop", "message": {"content": None}}]}, 200), ({}, 429), ({}, 401)]
)
async def test_azure_generation_failure(monkeypatch, payload, status):
    mock_http(monkeypatch, payload, status)
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "test")
    monkeypatch.setattr(settings, "azure_openai_api_key", "synthetic-key")
    with pytest.raises(ProviderUnavailable):
        await generate_ai_response("approved")


# Actual Presidio model inspection must detect an email and revalidate the redaction.
@pytest.mark.asyncio
async def test_presidio_real_detection(monkeypatch):
    monkeypatch.setattr(settings, "pii_mode", "presidio")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    result = await inspect_text("Please contact test.person@example.com.", PolicyDocument(name="Presidio"))
    assert result["decision"] == "REDACT"
    assert result["revalidated"] and "test.person@example.com" not in result["safe_text"]


# Export destinations are validated before any Azure credential is acquired.
def test_adls_rejects_unapproved_destination(monkeypatch):
    monkeypatch.setattr(settings, "adls_account_url", "https://attacker.example")
    with pytest.raises(ProviderUnavailable):
        upload_report("safe.json", "[]")


# A real transport timeout is normalized to an unavailable detector result.
@pytest.mark.asyncio
async def test_moderation_network_timeout(monkeypatch):
    client = mock_http(monkeypatch, {})
    client.post.side_effect = httpx.ReadTimeout("synthetic timeout")
    with pytest.raises(ProviderUnavailable):
        await moderate_user_prompt("safe")


# Successful ADLS upload uses the existing filesystem and forbids overwriting reports.
def test_adls_upload_contract(monkeypatch):
    from unittest.mock import MagicMock

    credential = MagicMock()
    service = MagicMock()
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: credential)
    monkeypatch.setattr("azure.storage.filedatalake.DataLakeServiceClient", lambda *args, **kwargs: service)
    monkeypatch.setattr(settings, "adls_account_url", "https://example.dfs.core.windows.net")
    monkeypatch.setattr(settings, "adls_file_system", "reports")
    upload_report("governance-reports/2026/10/28/test.json", "[]")
    filesystem = service.__enter__.return_value.get_file_system_client
    filesystem.assert_called_once_with("reports")
    file = filesystem.return_value.get_file_client
    file.assert_called_once_with("governance-reports/2026/10/28/test.json")
    from azure.core import MatchConditions

    file.return_value.upload_data.assert_called_once_with(b"[]", overwrite=True, match_condition=MatchConditions.IfMissing)


# Presidio email validation must not fetch public suffix data during inspection.
def test_presidio_email_validation_offline(monkeypatch):
    from app.engine import get_pii_analyzer

    monkeypatch.setattr(
        "tldextract.extract", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Default online extractor forbidden"))
    )
    get_pii_analyzer.cache_clear()
    analyzer = get_pii_analyzer()
    assert any(
        finding.entity_type == "EMAIL_ADDRESS" for finding in analyzer.analyze(text="Contact test.person@example.com", language="en")
    )
    names = {recognizer.name for recognizer in analyzer.registry.recognizers}
    assert "OfflineEmailRecognizer" in names and "EmailRecognizer" not in names
