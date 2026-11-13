import pytest

from app.country_recognizers import valid
from app.engine import detect_sensitive_information, get_pii_analyzer, inspect_text, redact_personal_information
from app.schemas import PolicyDocument


CASES = [
    ("IN_PAN", "PAN", "ABCPD1234F", "ABCZD1234F"),
    ("AU_ABN", "ABN", "51 824 753 556", "51 824 753 557"),
    ("AU_ACN", "ACN", "004 085 616", "004 085 617"),
    ("AU_TFN", "TFN", "123 456 782", "123 456 783"),
    ("PL_PESEL", "PESEL", "44051401359", "44051401358"),
    ("IN_AADHAAR", "Aadhaar", "2341 2341 2346", "2341 2341 2347"),
    ("AU_MEDICARE", "Medicare", "2123 4567 01", "2123 4567 11"),
    ("KR_RRN", "RRN", "900101-1234568", "900101-1234569"),
    ("TH_TNIN", "TIN", "1234567890121", "1234567890122"),
    ("FI_PERSONAL_ID", "HETU", "010101-123N", "010101-123P"),
]


@pytest.mark.parametrize("entity,label,positive,negative", CASES)
def test_validated_identifier_detection(entity, label, positive, negative):
    analyzer = get_pii_analyzer()
    assert entity in analyzer.get_supported_entities(language="en")
    assert valid(entity, positive)
    assert not valid(entity, negative)
    assert any(item.entity_type == entity for item in analyzer.analyze(text=f"{label}: {positive}", language="en", entities=[entity]))
    assert not analyzer.analyze(text=f"{label}: {negative}", language="en", entities=[entity])
    assert not analyzer.analyze(text=f"Unrelated value {positive}", language="en", entities=[entity])


@pytest.mark.parametrize("entity,label,positive,_", CASES)
def test_country_identifier_policy_enforcement(monkeypatch, entity, label, positive, _):
    from app.config import settings

    monkeypatch.setattr(settings, "pii_mode", "presidio")
    policy = PolicyDocument(name="Synthetic PII", rules={"secret_detection": {"enabled": False}, "blocked_keywords": {"enabled": False}, "moderation": {"enabled": False}, "pii_detection": {"entities": [entity], "action": "REDACT"}})
    text = f"{label}: {positive}"
    spans = detect_sensitive_information(text, "pii_detection", policy)
    assert spans
    assert positive not in redact_personal_information(text, spans)
    assert detect_sensitive_information("contact test@example.com", "pii_detection", policy) == []


def test_existing_presidio_recognizers_remain_registered():
    assert {"EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "CRYPTO", "NRP"} <= set(get_pii_analyzer().get_supported_entities(language="en"))


@pytest.mark.parametrize("entity,text", [
    ("PERSON", "John Smith met the team yesterday."),
    ("LOCATION", "The office is in New York City."),
    ("DATE_TIME", "The meeting is on January 5, 2026."),
    ("IP_ADDRESS", "Server IP: 192.0.2.1"),
    ("URL", "Visit https://example.com for details."),
])
def test_core_english_entities_execute(entity, text):
    assert any(item.entity_type == entity for item in get_pii_analyzer().analyze(text=text, language="en", entities=[entity]))


@pytest.mark.parametrize("entity,label,value", [
    ("IT_DRIVER_LICENSE", "Driver license", "AB1234567C"),
    ("IT_FISCAL_CODE", "Fiscal code", "RSSMRA85M01H501Z"),
    ("IT_IDENTITY_CARD", "Identity card", "AB1234567"),
    ("IT_PASSPORT", "Passport", "AB1234567"),
    ("IN_VEHICLE_REGISTRATION", "Vehicle registration", "KA01AB1234"),
    ("SG_NRIC_FIN", "NRIC", "S1234567D"),
])
def test_new_country_entities_execute_only_with_context(entity, label, value):
    analyzer = get_pii_analyzer()
    assert analyzer.analyze(text=f"{label}: {value}", language="en", entities=[entity])
    assert not analyzer.analyze(text=f"Unrelated {value}", language="en", entities=[entity])


def test_capabilities_report_installed_presidio_recognizers(monkeypatch):
    from app.config import settings
    from app.routers.system import capabilities
    monkeypatch.setattr(settings, "pii_mode", "presidio")
    result = capabilities(user=None)
    assert result["pii_status"] == "AVAILABLE"
    assert set(result["pii_entities"]) == set(result["available_pii_entities"])
    monkeypatch.setattr(settings, "pii_mode", "regex")
    assert capabilities(user=None)["available_pii_entities"] == ["CREDIT_CARD", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]


@pytest.mark.parametrize("entity,label,positive,negative", [
    ("IT_VAT_CODE", "VAT", "12345678903", "12345678904"),
    ("ES_NIF", "NIF", "12345678Z", "12345678A"),
])
def test_native_checksum_recognizers_with_english_context(entity, label, positive, negative):
    analyzer = get_pii_analyzer()
    assert analyzer.analyze(text=f"{label}: {positive}", language="en", entities=[entity])
    assert not analyzer.analyze(text=f"{label}: {negative}", language="en", entities=[entity])
    assert not analyzer.analyze(text=f"Unrelated {positive}", language="en", entities=[entity])


@pytest.mark.asyncio
@pytest.mark.parametrize("entity,label,positive,negative", CASES)
async def test_country_identifier_block_redact_and_allow(monkeypatch, entity, label, positive, negative):
    from app.config import settings

    monkeypatch.setattr(settings, "pii_mode", "presidio")
    base_rules = {"secret_detection": {"enabled": False}, "blocked_keywords": {"enabled": False}, "moderation": {"enabled": False}}
    def policy(action):
        return PolicyDocument(name="Synthetic identifier decision", rules={**base_rules, "pii_detection": {"entities": [entity], "action": action}})

    blocked = await inspect_text(f"{label}: {positive}", policy("BLOCK"))
    assert blocked["decision"] == "BLOCK"
    assert blocked["findings"][0]["category"] == "pii_detection"
    redacted = await inspect_text(f"{label}: {positive}", policy("REDACT"))
    assert redacted["decision"] == "REDACT"
    assert redacted["revalidated"] is True
    assert positive not in redacted["safe_text"]
    allowed = await inspect_text(f"{label}: {negative}", policy("BLOCK"))
    assert allowed["decision"] == "ALLOW"
