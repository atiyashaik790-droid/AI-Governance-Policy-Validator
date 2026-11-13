"""Remaining review fixture contract and explicit integration evidence; mocks only."""
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from app import integration_verification as verification, providers
from app.config import settings





@pytest.fixture
def configured(client, monkeypatch):
    for name, value in {"provider_mode": "live", "integration_verification_enabled": True,
                        "azure_openai_endpoint": "https://synthetic.openai.azure.com", "azure_openai_deployment": "fixture",
                        "azure_openai_api_key": "synthetic-key-not-a-secret", "openai_api_key": "synthetic-moderation-key",
                        "adls_account_url": "https://synthetic.dfs.core.windows.net", "adls_file_system": "synthetic"}.items():
        monkeypatch.setattr(settings, name, value)
    mocks = [AsyncMock(return_value="OK"), AsyncMock(return_value=[]), Mock(), Mock(return_value=hashlib.sha256(b'{"verification":"synthetic"}').hexdigest())]
    for name, value in zip(["generate_ai_response", "moderate_user_prompt", "upload_report", "report_digest"], mocks):
        monkeypatch.setattr(providers, name, value)
    return client, mocks


def test_settings_presence_never_verifies_and_refresh_never_calls_providers(configured):
    client, mocks = configured
    for _ in range(2):
        value = client.get("/api/settings").json()
        assert value["database_status"] == "CONNECTED"
        assert all(r["status"] == "CONFIGURED_NOT_VERIFIED" and r["last_verification_at"] is None for r in value["integrations"].values())
        assert "synthetic-key" not in str(value)
    for mock in mocks:
        mock.assert_not_called()


@pytest.mark.parametrize("integration", ["azure_generation", "moderation", "adls"])
def test_verified_requires_explicit_success_and_is_tenant_scoped(configured, integration):
    client, mocks = configured
    result = client.post(f"/api/integrations/{integration}/verify", json={"confirm_billable_operation": True})
    assert result.status_code == 200 and result.json()["status"] == "VERIFIED"
    assert result.json()["last_verification_at"]
    value = client.get("/api/settings").json()
    assert value["integrations"][integration]["status"] == "VERIFIED"
    client.headers["Authorization"] = "Bearer foreign"
    assert client.get("/api/settings").json()["integrations"][integration]["status"] == "CONFIGURED_NOT_VERIFIED"
    assert sum(m.call_count for m in mocks) == (2 if integration == "adls" else 1)


def test_failure_is_sanitized_and_upload_without_readback_is_not_verified(configured):
    client, mocks = configured
    mocks[-1].side_effect = RuntimeError("secret token raw sensitive provider body")
    result = client.post("/api/integrations/adls/verify", json={"confirm_billable_operation": True})
    assert result.status_code == 200 and result.json()["status"] == "FAILED"
    assert result.json()["error_code"] == "VERIFICATION_FAILED"
    assert "secret" not in result.text and "token" not in result.text


def test_stale_changed_configuration_and_missing_configuration(configured, monkeypatch):
    client, _ = configured
    initial = datetime(2026, 11, 7, tzinfo=timezone.utc)
    monkeypatch.setattr(verification, "utc_now", lambda: initial)
    assert client.post("/api/integrations/azure_generation/verify", json={"confirm_billable_operation": True}).json()["status"] == "VERIFIED"
    monkeypatch.setattr(verification, "utc_now", lambda: initial + timedelta(hours=25))
    assert client.get("/api/settings").json()["azure_generation"] == "STALE"
    monkeypatch.setattr(settings, "azure_openai_api_key", "rotated-synthetic-key")
    assert client.get("/api/settings").json()["azure_generation"] == "CONFIGURED_NOT_VERIFIED"
    monkeypatch.setattr(settings, "azure_openai_deployment", "")
    assert client.get("/api/settings").json()["azure_generation"] == "NOT_CONFIGURED"


def test_default_gate_confirmation_role_and_rate_limit(configured, monkeypatch):
    client, mocks = configured
    monkeypatch.setattr(settings, "integration_verification_enabled", False)
    assert client.post("/api/integrations/moderation/verify", json={"confirm_billable_operation": True}).status_code == 403
    monkeypatch.setattr(settings, "integration_verification_enabled", True)
    assert client.post("/api/integrations/moderation/verify", json={}).status_code == 422
    assert client.post("/api/integrations/moderation/verify", json={"confirm_billable_operation": False}).status_code == 422
    client.headers["Authorization"] = "Bearer developer"
    assert client.post("/api/integrations/moderation/verify", json={"confirm_billable_operation": True}).status_code == 403
    for mock in mocks:
        mock.assert_not_called()
    client.headers["Authorization"] = "Bearer admin"
    assert client.post("/api/integrations/moderation/verify", json={"confirm_billable_operation": True}).status_code == 200
    assert client.post("/api/integrations/moderation/verify", json={"confirm_billable_operation": True}).status_code == 429
    assert mocks[1].call_count == 1
