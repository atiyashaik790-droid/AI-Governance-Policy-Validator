"""Versioned immutable snapshots; reuse existing ADLS claim/reconciliation code."""

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError

from .. import exports
from ..config import settings
from ..models import Export, ExportJob, Audit
from ..usage import claim_action
from . import reporting_v2

CSV_FIELDS = ("schema_version", "row_type", "request_id", "timestamp", "execution_mode", "request_decision", "policy_id",
              "version_id", "version", "document_sha256", "policy_decision", "inspection_status", "failure_reasons", "inspections")


def versioned_contract():
    # A legacy operator may already have used a key beginning "v2:". Its JSON
    # array/legacy CSV snapshot must never be relabeled as a versioned envelope.
    return (ExportJob.idempotency_key.startswith("v2:"), or_(
        ExportJob.content.startswith('{"policy_evaluation_count": '), ExportJob.content.startswith(",".join(CSV_FIELDS))))


def content_for(requests, first, last, format):
    if format == "json":
        return json.dumps({"schema_version": "2.0", "window": {"start": first, "end_exclusive": last},
                           "request_count": len(requests), "policy_evaluation_count": sum(r["policy_evaluation_count"] for r in requests),
                           "requests": requests}, sort_keys=True)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for request in requests:
        common = {"schema_version": "2.0", "request_id": request["request_id"], "timestamp": request["timestamp"], "execution_mode": request["execution_mode"]}
        writer.writerow({**common, "row_type": "request", "request_decision": request["decision"],
                         **(request["legacy"] or {}), "failure_reasons": json.dumps(request.get("failure_reasons", [])),
                         "inspections": json.dumps(request.get("inspections", {}))})
        for evidence in request["policy_evidence"]:
            writer.writerow({**common, "row_type": "policy_evidence", "policy_decision": evidence["decision"],
                             **{key: evidence[key] for key in ("policy_id", "version_id", "version", "document_sha256", "inspection_status")},
                             "failure_reasons": json.dumps(evidence["failure_reasons"]), "inspections": json.dumps(evidence["inspections"])})
    return stream.getvalue()


def report(db, user, identifier):
    row = db.scalar(select(Export).join(ExportJob, ExportJob.id == Export.id).where(
        Export.tenant == user.tenant, Export.id == identifier, ExportJob.tenant == user.tenant, *versioned_contract()))
    if row is None:
        raise HTTPException(404, "Versioned export not found")
    return {"schema_version": "2.0", **exports.public_report(db, row)}


def create(db, user, payload):
    request_hash = hashlib.sha256(json.dumps({"schema_version": "2.0", **payload.model_dump(exclude={"idempotency_key"})}, sort_keys=True).encode()).hexdigest()
    key = "v2:" + (hashlib.sha256(payload.idempotency_key.encode()).hexdigest() if payload.idempotency_key else str(uuid4()))
    existing = db.scalar(select(ExportJob).where(ExportJob.tenant == user.tenant, ExportJob.idempotency_key == key))
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key already used for a different versioned export")
        return report(db, user, existing.id)
    first, last = exports.date_bounds(payload.start_date, payload.end_date)
    claim_action(db, user, "export", settings.export_per_minute)
    model, _, _ = reporting_v2.context(db, user)
    rows = list(db.scalars(select(model).where(model.tenant == user.tenant, model.created >= first, model.created < last)
                           .order_by(model.created, model.id).limit(settings.export_max_records + 1)))
    if len(rows) > settings.export_max_records:
        raise HTTPException(413, "Export exceeds request limit; select a smaller date range")
    requests = [reporting_v2.execution_view(db, user, row, detail=True) for row in rows]
    content = content_for(requests, first, last, payload.format)
    if len(content.encode()) > settings.export_max_bytes:
        raise HTTPException(413, "Export exceeds byte limit; select a smaller date range")
    row = Export(tenant=user.tenant, status="PENDING")
    try:
        db.add(row)
        db.flush()
        row.path = f"governance-reports/v2/{datetime.now(timezone.utc):%Y/%m/%d}/{row.id}.{payload.format}"
        db.add(ExportJob(id=row.id, tenant=user.tenant, idempotency_key=key, request_hash=request_hash,
                         content_hash=hashlib.sha256(content.encode()).hexdigest(), content=content))
        db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action="report.v2.PENDING", resource=row.id))
        db.commit()  # Preserve the exact snapshot before storage; never rebuild during recovery.
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(ExportJob).where(ExportJob.tenant == user.tenant, ExportJob.idempotency_key == key))
        if existing and existing.request_hash == request_hash:
            return report(db, user, existing.id)
        raise HTTPException(409, "Concurrent versioned export conflict") from None
    exports.process(db, user, row.id, reconcile=False)
    return report(db, user, row.id)


def reconcile(db, user, identifier):
    report(db, user, identifier)
    exports.process(db, user, identifier, reconcile=True)
    return report(db, user, identifier)
