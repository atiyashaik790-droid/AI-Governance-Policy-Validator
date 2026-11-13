"""Allowlisted metadata and complete captured-set accounting for MULTI requests."""

import re

from ..engine import local_rules
from ..engine_multi_policy import LOCAL_CONTROLS, KNOWN_CATEGORIES, strongest
from ..schemas import PolicyDocument, AttachmentMetadata

DECISIONS = {"ALLOW", "REDACT", "HUMAN_REVIEW", "BLOCK"}
STATUSES = {"SATISFIED", "FAILED", "UNKNOWN", "NOT_APPLICABLE", "WITHHELD_LOCAL_HOLD"}
REASONS = {"EVIDENCE_MISSING", "EVIDENCE_INVALID", "PIN_MISMATCH", "CARDINALITY_MISMATCH", "DETECTOR_UNAVAILABLE",
           "MODERATION_INCOMPLETE", "LOCAL_HOLD", "INSPECTION_INCOMPLETE", "NOT_REQUIRED", "INPUT_HELD", "GENERATION_FAILED",
           "REQUEST_TIMEOUT", "REQUEST_FENCED", "INSPECTION_FAILED"}


def choice(value, allowed, default=None):
    return value if isinstance(value, str) and value in allowed else default


def reasons(values):
    return sorted({v for v in values if isinstance(v, str) and v in REASONS}) if isinstance(values, list) else []


def control_category(value):
    return isinstance(value, str) and (value in (*LOCAL_CONTROLS, "moderation") or
                                      re.fullmatch(r"custom:[a-zA-Z0-9_-]{1,64}", value) is not None)


def local_metadata(value):
    value = value if isinstance(value, dict) else {}
    breakdown = value.get("breakdown", {})
    breakdown = breakdown if isinstance(breakdown, dict) else {}
    findings = []
    for finding in value.get("findings", []) if isinstance(value.get("findings"), list) else []:
        if not isinstance(finding, dict) or not control_category(finding.get("category")):
            continue
        item = {"category": finding["category"]}
        if type(finding.get("count")) is int and finding["count"] >= 0:
            item["count"] = finding["count"]
        if choice(finding.get("action"), DECISIONS):
            item["action"] = finding["action"]
        if choice(finding.get("status"), STATUSES):
            item["status"] = finding["status"]
        if isinstance(finding.get("categories"), list):
            item["categories"] = sorted({c for c in finding["categories"] if isinstance(c, str) and c in KNOWN_CATEGORIES})
        findings.append(item)
    return {"decision": choice(value.get("decision"), DECISIONS, "BLOCK"),
            "breakdown": {c: breakdown[c] for c in breakdown if control_category(c) and choice(breakdown.get(c), STATUSES)},
            "findings": findings}


def policy_metadata(value):
    """Also used when reading historical Phase D evidence; unknown fields never escape."""
    value = value if isinstance(value, dict) else {}
    moderation = value.get("moderation", {})
    moderation = moderation if isinstance(moderation, dict) else {}
    return {"decision": choice(value.get("decision"), DECISIONS, "BLOCK"),
            "inspection_status": choice(value.get("inspection_status"), {"COMPLETE", "INCOMPLETE", "NOT_RUN"}, "INCOMPLETE"),
            "local": local_metadata(value.get("local")),
            "reinspection": local_metadata(value["reinspection"]) if isinstance(value.get("reinspection"), dict) else None,
            "moderation": {"status": choice(moderation.get("status"), STATUSES, "UNKNOWN"),
                           **{key: sorted({c for c in moderation[key] if isinstance(c, str) and c in KNOWN_CATEGORIES})
                              for key in ("categories", "checked_categories") if isinstance(moderation.get(key), list)}},
            "failure_reasons": reasons(value.get("failure_reasons"))}


def skipped(reason):
    return {"decision": "BLOCK", "inspection_status": "NOT_RUN", "failure_reasons": [reason]}


def validate_stage(stage, pins):
    """Reconcile every captured pin, retaining explicit missing/incomplete entries.

    Safe text survives only when all captured identities and enabled controls have
    complete evidence. No arbitrary provider fields are carried into persistence.
    """
    stage = stage if isinstance(stage, dict) else {}
    values = stage.get("policies", [])
    values = values if isinstance(values, list) else []
    by_id, duplicates = {}, set()
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("policy_id"), str):
            if value["policy_id"] in by_id:
                duplicates.add(value["policy_id"])
            by_id[value["policy_id"]] = value
    failure = reasons(stage.get("failure_reasons"))
    if len(values) != len(pins) or set(by_id) != {p.policy_id for p in pins} or duplicates:
        failure.append("CARDINALITY_MISMATCH")
    policies = []
    redacted = any(isinstance(v, dict) and isinstance(v.get("local"), dict) and v["local"].get("decision") == "REDACT" for v in values)
    for pin in sorted(pins, key=lambda p: p.policy_id):
        raw = by_id.get(pin.policy_id)
        item = policy_metadata(raw)
        item.update(policy_id=pin.policy_id, version_id=pin.version_id, version=pin.number, document_sha256=pin.document_sha256)
        errors = list(item["failure_reasons"])
        if raw is None:
            errors.append("EVIDENCE_MISSING")
        elif pin.policy_id in duplicates:
            errors.append("EVIDENCE_INVALID")
        elif any(raw.get(key) != expected for key, expected in {"version_id": pin.version_id, "version": pin.number, "document_sha256": pin.document_sha256}.items()):
            errors.append("PIN_MISMATCH")
        document = PolicyDocument.model_validate_json(pin.document_json)
        needs_reinspection = redacted and stage.get("decision") in {"ALLOW", "REDACT"}
        for local in [item["local"]] + ([item["reinspection"]] if needs_reinspection or item["reinspection"] is not None else []):
            if local is None:
                errors.append("EVIDENCE_MISSING")
                continue
            for category, rule in local_rules(document):
                status = local["breakdown"].get(category)
                enabled = rule.enabled
                if enabled and status not in {"SATISFIED", "FAILED"}:
                    errors.append("DETECTOR_UNAVAILABLE")
                if not enabled and status != "NOT_APPLICABLE":
                    errors.append("EVIDENCE_INVALID")
        mod_status = item["moderation"]["status"]
        if document.rules.moderation.enabled:
            selected = set(document.rules.moderation.categories or KNOWN_CATEGORIES)
            if mod_status == "WITHHELD_LOCAL_HOLD":
                errors.append("LOCAL_HOLD")
            elif mod_status not in {"SATISFIED", "FAILED"} or not selected <= set(item["moderation"].get("checked_categories", [])):
                errors.append("MODERATION_INCOMPLETE")
        elif mod_status != "NOT_APPLICABLE":
            errors.append("EVIDENCE_INVALID")
        item["failure_reasons"] = sorted(set(errors))
        if errors:
            item["inspection_status"] = "INCOMPLETE"
            if any(e != "LOCAL_HOLD" for e in errors) and item["decision"] in {"ALLOW", "REDACT"}:
                item["decision"] = "BLOCK"
        policies.append(item)
    decision = strongest([p["decision"] for p in policies] + [choice(stage.get("decision"), DECISIONS, "BLOCK")])
    complete = not failure and stage.get("inspection_status") == "COMPLETE" and all(p["inspection_status"] == "COMPLETE" for p in policies)
    if not complete:
        failure.append("INSPECTION_INCOMPLETE")
        if decision in {"ALLOW", "REDACT"}:
            decision = "BLOCK"
    safe = stage.get("safe_text")
    return {"decision": decision, "inspection_status": "COMPLETE" if complete else "INCOMPLETE", "policy_count": len(pins),
            "policies": policies, "failure_reasons": sorted(set(failure)), "revalidated": stage.get("revalidated") is True and complete,
            "safe_text": safe if isinstance(safe, str) and safe.strip() and complete and decision in {"ALLOW", "REDACT"} else None}


def prepare(admission, operation, result):
    stages = {name: validate_stage(result[name], admission.pins) for name in ("input", "output") if isinstance(result.get(name), dict)}
    failures = reasons(result.get("failure_reasons"))
    metadata = {"schema_version": "2.0", "operation": operation, "execution_mode": "MULTI", "set_revision": admission.set_revision,
                "captured_policy_count": len(admission.pins), "decision": result["decision"], "failure_reasons": failures,
                "model_invoked": result.get("model_invoked") is True,
                "generation_status": result.get("generation_status") if result.get("generation_status") in {"NOT_INVOKED", "SUCCEEDED", "FAILED"} else "FAILED"}
    if result.get("attachment") is not None:
        metadata["attachment"] = AttachmentMetadata.model_validate(result["attachment"]).model_dump()
    if isinstance(result.get("source_review_id"), str):
        metadata["source_review_id"] = result["source_review_id"]
    for name, stage in stages.items():
        metadata[name] = {k: v for k, v in stage.items() if k != "safe_text"}
    entries = []
    for pin in admission.pins:
        evidence = {"schema_version": "2.0", "failure_reasons": list(failures)}
        actual = []
        required_complete = not failures and not (operation == "generate" and result.get("generation_status") == "FAILED")
        for name in ("input", "output"):
            required = name == ("output" if operation == "validate-output" else "input") or operation == "generate" and result.get("generation_status") == "SUCCEEDED"
            if name in stages:
                policy = next(p for p in stages[name]["policies"] if p["policy_id"] == pin.policy_id)
                evidence[name] = policy
                actual.append(policy["decision"])
                required_complete = required_complete and policy["inspection_status"] == "COMPLETE"
                evidence["failure_reasons"].extend(policy["failure_reasons"])
            else:
                reason = failures[0] if failures else "EVIDENCE_MISSING" if required else "GENERATION_FAILED" if operation == "generate" and result.get("generation_status") == "FAILED" else "INPUT_HELD" if operation == "generate" else "NOT_REQUIRED"
                evidence[name] = skipped(reason)
                if required:
                    required_complete = False
                if reason != "NOT_REQUIRED":
                    evidence["failure_reasons"].append(reason)
        evidence["failure_reasons"] = sorted(set(evidence["failure_reasons"]))
        entries.append((pin, strongest(actual) if actual else "BLOCK", "COMPLETE" if required_complete else "INCOMPLETE", evidence))
    return metadata, entries
