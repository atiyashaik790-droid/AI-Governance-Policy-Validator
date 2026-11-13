"""Existing review visibility, metadata protection and disposition operations."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..dependencies import DB, USER
from ..models import Review, Execution, ReviewAssignment, ReviewNote
from ..schemas import PolicyDocument
from ..security import Identity, require_role
from ..protected_reviews import structured_reason, purge_resolved
from ..engine import detect_sensitive_information, redact_personal_information
from ..repositories import record_audit_event, serialize


def get_review(db: Session, user: Identity, review_id: str):
    require_role(user, "Admin", "Reviewer", "Auditor", "Developer", "Policy Owner")
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    review = db.scalar(select(Review).where(Review.id == review_id, Review.tenant == user.tenant)
                       .with_hint(Review, "WITH (UPDLOCK, HOLDLOCK)", "mssql")
                       .execution_options(populate_existing=True))
    if not review:
        raise HTTPException(404, "Review not found")
    if user.role in ("Developer", "Policy Owner"):
        execution = db.get(Execution, review.execution_id)
        if not execution or execution.actor != user.user:
            raise HTTPException(404, "Review not found")
    return review


def sanitize_review_reason(reason: str) -> str:
    if not reason:
        return ""
    policy = PolicyDocument(name="Review metadata protection")
    try:
        spans = detect_sensitive_information(reason, "secret_detection", policy)
        spans += detect_sensitive_information(reason, "pii_detection", policy)
        return redact_personal_information(reason, spans)[:1000]
    except Exception:
        raise HTTPException(503, "Review metadata inspection unavailable") from None


def resolve_review(review_id: str, operation: str, db: Session = DB, user: Identity = USER, reason: str = ""):
    require_role(user, "Admin", "Reviewer")
    review = get_review(db, user, review_id)
    if operation not in ("approve", "reject"):
        raise HTTPException(404, "Unknown review action")
    if review.status != "PENDING":
        raise HTTPException(409, "Review already resolved")
    assignment = db.get(ReviewAssignment, review_id)
    if assignment and assignment.assigned_reviewer and assignment.assigned_reviewer != user.user and user.role != "Admin":
        raise HTTPException(403, "This case is assigned to another reviewer")
    reason = sanitize_review_reason(structured_reason(db, reason))
    db.add(ReviewNote(review_id=review_id, tenant=user.tenant, actor=user.user, action=operation, reason=reason))
    review.status = "APPROVED_RESUBMIT_REQUIRED" if operation == "approve" else "REJECTED"
    purge_resolved(db, user, review)
    record_audit_event(db, user, f"review.{operation}", review.id)
    db.flush()
    return {
        **serialize(review),
        "instruction": "Submit revised content through all current policy gates. No content is released by review.",
    }
