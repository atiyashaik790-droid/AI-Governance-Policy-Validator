"""Synthetic contextual credentials must be withheld without blocking API-key discussion."""

from unittest.mock import AsyncMock

import pytest

from app.engine import detect_sensitive_information
from app.schemas import PolicyDocument

SYNTHETIC_KEY = "SyntheticKey9AbCdEfGhIjKlMnOpQrStUv"


@pytest.mark.parametrize(
    "text",
    [
        f'my api key is "{SYNTHETIC_KEY}"',
        f"here is my api key value '{SYNTHETIC_KEY}",
        f"API KEY VALUE IS: {SYNTHETIC_KEY}",
        f"api_key is {SYNTHETIC_KEY}",
        f"api-key value = {SYNTHETIC_KEY}",
        f"api key: {SYNTHETIC_KEY}",
    ],
)
def test_contextual_api_key_detected(text):
    assert detect_sensitive_information(text, "secret_detection", PolicyDocument(name="Secrets"))


@pytest.mark.parametrize(
    "text",
    [
        "How can I store an API key securely?",
        "My API key is stored in an environment variable.",
        "Explain how an API key value is generated.",
        "The API key is important for authentication.",
        "The API key value is a placeholder.",
    ],
)
def test_api_key_discussion_is_not_a_secret(text):
    assert not detect_sensitive_information(text, "secret_detection", PolicyDocument(name="Secrets"))


def test_keyword_separator_spaces_do_not_change_matching():
    policy = PolicyDocument(name="Keywords")
    policy.rules.blocked_keywords.values = ["api_key=", " api-key:", " authorization: bearer", " api key is "]
    assert detect_sensitive_information("api key is synthetic", "blocked_keywords", policy)


def test_contextual_secret_blocked_in_simulation_and_generation(client, monkeypatch):
    provider = AsyncMock()
    monkeypatch.setattr("app.providers.generate_ai_response", provider)
    policy = PolicyDocument(name="Contextual key protection")
    identifier = client.post("/api/policies", json=policy.model_dump()).json()["id"]
    text = f'Here is my api key value "{SYNTHETIC_KEY}"'
    simulation = client.post(f"/api/policies/{identifier}/simulate", json={"text": text})
    assert simulation.status_code == 200
    assert simulation.json()["decision"] == "BLOCK"
    for operation in ("submit", "approve", "publish", "activate"):
        assert client.post(f"/api/policies/{identifier}/{operation}").status_code == 200
    for operation in ("validate-input", "validate-output", "generate"):
        response = client.post(f"/api/governance/{operation}", json={"text": text})
        assert response.status_code == 200
        result = response.json()
        assert result["decision"] == "BLOCK"
        assert result["safe_response"] is None
        assert not result["model_invoked"]
    provider.assert_not_called()
    assert SYNTHETIC_KEY not in client.get("/api/audit/executions").text
