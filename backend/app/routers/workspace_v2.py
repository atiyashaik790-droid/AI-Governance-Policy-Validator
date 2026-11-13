"""Workspace management only; mutations reuse the Phase B transaction owners."""

import re
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import Field, StrictBool
from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from ..dependencies import DB, USER
from ..models import Assignment, Policy, Version
from ..models_multi_policy import WorkspacePolicyState as State, WorkspacePolicyAssignment as Pin, WorkspacePolicyAssignmentEvent as Event
from ..repositories import serialize
from ..schemas import StrictModel
from ..security import Identity, require_role
from ..services import policy_sets as domain

router = APIRouter(prefix="/api/v2/workspace", tags=["Workspace policy management"])


class ModeChange(StrictModel):
    mode: Literal["LEGACY", "MULTI"]
    seed_legacy_assignment: StrictBool | None = None
    legacy_version_id: str | None = Field(None, min_length=1, max_length=36)


class AssignmentChange(StrictModel):
    active: StrictBool
    version_id: str | None = Field(None, min_length=1, max_length=36)


def revision_header(value):
    if value is None:
        raise HTTPException(428, "POLICY_SET_PRECONDITION_REQUIRED")
    # A single strong workspace ETag is required; wildcard/weak validators cannot fence writes.
    if not re.fullmatch(r'"[1-9][0-9]{0,18}"', value):
        raise HTTPException(412, "POLICY_SET_PRECONDITION_FAILED")
    return value[1:-1]


def etag(response, revision):
    response.headers["ETag"] = f'"{revision}"'


def read_state(db, user):
    # Explicit SQLite read transaction and SQL Server range locks keep the state,
    # counts and page coherent without initializing state or emitting GET events.
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")
    available = domain.schema_006(db)
    state = db.scalar(select(State).where(State.tenant == user.tenant)
                      .with_hint(State, "WITH (HOLDLOCK)", "mssql")) if available else None
    return available, state.mode if state else "LEGACY", state.set_revision if state else 1


def active_count(db, user, mode):
    if mode == "MULTI":
        return db.scalar(select(func.count()).select_from(Pin).where(Pin.tenant == user.tenant, Pin.active == true()))
    return db.scalar(select(func.count()).select_from(Assignment)
                     .join(Version, Version.id == Assignment.version_id)
                     .join(Policy, Policy.id == Version.policy_id)
                     .where(Assignment.tenant == user.tenant, Version.tenant == user.tenant,
                            Policy.tenant == user.tenant, Policy.enabled == 1,
                            Policy.status.not_in(["ARCHIVED", "DELETED"])))


@router.get("/policy-state")
def policy_state(response: Response, db: Session = DB, user: Identity = USER):
    available, mode, revision = read_state(db, user)
    if available:
        etag(response, revision)
    return {"mode": mode, "multi_policy_available": available,
            "set_revision": revision if available else None, "active_policy_count": active_count(db, user, mode)}


@router.put("/policy-mode")
def policy_mode(payload: ModeChange, response: Response, db: Session = DB, user: Identity = USER,
                if_match: str | None = Header(None, alias="If-Match")):
    require_role(user, "Admin")
    revision = domain.change_mode(db, user, payload.mode, expected_revision=revision_header(if_match),
                                  seed_legacy_assignment=payload.seed_legacy_assignment, legacy_version_id=payload.legacy_version_id)
    etag(response, revision)
    return {"set_revision": revision}


@router.put("/policy-assignments/{policy_id}")
def policy_assignment(policy_id: str, payload: AssignmentChange, response: Response, db: Session = DB, user: Identity = USER,
                      if_match: str | None = Header(None, alias="If-Match")):
    require_role(user, "Admin")
    revision = domain.change_assignment(db, user, policy_id, active=payload.active, version_id=payload.version_id,
                                        expected_revision=revision_header(if_match))
    etag(response, revision)
    return {"set_revision": revision}


def page(db, user, response, model, offset, limit):
    available, mode, revision = read_state(db, user)
    if not available:
        raise HTTPException(503, "SCHEMA_006_REQUIRED")
    query = select(model).where(model.tenant == user.tenant)
    total = db.scalar(select(func.count()).select_from(model).where(model.tenant == user.tenant))
    ordering = (Pin.policy_id,) if model is Pin else (Event.set_revision.desc(), Event.event_ordinal.desc(), Event.id)
    items = [{k: v for k, v in serialize(row).items() if k != "tenant"}
             for row in db.scalars(query.order_by(*ordering).offset(offset).limit(limit))]
    if model is Pin:
        for item in items:
            item["version"] = db.scalar(select(Version.number).where(Version.tenant == user.tenant,
                Version.policy_id == item["policy_id"], Version.id == item["version_id"]))
    etag(response, revision)
    return {"items": items, "total": total, "offset": offset, "limit": limit,
            "set_revision": revision, "mode": mode, "active_policy_count": active_count(db, user, mode)}


@router.get("/policy-assignments")
def policy_assignments(response: Response, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                       db: Session = DB, user: Identity = USER):
    return page(db, user, response, Pin, offset, limit)


@router.get("/policy-assignment-events")
def policy_assignment_events(response: Response, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                             db: Session = DB, user: Identity = USER):
    return page(db, user, response, Event, offset, limit)
