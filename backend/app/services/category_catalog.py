"""Keep draft custom rules and the tenant category catalog consistent."""

import json

from fastapi import HTTPException
from sqlalchemy import delete, inspect, select

from ..models import GovernanceCategory, PolicyCategory


def sync_draft_categories(db, tenant, policy_id, document):
    connection = db.connection()
    schema = "dbo" if connection.dialect.name == "mssql" else None
    if not inspect(connection).has_table("policy_categories", schema=schema):
        return
    desired = {rule.id: rule for rule in document.custom_categories}
    current = {
        association.category_id: association
        for association in db.scalars(select(PolicyCategory).where(PolicyCategory.tenant == tenant, PolicyCategory.policy_id == policy_id))
    }
    for category_id, rule in desired.items():
        category = db.get(GovernanceCategory, category_id)
        if category is None:
            category = GovernanceCategory(
                id=category_id,
                tenant=tenant,
                name=rule.name,
                description=rule.description,
                enabled=int(rule.enabled),
                action=rule.action,
                detector=rule.detection,
                values_json=json.dumps(rule.values),
            )
            db.add(category)
            db.flush()
        elif category.tenant != tenant or category.builtin:
            raise HTTPException(409, "Custom category ID belongs to another catalog entry")
        else:
            existing = (
                category.name,
                category.description,
                bool(category.enabled),
                category.action,
                category.detector,
                json.loads(category.values_json),
            )
            proposed = (rule.name, rule.description, rule.enabled, rule.action, rule.detection, rule.values)
            if existing != proposed:
                other_policy = db.scalar(
                    select(PolicyCategory.policy_id)
                    .where(PolicyCategory.category_id == category_id, PolicyCategory.policy_id != policy_id)
                    .limit(1)
                )
                if other_policy:
                    raise HTTPException(409, "Shared category must be unassigned before editing its rule")
                category.name, category.description = rule.name, rule.description
                category.enabled, category.action = int(rule.enabled), rule.action
                category.detector, category.values_json = rule.detection, json.dumps(rule.values)
                category.revision += 1
        if category_id not in current:
            db.add(PolicyCategory(tenant=tenant, policy_id=policy_id, category_id=category_id))
    for category_id, association in current.items():
        if category_id not in desired:
            category = db.get(GovernanceCategory, category_id)
            if category is not None and not category.builtin:
                db.delete(association)


def clear_policy_categories(db, tenant, policy_id):
    connection = db.connection()
    schema = "dbo" if connection.dialect.name == "mssql" else None
    if inspect(connection).has_table("policy_categories", schema=schema):
        db.execute(delete(PolicyCategory).where(PolicyCategory.tenant == tenant, PolicyCategory.policy_id == policy_id))
