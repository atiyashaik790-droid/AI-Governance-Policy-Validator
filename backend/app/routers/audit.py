"""Audit and analytics HTTP handlers, preserving all existing aliases."""

from fastapi import Query, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..dependencies import DB, USER
from ..models import Audit, Execution
from ..security import Identity
from ..repositories import serialize
from .. import analytics as analytics_service
from ..services.policy_sets import guard_v1_history, multi_mode, fail
from ..exports import date_bounds
from ..services.audit_attribution import execution_attribution, event_view


def executions(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER,
               start_date: str | None = None, end_date: str | None = None):
    filters = [Execution.tenant == user.tenant]
    if start_date is not None or end_date is not None:
        try:
            first, last = date_bounds(start_date, end_date)
        except OverflowError:
            raise HTTPException(422, "Use valid ISO dates in a window of at most 366 days") from None
        guard_v1_history(db, user, first=first, last=last)
        filters.extend([Execution.created >= first, Execution.created < last])
    else:
        guard_v1_history(db, user)
    rows = db.scalars(select(Execution).where(*filters).order_by(Execution.created.desc(), Execution.id).offset(offset).limit(limit))
    return [{**serialize(row), **execution_attribution(db, user, row)} for row in rows]


def audit_events(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    category: str = Query("all", pattern="^(all|policy|governance|administration)$"),
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = DB,
    user: Identity = USER,
):
    query = select(Audit).where(Audit.tenant == user.tenant)
    if start_date is not None or end_date is not None:
        try:
            first, last = date_bounds(start_date, end_date)
        except OverflowError:
            raise HTTPException(422, "Use valid ISO dates in a window of at most 366 days") from None
        query = query.where(Audit.created >= first, Audit.created < last)
    if category in ("policy", "governance"):
        query = query.where(Audit.action.startswith(category + "."))
    elif category == "administration":
        query = query.where(~Audit.action.startswith("policy."), ~Audit.action.startswith("governance."))
    return [event_view(db, user, row) for row in db.scalars(query.order_by(Audit.created.desc(), Audit.id).offset(offset).limit(limit))]


def analytics(db: Session = DB, user: Identity = USER, start_date: str | None = None, end_date: str | None = None):
    if multi_mode(db, user):
        fail(409, "USE_API_V2")
    first, last = date_bounds(start_date, end_date)
    guard_v1_history(db, user, first=first, last=last)
    return analytics_service.overview(db, user, start_date, end_date)
