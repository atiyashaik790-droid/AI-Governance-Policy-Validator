"""Encrypted review-only prompts. No original content enters reporting metadata."""
import asyncio
import base64
from contextlib import asynccontextmanager
import json
import re
import secrets
import threading
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from sqlalchemy import select, delete, text, inspect

from . import database
from .config import settings
from .models import Review, ReviewAssignment, Execution, Audit
from .models_review_content import ProtectedReviewContent as Content
from .repositories import record_audit_event
from .schemas import StrictModel
from .stage_timing import stage, logger

RETENTION = 7 * 86400
INTERVAL = 900
MAX_HEARTBEAT_AGE = 960
REASONS = ("Reviewed policy requirements", "Additional context required", "Policy restriction confirmed",
           "Resubmission required", "Assigned for review")


def unavailable():
    return HTTPException(503, "Protected review content is temporarily unavailable")


def keyring():
    try:
        # Reject duplicate key IDs, not just malformed JSON.
        def unique(pairs):
            value = {}
            for key, entry in pairs:
                if key in value:
                    raise ValueError()
                value[key] = entry
            return value
        values = json.loads(settings.review_content_keys_json, object_pairs_hook=unique)
        if not isinstance(values, dict) or not 1 <= len(values) <= 32:
            raise ValueError()
        keys = {}
        for key_id, encoded in values.items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key_id):
                raise ValueError()
            key = base64.b64decode(encoded, validate=True)
            credentials = [value for value in (settings.entra_client_secret, settings.azure_openai_api_key, settings.openai_api_key) if value]
            if len(key) != 32 or encoded in credentials or key in [value.encode() for value in credentials]:
                raise ValueError()
            keys[key_id] = key
        if settings.review_content_active_key_id not in keys:
            raise ValueError()
        return keys
    except Exception:
        raise unavailable() from None


def schema_available(db):
    # No protected-table access on 005/006. Never infer 007 from local table names.
    if "alembic_version" not in inspect(db.connection()).get_table_names():
        return False
    return list(db.scalars(text("SELECT version_num FROM alembic_version"))) in (["007"], ["008"], ["009"], ["010"])


def clock(db):
    from .services.policy_sets import database_now
    return int(database_now(db).timestamp())


class CleanupHealth:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine = None
        self.running = False
        self.success_at = None
        self.first_pass = threading.Event()

    def start(self, engine):
        with self.lock:
            self.engine, self.running, self.success_at = engine, True, None
            self.first_pass = threading.Event()

    def stop(self):
        with self.lock:
            self.running, self.success_at = False, None
            self.first_pass.set()

    def record(self, engine, success):
        with self.lock:
            if self.running and self.engine is engine:
                self.success_at = time.monotonic() if success else None
                self.first_pass.set()

    def wait_for_first_pass(self, engine, timeout):
        """Wait for completion, including failure; never manufacture a heartbeat."""
        with self.lock:
            if not self.running or self.engine is not engine:
                return False
            first_pass = self.first_pass
        completed = first_pass.wait(timeout)
        with self.lock:
            return (completed and self.running and self.engine is engine
                    and self.first_pass is first_pass)

    def healthy(self, engine):
        with self.lock:
            return (self.running and self.engine is engine and self.success_at is not None
                    and 0 <= time.monotonic() - self.success_at <= MAX_HEARTBEAT_AGE)


health = CleanupHealth()


def delete_content(db, *criteria):
    """Use deleted identities, never DBAPI rowcount (-1 can mean unknown).

    SQL Server emits OUTPUT deleted.review_id; only metadata is returned.
    The frozen content trigger covers UPDATE, not DELETE. The caller owns
    the transaction and must commit the matching audit before counting success.
    """
    return list(db.scalars(delete(Content).where(*criteria)
                           .returning(Content.review_id)
                           .execution_options(synchronize_session=False)))


def cleanup_once(engine, factory=None):
    """At most 200 conditional deletes; audit and deletion commit together.

    The unchanged two-second scheduling budget limits additional work. A first
    row must be allowed to make progress even when guarded SQL setup consumed
    the budget. It is not a SQL statement timeout (the driver supplies that).
    """
    removed, attempted, selected = 0, 0, 0
    started = time.monotonic()
    deadline = started + 2
    step, reason = "schema", "SQL_FAILURE"
    try:
        with (factory or database.SessionLocal)() as db:
            if db.bind is not engine or not schema_available(db):
                reason = "SCHEMA_UNAVAILABLE"
                raise unavailable()
            step = "clock"
            cutoff = clock(db)
            for _ in range(4):
                step = "eligibility"
                rows = db.execute(select(Content.tenant, Content.review_id).where(Content.expires_at <= cutoff)
                                  .order_by(Content.expires_at, Content.tenant, Content.review_id).limit(50)).all()
                selected += len(rows)
                if not rows:
                    break
                pending = 0
                for tenant, review_id in rows:
                    if attempted and time.monotonic() >= deadline:
                        break
                    attempted += 1
                    step = "delete"
                    deleted = delete_content(db, Content.tenant == tenant, Content.review_id == review_id,
                                             Content.expires_at <= cutoff)
                    if deleted:
                        pending += len(deleted)
                        step = "audit"
                        db.add(Audit(tenant=tenant, actor="system:review-cleanup", action="review.content.expired", resource=review_id))
                step = "commit"
                db.commit()
                removed += pending  # Never count a transaction that rolls back.
                if time.monotonic() >= deadline:
                    break
            step = "backlog"
            backlog = db.scalar(select(Content.review_id).where(Content.expires_at <= cutoff).limit(1)) is not None
        reason = "BACKLOG" if backlog else "COMPLETE"
        healthy = not backlog
    except Exception:
        healthy = False
    health.record(engine, healthy)
    # No SQL text, error messages, identifiers, ciphertext, prompts or keys.
    diagnostic = {"event": "cleanup.pass", "stage": step, "reason": reason,
                  "selected": selected, "attempted": attempted, "removed": removed,
                  "healthy": healthy, "elapsed_ms": round((time.monotonic() - started) * 1000, 3)}
    logger.info(json.dumps(diagnostic))
    return {"removed": removed, "healthy": healthy}


@asynccontextmanager
async def lifespan(app):
    # Disabled feature performs no background database work or schema changes.
    task = None
    if settings.review_capture_enabled or settings.review_cleanup_enabled:
        factory = database.SessionLocal
        engine = factory.kw["bind"]
        health.start(engine)

        async def run():
            while True:
                worker = asyncio.create_task(asyncio.to_thread(cleanup_once, engine, factory))
                try:
                    result = await asyncio.shield(worker)
                except asyncio.CancelledError:
                    await worker  # Drain the bounded DB pass; do not orphan a cleanup thread.
                    raise
                await asyncio.sleep(INTERVAL if result["healthy"] else 30)
        task = asyncio.create_task(run())
    try:
        yield
    finally:
        health.stop()  # Immediately refuse new captures during shutdown.
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


def ensure_ready(db):
    if settings.review_capture_enabled:
        keyring()
        from .schema_compatibility import inspect_schema
        with stage("review.schema", db):
            inspect_schema(db, require_sso=settings.sso_enabled)
        if not schema_available(db) or not health.healthy(db.bind):
            raise unavailable()


def aad(tenant, review_id, execution_id, kind, version, expiry):
    return json.dumps([tenant, review_id, execution_id, kind, version, expiry],
                      ensure_ascii=True, separators=(",", ":")).encode("ascii")


def encrypt_prompt(prompt, tenant, review_id, execution_id, created):
    keys = keyring()
    key_id = settings.review_content_active_key_id
    try:
        if not isinstance(prompt, str) or len(prompt) > 12000:
            raise ValueError()
        raw = prompt.encode("utf-8", errors="strict")
        nonce, expiry = secrets.token_bytes(12), created + RETENTION
        ciphertext = AESGCM(keys[key_id]).encrypt(nonce, raw, aad(tenant, review_id, execution_id, "original_prompt", 1, expiry))
        return Content(tenant=tenant, review_id=review_id, content_kind="original_prompt", format_version=1,
                       key_id=key_id, nonce=nonce, ciphertext=ciphertext, created_at=created, expires_at=expiry)
    except Exception:
        raise unavailable() from None


def decrypt_prompt(content, execution_id):
    try:
        keys = keyring()
        if content.content_kind != "original_prompt" or content.format_version != 1:
            raise ValueError()
        raw = AESGCM(keys[content.key_id]).decrypt(content.nonce, content.ciphertext,
            aad(content.tenant, content.review_id, execution_id, content.content_kind, content.format_version, content.expires_at))
        return raw.decode("utf-8", errors="strict")
    except Exception:
        raise unavailable() from None


def capture(db, user, review, original_prompt):
    if not settings.review_capture_enabled:
        return
    ensure_ready(db)
    content = encrypt_prompt(original_prompt, user.tenant, review.id, review.execution_id, clock(db))
    db.add(content)
    record_audit_event(db, user, "review.content.retained", review.id)
    db.flush()  # Failure rolls back case, content and execution together.


def structured_reason(db, value):
    if schema_available(db) and value and value not in REASONS:
        raise HTTPException(422, "Select a structured review reason; free-form sensitive commentary is not accepted")
    return value


def purge_resolved(db, user, review):
    if schema_available(db):
        changed = delete_content(db, Content.tenant == user.tenant, Content.review_id == review.id)
        if changed:
            record_audit_event(db, user, "review.content.purged", review.id)


def metadata(db, user, review):
    if not schema_available(db):
        return {"availability": "NEVER_RETAINED", "can_reveal": False, "structured_notes_only": False}
    # No ciphertext/nonce is loaded or returned by metadata serializers.
    stored = db.execute(select(Content.expires_at, Content.key_id).where(Content.tenant == user.tenant, Content.review_id == review.id)).first()
    expiry = stored.expires_at if stored else None
    if expiry is None:
        events = set(db.scalars(select(Audit.action).where(Audit.tenant == user.tenant, Audit.resource == review.id,
                                                         Audit.action.in_(["review.content.expired", "review.content.purged", "review.content.retained"]))))
        state = "PURGED" if "review.content.purged" in events else "EXPIRED" if "review.content.expired" in events else "UNAVAILABLE" if events else "NEVER_RETAINED"
    elif clock(db) >= expiry:
        state = "EXPIRED"
    else:
        state = "UNAVAILABLE"
        if settings.review_capture_enabled and health.healthy(db.bind):
            try:
                keys = keyring()
                if stored.key_id in keys:
                    state = "AVAILABLE"
            except HTTPException:
                pass
    assigned = db.scalar(select(ReviewAssignment.assigned_reviewer).where(ReviewAssignment.tenant == user.tenant, ReviewAssignment.id == review.id))
    permitted = (state == "AVAILABLE" and review.status == "PENDING" and user.role in {"Admin", "Reviewer"}
                 and bool(user.session_id) and assigned == user.user)
    return {"availability": state, "can_reveal": permitted, "expires_at": expiry,
            "structured_notes_only": True}


def review_context(execution):
    try:
        data = json.loads(execution.metadata_json)
        trigger = next((stage.upper() for stage in ("output", "input")
                        if isinstance(data.get(stage), dict) and data[stage].get("decision") == "HUMAN_REVIEW"), "Not recorded")
        return {"review_trigger": trigger, "attachment_present": isinstance(data.get("attachment"), dict),
                "attachment_contents_retained": False}
    except (ValueError, TypeError, AttributeError):
        return {"review_trigger": "Not recorded", "attachment_present": False, "attachment_contents_retained": False}


class RevealRequest(StrictModel):
    pass


def reveal(db, user, review_id, expected_version):
    from .security import require_role
    from .services.reviews import get_review
    from . import usage
    require_role(user, "Admin", "Reviewer")
    if not user.session_id:
        raise HTTPException(403, "An authenticated session is required")
    # Same parent lock is used by assignment/disposition to serialize against reveal.
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    review = db.scalar(select(Review).where(Review.tenant == user.tenant, Review.id == review_id)
                       .with_hint(Review, "WITH (UPDLOCK, HOLDLOCK)", "mssql").execution_options(populate_existing=True))
    if review is None:
        raise HTTPException(404, "Review not found")
    get_review(db, user, review_id)
    assignment = db.scalar(select(ReviewAssignment).where(ReviewAssignment.tenant == user.tenant, ReviewAssignment.id == review_id))
    if not assignment or assignment.assigned_reviewer != user.user:
        record_audit_event(db, user, "review.content.denied", review_id)
        db.commit()
        raise HTTPException(403, "Only the explicitly assigned reviewer may reveal content")
    if expected_version is None:
        raise HTTPException(428, "Refresh the review before revealing content")
    if expected_version != f'"{review.row_version}"' or review.status != "PENDING":
        raise HTTPException(412, "Review changed; refresh before revealing content")
    # Enforce tenant on execution too, rather than relying on the FK alone.
    execution = db.scalar(select(Execution).where(Execution.tenant == user.tenant, Execution.id == review.execution_id))
    if execution is None:
        raise HTTPException(404, "Review not found")
    if not schema_available(db):
        raise HTTPException(410, "Original prompt was not retained for this review")
    content = db.scalar(select(Content).where(Content.tenant == user.tenant, Content.review_id == review.id))
    if content is None:
        state = metadata(db, user, review)["availability"]
        raise HTTPException(410, "Original prompt expired" if state == "EXPIRED" else "Original prompt was not retained or was purged")
    if clock(db) >= content.expires_at:
        raise HTTPException(410, "Original prompt expired")
    ensure_ready(db)
    if not settings.review_capture_enabled:
        raise unavailable()
    usage.claim_action(db, user, "review-content-reveal", 10)
    plaintext = decrypt_prompt(content, execution.id)
    record_audit_event(db, user, "review.content.viewed", review.id)
    db.flush()
    if clock(db) >= content.expires_at:
        raise HTTPException(410, "Original prompt expired")
    db.commit()  # A failed audit commit cannot return plaintext.
    if clock(db) >= content.expires_at:
        raise HTTPException(410, "Original prompt expired")
    return {"original_prompt": plaintext, "expires_at": content.expires_at,
            "review_version": review.row_version, "clear_after_seconds": min(300, content.expires_at - clock(db))}
