"""Offline-testable expiry policy, NOT a certified Azure watchdog.

Adapters must enforce their own RPC deadlines. Run from an independent executor;
calling this on the harness host cannot protect against host suspension.
No Azure mutation adapter is provided and creation remains blocked.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class Expiry:
    resource_id: str
    created: datetime  # ARM properties.creationDate, never local create intent
    lifetime: timedelta = timedelta(hours=4)
    margin: timedelta = timedelta(hours=1)

    def __post_init__(self):
        if self.created.tzinfo is None or self.created.utcoffset() != timedelta(0):
            raise ValueError("ARM creation time must be UTC-aware")
        if not timedelta(0) < self.margin < self.lifetime <= timedelta(hours=4):
            raise ValueError("Invalid authorized lifetime or cleanup margin")

    @property
    def deadline(self):
        return self.created + self.lifetime

    @property
    def stop_at(self):
        return self.deadline - self.margin


def tick(policy, *, now, stop_test, delete, arm_absent, inventory_absent, record):
    """One independent wall-clock pass; caller repeats failed cleanup passes.

    Deletion never depends on parent liveness, state-file success or termination.
    A 404 alone is insufficient. No raw adapter exceptions are recorded.
    """
    current = now()
    if current.tzinfo is None:
        raise ValueError("UTC-aware clock required")
    if current < policy.created:
        raise ValueError("Creation time is in the future; clock evidence invalid")
    base = {"resource_id": policy.resource_id,
            "creation_utc": policy.created.isoformat(),
            "cleanup_start_utc": policy.stop_at.isoformat(),
            "deadline_utc": policy.deadline.isoformat()}
    if current < policy.stop_at:
        return "WAIT"
    # Record failure must never prevent cleanup. Persisted evidence is still
    # required for certification; best-effort logging is not proof of safety.
    def report(event, **fields):
        try:
            record({**base, "event": event, "utc": now().isoformat(), **fields})
        except Exception:
            pass

    if current >= policy.deadline:
        report("LIMIT_BREACH")
    try:
        stop_test()
    except Exception:
        report("TERMINATION_FAILED")
    try:
        delete(policy.resource_id)
    except Exception:
        report("DELETE_FAILED")
    try:
        arm = arm_absent(policy.resource_id)
        inventory = inventory_absent(policy.resource_id)
    except Exception:
        report("ABSENCE_CHECK_FAILED")
        return "UNCONFIRMED"
    if not (arm and inventory):
        report("DELETION_UNCONFIRMED")
        return "UNCONFIRMED"
    observed = now().astimezone(timezone.utc)
    report("DELETION_CONFIRMED", deletion_observed_utc=observed.isoformat(),
           late=observed >= policy.deadline)
    return "DELETED_LATE" if observed >= policy.deadline else "DELETED"
