"""Deterministic enforcement; scores are explanatory, never release gates."""

import re
import asyncio
import threading
from functools import lru_cache
from .schemas import PolicyDocument
from .pii import normalized_view, supplemental_findings
from .config import settings
from .providers import moderate_user_prompt, ProviderUnavailable

DETECTOR_SLOTS = threading.BoundedSemaphore(4)


def bounded_detection(text, category, policy):
    if not DETECTOR_SLOTS.acquire(blocking=False):
        raise RuntimeError("Detector capacity unavailable")
    try:
        return detect_sensitive_information(text, category, policy)
    finally:
        DETECTOR_SLOTS.release()


WEIGHTS = {"secret_detection": 30, "pii_detection": 25, "moderation": 25, "blocked_keywords": 20}
PRIORITY = {"ALLOW": 0, "REDACT": 1, "HUMAN_REVIEW": 2, "BLOCK": 3}
SECRET_PATTERNS = [
    r"\bsk-[A-Za-z0-9_-]{20,}",
    r"(?i)\bBearer[ \t]+[A-Za-z0-9._~+/-]{16,}={0,2}",
    r"\bAKIA[A-Z0-9]{16}\b",
    r'(?i)\b(?:api[ _-]?key|password|client_secret)\s*[:=]\s*["\']?[^\s"\']{8,}',
    # Natural-language disclosure requires a long token with letters and digits,
    # so ordinary questions about API keys do not become secret findings.
    r'(?i)\bapi[ _-]?key\s+(?:is|value(?:\s+is)?)\s*[:=]?\s*["\']?'
    r"(?=[A-Za-z0-9_./+~-]*[A-Za-z])(?=[A-Za-z0-9_./+~-]*[0-9])[A-Za-z0-9_./+~-]{16,}",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
]
PII_PATTERNS = [r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", r"\b\d{3}-\d{2}-\d{4}\b", r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)"]


# Initialize Presidio with the installed NLP model and strictly offline email validation.
@lru_cache(maxsize=1)
def get_pii_analyzer():
    import importlib.util

    if importlib.util.find_spec("en_core_web_sm") is None:
        raise RuntimeError("Presidio model must be installed explicitly; runtime downloads are disabled")
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(
        nlp_configuration={"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}
    )
    engine = provider.create_engine()
    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=engine)
    from presidio_analyzer.predefined_recognizers import EmailRecognizer
    from tldextract import TLDExtract

    offline_domains = TLDExtract(suffix_list_urls=(), cache_dir=None)

    class OfflineEmailRecognizer(EmailRecognizer):
        # Validate email domains using bundled suffix data, with no runtime network calls.
        def validate_result(self, pattern_text: str) -> bool:
            return offline_domains(pattern_text).fqdn != ""

    registry.remove_recognizer("EmailRecognizer")
    registry.add_recognizer(OfflineEmailRecognizer(name="OfflineEmailRecognizer"))
    from .country_recognizers import register_country_recognizers

    register_country_recognizers(registry)
    return AnalyzerEngine(nlp_engine=engine, registry=registry, supported_languages=["en"])


# Find sensitive spans without returning the matched secret values.
def detect_sensitive_information(text: str, category: str, policy: PolicyDocument) -> list[tuple[int, int]]:
    if category.startswith("custom:"):
        from .custom_rules import detect
        rule = next(rule for rule in policy.custom_categories if category == f"custom:{rule.id}")
        return detect(text, rule)
    if category == "pii_detection":
        view, positions = normalized_view(text)
        entities = policy.rules.pii_detection.entities
        if (
            settings.pii_mode == "regex"
            and entities
            and any(entity not in ("EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN") for entity in entities)
        ):
            raise ValueError("Selected PII entity requires an installed Presidio recognizer")
        findings = supplemental_findings(view, entities)
        if settings.pii_mode == "presidio":
            analyzer = get_pii_analyzer()
            supported = analyzer.get_supported_entities(language="en")
            if entities and any(
                entity not in supported and entity not in ("EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN") for entity in entities
            ):
                raise ValueError("Selected PII entity is unavailable in installed recognizers")
            selected = [entity for entity in entities if entity in supported] if entities else None
            if selected is None or selected:
                findings.extend((finding.start, finding.end) for finding in analyzer.analyze(text=view, language="en", entities=selected))
        return sorted({(positions[start][0], positions[end - 1][1]) for start, end in findings if 0 <= start < end <= len(positions)})
    patterns = SECRET_PATTERNS if category == "secret_detection" else PII_PATTERNS
    if category == "blocked_keywords":
        patterns = [re.escape(value.strip()) for value in policy.rules.blocked_keywords.values]
    view, positions = normalized_view(text)
    return sorted(
        {
            (positions[match.start()][0], positions[match.end() - 1][1])
            for pattern in patterns
            for match in re.finditer(pattern, view, re.I)
            if match.end() > match.start()
        }
    )


# Replace overlapping sensitive spans once, leaving no original sensitive substring.
def redact_personal_information(text: str, spans: list[tuple[int, int]]) -> str:
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    for start, end in reversed(merged):
        text = text[:start] + "[REDACTED]" + text[end:]
    return text


# Score only satisfied controls; unknown and failed controls receive zero weight.
def calculate_compliance_score(statuses: dict[str, str]) -> tuple[float, dict]:
    weights = {**WEIGHTS, **{category: 20 for category in statuses if category.startswith("custom:")}}
    denominator = sum(weight for category, weight in weights.items() if statuses[category] != "NOT_APPLICABLE")
    contributions = {category: weight if statuses[category] == "SATISFIED" else 0 for category, weight in weights.items()}
    return (round(100 * sum(contributions.values()) / denominator, 2) if denominator else 0), contributions


def local_rules(policy):
    return [(name, getattr(policy.rules, name)) for name in ("secret_detection", "pii_detection", "blocked_keywords")] + [
        (f"custom:{rule.id}", rule) for rule in policy.custom_categories
    ]


# Inspect all controls, redact permitted spans, and revalidate before releasing text.
async def inspect_text(text: str, policy: PolicyDocument, revalidation: bool = False) -> dict:
    statuses, findings, actions, spans = {}, [], [], []
    sanitized = text
    for category, rule in local_rules(policy):
        if not rule.enabled:
            statuses[category] = "NOT_APPLICABLE"
            continue
        try:
            matches = await asyncio.to_thread(bounded_detection, text, category, policy)
            statuses[category] = "FAILED" if matches else "SATISFIED"
            if matches:
                findings.append({"category": category, "count": len(matches), "action": rule.action})
                actions.append(rule.action)
                if rule.action == "REDACT":
                    spans.extend(matches)
        except Exception:
            statuses[category] = "UNKNOWN"
            actions.append("BLOCK")
            findings.append({"category": category, "status": "UNKNOWN"})
    if spans:
        sanitized = redact_personal_information(text, spans)
    rule = policy.rules.moderation
    if rule.enabled:
        try:
            if any(action in ("BLOCK", "HUMAN_REVIEW") for action in actions):
                categories = None
            elif rule.categories:
                categories = await moderate_user_prompt(sanitized, required_categories=rule.categories)
            else:
                categories = await moderate_user_prompt(sanitized)
            if categories and rule.categories is not None:
                categories = [category for category in categories if category in rule.categories]
            statuses["moderation"] = "UNKNOWN" if categories is None else ("FAILED" if categories else "SATISFIED")
            if categories:
                actions.append(rule.action)
                findings.append({"category": "moderation", "categories": categories, "action": rule.action})
        except ProviderUnavailable:
            statuses["moderation"] = "UNKNOWN"
            actions.append("BLOCK")
            findings.append({"category": "moderation", "status": "UNKNOWN"})
    else:
        statuses["moderation"] = "NOT_APPLICABLE"
    decision = max(actions or ["ALLOW"], key=PRIORITY.get)
    score, contributions = calculate_compliance_score(statuses)
    result = {
        "decision": decision,
        "score": score,
        "breakdown": statuses,
        "contributions": contributions,
        "findings": findings,
        "revalidated": False,
        "safe_text": None,
    }
    if decision == "REDACT":
        if revalidation:
            result["decision"] = "BLOCK"
        else:
            checked = await inspect_text(sanitized, policy, True)
            result["revalidated"] = checked["decision"] == "ALLOW"
            if result["revalidated"]:
                result["safe_text"] = sanitized
            else:
                result["decision"] = checked["decision"] if checked["decision"] in ("BLOCK", "HUMAN_REVIEW") else "BLOCK"
    elif decision == "ALLOW":
        result["safe_text"] = sanitized
    return result
