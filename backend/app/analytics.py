"""Portable database aggregation with a bounded recent metadata sample."""

import json
from sqlalchemy import select, func, case, Float, cast, or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mssql import NVARCHAR
from .models import Execution, Policy, Review, Version, Assignment
from .exports import date_bounds
from .security import Identity


def overview(db: Session, user: Identity, start: str | None, end: str | None) -> dict:
    first, last = date_bounds(start, end)
    filters = (Execution.tenant == user.tenant, Execution.created >= first, Execution.created < last)
    decisions = dict.fromkeys(("ALLOW", "REDACT", "BLOCK", "HUMAN_REVIEW"), 0)
    decisions.update(dict(db.execute(select(Execution.decision, func.count()).where(*filters).group_by(Execution.decision)).all()))
    dialect = db.bind.dialect.name

    def value(path):
        function = func.json_value if dialect == "mssql" else func.json_extract
        document = cast(Execution.metadata_json, NVARCHAR(None)) if dialect == "mssql" else Execution.metadata_json
        return function(document, path)

    contributions, violations = {}, {}
    for category in ("secret_detection", "pii_detection", "moderation", "blocked_keywords"):
        input_status = value(f"$.input.breakdown.{category}")
        output_status = value(f"$.output.breakdown.{category}")
        failed_control = or_(input_status.in_(("FAILED", "UNKNOWN")), output_status.in_(("FAILED", "UNKNOWN")))
        # A control contributes only when neither inspected stage failed or was unknown.
        contribution = case(
            (failed_control, 0),
            else_=func.coalesce(value(f"$.output.contributions.{category}"), value(f"$.input.contributions.{category}")),
        )
        weight, failed = db.execute(
            select(
                func.coalesce(func.sum(cast(contribution, Float)), 0),
                func.coalesce(func.sum(case((failed_control, 1), else_=0)), 0),
            ).where(*filters)
        ).one()
        if weight:
            contributions[category] = weight
        if failed:
            violations[category] = failed
    recent = list(db.scalars(select(Execution).where(*filters).order_by(Execution.created.desc(), Execution.id.desc()).limit(100)))
    trends = []
    for row in reversed(recent):
        metadata = json.loads(row.metadata_json)
        stages = [metadata[stage] for stage in ("input", "output") if metadata.get(stage)]
        if stages:
            trends.append({"date": row.created[:10], "score": min(stage["score"] for stage in stages)})
    assignment = db.get(Assignment, user.tenant)
    active = db.get(Version, assignment.version_id) if assignment else None
    active_policy = db.get(Policy, active.policy_id) if active and active.tenant == user.tenant else None
    return {
        "total_policies": db.scalar(
            select(func.count()).select_from(Policy).where(Policy.tenant == user.tenant, Policy.status != "DELETED")
        ),
        "active_policies": int(bool(active_policy and active_policy.enabled and active_policy.status not in ("ARCHIVED", "DELETED"))),
        "total_validations": sum(decisions.values()),
        "decisions": decisions,
        "trends": trends,
        "violations": violations,
        "contributions": contributions,
        "active_policy": {"id": active.policy_id, "version": active.number} if active_policy else None,
        "pending_reviews": db.scalar(
            select(func.count()).select_from(Review).where(Review.tenant == user.tenant, Review.status == "PENDING")
        ),
        "window": {"start": first, "end_exclusive": last},
        "trend_sample_limit": 100,
        "aggregation": "Each execution counts once per control if either input or output failed or was unknown",
    }
