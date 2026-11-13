"""Existing tenant policy resolution and lifecycle operations."""

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..config import settings
from ..dependencies import DB, USER
from ..models import Policy, Version, Assignment
from ..schemas import PolicyDocument
from ..security import Identity, require_role
from ..repositories import record_audit_event, serialize
from .policy_sets import guard_legacy, guard_lifecycle, multi_mode, legacy_assignment_changed, legacy_eligibility_changed
from ..models_multi_policy import WorkspacePolicyAssignment


def get_policy(db: Session, user: Identity, policy_id: str, include_deleted: bool = False) -> Policy:
    policy = db.scalar(select(Policy).where(Policy.id == policy_id, Policy.tenant == user.tenant))
    if not policy or (policy.status == "DELETED" and not include_deleted):
        raise HTTPException(404, "Policy not found")
    return policy


def load_active_policy(db: Session, user: Identity):
    guard_legacy(db, user)
    assignment = db.get(Assignment, user.tenant)
    version = db.get(Version, assignment.version_id) if assignment else None
    policy = get_policy(db, user, version.policy_id) if version and version.tenant == user.tenant else None
    if not policy or not policy.enabled or policy.status in ("ARCHIVED", "DELETED"):
        raise HTTPException(409, "No enabled active policy; request withheld")
    return policy, version, PolicyDocument.model_validate_json(version.document)


def policy_details(db: Session, user: Identity, policy: Policy) -> dict:
    has_versions = db.scalar(select(Version.id).where(Version.policy_id == policy.id, Version.tenant == user.tenant).limit(1)) is not None
    active = (
        db.scalar(
            select(Version.id)
            .join(Assignment, Assignment.version_id == Version.id)
            .where(Assignment.tenant == user.tenant, Version.tenant == user.tenant, Version.policy_id == policy.id)
        )
        is not None
    )
    if multi_mode(db, user):
        pin = db.get(WorkspacePolicyAssignment, (user.tenant, policy.id), populate_existing=True)
        active = bool(pin and pin.active)
    return {**serialize(policy), "has_published_versions": has_versions, "is_active": active}


def transition_policy(policy_id: str, operation: str, db: Session = DB, user: Identity = USER):
    workspace_state = guard_lifecycle(db, user, policy_id, operation)
    policy = get_policy(db, user, policy_id)
    if operation in ("approve", "reject"):
        require_role(user, "Admin", "Reviewer")
    else:
        require_role(user, "Admin", "Policy Owner")
    if operation in ("submit", "approve", "publish"):
        expected = {"submit": "DRAFT", "approve": "SUBMITTED", "publish": "APPROVED"}[operation]
        if policy.status != expected:
            raise HTTPException(409, f"{operation} requires {expected}")
        document = PolicyDocument.model_validate_json(policy.draft)
        if document.rules.pii_detection.enabled and document.rules.pii_detection.entities:
            from ..engine import get_pii_analyzer

            available = {"EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"}
            if settings.pii_mode == "presidio":
                try:
                    available.update(get_pii_analyzer().get_supported_entities(language="en"))
                except Exception:
                    raise HTTPException(503, "PII recognizers unavailable; policy cannot advance") from None
            if set(document.rules.pii_detection.entities) - available:
                raise HTTPException(422, "Policy selects PII entities unavailable in the configured detector")
        policy.status = {"submit": "SUBMITTED", "approve": "APPROVED", "publish": "PUBLISHED"}[operation]
        if operation == "publish":
            number = (db.scalar(select(func.max(Version.number)).where(Version.policy_id == policy_id)) or 0) + 1
            db.add(Version(policy_id=policy_id, tenant=user.tenant, number=number, document=policy.draft))
    elif operation == "reject":
        if policy.status != "SUBMITTED":
            raise HTTPException(409, "Rejection requires SUBMITTED")
        policy.status = "DRAFT"
    elif operation == "activate":
        version = db.scalar(
            select(Version).where(Version.policy_id == policy_id, Version.tenant == user.tenant).order_by(Version.number.desc())
        )
        if not version or not policy.enabled or policy.status != "PUBLISHED":
            raise HTTPException(409, "Activation requires enabled published policy")
        # A concurrent disable/delete must invalidate an activation's stale read.
        policy.row_version += 1
        db.flush()
        assignment = db.get(Assignment, user.tenant)
        previous_version_id = assignment.version_id if assignment else None
        if assignment:
            assignment.version_id = version.id
        else:
            db.add(Assignment(tenant=user.tenant, version_id=version.id))
        legacy_assignment_changed(db, user, workspace_state, previous_version_id, version)
    elif operation in ("enable", "disable"):
        if policy.status == "ARCHIVED":
            raise HTTPException(409, "Archived policies cannot be enabled")
        previous_enabled = policy.enabled
        policy.enabled = int(operation == "enable")
        legacy_eligibility_changed(db, user, workspace_state, policy, previous_enabled)
    elif operation == "archive":
        assignment = db.get(Assignment, user.tenant)
        active_version = db.get(Version, assignment.version_id) if assignment else None
        if not multi_mode(db, user) and active_version and active_version.policy_id == policy_id:
            raise HTTPException(409, "Activate another policy before archiving")
        policy.status, policy.enabled = "ARCHIVED", 0
    else:
        raise HTTPException(404, "Unknown lifecycle operation")
    record_audit_event(db, user, f"policy.{operation}", policy_id)
    db.flush()
    return policy_details(db, user, policy)
