"""Review-only demo plan and disposable SQLite seed rehearsal. No cloud apply mode."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from manage_sso_membership import apply_mapping, validate_mapping

PROFILE = "gpv-clean-demo-v2"
TENANT = "clean-demo-local"
DIRECTORY = "11111111-1111-4111-8111-111111111111"


def plan():
    from app.schemas import PolicyDocument

    def document(name, enabled, *, entities=None, pii_action="REDACT", **extra):
        rules = {
            key: {"enabled": key in enabled, "action": "BLOCK"}
            for key in (
                "secret_detection",
                "pii_detection",
                "moderation",
                "blocked_keywords",
            )
        }
        rules["pii_detection"].update(
            action=pii_action, entities=entities or ["EMAIL_ADDRESS", "PHONE_NUMBER"]
        )
        rules["blocked_keywords"]["values"] = ["internal-only", "confidential-demo"]
        return PolicyDocument(name=name, rules=rules, **extra).model_dump(mode="json")

    policies = [
        document("Customer Personal Data Protection", {"pii_detection"}),
        document("API Key and Secret Leakage Prevention", {"secret_detection"}),
        document(
            "Credit Card Data Protection",
            {"pii_detection"},
            entities=["CREDIT_CARD"],
            pii_action="BLOCK",
        ),
        document("Confidential Company Information Protection", {"blocked_keywords"}),
        document("Unsafe Content Prevention", {"moderation"}),
        document(
            "Human Approval for Sensitive Requests",
            set(),
            custom_categories=[
                {
                    "id": "review-required",
                    "name": "Synthetic review",
                    "action": "HUMAN_REVIEW",
                    "detection": "keyword",
                    "values": ["review-required"],
                }
            ],
        ),
        document(
            "AI Output Data Leakage Prevention",
            {"pii_detection", "secret_detection"},
            entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD"],
        ),
        document(
            "Enterprise AI Safety Baseline",
            {"pii_detection", "secret_detection", "moderation", "blocked_keywords"},
        ),
    ]
    memberships = [
        validate_mapping(
            {
                "directory_tenant": DIRECTORY,
                "object_id": f"22222222-2222-4222-8222-{number:012d}",
                "tenant": TENANT,
                "actor": "synthetic-" + role.lower(),
                "role": role,
                "enabled": True,
            }
        )
        for number, role in enumerate(("Admin", "User"), 1)
    ]
    return {
        "mode": "LOCAL_REHEARSAL_ONLY",
        "profile": PROFILE,
        "tenant": TENANT,
        "memberships": memberships,
        "policies": policies,
        "policy_mode": "MULTI",
        "cloud_apply_available": False,
        "notes": [
            "Synthetic object IDs are not real Entra accounts.",
            "Output safety rules inspect both stages; no output-only selector exists.",
            "Moderation and generation remain fixture-only during local tests.",
        ],
    }


def seed_local(db, *, persistent_live_chat=False):
    """Resume seed-owned records; reject drift. Caller supplies a disposable /tmp DB
    or opts into the exact dedicated persistent local-chat target.

    Policy-set operations commit individually. Re-entry resumes committed stages;
    an exception rolls back the current transaction, not earlier audited stages.
    """
    from sqlalchemy import select
    from app.models import Policy, Version, SsoMembership
    from app.models_multi_policy import WorkspacePolicyState, WorkspacePolicyAssignment
    from app.security import Identity
    from app.services.policies import transition_policy
    from app.services.policy_sets import change_mode, change_assignment

    bind = db.get_bind()
    database = bind.url.database
    persistent_target = Path(__file__).resolve().parents[1] / "private" / "live-local-chat" / "offline.db"
    if (
        bind.dialect.name != "sqlite"
        or not database
        or not (Path(database).resolve().is_relative_to(Path("/tmp"))
                or persistent_live_chat and Path(database).resolve() == persistent_target.resolve())
    ):
        raise ValueError("Only a disposable SQLite file under /tmp is allowed")
    spec = plan()
    admin = Identity("synthetic-admin", TENANT, "Admin")
    # Check all existing seed-owned records before any write; never overwrite drift.
    for mapping in spec["memberships"]:
        existing = db.scalar(
            select(SsoMembership).where(
                SsoMembership.directory_tenant == mapping["directory_tenant"],
                SsoMembership.object_id == mapping["object_id"],
            )
        )
        if existing and any(
            getattr(existing, key) != value for key, value in mapping.items()
        ):
            raise ValueError("Membership drift; operator review required")
    for document in spec["policies"]:
        identifier = str(
            uuid5(NAMESPACE_URL, PROFILE + ":" + TENANT + ":" + document["name"])
        )
        existing = db.get(Policy, identifier)
        if existing and (
            existing.tenant != TENANT
            or json.loads(existing.draft) != document
            or existing.name != document["name"]
            or not existing.enabled
            or existing.status not in {"DRAFT", "SUBMITTED", "APPROVED", "PUBLISHED"}
        ):
            raise ValueError("Policy drift; operator review required")
        if existing:
            versions = list(
                db.scalars(select(Version).where(Version.policy_id == identifier))
            )
            if any(
                v.tenant != TENANT or json.loads(v.document) != document
                for v in versions
            ):
                raise ValueError("Published version drift; operator review required")
    try:
        for mapping in spec["memberships"]:
            existing = db.scalar(
                select(SsoMembership).where(
                    SsoMembership.directory_tenant == mapping["directory_tenant"],
                    SsoMembership.object_id == mapping["object_id"],
                )
            )
            if not existing:
                apply_mapping(db, mapping, admin.user, "LOCAL-ONLY")
        db.commit()
        for document in spec["policies"]:
            identifier = str(
                uuid5(NAMESPACE_URL, PROFILE + ":" + TENANT + ":" + document["name"])
            )
            policy = db.get(Policy, identifier)
            if not policy:
                policy = Policy(
                    id=identifier,
                    tenant=TENANT,
                    name=document["name"],
                    draft=json.dumps(document),
                )
                db.add(policy)
                db.commit()
            for status, operation in (
                ("DRAFT", "submit"),
                ("SUBMITTED", "approve"),
                ("APPROVED", "publish"),
            ):
                if policy.status == status:
                    transition_policy(identifier, operation, db, admin)
                    db.commit()
            version = db.scalar(
                select(Version).where(
                    Version.policy_id == identifier, Version.tenant == TENANT
                )
            )
            if version is None:
                raise ValueError("Published policy has no version")
            state = db.get(WorkspacePolicyState, TENANT, populate_existing=True)
            if not state or state.mode != "MULTI":
                change_mode(
                    db,
                    admin,
                    "MULTI",
                    expected_revision=state.set_revision if state else 1,
                    seed_legacy_assignment=False,
                )
            state = db.get(WorkspacePolicyState, TENANT, populate_existing=True)
            pin = db.get(
                WorkspacePolicyAssignment, (TENANT, identifier), populate_existing=True
            )
            if pin and (not pin.active or pin.version_id != version.id):
                raise ValueError("Assignment drift; operator review required")
            change_assignment(
                db,
                admin,
                identifier,
                active=True,
                version_id=version.id,
                expected_revision=state.set_revision,
            )
    except Exception:
        db.rollback()
        raise
    return spec


if __name__ == "__main__":
    print(json.dumps(plan(), indent=2))
