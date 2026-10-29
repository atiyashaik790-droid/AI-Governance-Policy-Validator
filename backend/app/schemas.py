"""Strict, versioned policy documents and bounded request bodies."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Action = Literal["ALLOW", "REDACT", "HUMAN_REVIEW", "BLOCK"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Rule(StrictModel):
    enabled: bool = True
    action: Action = "BLOCK"


class KeywordRule(Rule):
    values: list[str] = Field(default_factory=lambda: ["internal-only"], max_length=100)

    # Reject ambiguous empty keywords and unsupported redaction semantics.
    @model_validator(mode="after")
    def validate_keywords(self):
        if any(not value.strip() or len(value) > 100 for value in self.values):
            raise ValueError("Keywords must contain 1–100 characters")
        return self


class Rules(StrictModel):
    secret_detection: Rule = Field(default_factory=Rule)
    pii_detection: Rule = Field(default_factory=lambda: Rule(action="REDACT"))
    moderation: Rule = Field(default_factory=Rule)
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


class TextRequest(StrictModel):
    text: str = Field(min_length=1, max_length=12000)


class FeedbackRequest(StrictModel):
    execution_id: str
    rating: int = Field(ge=1, le=5)


class ExportRequest(StrictModel):
    format: Literal["json", "csv"] = "json"


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
    provider_mode: Literal["live", "fixture"]
    policy_id: str
    policy_version: int
    duration_ms: float
    request_id: str
    review_id: str | None = None
    provider_error: str | None = None


class PolicyResponse(StrictModel):
    id: str
    tenant: str
    name: str
    draft: str
    status: str
    enabled: int
    revision: int
    row_version: int
