"""Strict, versioned policy documents and bounded request bodies."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

Action = Literal["ALLOW", "REDACT", "HUMAN_REVIEW", "BLOCK"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Rule(StrictModel):
    enabled: bool = Field(default=True, strict=True)
    action: Action = "BLOCK"


class KeywordRule(Rule):
    values: list[str] = Field(default_factory=lambda: ["internal-only"], max_length=100)

    # Reject ambiguous empty keywords and unsupported redaction semantics.
    @model_validator(mode="after")
    def validate_keywords(self):
        if any(not value.strip() or len(value) > 100 for value in self.values):
            raise ValueError("Keywords must contain 1–100 characters")
        return self


PIIEntity = Literal[
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "PERSON",
    "LOCATION",
    "IP_ADDRESS",
    "URL",
    "DATE_TIME",
    "IBAN_CODE",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_PASSPORT",
    "US_ITIN",
    "UK_NHS",
    "MEDICAL_LICENSE",
    "CRYPTO",
    "NRP",
    "AU_ABN",
    "AU_ACN",
    "AU_TFN",
    "AU_MEDICARE",
    "IN_PAN",
    "IN_AADHAAR",
    "IN_VEHICLE_REGISTRATION",
    "SG_NRIC_FIN",
    "ES_NIF",
    "IT_FISCAL_CODE",
    "IT_DRIVER_LICENSE",
    "IT_VAT_CODE",
    "IT_PASSPORT",
    "IT_IDENTITY_CARD",
    "PL_PESEL",
    "FI_PERSONAL_ID",
    "KR_RRN",
    "TH_TNIN",
]
ModerationCategory = Literal[
    "harassment",
    "harassment/threatening",
    "hate",
    "hate/threatening",
    "illicit",
    "illicit/violent",
    "self-harm",
    "self-harm/intent",
    "self-harm/instructions",
    "sexual",
    "sexual/minors",
    "violence",
    "violence/graphic",
]


class PIIRule(Rule):
    # None preserves all installed recognizers for existing 1.0 policies.
    entities: list[PIIEntity] | None = Field(default=None, min_length=1, max_length=40)


class ModerationRule(Rule):
    categories: list[ModerationCategory] | None = Field(default=None, min_length=1, max_length=13)


class Rules(StrictModel):
    secret_detection: Rule = Field(default_factory=Rule)
    pii_detection: PIIRule = Field(default_factory=lambda: PIIRule(action="REDACT"))
    moderation: ModerationRule = Field(default_factory=ModerationRule)
    blocked_keywords: KeywordRule = Field(default_factory=KeywordRule)

    # ALLOW cannot be used as the action for a detected security violation.
    @model_validator(mode="after")
    def validate_actions(self):
        for name in type(self).model_fields:
            rule = getattr(self, name)
            if rule.action == "ALLOW" or (name == "moderation" and rule.action == "REDACT"):
                raise ValueError("Violation actions must enforce protection; moderation cannot redact")
        return self


class PolicyDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1, max_length=120, pattern=r"^[\w .-]+$")
    description: str = Field(default="", max_length=1000)
    rules: Rules = Field(default_factory=Rules)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError("Policy name must not be blank")
        return value


class TextRequest(StrictModel):
    source_review_id: str | None = Field(default=None, min_length=36, max_length=36)
    text: str = Field(strict=True, min_length=1, max_length=12000)

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value):
        if not value.strip():
            raise ValueError("Text must not be blank")
        return value


class FeedbackRequest(StrictModel):
    execution_id: str = Field(strict=True, min_length=1, max_length=36)
    rating: int = Field(strict=True, ge=1, le=5)


class ExportRequest(StrictModel):
    format: Literal["json", "csv"] = "json"
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class RollbackRequest(StrictModel):
    version: int = Field(strict=True, ge=1)


class ReviewUpdate(StrictModel):
    assigned_reviewer: str = Field(default="", max_length=100)
    reason: str = Field(default="", max_length=1000)


class ReviewResolution(StrictModel):
    reason: str = Field(default="", max_length=1000)


class InspectionResult(StrictModel):
    decision: Action
    score: float
    breakdown: dict[str, str]
    contributions: dict[str, int]
    findings: list[dict]
    revalidated: bool
    safe_text: str | None


class GovernanceResult(StrictModel):
    input: InspectionResult | None
    output: InspectionResult | None
    decision: Action
    safe_response: str | None
    model_invoked: bool
    generation_status: Literal["NOT_INVOKED", "SUCCEEDED", "FAILED"] = "NOT_INVOKED"
    provider_mode: Literal["live", "fixture"]
    policy_id: str
    policy_name: str = ""
    policy_version: int
    duration_ms: float
    request_id: str
    review_id: str | None = None
    source_review_id: str | None = None
    provider_error: str | None = None
    provider_diagnostics: dict[str, str | int] | None = None


class PolicyResponse(StrictModel):
    has_published_versions: bool = False
    is_active: bool = False
    id: str
    tenant: str
    name: str
    draft: str
    status: str
    enabled: int
    revision: int
    row_version: int
