"""Request-level, tenant-filtered dashboard analytics from persisted inspection metadata.

One request contributes at most once per stage and category to findings, even
when several policies detect it. A control earns its configured weight when all
applicable policy inspections have a known result (SATISFIED or FAILED).
Detection is not an enforcement failure: blocked unsafe content can earn full
control coverage. Unknown/withheld evidence earns zero; disabled controls are
excluded from the denominator. This measures evidenced control execution, not
regulatory certification or detector accuracy.
"""

import json
from collections import defaultdict

WEIGHTS = {"secret_detection": 30, "pii_detection": 25, "moderation": 25, "configured_rules": 20}
LABELS = {"secret_detection": "Secrets and API keys", "pii_detection": "Personally identifiable information",
          "moderation": "Moderation / unsafe content", "blocked_keywords": "Blocked keywords / confidential information",
          "custom": "Other configured policy violations"}


def category(name):
    return "custom" if isinstance(name, str) and name.startswith("custom:") else name if name in (*WEIGHTS, "blocked_keywords") else None


def stages(metadata):
    for stage in ("input", "output"):
        value = metadata.get(stage)
        if isinstance(value, dict):
            policies = value.get("policies")
            if isinstance(policies, list):
                yield stage, policies
            else:
                yield stage, [value]


def inspect_policy(policy):
    if "local" not in policy:
        yield policy
        return
    local = policy.get("local")
    if isinstance(local, dict):
        yield local
    moderation = policy.get("moderation")
    if isinstance(moderation, dict):
        yield {"breakdown": {"moderation": moderation.get("status")},
               "findings": [{"category": "moderation", "categories": moderation.get("categories", [])}]
               if moderation.get("status") == "FAILED" else []}


def aggregate(rows):
    counts = {key: 0 for key in LABELS}
    unknown = 0
    earned_total = denominator_total = known_observations = 0
    scored_requests = 0
    daily = defaultdict(lambda: [0, 0, 0])
    findings_available = False
    findings_reliable = True
    for row in rows:
        try:
            metadata = json.loads(row.metadata_json)
        except (ValueError, TypeError):
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        request_controls = defaultdict(list)
        findings = set()
        has_evidence = False
        for stage, policies in stages(metadata):
            for policy in policies:
                if not isinstance(policy, dict):
                    unknown += 1
                    findings_reliable = False
                    continue
                for part in inspect_policy(policy):
                    breakdown = part.get("breakdown")
                    if not isinstance(breakdown, dict):
                        continue
                    if breakdown:
                        has_evidence = True
                        findings_available = True
                    for raw, status in breakdown.items():
                        group = category(raw)
                        if group and status != "NOT_APPLICABLE":
                            request_controls[(stage, "configured_rules" if group in ("blocked_keywords", "custom") else group)].append(status)
                    items = part.get("findings")
                    confirmed = set()
                    if isinstance(items, list):
                        for finding in items:
                            if not isinstance(finding, dict):
                                continue
                            group = category(finding.get("category"))
                            if group and finding.get("status") != "UNKNOWN" and (
                                (type(finding.get("count")) is int and finding["count"] > 0)
                                or (group == "moderation" and bool(finding.get("categories")))
                            ) and breakdown.get(finding["category"]) == "FAILED":
                                findings.add((stage, group))
                                confirmed.add(finding["category"])
                    if any(status == "FAILED" and raw not in confirmed for raw, status in breakdown.items() if category(raw)):
                        findings_reliable = False
        for _, group in findings:
            counts[group] += 1
        if not has_evidence:
            unknown += 1
        if request_controls:
            by_control = defaultdict(list)
            for (_, group), statuses in request_controls.items():
                by_control[group].extend(statuses)
            denominator = sum(WEIGHTS.get(group, 20) for group in by_control)
            earned = sum(WEIGHTS.get(group, 20) for group, statuses in by_control.items()
                         if statuses and all(status in ("SATISFIED", "FAILED") for status in statuses))
            known = sum(status in ("SATISFIED", "FAILED") for statuses in by_control.values() for status in statuses)
            known_observations += known
            if denominator:
                earned_total += earned
                denominator_total += denominator
                scored_requests += 1
                daily[str(row.created)[:10]][0] += earned
                daily[str(row.created)[:10]][1] += denominator
                daily[str(row.created)[:10]][2] += known
                unknown += sum(any(status not in ("SATISFIED", "FAILED") for status in statuses)
                               for statuses in by_control.values())
    return {"score": round(100 * earned_total / denominator_total, 2) if denominator_total and known_observations else None,
            "scored_requests": scored_requests, "incomplete_inspections": unknown,
            "trends": [{"date": day, "score": round(100 * values[0] / values[1], 2)}
                       for day, values in sorted(daily.items()) if values[2]],
            "violations": counts, "findings_available": findings_available and findings_reliable,
            "counting": "One request-stage-category finding; duplicate policy detections count once"}
