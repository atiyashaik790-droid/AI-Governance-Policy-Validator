"""Explicit maintenance for expired operational bookkeeping; business history is preserved."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, delete, update
from sqlalchemy.orm import Session
from .models import DemoSession, RateBucket, InferenceUsage, ExportJob, now
from .config import settings


def plan(db: Session, tenant: str | None = None) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.retention_days)).isoformat()
    session_filter = [DemoSession.expires < cutoff]
    usage_filter = [InferenceUsage.status == "RESERVED", InferenceUsage.expires <= now()]
    export_filter = [ExportJob.state.in_(("FAILED", "PENDING", "UPLOADING")), ExportJob.lease_until <= now()]
    if tenant:
        session_filter.append(DemoSession.tenant == tenant)
        usage_filter.append(InferenceUsage.tenant == tenant)
        export_filter.append(ExportJob.tenant == tenant)

    def count(model, predicates):
        return db.scalar(select(func.count()).select_from(model).where(*predicates))

    return {
        "mode": "READ_ONLY_PLAN",
        "session_cutoff": cutoff,
        "expired_sessions": count(DemoSession, session_filter),
        "expired_inference_leases": count(InferenceUsage, usage_filter),
        "exports_requiring_inspection": count(ExportJob, export_filter),
        # Bucket IDs are opaque; only an operator can clean expired buckets globally.
        "expired_rate_buckets_global": None if tenant else count(RateBucket, [RateBucket.expires < now(), RateBucket.used > 0]),
        "preserved": [
            "policies",
            "versions",
            "audit",
            "executions",
            "reviews",
            "feedback",
            "exports",
            "export snapshots",
            "permanent idempotency markers",
        ],
    }


def apply_bookkeeping(db: Session) -> dict:
    """Operator-only transaction; never invoked by HTTP or application startup."""
    result = plan(db)
    cutoff = result["session_cutoff"]
    sessions = db.execute(delete(DemoSession).where(DemoSession.expires < cutoff)).rowcount
    buckets = db.execute(delete(RateBucket).where(RateBucket.expires < now(), RateBucket.used > 0)).rowcount
    leases = db.execute(
        update(InferenceUsage)
        .where(InferenceUsage.status == "RESERVED", InferenceUsage.expires <= now())
        .values(status="EXPIRED", finished=now())
    ).rowcount
    db.commit()
    return {
        "mode": "EXPIRED_BOOKKEEPING_APPLIED",
        "sessions_removed": sessions,
        "rate_buckets_removed": buckets,
        "leases_expired": leases,
        "business_history_deleted": False,
        "storage_operations": 0,
    }
