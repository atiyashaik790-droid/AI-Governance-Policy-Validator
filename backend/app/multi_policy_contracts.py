"""Phase D contracts only: no detectors, moderation, generation or release code."""

from dataclasses import dataclass
from typing import get_args
from .schemas import ModerationCategory, PolicyDocument

STAGES = (
    "LOCAL_INSPECTION_ALL_POLICIES", "GLOBAL_HOLD_GATE", "COMMON_REDACTION",
    "ALL_POLICY_REVALIDATION", "MODERATION_COVERAGE_GATE",
)
DECISION_PRECEDENCE = ("ALLOW", "REDACT", "HUMAN_REVIEW", "BLOCK")
MAX_REDACTION_PASSES_PER_STAGE = 1
MAX_GENERATION_DISPATCHES_PER_HTTP_REQUEST = 1


@dataclass(frozen=True)
class InspectionContract:
    policy_count: int
    moderation_categories: frozenset[str]
    stages: tuple[str, ...] = STAGES
    unknown_required_control_withholds: bool = True
    held_text_must_not_leave_process: bool = True


def inspection_contract(documents: tuple[PolicyDocument, ...]) -> InspectionContract:
    """None selectors require the complete known category set, never zero."""
    categories = set()
    for document in documents:
        rule = document.rules.moderation
        if rule.enabled:
            categories.update(rule.categories if rule.categories is not None else get_args(ModerationCategory))
    return InspectionContract(len(documents), frozenset(categories))
