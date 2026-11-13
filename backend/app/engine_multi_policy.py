"""Captured-set evaluation, separate from the unchanged LEGACY inspector.

Only a fully inspected common text can be released. Findings contain counts and
categories, never matched text. Detector caches live for one evaluation only.
"""

import asyncio
import time
from hashlib import sha256
from typing import get_args

from . import engine, providers
from .config import settings
from .schemas import ModerationCategory, PolicyDocument

LOCAL_CONTROLS = ("secret_detection", "pii_detection", "blocked_keywords")
KNOWN_CATEGORIES = frozenset(get_args(ModerationCategory))


def strongest(decisions):
    return max(decisions, key=engine.PRIORITY.__getitem__, default="ALLOW")


async def moderation_evidence(text, required):
    """The existing adapter checks required coverage before returning flags.

    Always pass the full explicit selector, including all known categories for
    a default rule. A missing false category must never become an implicit pass.
    """
    flagged = await providers.moderate_user_prompt(text, required_categories=sorted(required))
    if (not isinstance(flagged, list) or any(type(c) is not str or c not in KNOWN_CATEGORIES for c in flagged)
            or len(set(flagged)) != len(flagged)):
        raise ValueError("Invalid moderation evidence")
    return {category: category in flagged for category in required}


def detector_key(text, category, document):
    # Actions do not affect detection; selectors and detector mode do. Different
    # selectors never share an unqualified negative result.
    if category.startswith("custom:"):
        rule = next(rule for rule in document.custom_categories if category == f"custom:{rule.id}")
        configuration = (rule.detection, tuple(rule.values))
    elif category == "pii_detection":
        entities = document.rules.pii_detection.entities
        configuration = (settings.pii_mode, None if entities is None else tuple(sorted(set(entities))))
    elif category == "blocked_keywords":
        configuration = tuple(sorted(set(document.rules.blocked_keywords.values)))
    else:
        configuration = tuple(engine.SECRET_PATTERNS)
    return text, category, configuration


def remaining(deadline):
    duration = min(settings.provider_timeout, deadline - time.monotonic())
    if duration <= 0:
        raise TimeoutError("Inspection deadline")
    return duration


async def local_inspection(text, document, cache, deadline):
    statuses, findings, decisions, redactions = {}, [], [], []
    for category, rule in engine.local_rules(document):
        if not rule.enabled:
            statuses[category] = "NOT_APPLICABLE"
            continue
        key = detector_key(text, category, document)
        if key not in cache:
            try:
                timeout = remaining(deadline)
                matches = await asyncio.wait_for(
                    asyncio.to_thread(engine.bounded_detection, text, category, document), timeout
                )
                if not isinstance(matches, list) or any(
                    not isinstance(span, (tuple, list)) or len(span) != 2
                    or any(type(position) is not int for position in span)
                    or not 0 <= span[0] < span[1] <= len(text) for span in matches
                ):
                    raise ValueError("Invalid detector evidence")
                cache[key] = tuple(sorted(set(tuple(span) for span in matches)))
            except Exception:
                cache[key] = None
        matches = cache[key]
        if matches is None:
            statuses[category] = "UNKNOWN"
            decisions.append("BLOCK")
            findings.append({"category": category, "status": "UNKNOWN"})
        else:
            statuses[category] = "FAILED" if matches else "SATISFIED"
            if matches:
                decisions.append(rule.action)
                findings.append({"category": category, "count": len(matches), "action": rule.action})
                if rule.action == "REDACT":
                    redactions.extend(matches)
    return {"decision": strongest(decisions), "breakdown": statuses, "findings": findings}, redactions


async def evaluate_policy_set(text, pins, *, deadline=None):
    """Inspect every exact published pin; no policy-count cutoff or global cache."""
    if not isinstance(text, str) or not text.strip() or not pins:
        raise ValueError("Nonempty text and captured policy set required")
    deadline = deadline if deadline is not None else time.monotonic() + settings.inference_deadline
    ordered = sorted(pins, key=lambda pin: (pin.policy_id, pin.version_id))
    if len({pin.policy_id for pin in ordered}) != len(ordered):
        raise ValueError("Duplicate policy snapshot")
    documents = []
    for pin in ordered:
        if sha256(pin.document_json.encode()).hexdigest() != pin.document_sha256:
            raise ValueError("Invalid published snapshot digest")
        documents.append(PolicyDocument.model_validate_json(pin.document_json))
    cache, policies, spans = {}, [], []
    for pin, document in zip(ordered, documents):
        local, redactions = await local_inspection(text, document, cache, deadline)
        spans.extend(redactions)
        policies.append({"policy_id": pin.policy_id, "version_id": pin.version_id, "version": pin.number,
                         "document_sha256": pin.document_sha256, "local": local, "reinspection": None,
                         "moderation": {"status": "NOT_APPLICABLE"}, "decision": local["decision"]})

    held = any(p["decision"] in {"BLOCK", "HUMAN_REVIEW"} for p in policies)
    sanitized = None if held else engine.redact_personal_information(text, spans)
    if spans and not held:
        # One common redaction pass, then EVERY policy inspects the same text.
        for result, document in zip(policies, documents):
            checked, _ = await local_inspection(sanitized, document, cache, deadline)
            result["reinspection"] = checked
            decision = "BLOCK" if checked["decision"] == "REDACT" else checked["decision"]
            result["decision"] = strongest([result["decision"], decision])
        held = any(p["decision"] in {"BLOCK", "HUMAN_REVIEW"} for p in policies)

    required = set().union(*(set(doc.rules.moderation.categories or KNOWN_CATEGORIES)
                             for doc in documents if doc.rules.moderation.enabled))
    coverage = None
    if required and not held:
        try:
            timeout = remaining(deadline)
            coverage = await asyncio.wait_for(moderation_evidence(sanitized, required), timeout)
            if not isinstance(coverage, dict) or any(
                type(k) is not str or k not in KNOWN_CATEGORIES or type(v) is not bool for k, v in coverage.items()
            ):
                raise ValueError("Invalid moderation coverage")
        except Exception:
            coverage = None
    for result, document in zip(policies, documents):
        rule = document.rules.moderation
        if rule.enabled:
            selected = set(rule.categories or KNOWN_CATEGORIES)
            if held:
                result["moderation"] = {"status": "WITHHELD_LOCAL_HOLD"}
            elif coverage is None or not selected <= coverage.keys():
                result["moderation"] = {"status": "UNKNOWN"}
                result["decision"] = "BLOCK"
            else:
                flagged = sorted(category for category in selected if coverage[category])
                result["moderation"] = {"status": "FAILED" if flagged else "SATISFIED", "categories": flagged,
                                        "checked_categories": sorted(selected)}
                if flagged:
                    result["decision"] = strongest([result["decision"], rule.action])
        local_complete = "UNKNOWN" not in result["local"]["breakdown"].values()
        reinspection = result["reinspection"]
        if spans:
            local_complete = local_complete and reinspection is not None and "UNKNOWN" not in reinspection["breakdown"].values()
        complete = local_complete and result["moderation"]["status"] not in {"UNKNOWN", "WITHHELD_LOCAL_HOLD"}
        result["inspection_status"] = "COMPLETE" if complete else "INCOMPLETE"
    decision = strongest(p["decision"] for p in policies)
    complete = all(p["inspection_status"] == "COMPLETE" for p in policies)
    if time.monotonic() >= deadline:
        complete = False
    if decision in {"ALLOW", "REDACT"} and not complete:
        decision = "BLOCK"
    return {"decision": decision, "inspection_status": "COMPLETE" if complete else "INCOMPLETE",
            "policy_count": len(policies), "policies": policies, "revalidated": bool(spans) and complete and decision == "REDACT",
            "safe_text": sanitized if complete and decision in {"ALLOW", "REDACT"} else None}
