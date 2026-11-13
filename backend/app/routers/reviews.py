"""Review HTTP handlers; disposition routes are registered explicitly in main."""

import json
from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..protected_reviews import structured_reason, metadata as content_metadata, review_context
from ..dependencies import DB, USER
from ..models import Review, Execution, ReviewAssignment, ReviewNote
from ..schemas import ReviewUpdate
from ..security import Identity, require_role, account_enabled
from ..repositories import serialize, list_records, record_audit_event
from ..services.reviews import get_review, sanitize_review_reason
from ..services.policy_sets import guard_v1_history
from ..services.audit_attribution import execution_attribution


def reviews(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Reviewer", "Auditor", "Developer", "Policy Owner")
    if user.role in ("Developer", "Policy Owner"):
        return [
            serialize(row)
            for row in db.scalars(
                select(Review)
                .join(Execution, Review.execution_id == Execution.id)
                .where(Review.tenant == user.tenant, Execution.tenant == user.tenant, Execution.actor == user.user)
                .order_by(Review.created.desc(), Review.id)
                .offset(offset)
                .limit(limit)
            )
        ]
    return list_records(db, user, Review, offset, limit)


def review_detail(review_id: str, db: Session = DB, user: Identity = USER):
    review = get_review(db, user, review_id)
    guard_v1_history(db, user, execution_id=review.execution_id)
    execution = db.get(Execution, review.execution_id)
    return {
        **serialize(review),
        "execution": {**serialize(execution), **execution_attribution(db, user, execution)},
        "assignment": serialize(db.get(ReviewAssignment, review_id)) if db.get(ReviewAssignment, review_id) else None,
        "decision_history": [
            serialize(note)
            for note in db.scalars(
                select(ReviewNote)
                .where(ReviewNote.review_id == review_id, ReviewNote.tenant == user.tenant)
                .order_by(ReviewNote.created, ReviewNote.id)
            )
        ],
        **review_context(execution),
        "row_version": review.row_version,
        "protected_content": content_metadata(db, user, review),
        "instruction": "Original content is not stored in ordinary metadata. Submit revised text through the playground; all current gates run again.",
    }


def assign_review(review_id: str, payload: ReviewUpdate, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Reviewer")
    review = get_review(db, user, review_id)
    if review.status != "PENDING":
        raise HTTPException(409, "Only pending reviews can be assigned")
    if payload.assigned_reviewer:
        if user.session_id and user.session_id.startswith("sso:"):
            from ..models import SsoMembership

            permitted = (
                db.scalar(
                    select(SsoMembership.id).where(
                        SsoMembership.tenant == user.tenant,
                        SsoMembership.directory_tenant == str(UUID(settings.entra_tenant_id)),
                        SsoMembership.actor == payload.assigned_reviewer,
                        SsoMembership.enabled == 1,
                        SsoMembership.role.in_(("Admin", "Reviewer")),
                    )
                )
                is not None
            )
        else:
            accounts = json.loads(settings.demo_accounts_json)
            permitted = any(
                account["user"] == payload.assigned_reviewer
                and account["tenant"] == user.tenant
                and account["role"] in ("Admin", "Reviewer")
                and account_enabled(account)
                for account in accounts
            )
        if not permitted:
            raise HTTPException(422, "Select an enabled reviewer in this tenant")
    assignment = db.get(ReviewAssignment, review_id)
    if user.role != "Admin":
        if assignment and assignment.assigned_reviewer and assignment.assigned_reviewer != user.user:
            raise HTTPException(403, "Only the assigned reviewer or an administrator can reassign this case")
        if not assignment or not assignment.assigned_reviewer:
            if payload.assigned_reviewer != user.user:
                raise HTTPException(403, "Reviewers may claim an unassigned case for themselves")
    if not assignment:
        assignment = ReviewAssignment(id=review_id, tenant=user.tenant)
        db.add(assignment)
    # Invalidate a disposition loaded before a concurrent reassignment.
    review.row_version += 1
    payload.reason = sanitize_review_reason(structured_reason(db, payload.reason))
    assignment.assigned_reviewer, assignment.reason = payload.assigned_reviewer, payload.reason
    assignment.updated = datetime.now(timezone.utc).isoformat()
    db.add(ReviewNote(review_id=review_id, tenant=user.tenant, actor=user.user, action="assigned", reason=payload.reason))
    record_audit_event(db, user, "review.assigned", review.id)
    return {"review_id": review.id, **payload.model_dump()}
