"""Authorized HTTP adapters for the existing export and recovery service."""

from fastapi import Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..dependencies import DB, USER
from ..models import Export
from ..schemas import ExportRequest
from ..security import Identity, require_role
from .. import exports


def export_sanitized_report(payload: ExportRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return exports.create(db, user, payload)


def reconcile_export(export_id: str, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return exports.process(db, user, export_id, reconcile=True)


def report_exports(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return [
        exports.public_report(db, report)
        for report in db.scalars(
            select(Export).where(Export.tenant == user.tenant).order_by(Export.created.desc(), Export.id).offset(offset).limit(limit)
        )
    ]
