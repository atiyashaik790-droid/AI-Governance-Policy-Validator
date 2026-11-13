"""Versioned metadata-only history and request/policy accounting."""

import json
from fastapi import HTTPException
from sqlalchemy import select, func

from ..exports import date_bounds
from ..protected_reviews import metadata as content_metadata, review_context
from ..models import Execution, Review, ReviewNote, ReviewAssignment, Version
from ..models_multi_policy import Execution006, ExecutionPolicyEvidence as Evidence
from ..routers.workspace_v2 import read_state, active_count
from ..security import require_role
from .multi_policy_evidence import local_metadata, policy_metadata, reasons
from .audit_attribution import execution_attribution, policy_label
from .dashboard_findings import aggregate as dashboard_aggregate
from .reviews import get_review, sanitize_review_reason


def context(db, user):
    available, mode, revision = read_state(db, user)
    return Execution006 if available else Execution, mode, revision


def parsed(value):
    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


def evidence_view(db, user, row):
    data = parsed(row.evidence_json)
    version = db.scalar(select(Version.number).where(Version.tenant == user.tenant, Version.policy_id == row.policy_id, Version.id == row.version_id))
    return {"policy_name": policy_label(db, user.tenant, row.policy_id, version_id=row.version_id)["name"], "policy_id": row.policy_id, "version_id": row.version_id, "version": version, "document_sha256": row.document_sha256,
            "set_revision": row.set_revision, "decision": row.effective_decision, "inspection_status": row.inspection_status,
            "failure_reasons": reasons(data.get("failure_reasons")),
            "inspections": {stage: policy_metadata(data[stage]) for stage in ("input", "output") if isinstance(data.get(stage), dict)}}


def execution_view(db, user, row, *, detail=False):
    mode = getattr(row, "execution_mode", "LEGACY")
    data = parsed(row.metadata_json)
    count = db.scalar(select(func.count()).select_from(Evidence).where(Evidence.tenant == user.tenant, Evidence.execution_id == row.id)) if mode == "MULTI" else 1
    captured = data.get("captured_policy_count")
    if type(captured) is not int or captured < 1:
        captured = max([v["policy_count"] for v in data.values() if isinstance(v, dict) and type(v.get("policy_count")) is int and v["policy_count"] > 0] or [count])
    result = {"schema_version": "2.0", "request_id": row.id, "timestamp": row.created, "actor": row.actor,
              "decision": row.decision, "execution_mode": mode, "policy_evaluation_count": count,
              "captured_policy_count": captured if mode == "MULTI" else 1,
              "cardinality_complete": mode == "LEGACY" or count > 0 and count == captured,
              "legacy": {"policy_id": row.policy_id, "version": row.version} if mode == "LEGACY" else None}
    result.update(execution_attribution(db, user, row))
    if detail:
        if isinstance(data.get("attachment"), dict):
            from ..schemas import AttachmentMetadata
            try:
                result["attachment"] = AttachmentMetadata.model_validate(data["attachment"]).model_dump()
            except ValueError:
                pass
        result["failure_reasons"] = reasons(data.get("failure_reasons"))
        result["policy_evidence"] = [evidence_view(db, user, e) for e in db.scalars(select(Evidence).where(
            Evidence.tenant == user.tenant, Evidence.execution_id == row.id).order_by(Evidence.policy_id))] if mode == "MULTI" else []
        if mode == "LEGACY":
            result["inspections"] = {stage: local_metadata(data[stage]) for stage in ("input", "output") if isinstance(data.get(stage), dict)}
    return result


def execution(db, user, identifier):
    model, _, _ = context(db, user)
    row = db.scalar(select(model).where(model.tenant == user.tenant, model.id == identifier))
    if row is None:
        raise HTTPException(404, "Execution not found")
    return execution_view(db, user, row, detail=True)


def executions(db, user, offset, limit, start=None, end=None):
    model, _, _ = context(db, user)
    first, last = date_bounds(start, end)
    filters = (model.tenant == user.tenant, model.created >= first, model.created < last)
    total = db.scalar(select(func.count()).select_from(model).where(*filters))
    rows = db.scalars(select(model).where(*filters).order_by(model.created.desc(), model.id).offset(offset).limit(limit))
    return {"schema_version": "2.0", "items": [execution_view(db, user, row) for row in rows], "total": total, "offset": offset, "limit": limit}


def overview(db, user, start=None, end=None):
    model, mode, _ = context(db, user)
    first, last = date_bounds(start, end)
    filters = (model.tenant == user.tenant, model.created >= first, model.created < last)
    decisions = dict.fromkeys(("ALLOW", "REDACT", "HUMAN_REVIEW", "BLOCK"), 0)
    decisions.update(dict(db.execute(select(model.decision, func.count()).where(*filters).group_by(model.decision)).all()))
    requests = sum(decisions.values())
    if model is Execution006:
        modes = dict(db.execute(select(model.execution_mode, func.count()).where(*filters).group_by(model.execution_mode)).all())
        policy_count = db.scalar(select(func.count()).select_from(Evidence).join(model, model.id == Evidence.execution_id)
                                 .where(*filters, Evidence.tenant == user.tenant)) + modes.get("LEGACY", 0)
    else:
        modes, policy_count = {"LEGACY": requests}, requests
    analytics = dashboard_aggregate(db.scalars(select(model).where(*filters).order_by(model.created, model.id)).yield_per(500))
    return {"schema_version": "2.0", "request_count": requests, "policy_evaluation_count": policy_count, "decisions": decisions,
            "requests_by_mode": {m: modes.get(m, 0) for m in ("LEGACY", "MULTI")}, "workspace_mode": mode,
            "active_policy_count": active_count(db, user, mode), "pending_reviews": db.scalar(select(func.count()).select_from(Review)
                .where(Review.tenant == user.tenant, Review.status == "PENDING")), "window": {"start": first, "end_exclusive": last},
            "counting": "Requests count once; each captured policy evidence row counts once; legacy requests count as one policy evaluation",
            "compliance": analytics}


def reviews(db, user, offset, limit):
    require_role(user, "Admin", "Reviewer", "Auditor", "Developer", "Policy Owner")
    model, _, _ = context(db, user)
    filters = [Review.tenant == user.tenant, model.tenant == user.tenant]
    if user.role in {"Developer", "Policy Owner"}:
        filters.append(model.actor == user.user)
    query = select(Review, model).join(model, Review.execution_id == model.id).where(*filters)
    total = db.scalar(select(func.count()).select_from(Review).join(model, Review.execution_id == model.id).where(*filters))
    rows = db.execute(query.order_by(Review.created.desc(), Review.id).offset(offset).limit(limit)).all()
    return {"schema_version": "2.0", "total": total, "offset": offset, "limit": limit,
            "items": [{"review_id": review.id, "status": review.status, "created": review.created,
                       "execution": execution_view(db, user, row)} for review, row in rows]}


def review_detail(db, user, identifier):
    review = get_review(db, user, identifier)
    detail = execution(db, user, review.execution_id)
    assignment = db.scalar(select(ReviewAssignment).where(ReviewAssignment.id == review.id, ReviewAssignment.tenant == user.tenant))
    notes = db.scalars(select(ReviewNote).where(ReviewNote.review_id == review.id, ReviewNote.tenant == user.tenant).order_by(ReviewNote.created, ReviewNote.id))
    model, _, _ = context(db, user)
    row = db.scalar(select(model).where(model.tenant == user.tenant, model.id == review.execution_id))
    return {"schema_version": "2.0", "review_id": review.id, "status": review.status, "execution": detail,
            **review_context(row),
            "row_version": review.row_version, "created": review.created, "protected_content": content_metadata(db, user, review),
            "contributing_policy_ids": [e["policy_id"] for e in detail["policy_evidence"] if e["decision"] == "HUMAN_REVIEW"],
            "assigned_reviewer": assignment.assigned_reviewer if assignment else None,
            "decision_history": [{"actor": n.actor, "action": n.action, "created": n.created, "reason": sanitize_review_reason(n.reason)} for n in notes],
            "instruction": "Original content is excluded from ordinary metadata. Approval requires resubmission under all current policies; no content is released by review."}
