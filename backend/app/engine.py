"""Deterministic enforcement; scores are explanatory, never release gates."""

import re
from functools import lru_cache
from .schemas import PolicyDocument
from .config import settings
from .providers import moderate_user_prompt, ProviderUnavailable

WEIGHTS = {"secret_detection": 30, "pii_detection": 25, "moderation": 25, "blocked_keywords": 20}
PRIORITY = {"ALLOW": 0, "REDACT": 1, "HUMAN_REVIEW": 2, "BLOCK": 3}
SECRET_PATTERNS = [
    r"\bsk-[A-Za-z0-9_-]{20,}",
    r"\bAKIA[A-Z0-9]{16}\b",
    r'(?i)\b(?:api[_-]?key|password|client_secret)\s*[:=]\s*["\']?[^\s"\']{8,}',
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
    return AnalyzerEngine(nlp_engine=engine, registry=registry, supported_languages=["en"])


# Find sensitive spans without returning the matched secret values.
def detect_sensitive_information(text: str, category: str, policy: PolicyDocument) -> list[tuple[int, int]]:
    if category == "pii_detection" and settings.pii_mode == "presidio":
        return [(finding.start, finding.end) for finding in get_pii_analyzer().analyze(text=text, language="en")]
    patterns = SECRET_PATTERNS if category == "secret_detection" else PII_PATTERNS
    if category == "blocked_keywords":
        patterns = [re.escape(value) for value in policy.rules.blocked_keywords.values]
    return [(match.start(), match.end()) for pattern in patterns for match in re.finditer(pattern, text, re.I)]


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
    denominator = sum(weight for category, weight in WEIGHTS.items() if statuses[category] != "NOT_APPLICABLE")
    contributions = {category: weight if statuses[category] == "SATISFIED" else 0 for category, weight in WEIGHTS.items()}
    return (round(100 * sum(contributions.values()) / denominator, 2) if denominator else 0), contributions


# Inspect all controls, redact permitted spans, and revalidate before releasing text.
async def inspect_text(text: str, policy: PolicyDocument, revalidation: bool = False) -> dict:
    statuses, findings, actions, spans = {}, [], [], []
    sanitized = text
    for category in ("secret_detection", "pii_detection", "blocked_keywords"):
        rule = getattr(policy.rules, category)
        if not rule.enabled:
            statuses[category] = "NOT_APPLICABLE"
            continue
        try:
            matches = detect_sensitive_information(text, category, policy)
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
            categories = (
                await moderate_user_prompt(sanitized) if not any(action in ("BLOCK", "HUMAN_REVIEW") for action in actions) else None
            )
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
