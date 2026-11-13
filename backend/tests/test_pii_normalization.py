"""Synthetic PII, source span mapping, policy selectors and unchanged safe text."""

import pytest
from app.config import settings
from app.engine import inspect_text
from app.schemas import PolicyDocument


@pytest.mark.parametrize(
    "value",
    [
        "Person@Example.COM",
        "person [at] example [dot] com",
        "person(at)example(dot)com",
        "per\u200bson@example.com",
        "ｐｅｒｓｏｎ＠ｅｘａｍｐｌｅ．ｃｏｍ",
        "person @ example . com",
        "+91 9876543210",
        "4111 1111 1111 1111",
        "123-45-6789",
    ],
)
@pytest.mark.asyncio
async def test_normalized_pii_redacts_original_spans(monkeypatch, value):
    monkeypatch.setattr(settings, "pii_mode", "regex")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    result = await inspect_text(f"Before {value} after", PolicyDocument(name="Synthetic"))
    assert result["decision"] == "REDACT" and result["revalidated"]
    assert result["safe_text"] == "Before [REDACTED] after"


@pytest.mark.parametrize(
    "value",
    [
        "Meet at noon",
        "See example.com for details",
        "Ordinary punctuation. Next sentence.",
        "Contact the support team",
        "[REDACTED]",
        "Café governance",
        "user [at] noon",
    ],
)
@pytest.mark.asyncio
async def test_normalization_preserves_safe_original_text(monkeypatch, value):
    monkeypatch.setattr(settings, "pii_mode", "regex")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    result = await inspect_text(value, PolicyDocument(name="Synthetic"))
    assert result["decision"] == "ALLOW" and result["safe_text"] == value


@pytest.mark.asyncio
async def test_selectable_entities_and_categories(monkeypatch):
    monkeypatch.setattr(settings, "pii_mode", "regex")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    policy = PolicyDocument(
        name="Selective",
        rules={"pii_detection": {"entities": ["EMAIL_ADDRESS"], "action": "REDACT"}, "moderation": {"categories": ["hate"]}},
    )
    assert (await inspect_text("[MODERATION_FLAG]", policy))["decision"] == "ALLOW"
    assert (await inspect_text("+91 9876543210", policy))["decision"] == "ALLOW"
    assert (await inspect_text("user@example.com", policy))["decision"] == "REDACT"
    policy.rules.moderation.categories = ["violence"]
    assert (await inspect_text("[MODERATION_FLAG]", policy))["decision"] == "BLOCK"


@pytest.mark.asyncio
async def test_credit_card_luhn_and_false_positive(monkeypatch):
    monkeypatch.setattr(settings, "pii_mode", "regex")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    policy = PolicyDocument(name="Cards", rules={"pii_detection": {"entities": ["CREDIT_CARD"], "action": "REDACT"}})
    assert (await inspect_text("4111-1111-1111-1111", policy))["decision"] == "REDACT"
    assert (await inspect_text("4111-1111-1111-1112", policy))["decision"] == "ALLOW"


@pytest.mark.asyncio
async def test_real_presidio_normalized_email_and_phone(monkeypatch):
    monkeypatch.setattr(settings, "pii_mode", "presidio")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    policy = PolicyDocument(
        name="Installed recognizers", rules={"pii_detection": {"entities": ["EMAIL_ADDRESS", "PHONE_NUMBER"], "action": "REDACT"}}
    )
    result = await inspect_text("Contact person [at] example [dot] com or +91 9876543210", policy)
    assert result["decision"] == "REDACT" and result["revalidated"]
    assert "example" not in result["safe_text"] and "9876543210" not in result["safe_text"]


@pytest.mark.asyncio
async def test_regex_rejects_unsupported_entity_selection(monkeypatch):
    monkeypatch.setattr(settings, "pii_mode", "regex")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    policy = PolicyDocument(name="Unsupported local entity", rules={"pii_detection": {"entities": ["PERSON"]}})
    result = await inspect_text("Synthetic ordinary text", policy)
    assert result["decision"] == "BLOCK" and result["breakdown"]["pii_detection"] == "UNKNOWN"


@pytest.mark.asyncio
@pytest.mark.parametrize("entity,label,value", [
    ("IN_AADHAAR", "Aadhaar", "2341 2341 2346"),
    ("IN_PAN", "PAN", "ABCPD1234F"),
    ("CREDIT_CARD", "Card", "4111 1111 1111 1111"),
    ("EMAIL_ADDRESS", "Email", "person@example.com"),
    ("PHONE_NUMBER", "Phone", "+91 9876543210"),
    ("US_SSN", "SSN", "123-45-6789"),
    ("IP_ADDRESS", "Server IP", "192.0.2.1"),
    ("IBAN_CODE", "IBAN", "GB82 WEST 1234 5698 7654 32"),
    ("PERSON", "Person", "John Smith"),
    ("IT_PASSPORT", "Passport", "AB1234567"),
])
async def test_supported_identifiers_enforce_block_and_redact(monkeypatch, entity, label, value):
    from app import engine
    async def inline(function, *args):
        return function(*args)
    monkeypatch.setattr(engine.asyncio, "to_thread", inline)
    monkeypatch.setattr(settings, "pii_mode", "presidio")
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    text = f"{label}: {value}"
    for action in ("BLOCK", "REDACT"):
        policy = PolicyDocument(name="Synthetic identifier", rules={"pii_detection": {"entities": [entity], "action": action}})
        result = await inspect_text(text, policy)
        assert result["decision"] == action
        if action == "BLOCK":
            assert result["safe_text"] is None
        else:
            assert value not in result["safe_text"]
