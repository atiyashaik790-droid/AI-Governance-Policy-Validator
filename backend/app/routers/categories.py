"""Tenant-scoped category catalog and draft policy associations."""

import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import Field, StrictBool
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from ..dependencies import DB, USER
from ..models import GovernanceCategory, Policy, PolicyCategory
from ..repositories import record_audit_event
from ..schemas import CustomCategory, PolicyDocument, StrictModel
from ..security import Identity, require_role


def category_schema(db: Session = DB, user: Identity = USER):
    require_role(user, *READ_ROLES)
    connection = db.connection()
    schema = "dbo" if connection.dialect.name == "mssql" else None
    if not inspect(connection).has_table("governance_categories", schema=schema) or not inspect(connection).has_table(
        "policy_categories", schema=schema
    ):
        raise HTTPException(503, "Category schema revision 009 is required")


router = APIRouter(prefix="/api/categories", tags=["Governance categories"], dependencies=[Depends(category_schema)])
READ_ROLES = ("Admin", "Reviewer", "Auditor", "Developer", "Policy Owner")


class CategoryInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    enabled: StrictBool = True
    action: Literal["BLOCK", "REDACT", "HUMAN_REVIEW"] = "BLOCK"
    detection: Literal["keyword", "regex"] = "keyword"
    values: list[str] = Field(min_length=1, max_length=10)


def custom_rule(category):
    return CustomCategory.model_validate(
        {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "enabled": bool(category.enabled),
            "action": category.action,
            "detection": category.detector,
            "values": json.loads(category.values_json),
        }
    )


def category_data(db, category, tenant):
    associations = db.scalars(
        select(PolicyCategory.policy_id)
        .where(PolicyCategory.tenant == tenant, PolicyCategory.category_id == category.id)
        .order_by(PolicyCategory.policy_id)
    ).all()
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "builtin": bool(category.builtin),
        "enabled": bool(category.enabled),
        "detection": category.detector,
        "action": category.action,
        "values": [] if category.builtin else json.loads(category.values_json),
        "revision": category.revision,
        "policy_ids": associations,
    }


def get_category(db, user, category_id):
    category = db.scalar(
        select(GovernanceCategory).where(
            GovernanceCategory.id == category_id,
            GovernanceCategory.tenant.in_(["*", user.tenant]),
        )
    )
    if category is None:
        raise HTTPException(404, "Category not found")
    return category


def check_revision(category, if_match):
    if if_match is None:
        raise HTTPException(428, "CATEGORY_PRECONDITION_REQUIRED")
    if if_match != f'"{category.revision}"':
        raise HTTPException(412, "CATEGORY_PRECONDITION_FAILED")


def validate_input(payload, category_id):
    return CustomCategory.model_validate({"id": category_id, **payload.model_dump()})


@router.get("")
def list_categories(
    search: str = Query("", max_length=120),
    enabled: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = DB,
    user: Identity = USER,
):
    require_role(user, *READ_ROLES)
    query = select(GovernanceCategory).where(GovernanceCategory.tenant.in_(["*", user.tenant]))
    if search:
        query = query.where(GovernanceCategory.name.icontains(search, autoescape=True))
    if enabled is not None:
        query = query.where(GovernanceCategory.enabled == int(enabled))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    categories = db.scalars(
        query.order_by(GovernanceCategory.builtin.desc(), GovernanceCategory.name, GovernanceCategory.id).offset(offset).limit(limit)
    ).all()
    return {
        "items": [category_data(db, category, user.tenant) for category in categories],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{category_id}")
def view_category(category_id: str, response: Response, db: Session = DB, user: Identity = USER):
    require_role(user, *READ_ROLES)
    category = get_category(db, user, category_id)
    response.headers["ETag"] = f'"{category.revision}"'
    return category_data(db, category, user.tenant)


@router.post("", status_code=201)
def create_category(payload: CategoryInput, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin")
    category_id = str(uuid.uuid4())
    rule = validate_input(payload, category_id)
    if db.scalar(
        select(GovernanceCategory.id).where(
            GovernanceCategory.tenant.in_(["*", user.tenant]),
            func.lower(GovernanceCategory.name) == rule.name.casefold(),
        )
    ):
        raise HTTPException(409, "Category name already exists")
    category = GovernanceCategory(
        id=category_id,
        tenant=user.tenant,
        name=rule.name,
        description=rule.description,
        enabled=int(rule.enabled),
        action=rule.action,
        detector=rule.detection,
        values_json=json.dumps(rule.values),
    )
    db.add(category)
    db.flush()
    record_audit_event(db, user, "category.created", category.id)
    return category_data(db, category, user.tenant)


@router.put("/{category_id}")
def update_category(
    category_id: str,
    payload: CategoryInput,
    response: Response,
    db: Session = DB,
    user: Identity = USER,
    if_match: str | None = Header(None, alias="If-Match"),
):
    require_role(user, "Admin")
    category = get_category(db, user, category_id)
    if category.builtin:
        raise HTTPException(403, "Built-in categories cannot be edited")
    check_revision(category, if_match)
    if db.scalar(select(PolicyCategory.category_id).where(PolicyCategory.category_id == category.id).limit(1)):
        raise HTTPException(409, "Unassign category from policies before editing")
    rule = validate_input(payload, category.id)
    duplicate = db.scalar(
        select(GovernanceCategory.id).where(
            GovernanceCategory.id != category.id,
            GovernanceCategory.tenant.in_(["*", user.tenant]),
            func.lower(GovernanceCategory.name) == rule.name.casefold(),
        )
    )
    if duplicate:
        raise HTTPException(409, "Category name already exists")
    category.name, category.description = rule.name, rule.description
    category.enabled, category.action = int(rule.enabled), rule.action
    category.detector, category.values_json = rule.detection, json.dumps(rule.values)
    category.revision += 1
    db.flush()
    record_audit_event(db, user, "category.updated", category.id)
    response.headers["ETag"] = f'"{category.revision}"'
    return category_data(db, category, user.tenant)


@router.delete("/{category_id}")
def delete_category(category_id: str, db: Session = DB, user: Identity = USER, if_match: str | None = Header(None, alias="If-Match")):
    require_role(user, "Admin")
    category = get_category(db, user, category_id)
    if category.builtin:
        raise HTTPException(403, "Built-in categories cannot be deleted")
    check_revision(category, if_match)
    if db.scalar(select(PolicyCategory.category_id).where(PolicyCategory.category_id == category.id).limit(1)):
        raise HTTPException(409, "Referenced category cannot be deleted")
    record_audit_event(db, user, "category.deleted", category.id)
    db.delete(category)
    return {"deleted": True}


@router.put("/{category_id}/policies/{policy_id}")
def assign_category(category_id: str, policy_id: str, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin")
    category = get_category(db, user, category_id)
    policy = db.scalar(select(Policy).where(Policy.id == policy_id, Policy.tenant == user.tenant))
    if policy is None:
        raise HTTPException(404, "Policy not found")
    if policy.status != "DRAFT":
        raise HTTPException(409, "Only draft policies can change category associations")
    existing = db.get(PolicyCategory, (user.tenant, policy_id, category_id))
    if existing is None:
        if not category.builtin:
            document = PolicyDocument.model_validate_json(policy.draft)
            if all(item.id != category.id for item in document.custom_categories):
                document.custom_categories.append(custom_rule(category))
                policy.draft = document.model_dump_json()
                policy.revision += 1
        db.add(PolicyCategory(tenant=user.tenant, policy_id=policy_id, category_id=category_id))
        db.flush()
        record_audit_event(db, user, "category.policy_assigned", category.id)
    return category_data(db, category, user.tenant)


@router.delete("/{category_id}/policies/{policy_id}")
def unassign_category(category_id: str, policy_id: str, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin")
    category = get_category(db, user, category_id)
    policy = db.scalar(select(Policy).where(Policy.id == policy_id, Policy.tenant == user.tenant))
    if policy is None:
        raise HTTPException(404, "Policy not found")
    if policy.status != "DRAFT":
        raise HTTPException(409, "Only draft policies can change category associations")
    association = db.get(PolicyCategory, (user.tenant, policy_id, category_id))
    if association is not None:
        if not category.builtin:
            document = PolicyDocument.model_validate_json(policy.draft)
            document.custom_categories = [item for item in document.custom_categories if item.id != category.id]
            policy.draft = document.model_dump_json()
            policy.revision += 1
        db.delete(association)
        db.flush()
        record_audit_event(db, user, "category.policy_unassigned", category.id)
    return category_data(db, category, user.tenant)
