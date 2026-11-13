"""Policy HTTP handlers; main registers them in the original global route order."""

import asyncio
import time
from fastapi import HTTPException, Query, Header
from sqlalchemy import select, func, case, true
from sqlalchemy.orm import Session
from ..config import settings
from ..dependencies import DB, USER
from ..models import Policy, Version, Assignment
from ..schemas import PolicyDocument, TextRequest, RollbackRequest
from ..security import Identity, require_role
from ..engine import inspect_text
from .. import usage
from ..repositories import serialize, record_audit_event
from ..services.policies import get_policy, policy_details
from ..services import policy_sets
from ..services.category_catalog import clear_policy_categories, sync_draft_categories


def get_all_policies(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str = Query("", max_length=120),
    status: str | None = Query(None, pattern="^(DRAFT|SUBMITTED|APPROVED|PUBLISHED|ARCHIVED)$"),
    enabled: bool | None = None,
    db: Session = DB,
    user: Identity = USER,
):
    query = select(Policy).where(Policy.tenant == user.tenant, Policy.status != "DELETED")
    if search:
        query = query.where(Policy.name.icontains(search, autoescape=True))
    if status:
        query = query.where(Policy.status == status)
    if enabled is not None:
        query = query.where(Policy.enabled == int(enabled))
    published = select(Version.id).where(Version.policy_id == Policy.id, Version.tenant == user.tenant).exists()
    active = (
        select(Assignment.tenant)
        .join(Version, Assignment.version_id == Version.id)
        .where(Assignment.tenant == user.tenant, Version.tenant == user.tenant, Version.policy_id == Policy.id)
        .exists()
    )
    if policy_sets.multi_mode(db, user):
        from ..models_multi_policy import WorkspacePolicyAssignment as MultiAssignment
        active = select(MultiAssignment.policy_id).where(
            MultiAssignment.tenant == user.tenant, MultiAssignment.policy_id == Policy.id, MultiAssignment.active == true()
        ).exists()
    latest_version = select(func.max(Version.number)).where(Version.policy_id == Policy.id, Version.tenant == user.tenant).scalar_subquery()
    return [
        {**serialize(row), "has_published_versions": bool(has_versions), "is_active": bool(is_active), "latest_version_number": version_number}
        for row, has_versions, is_active, version_number in db.execute(
            # SQL Server permits EXISTS as a predicate, but not a SELECT value.
            query.add_columns(case((published, 1), else_=0), case((active, 1), else_=0), latest_version)
            .order_by(Policy.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


def create_new_policy(document: PolicyDocument, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    if document.custom_categories or document.decision_messages:
        require_role(user, "Admin")
    policy = Policy(tenant=user.tenant, name=document.name, draft=document.model_dump_json())
    db.add(policy)
    db.flush()
    sync_draft_categories(db, user.tenant, policy.id, document)
    record_audit_event(db, user, "policy.created", policy.id)
    return policy_details(db, user, policy)


def view_policy(policy_id: str, db: Session = DB, user: Identity = USER):
    return policy_details(db, user, get_policy(db, user, policy_id, include_deleted=True))


def update_existing_policy(
    policy_id: str,
    document: PolicyDocument,
    db: Session = DB,
    user: Identity = USER,
    expected_version: str | None = Header(default=None, alias="If-Match"),
):
    require_role(user, "Admin", "Policy Owner")
    policy_sets.guard_lifecycle(db, user, policy_id, "edit")
    policy = get_policy(db, user, policy_id)
    previous = PolicyDocument.model_validate_json(policy.draft)
    if document.custom_categories != previous.custom_categories or document.decision_messages != previous.decision_messages:
        require_role(user, "Admin")
    if policy.status == "ARCHIVED":
        raise HTTPException(409, "Archived policy cannot be edited")
    if expected_version is None:
        raise HTTPException(428, "Reload this policy and send its row_version in If-Match")
    if expected_version.strip('"') != str(policy.row_version):
        raise HTTPException(412, "Policy changed since you opened it; reload and review your changes")
    policy.draft, policy.name, policy.status = document.model_dump_json(), document.name, "DRAFT"
    policy.revision += 1
    sync_draft_categories(db, user.tenant, policy.id, document)
    record_audit_event(db, user, "policy.draft_updated", policy.id)
    db.flush()
    return policy_details(db, user, policy)


def delete_draft_policy(
    policy_id: str,
    db: Session = DB,
    user: Identity = USER,
    expected_version: str | None = Header(default=None, alias="If-Match"),
):
    require_role(user, "Admin", "Policy Owner")
    policy_sets.guard_lifecycle(db, user, policy_id, "delete")
    policy = get_policy(db, user, policy_id)
    versions = db.scalar(select(func.count()).select_from(Version).where(Version.policy_id == policy_id, Version.tenant == user.tenant))
    if versions:
        if expected_version is None:
            raise HTTPException(428, "Reload this policy and send its row_version in If-Match")
        if expected_version.strip('"') != str(policy.row_version):
            raise HTTPException(412, "Policy changed since you opened it; reload and review your changes")
        assignment = db.get(Assignment, user.tenant)
        active_version = db.get(Version, assignment.version_id) if assignment else None
        if not policy_sets.multi_mode(db, user) and active_version and active_version.policy_id == policy.id:
            raise HTTPException(409, "Activate another policy before deleting this policy")
        if policy.enabled:
            raise HTTPException(409, "Disable this policy before deleting it")
        policy.status, policy.enabled = "DELETED", 0
        clear_policy_categories(db, user.tenant, policy.id)
        record_audit_event(db, user, "policy.removed", policy.id)
        db.flush()
        return {"deleted": True, "history_retained": True}
    if policy.status != "DRAFT":
        raise HTTPException(409, "Only never-published drafts can be deleted")
    record_audit_event(db, user, "policy.deleted", policy.id)
    clear_policy_categories(db, user.tenant, policy.id)
    db.delete(policy)
    return {"deleted": True}


async def simulate_policy(policy_id: str, payload: TextRequest, db: Session = DB, user: Identity = USER):
    policy_sets.guard_legacy(db, user)
    policy = get_policy(db, user, policy_id)
    document = PolicyDocument.model_validate_json(policy.draft)
    admission = policy_sets.admit(db, user, legacy_only=True, simulation=True) if policy_sets.schema_006(db) else None
    identifier = admission.reservation_id if admission else usage.reserve(db, user)
    state = "FAILED"
    try:
        async with asyncio.timeout(settings.inference_deadline):
            deadline = time.monotonic() + settings.inference_deadline
            result = await inspect_text(payload.text, document)
        if time.monotonic() >= deadline:
            raise HTTPException(504, "Simulation deadline exceeded; response withheld")
        record_audit_event(db, user, "policy.simulated", policy_id)
        if admission:
            policy_sets.fence(db, user, admission, hold=True)
            policy_sets.finish_admission(db, user, admission, "SIMULATED", commit=False)
        db.commit()
        if time.monotonic() >= deadline:
            raise HTTPException(504, "Simulation deadline exceeded after persistence; inspect audit history")
        state = "SIMULATED"
        return result
    except TimeoutError:
        raise HTTPException(504, "Simulation deadline exceeded; response withheld") from None
    finally:
        db.rollback()
        if admission:
            policy_sets.finish_admission(db, user, admission, state)
        else:
            usage.finish(db, identifier, state)


def policy_versions(
    policy_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER
):
    get_policy(db, user, policy_id, include_deleted=True)
    return [
        serialize(row)
        for row in db.scalars(
            select(Version)
            .where(Version.policy_id == policy_id, Version.tenant == user.tenant)
            .order_by(Version.number.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


def rollback_policy(policy_id: str, payload: RollbackRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    policy_sets.guard_lifecycle(db, user, policy_id, "rollback")
    policy = get_policy(db, user, policy_id)
    if policy.status == "ARCHIVED":
        raise HTTPException(409, "Archived policies cannot be rolled back")
    version = db.scalar(
        select(Version).where(Version.policy_id == policy_id, Version.tenant == user.tenant, Version.number == payload.version)
    )
    if not version:
        raise HTTPException(404, "Eligible published version not found")
    document = PolicyDocument.model_validate_json(version.document)
    previous = PolicyDocument.model_validate_json(policy.draft)
    if document.custom_categories != previous.custom_categories or document.decision_messages != previous.decision_messages:
        require_role(user, "Admin")
    policy.draft, policy.name, policy.status = document.model_dump_json(), document.name, "DRAFT"
    policy.revision += 1
    sync_draft_categories(db, user.tenant, policy.id, document)
    record_audit_event(db, user, "policy.rollback.DRAFT_REAPPROVAL_REQUIRED", policy.id)
    db.flush()
    return policy_details(db, user, policy)
