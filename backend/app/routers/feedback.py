"""Existing feedback creation, deduplication and aggregation handlers."""

from fastapi import HTTPException
from sqlalchemy import select, func, cast, Float
from sqlalchemy.orm import Session
from ..dependencies import DB, USER
from ..models import Execution, Feedback, Audit
from ..schemas import FeedbackRequest
from ..security import Identity
from .. import usage
from ..repositories import record_audit_event, serialize


def collect_feedback(payload: FeedbackRequest, db: Session = DB, user: Identity = USER):
    execution = db.scalar(select(Execution).where(Execution.id == payload.execution_id, Execution.tenant == user.tenant))
    if not execution:
        raise HTTPException(404, "Execution not found")
    prior = db.scalar(
        select(Feedback.id)
        .join(Audit, Audit.resource == Feedback.id)
        .where(
            Feedback.tenant == user.tenant,
            Feedback.execution_id == payload.execution_id,
            Audit.tenant == user.tenant,
            Audit.actor == user.user,
            Audit.action == "feedback.created",
        )
        .limit(1)
    )
    if prior:
        raise HTTPException(409, "You have already submitted feedback for this execution")
    usage.claim_action(db, user, "feedback:" + payload.execution_id, 1, once=True)
    feedback = Feedback(tenant=user.tenant, **payload.model_dump())
    db.add(feedback)
    db.flush()
    record_audit_event(db, user, "feedback.created", feedback.id)
    return serialize(feedback)


def feedback_summary(db: Session = DB, user: Identity = USER):
    return {
        "count": db.scalar(select(func.count()).select_from(Feedback).where(Feedback.tenant == user.tenant)),
        "average": db.scalar(select(func.avg(cast(Feedback.rating, Float))).where(Feedback.tenant == user.tenant)),
    }
