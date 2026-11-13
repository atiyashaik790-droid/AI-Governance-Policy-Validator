"""Read-only, tenant-scoped labels and safe attribution; no historical backfill."""
import json
from sqlalchemy import select
from ..models import Policy, Version
from ..models_multi_policy import ExecutionPolicyEvidence as Evidence
from ..execution_identity import recorded_identity
from ..repositories import serialize

MISSING = "Not recorded"
NA = "Not applicable"
CATEGORIES = {"pii_detection", "secret_detection", "moderation", "blocked_keywords"}


def parsed(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def policy_label(db, tenant, policy_id, *, number=None, version_id=None):
    query = select(Version).where(Version.tenant == tenant, Version.policy_id == policy_id)
    if number is not None:
        query = query.where(Version.number == number)
    if version_id is not None:
        query = query.where(Version.id == version_id)
    version = db.scalar(query.order_by(Version.number.desc()).limit(1))
    if version:
        name = parsed(version.document).get("name")
        return {"policy_id": policy_id, "name": name if isinstance(name, str) and 0 < len(name) <= 120 else MISSING,
                "version": version.number, "version_id": version.id, "name_source": "retained published version"}
    return {"policy_id": policy_id, "name": MISSING, "version": number, "version_id": version_id, "name_source": MISSING}


def violations(metadata):
    found = set()

    def inspect(value):
        if not isinstance(value, dict):
            return
        items = value.get("findings", [])
        items = items if isinstance(items, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            category = item.get("category")
            if isinstance(category, str):
                if category.startswith("custom:"):
                    found.add("custom_policy")
                elif category in CATEGORIES:
                    found.add(category)
        breakdown = value.get("breakdown", {})
        local_hold = any(isinstance(item, dict) and item.get("action") in {"BLOCK", "HUMAN_REVIEW"} and item.get("count") for item in items)
        if isinstance(breakdown, dict) and any(status == "UNKNOWN" and not (name == "moderation" and local_hold) for name, status in breakdown.items()):
            found.add("inspection_unavailable")
    for name in ("input", "output"):
        stage = metadata.get(name)
        inspect(stage)
        if isinstance(stage, dict):
            policies = stage.get("policies", [])
            for policy in policies if isinstance(policies, list) else []:
                if not isinstance(policy, dict):
                    continue
                inspect(policy.get("local"))
                inspect(policy.get("reinspection"))
                moderation = policy.get("moderation", {})
                if isinstance(moderation, dict) and moderation.get("status") == "FAILED":
                    found.add("moderation")
    return sorted(found)


def execution_attribution(db, user, row):
    metadata = parsed(row.metadata_json)
    identity = recorded_identity(row, metadata)
    if getattr(row, "execution_mode", "LEGACY") == "MULTI":
        policies = [policy_label(db, user.tenant, evidence.policy_id, version_id=evidence.version_id)
                    for evidence in db.scalars(select(Evidence).where(Evidence.tenant == user.tenant, Evidence.execution_id == row.id)
                                               .order_by(Evidence.policy_id))]
    else:
        policies = [policy_label(db, user.tenant, row.policy_id, number=row.version)] if row.policy_id else []
    return {"actor": row.actor or MISSING, "actor_role": identity["role"] if identity else MISSING,
            "execution_identity": identity, "policies": policies,
            "policy_names": [p["name"] for p in policies] or [MISSING],
            "violation_categories": violations(metadata) or ([NA] if metadata else [MISSING])}


def event_view(db, user, row):
    value = serialize(row)
    value.update(actor=row.actor or MISSING, actor_role=row.actor_role or MISSING, policy_name=NA, policy_name_source=NA)
    if row.action.startswith("policy.") and not row.action.startswith("policy.mode."):
        label = policy_label(db, user.tenant, row.resource)
        if label["name"] == MISSING:
            policy = db.scalar(select(Policy).where(Policy.tenant == user.tenant, Policy.id == row.resource))
            if policy:
                label.update(name=policy.name, name_source="current policy record; event-time name not recorded")
        value.update(policy_name=label["name"], policy_name_source=label["name_source"], version=label["version"])
    return value
