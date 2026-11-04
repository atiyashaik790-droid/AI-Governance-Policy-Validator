"""Transactional export snapshots and explicit, bounded recovery; no automatic retries."""

import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, update, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .models import Export, ExportJob, Execution, Audit, now
from .schemas import ExportRequest
from .security import Identity
from . import providers
from .usage import claim_action


def date_bounds(start: str | None, end: str | None) -> tuple[str, str]:
    try:
        last = date.fromisoformat(end) if end else datetime.now(timezone.utc).date()
        first = date.fromisoformat(start) if start else last - timedelta(days=89)
        if first > last or (last - first).days > 365:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "Use valid ISO dates in a window of at most 366 days") from None
    return first.isoformat(), (last + timedelta(days=1)).isoformat()


def public_report(db: Session, report: Export) -> dict:
    job = db.get(ExportJob, report.id)
    return {
        "id": report.id,
        "tenant": report.tenant,
        "created": report.created,
        "status": report.status,
        "path": report.path,
        **({"state": job.state, "attempts": job.attempts, "error_code": job.error_code, "sha256": job.content_hash} if job else {}),
    }


def create(db: Session, user: Identity, payload: ExportRequest) -> dict:
    # Original request, rather than resolved dates, defines duplicate-request semantics.
    request_hash = hashlib.sha256(json.dumps(payload.model_dump(exclude={"idempotency_key"}), sort_keys=True).encode()).hexdigest()
    key = payload.idempotency_key
    if key:
        existing = db.scalar(select(ExportJob).where(ExportJob.tenant == user.tenant, ExportJob.idempotency_key == key))
        if existing:
            if existing.request_hash != request_hash:
                raise HTTPException(409, "Idempotency key already used for a different export request")
            return public_report(db, db.get(Export, existing.id))
    first, last = date_bounds(payload.start_date, payload.end_date)
    claim_action(db, user, "export", settings.export_per_minute)
    rows = list(
        db.scalars(
            select(Execution)
            .where(Execution.tenant == user.tenant, Execution.created >= first, Execution.created < last)
            .order_by(Execution.created, Execution.id)
            .limit(settings.export_max_records + 1)
        )
    )
    if len(rows) > settings.export_max_records:
        raise HTTPException(413, "Export exceeds record limit; select a smaller date range")
    metadata = [
        {"request_id": row.id, "timestamp": row.created, "decision": row.decision, "policy_id": row.policy_id, "version": row.version}
        for row in rows
    ]
    if payload.format == "json":
        content = json.dumps(metadata)
    else:
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=["request_id", "timestamp", "decision", "policy_id", "version"])
        writer.writeheader()
        writer.writerows(metadata)
        content = stream.getvalue()
    if len(content.encode()) > settings.export_max_bytes:
        raise HTTPException(413, "Export exceeds byte limit; select a smaller date range")
    report = Export(tenant=user.tenant, status="PENDING")
    try:
        db.add(report)
        db.flush()
        report.path = f"governance-reports/{datetime.now(timezone.utc):%Y/%m/%d}/{report.id}.{payload.format}"
        job = ExportJob(
            id=report.id,
            tenant=user.tenant,
            idempotency_key=key or report.id,
            request_hash=request_hash,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            content=content,
        )
        db.add(job)
        db.add(Audit(tenant=user.tenant, actor=user.user, action="report.PENDING", resource=report.id))
        db.commit()  # Durable SQL snapshot exists before any ADLS operation.
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(ExportJob).where(ExportJob.tenant == user.tenant, ExportJob.idempotency_key == key)) if key else None
        if existing and existing.request_hash == request_hash:
            return public_report(db, db.get(Export, existing.id))
        raise HTTPException(409, "Concurrent export request conflict; inspect export history") from None
    return process(db, user, report.id, reconcile=False)


def process(db: Session, user: Identity, identifier: str, reconcile: bool = True) -> dict:
    report = db.scalar(select(Export).where(Export.id == identifier, Export.tenant == user.tenant))
    job = db.scalar(select(ExportJob).where(ExportJob.id == identifier, ExportJob.tenant == user.tenant))
    if not report or not job:
        raise HTTPException(404, "Recoverable export not found; historical records are preserved")
    if job.state == "COMPLETED":
        return public_report(db, report)
    if reconcile:
        claim_action(db, user, "export-reconcile", settings.export_per_minute)
    current = now()
    if job.state == "UPLOADING" and job.lease_until > current:
        raise HTTPException(409, "Export is in progress; wait for its recovery lease to expire")
    if job.attempts >= settings.export_max_attempts and not reconcile:
        raise HTTPException(409, "Export attempt limit reached; reconcile existing storage evidence")
    # Conditional SQL claim allows only one owner to perform storage I/O.
    lease = (datetime.now(timezone.utc) + timedelta(seconds=settings.export_lease_seconds)).isoformat()
    claimed = db.execute(
        update(ExportJob)
        .where(
            ExportJob.id == identifier,
            ExportJob.tenant == user.tenant,
            ExportJob.state != "COMPLETED",
            or_(ExportJob.state != "UPLOADING", ExportJob.lease_until <= current),
            ExportJob.attempts == job.attempts,
        )
        .values(state="UPLOADING", lease_until=lease, attempts=ExportJob.attempts + 1, updated=current)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Export recovery already claimed")
    report.status = "UPLOADING"
    db.commit()
    db.refresh(job)
    attempts = job.attempts
    try:
        # Recovery always checks exact bounded bytes before a retry. No overwrite.
        digest = providers.report_digest(report.path, settings.export_max_bytes) if reconcile else None
        if digest is not None:
            if digest != job.content_hash:
                raise providers.ProviderUnavailable("Export content differs", code="EXPORT_CONTENT_MISMATCH")
        elif reconcile and attempts > settings.export_max_attempts:
            raise providers.ProviderUnavailable("Export attempt limit", code="EXPORT_ATTEMPT_LIMIT")
        else:
            providers.upload_report(report.path, job.content)
        state, status, error = "COMPLETED", "SUCCEEDED", ""
    except Exception as exception:
        state, status = "FAILED", "FAILED"
        error = (
            exception.diagnostics.get("code", "EXPORT_STORAGE_UNAVAILABLE")
            if isinstance(exception, providers.ProviderUnavailable)
            else "EXPORT_STORAGE_UNAVAILABLE"
        )
    # If this commit fails after upload, the earlier durable UPLOADING row survives.
    # Reconciliation after lease expiry verifies its checksum; it never blindly replays.
    finalized = db.execute(
        update(ExportJob)
        .where(ExportJob.id == identifier, ExportJob.tenant == user.tenant, ExportJob.state == "UPLOADING", ExportJob.lease_until == lease)
        .values(state=state, error_code=error, updated=now(), lease_until="")
    )
    if finalized.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Export ownership changed; inspect durable recovery state")
    report.status = status
    db.add(Audit(tenant=user.tenant, actor=user.user, action=f"report.{status}", resource=report.id))
    db.commit()
    return public_report(db, report)
