"""Shared tenant-scoped persistence and column serialization helpers."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Audit
from .security import Identity


def record_audit_event(db: Session, user: Identity, action: str, resource: str) -> None:
    db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action=action, resource=resource))


def serialize(record) -> dict:
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


def list_records(db: Session, user: Identity, model, offset: int, limit: int) -> list:
    ordering = (model.created.desc(), model.id) if hasattr(model, "created") else (model.id.desc(),)
    return [
        serialize(row)
        for row in db.scalars(select(model).where(model.tenant == user.tenant).order_by(*ordering).offset(offset).limit(limit))
    ]
