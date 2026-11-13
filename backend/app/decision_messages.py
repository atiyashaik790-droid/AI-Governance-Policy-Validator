"""Deterministic, content-free messages. Never invoke a provider or interpolate data."""
from .schemas import PolicyDocument

REASONS = {
    "personal": "Personal information is protected by the active policies.",
    "secret": "Secrets and API keys are protected by the active policies.",
    "confidential": "Confidential company information is protected by the active policies.",
    "unsafe": "The active content-safety policies restrict this content.",
    "custom": "A custom policy category restricts this content.",
    "generic": "The active governance policies restrict this content.",
}
GUIDANCE = {
    "revise": "Remove protected details from your prompt or attachment, then submit again.",
    "public_example": "Use a public example or non-sensitive placeholders when you revise and resubmit.",
    "contact_admin": "Contact your policy administrator for guidance before revising and resubmitting.",
}
CATEGORIES = {"pii_detection": "personal", "secret_detection": "secret", "blocked_keywords": "confidential", "moderation": "unsafe"}
ORDER = {category: i for i, category in enumerate(["secret", "personal", "confidential", "unsafe", "custom", "generic"])}


def technical_notice(provider=False):
    return {"kind": "technical", "category": "provider" if provider else "incomplete", "title": "Generation unavailable" if provider else "Inspection could not complete",
            "message": "The AI provider could not complete this request. No response is released." if provider else
                "Required inspection could not complete. Content is withheld until all required checks can finish.",
            "next_action": "Check request history before retrying. If this continues, contact your administrator."}


def decision_notice(result, documents):
    """Only final-decision contributors select the reason and versioned guidance."""
    if result.get("generation_status") == "FAILED" or result.get("provider_error"):
        return technical_notice(provider=True)
    final = result["decision"]
    contributors, unknown = [], False
    default_document = next(iter(documents.values()), None)

    def findings(value, document):
        nonlocal unknown
        if not isinstance(value, dict):
            return
        for finding in value.get("findings", []):
            if finding.get("status") == "UNKNOWN":
                unknown = True
            if finding.get("action") == final and (finding.get("count", 0) or finding.get("categories")):
                name = finding.get("category", "")
                category = "custom" if name.startswith("custom:") else CATEGORIES.get(name, "generic")
                contributors.append((category, document))
        # LEGACY deliberately withholds moderation after a known local hold.
        for name, status in value.get("breakdown", {}).items():
            if status == "UNKNOWN" and not (name == "moderation" and final in {"BLOCK", "HUMAN_REVIEW"} and contributors):
                unknown = True

    for stage in (result.get("input"), result.get("output")):
        if not isinstance(stage, dict):
            continue
        if any(reason not in {"LOCAL_HOLD", "INSPECTION_INCOMPLETE"} for reason in stage.get("failure_reasons", [])):
            unknown = True
        if "policies" not in stage:
            findings(stage, default_document)
        else:
            for policy in stage["policies"]:
                document = documents.get(policy.get("policy_id"))
                if any(reason != "LOCAL_HOLD" for reason in policy.get("failure_reasons", [])):
                    unknown = True
                findings(policy.get("local"), document)
                findings(policy.get("reinspection"), document)
                moderation = policy.get("moderation", {})
                if moderation.get("status") == "UNKNOWN":
                    unknown = True
                if moderation.get("status") == "FAILED" and document and document.rules.moderation.action == final:
                    contributors.append(("unsafe", document))
        if stage.get("inspection_status") == "INCOMPLETE" and not contributors:
            unknown = True
    if result.get("failure_reasons") or unknown:
        notice = technical_notice()
        if final == "HUMAN_REVIEW":
            notice["message"] += " Human review is required. " + (
                "The AI model was invoked, but its response is withheld pending review." if result.get("model_invoked") else
                "This request has not been sent to the AI model.")
            notice["next_action"] += " Review is metadata-only; approval requires resubmission under current policies."
        return notice
    if final == "ALLOW":
        return {"kind": "success", "category": "generic", "title": "Request passed governance",
                "message": "The inspected content passed the required governance checks.",
                "next_action": "Review the response before using or sharing it."}
    category, document = min(contributors, key=lambda item: ORDER[item[0]]) if contributors else ("generic", None)
    guidance = document.decision_messages.get(final) if document else None
    next_action = GUIDANCE[guidance or ("public_example" if final == "REDACT" else "revise")]
    reason = REASONS[category]
    if final == "BLOCK":
        return {"kind": "policy", "category": category, "title": "Request cannot be processed" if not result.get("model_invoked") else "Response cannot be released",
                "message": reason + " " + ("The request cannot be processed in its current form." if not result.get("model_invoked") else "The generated response is withheld."),
                "next_action": next_action}
    if final == "HUMAN_REVIEW":
        sent = "The AI model was invoked, but its response is withheld pending review." if result.get("model_invoked") else "This request has not been sent to the AI model."
        return {"kind": "policy", "category": category, "title": "Human review required", "message": reason + " " + sent,
                "next_action": "Track the metadata-only review. Approval records a disposition; resubmit under current policies before content can be released. " + next_action}
    return {"kind": "policy", "category": category, "title": "Sensitive information removed",
            "message": reason + " Sensitive information was removed from the request or response. A normal AI response is shown only after output governance succeeds.",
            "next_action": next_action}


def captured_documents(pins):
    return {pin.policy_id: PolicyDocument.model_validate_json(pin.document_json) for pin in pins}
