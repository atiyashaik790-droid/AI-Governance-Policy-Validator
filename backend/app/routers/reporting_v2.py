"""Metadata history/review/reporting only; no generation or validation routes."""

from typing import Literal
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..dependencies import DB, USER
from ..exports import date_bounds
from ..models import Audit, Export, ExportJob
from ..services.audit_attribution import event_view
from ..schemas import ExportRequest, ReviewResolution, ReviewUpdate
from ..security import Identity, require_role
from ..services import reporting_v2 as service, exports_v2
from ..services.reviews import resolve_review
from .reviews import assign_review

router = APIRouter(prefix="/api/v2", tags=["Versioned metadata reporting"])


class VersionedExportRequest(ExportRequest):
    schema_version: Literal["2.0"] = "2.0"


@router.get("/audit/executions")
def executions(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), start_date: str | None = None,
               end_date: str | None = None, db: Session = DB, user: Identity = USER):
    return service.executions(db, user, offset, limit, start_date, end_date)


@router.get("/audit/executions/{execution_id}")
def execution(execution_id: str, db: Session = DB, user: Identity = USER):
    return service.execution(db, user, execution_id)


@router.get("/audit/events")
def events(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
           category: str = Query("all", pattern="^(all|policy|governance|administration)$"), db: Session = DB, user: Identity = USER,
           start_date: str | None = None, end_date: str | None = None):
    filters = [Audit.tenant == user.tenant]
    if start_date is not None or end_date is not None:
        try:
            first, last = date_bounds(start_date, end_date)
        except OverflowError:
            raise HTTPException(422, "Use valid ISO dates in a window of at most 366 days") from None
        filters.extend([Audit.created >= first, Audit.created < last])
    if category in {"policy", "governance"}:
        filters.append(Audit.action.startswith(category + "."))
    elif category == "administration":
        filters.extend([~Audit.action.startswith("policy."), ~Audit.action.startswith("governance.")])
    query = select(Audit).where(*filters)
    return {"schema_version": "2.0", "total": db.scalar(select(func.count()).select_from(Audit).where(*filters)),
            "offset": offset, "limit": limit, "items": [{k: v for k, v in event_view(db, user, row).items() if k != "tenant"}
                for row in db.scalars(query.order_by(Audit.created.desc(), Audit.id).offset(offset).limit(limit))]}


@router.get("/analytics/overview")
def overview(start_date: str | None = None, end_date: str | None = None, db: Session = DB, user: Identity = USER):
    return service.overview(db, user, start_date, end_date)


@router.get("/reviews")
def reviews(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    return service.reviews(db, user, offset, limit)


@router.get("/reviews/{review_id}")
def review(review_id: str, db: Session = DB, user: Identity = USER):
    return service.review_detail(db, user, review_id)


@router.put("/reviews/{review_id}/assignment")
def assign(review_id: str, payload: ReviewUpdate, db: Session = DB, user: Identity = USER):
    return assign_review(review_id, payload, db, user)


@router.post("/reviews/{review_id}/approve")
def approve(review_id: str, payload: ReviewResolution, db: Session = DB, user: Identity = USER):
    return resolve_review(review_id, "approve", db, user, payload.reason)


@router.post("/reviews/{review_id}/reject")
def reject(review_id: str, payload: ReviewResolution, db: Session = DB, user: Identity = USER):
    return resolve_review(review_id, "reject", db, user, payload.reason)


@router.post("/reports/export", status_code=201)
def export(payload: VersionedExportRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return exports_v2.create(db, user, payload)


@router.get("/reports/exports")
def reports(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    filters = (Export.tenant == user.tenant, ExportJob.tenant == user.tenant, *exports_v2.versioned_contract())
    rows = db.scalars(select(Export).join(ExportJob, ExportJob.id == Export.id).where(*filters)
                      .order_by(Export.created.desc(), Export.id).offset(offset).limit(limit))
    return {"schema_version": "2.0", "offset": offset, "limit": limit,
            "total": db.scalar(select(func.count()).select_from(Export).join(ExportJob, ExportJob.id == Export.id).where(*filters)),
            "items": [exports_v2.report(db, user, row.id) for row in rows]}


@router.post("/reports/exports/{export_id}/reconcile")
def reconcile(export_id: str, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return exports_v2.reconcile(db, user, export_id)
