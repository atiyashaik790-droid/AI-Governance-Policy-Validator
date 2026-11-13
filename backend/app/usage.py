"""SQL-backed inference reservations; shared limits across workers, no extra service."""

import hashlib
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .models import RateBucket, InferenceUsage, now
from .security import Identity


def bucket_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def ensure_bucket(db: Session, key: str, expires: str) -> None:
    if db.get(RateBucket, key) is None:
        try:
            with db.begin_nested():
                db.add(RateBucket(id=key, used=0, expires=expires))
                db.flush()
        except IntegrityError:
            pass  # Another worker inserted the unique bucket; atomic UPDATE arbitrates.


def reserve(db: Session, user: Identity, *, commit: bool = True, gate_locked: bool = False, current: datetime | None = None) -> str:
    current = current or datetime.now(timezone.utc)
    minute = current.strftime("%Y-%m-%dT%H:%M")
    day = current.strftime("%Y-%m-%d")
    expires = (current + timedelta(days=2)).isoformat()
    # Fixed update order prevents workers acquiring shared locks in opposite order.
    limits = [
        (f"tenant:{user.tenant}:daily:{day}", settings.inference_daily_quota),
        (f"tenant:{user.tenant}:minute:{minute}", settings.inference_tenant_per_minute),
        (f"tenant:{user.tenant}:user:{user.user}:minute:{minute}", settings.inference_user_per_minute),
    ]
    try:
        # A permanent tenant gate serializes claims even across minute/day boundaries.
        if not gate_locked:
            gate = bucket_id(f"tenant:{user.tenant}:concurrency-gate")
            ensure_bucket(db, gate, expires)
            db.execute(update(RateBucket).where(RateBucket.id == gate).values(used=0, expires=expires))
        for value, limit in limits:
            key = bucket_id(value)
            ensure_bucket(db, key, expires)
            claimed = db.execute(update(RateBucket).where(RateBucket.id == key, RateBucket.used < limit).values(used=RateBucket.used + 1))
            if claimed.rowcount != 1:
                raise HTTPException(429, "Inference quota exhausted; wait for the next window", headers={"Retry-After": "60"})
        # Tenant/day row remains write-locked until commit, serializing lease claims.
        if gate_locked:
            active = 0
            for expiry in db.scalars(select(InferenceUsage.expires).where(InferenceUsage.tenant == user.tenant, InferenceUsage.status == "RESERVED")):
                try:
                    parsed = datetime.fromisoformat(expiry)
                    if parsed.tzinfo is None:
                        raise ValueError()
                except (TypeError, ValueError):
                    raise HTTPException(503, "INVALID_RESERVATION_EXPIRY") from None
                active += int(parsed > current)
        else:
            active = db.scalar(
                select(func.count())
                .select_from(InferenceUsage)
                .where(InferenceUsage.tenant == user.tenant, InferenceUsage.status == "RESERVED", InferenceUsage.expires > current.isoformat())
            )
        if active >= settings.inference_concurrency:
            raise HTTPException(429, "Concurrent inference limit reached", headers={"Retry-After": "5"})
        usage = InferenceUsage(
            tenant=user.tenant, actor=user.user, expires=(current + timedelta(seconds=settings.inference_deadline + 30)).isoformat()
        )
        db.add(usage)
        db.flush()
        identifier = usage.id
        if commit:
            db.commit()  # Reservation is durable before a provider can be called.
        return identifier
    except Exception:
        db.rollback()
        raise


def finish(db: Session, identifier: str, status: str, tokens: dict | None = None) -> None:
    values = {"status": status, "finished": now()}
    for field in ("prompt_tokens", "completion_tokens"):
        value = (tokens or {}).get(field)
        if type(value) is int and value >= 0:
            values[field] = value
    db.execute(update(InferenceUsage).where(InferenceUsage.id == identifier).values(**values))
    db.commit()


def summary(db: Session, user: Identity) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = db.get(RateBucket, bucket_id(f"tenant:{user.tenant}:daily:{today}"))
    used = daily.used if daily else 0
    # SQL Server does not equate duplicated positional parameters in SELECT/GROUP BY
    # expressions. Group by the stored column and classify expired leases separately.
    rows = dict(
        db.execute(
            select(InferenceUsage.status, func.count()).where(InferenceUsage.tenant == user.tenant).group_by(InferenceUsage.status)
        ).all()
    )
    expired = (
        db.scalar(
            select(func.count())
            .select_from(InferenceUsage)
            .where(InferenceUsage.tenant == user.tenant, InferenceUsage.status == "RESERVED", InferenceUsage.expires <= now())
        )
        or 0
    )
    if expired:
        rows["RESERVED"] = rows.get("RESERVED", 0) - expired
        if not rows["RESERVED"]:
            rows.pop("RESERVED")
        rows["EXPIRED"] = rows.get("EXPIRED", 0) + expired
    return {
        "date": today,
        "reserved_today": used,
        "daily_limit": settings.inference_daily_quota,
        "warning": used * 100 >= settings.inference_daily_quota * settings.inference_warning_percent,
        "warning_percent": settings.inference_warning_percent,
        "statuses": dict(rows),
        "concurrency_limit": settings.inference_concurrency,
        "user_per_minute": settings.inference_user_per_minute,
        "tenant_per_minute": settings.inference_tenant_per_minute,
        "tokens": {
            field: db.scalar(select(func.sum(getattr(InferenceUsage, field))).where(InferenceUsage.tenant == user.tenant))
            for field in ("prompt_tokens", "completion_tokens")
        },
        "billing": "Not calculated; only provider-reported token counts are recorded",
        "statistics_scope": "Reservation count is today UTC; statuses and tokens cover all retained history",
    }


def claim_action(db: Session, user: Identity, action: str, limit: int, *, once: bool = False) -> None:
    """Atomic shared SQL control; the caller commits it with the protected mutation."""
    current = datetime.now(timezone.utc)
    window = "permanent" if once else current.strftime("%Y-%m-%dT%H:%M")
    key = bucket_id(f"action:{user.tenant}:{user.user}:{action}:{window}")
    expires = "9999-12-31T23:59:59+00:00" if once else (current + timedelta(days=2)).isoformat()
    ensure_bucket(db, key, expires)
    claimed = db.execute(update(RateBucket).where(RateBucket.id == key, RateBucket.used < limit).values(used=RateBucket.used + 1))
    if claimed.rowcount != 1:
        raise HTTPException(
            409 if once else 429,
            "You have already submitted feedback for this execution" if once else "Operation rate limit reached; wait for the next minute",
            headers={} if once else {"Retry-After": "60"},
        )
