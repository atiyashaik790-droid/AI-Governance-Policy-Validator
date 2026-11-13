"""Offline 006 domain transactions. No routes, provider calls or background work.

Admission, mutation and release share the tenant gate. Public mutation/admission
functions own their transaction; guards and release fences leave commit to caller.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import and_, inspect, select, text, true, update
from sqlalchemy.orm import Session

from .. import usage
from ..models import Assignment, InferenceUsage, Policy, RateBucket, Version
from ..models_multi_policy import (
    MULTI_TABLES, Execution006, WorkspacePolicyState as State,
    WorkspacePolicyAssignment as Pin, WorkspacePolicyAssignmentEvent as Event,
)
from ..repositories import record_audit_event
from ..schemas import PolicyDocument
from ..security import require_role


def fail(status, code):
    raise HTTPException(status, code)


def schema_006(db: Session) -> bool:
    """Never infer MULTI from a missing/unsupported Azure schema marker."""
    connection = db.connection()
    tables = set(inspect(connection).get_table_names())
    if "alembic_version" in tables:
        revisions = list(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
        if len(revisions) != 1 or revisions[0] not in {"004", "005", "006", "007", "008", "009", "010", "011"}:
            fail(503, "SCHEMA_NOT_READY")
        current = revisions[0]
    elif connection.dialect.name == "sqlite":
        current = "006" if MULTI_TABLES <= tables else "005"
    else:
        fail(503, "SCHEMA_NOT_READY")
    if current in {"006", "007", "008", "009", "010", "011"} and not MULTI_TABLES <= tables or current not in {"006", "007", "008", "009", "010", "011"} and tables & MULTI_TABLES:
        fail(503, "SCHEMA_NOT_READY")
    if current not in {"006", "007", "008", "009", "010", "011"} and "validation_executions" in tables:
        if "execution_mode" in {c["name"] for c in inspect(connection).get_columns("validation_executions")}:
            fail(503, "SCHEMA_NOT_READY")
    return current in {"006", "007", "008", "009", "010", "011"}


def database_now(db):
    if db.bind.dialect.name == "mssql":
        value = db.scalar(text("SELECT SYSUTCDATETIME()"))
        return value.replace(tzinfo=timezone.utc)
    value = db.scalar(text("SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')"))
    return datetime.fromisoformat(value)


def lock_workspace(db, user):
    """Gate -> state -> policy -> assignment -> reservation, no provider work."""
    with db.no_autoflush:
        connection = db.connection()
        if connection.dialect.name == "sqlite":
            # SQLite's SELECT autobegin need not have begun a physical txn yet.
            if not connection.connection.driver_connection.in_transaction:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
        elif connection.dialect.name != "mssql":
            fail(503, "DATABASE_DIALECT_UNSUPPORTED")
        gate = usage.bucket_id(f"tenant:{user.tenant}:concurrency-gate")
        usage.ensure_bucket(db, gate, "9999-12-31T23:59:59+00:00")
        db.execute(update(RateBucket).where(RateBucket.id == gate).values(used=0))
        statement = select(State).where(State.tenant == user.tenant).with_hint(State, "WITH (UPDLOCK, HOLDLOCK)", "mssql")
        state = db.scalar(statement.execution_options(populate_existing=True))
        if state is None:
            state = State(tenant=user.tenant, mode="LEGACY", set_revision=1, updated_by=user.user)
            db.add(state)
            db.flush()
            db.add(Event(tenant=user.tenant, set_revision=1, event_ordinal=1,
                         event_type="INITIALIZE", new_mode="LEGACY", actor=user.user))
            db.flush()
        return state


@dataclass(frozen=True)
class PublishedPin:
    policy_id: str
    version_id: str
    number: int
    document_json: str
    document_sha256: str

    def legacy_tuple(self):
        return (SimpleNamespace(id=self.policy_id), SimpleNamespace(id=self.version_id, number=self.number),
                PolicyDocument.model_validate_json(self.document_json))


@dataclass(frozen=True)
class Admission:
    tenant: str
    actor: str
    reservation_id: str
    mode: str
    set_revision: int
    pins: tuple[PublishedPin, ...]


def published_pin(db, user, policy_id, version_id):
    policy = db.scalar(select(Policy).where(Policy.tenant == user.tenant, Policy.id == policy_id)
                       .with_hint(Policy, "WITH (UPDLOCK, HOLDLOCK)", "mssql").execution_options(populate_existing=True))
    version = db.scalar(select(Version).where(Version.tenant == user.tenant, Version.policy_id == policy_id, Version.id == version_id))
    if policy is None or version is None:
        fail(404, "PUBLISHED_PIN_NOT_FOUND")
    return _published_record(policy, version)


def _published_record(policy, version):
    if not policy.enabled or policy.status in {"ARCHIVED", "DELETED"}:
        fail(409, "POLICY_INELIGIBLE")
    try:
        PolicyDocument.model_validate_json(version.document)
    except Exception:
        fail(503, "POLICY_SET_INCONSISTENT")
    # Mutable DRAFT/SUBMITTED/APPROVED status does not revoke published history.
    return PublishedPin(policy.id, version.id, version.number, version.document, sha256(version.document.encode()).hexdigest())


def capture(db, user, state, *, simulation=False):
    if simulation:
        return ()
    if state.mode == "LEGACY":
        assignment = db.get(Assignment, user.tenant, populate_existing=True)
        version = db.get(Version, assignment.version_id) if assignment else None
        if not version or version.tenant != user.tenant:
            fail(409, "No enabled active policy; request withheld")
        try:
            return (published_pin(db, user, version.policy_id, version.id),)
        except HTTPException as error:
            if error.status_code == 409:
                fail(409, "No enabled active policy; request withheld")
            raise
    assignments = db.execute(
        select(Pin, Policy, Version)
        .outerjoin(Policy, and_(Policy.id == Pin.policy_id, Policy.tenant == Pin.tenant))
        .outerjoin(Version, and_(Version.id == Pin.version_id, Version.policy_id == Pin.policy_id, Version.tenant == Pin.tenant))
        .where(Pin.tenant == user.tenant, Pin.active == true()).order_by(Pin.policy_id)
        .execution_options(populate_existing=True)
    ).all()
    if not assignments:
        fail(409, "NO_ACTIVE_POLICIES")
    result = []
    for pin, policy, version in assignments:
        if policy is None or version is None or pin.changed_revision > state.set_revision:
            fail(503, "POLICY_SET_INCONSISTENT")
        try:
            result.append(_published_record(policy, version))
        except HTTPException:
            fail(503, "POLICY_SET_INCONSISTENT")
    return tuple(result)


def admit(db, user, *, legacy_only=False, simulation=False, expected_revision=None):
    """Capture and quota reservation commit atomically; never generate here."""
    if not simulation:
        require_role(user, "Admin", "Developer", "Policy Owner", "User")
    try:
        if not schema_006(db):
            fail(503, "SCHEMA_006_REQUIRED")
        state = lock_workspace(db, user)
        if (legacy_only or simulation) and state.mode != "LEGACY":
            fail(409, "USE_API_V2")
        if expected_revision is not None and str(state.set_revision) != str(expected_revision):
            fail(412, "POLICY_SET_PRECONDITION_FAILED")
        pins = capture(db, user, state, simulation=simulation)
        reservation_id = usage.reserve(db, user, commit=False, gate_locked=True, current=database_now(db))
        admitted = Admission(user.tenant, user.user, reservation_id, state.mode, state.set_revision, pins)
        db.commit()
        return admitted
    except Exception:
        db.rollback()
        raise


def fence(db, user, admission, *, hold=False):
    """Check ownership/expiry/mode; hold=True retains locks for audit commit."""
    try:
        if (admission.tenant, admission.actor) != (user.tenant, user.user):
            fail(403, "RESERVATION_OWNER_MISMATCH")
        state = lock_workspace(db, user)
        reservation = db.scalar(select(InferenceUsage).where(InferenceUsage.id == admission.reservation_id,
                                    InferenceUsage.tenant == user.tenant, InferenceUsage.actor == user.user)
                                .with_hint(InferenceUsage, "WITH (UPDLOCK, HOLDLOCK)", "mssql")
                                .execution_options(populate_existing=True))
        try:
            expiry = datetime.fromisoformat(reservation.expires) if reservation else None
            valid = expiry is not None and expiry.tzinfo is not None and expiry > database_now(db)
        except (ValueError, TypeError):
            valid = False
        if reservation is None or reservation.status != "RESERVED" or not valid:
            fail(409, "RESERVATION_FENCED")
        if state.mode != admission.mode or admission.mode == "MULTI" and state.set_revision != admission.set_revision:
            fail(409, "POLICY_SET_CHANGED")
        if admission.mode == "MULTI" and capture(db, user, state) != admission.pins:
            fail(503, "POLICY_SET_INCONSISTENT")
        if not hold:
            db.commit()
    except Exception:
        db.rollback()
        raise


def finish_admission(db, user, admission, status, tokens=None, *, commit=True):
    """Conditional completion cannot resurrect an EXPIRED/reconciled claim."""
    with db.no_autoflush:
        row = db.get(InferenceUsage, admission.reservation_id, populate_existing=True)
    if row is None or (row.tenant, row.actor) != (user.tenant, user.user) or row.status != "RESERVED":
        if commit:
            db.rollback()
        return False
    if status != "FAILED":
        fence(db, user, admission, hold=True)
    values = {"status": status, "finished": database_now(db).isoformat()}
    values.update({k: v for k, v in (tokens or {}).items()
                   if k in {"prompt_tokens", "completion_tokens"} and type(v) is int and v >= 0})
    changed = db.execute(update(InferenceUsage).where(InferenceUsage.id == admission.reservation_id,
                         InferenceUsage.tenant == user.tenant, InferenceUsage.actor == user.user,
                         InferenceUsage.status == "RESERVED").values(**values)).rowcount
    if commit:
        db.commit()
    return changed == 1


def _precondition(state, expected_revision):
    if expected_revision is None:
        fail(428, "POLICY_SET_PRECONDITION_REQUIRED")
    if str(state.set_revision) != str(expected_revision):
        fail(412, "POLICY_SET_PRECONDITION_FAILED")


def _bump(db, user, state):
    state.set_revision += 1
    state.updated_at = database_now(db).replace(tzinfo=None)
    state.updated_by = user.user
    db.flush()


def _event(db, user, state, kind, ordinal=1, **fields):
    db.add(Event(tenant=user.tenant, set_revision=state.set_revision, event_ordinal=ordinal,
                 event_type=kind, actor=user.user, **fields))


def change_assignment(db, user, policy_id, *, active, version_id=None, expected_revision=None):
    require_role(user, "Admin")
    try:
        if type(active) is not bool or active and not version_id or not active and version_id is not None:
            fail(422, "INVALID_ASSIGNMENT")
        if not schema_006(db):
            fail(503, "SCHEMA_006_REQUIRED")
        state = lock_workspace(db, user)
        _precondition(state, expected_revision)
        if state.mode != "MULTI":
            fail(409, "WORKSPACE_MODE_CONFLICT")
        pin = db.get(Pin, (user.tenant, policy_id), populate_existing=True)
        if active:
            published_pin(db, user, policy_id, version_id)
        elif pin is None:
            fail(404, "ASSIGNMENT_NOT_FOUND")
        if pin and pin.active == active and (not active or pin.version_id == version_id):
            db.commit()
            return state.set_revision
        old_version, old_active = (pin.version_id, pin.active) if pin else (None, None)
        kind = "REPIN" if active and old_active else "ACTIVATE" if active else "DEACTIVATE"
        _bump(db, user, state)
        if pin is None:
            pin = Pin(tenant=user.tenant, policy_id=policy_id)
            db.add(pin)
        pin.version_id = version_id if active else old_version
        pin.active, pin.changed_revision = active, state.set_revision
        pin.updated_at, pin.updated_by = state.updated_at, user.user
        _event(db, user, state, kind, policy_id=policy_id, old_version_id=old_version,
               new_version_id=pin.version_id, old_active=old_active, new_active=active)
        record_audit_event(db, user, "policy.assignment." + kind.lower(), policy_id)
        db.commit()
        return state.set_revision
    except Exception:
        db.rollback()
        raise


def change_mode(db, user, mode, *, expected_revision=None, seed_legacy_assignment=None, legacy_version_id=None):
    require_role(user, "Admin")
    try:
        if mode not in {"LEGACY", "MULTI"}:
            fail(422, "INVALID_MODE")
        if not schema_006(db):
            fail(503, "SCHEMA_006_REQUIRED")
        state = lock_workspace(db, user)
        _precondition(state, expected_revision)
        if state.mode == mode:
            db.commit()
            return state.set_revision
        if db.scalar(select(InferenceUsage.id).where(InferenceUsage.tenant == user.tenant, InferenceUsage.status == "RESERVED").limit(1)):
            fail(409, "TRANSITION_BUSY")
        active_pins = list(db.scalars(select(Pin).where(Pin.tenant == user.tenant, Pin.active == true()).order_by(Pin.policy_id)))
        old_mode = state.mode
        ordinal = 1
        if mode == "MULTI":
            if type(seed_legacy_assignment) is not bool or legacy_version_id is not None:
                fail(422, "EXPLICIT_LEGACY_SEED_REQUIRED")
            if active_pins:
                fail(503, "POLICY_SET_INCONSISTENT")
            seed = capture(db, user, state)[0] if seed_legacy_assignment else None
            _bump(db, user, state)
            if seed:
                pin = db.get(Pin, (user.tenant, seed.policy_id), populate_existing=True)
                old_version, old_active = (pin.version_id, pin.active) if pin else (None, None)
                if pin is None:
                    pin = Pin(tenant=user.tenant, policy_id=seed.policy_id)
                    db.add(pin)
                pin.version_id, pin.active = seed.version_id, True
                pin.changed_revision, pin.updated_by, pin.updated_at = state.set_revision, user.user, state.updated_at
                _event(db, user, state, "ACTIVATE", ordinal, policy_id=seed.policy_id,
                       old_version_id=old_version, new_version_id=seed.version_id, old_active=old_active, new_active=True)
                ordinal += 1
        else:
            if not legacy_version_id or seed_legacy_assignment is not None:
                fail(422, "EXPLICIT_LEGACY_VERSION_REQUIRED")
            if len(active_pins) > 1:
                fail(409, "DEACTIVATE_OTHER_POLICIES_FIRST")
            version = db.scalar(select(Version).where(Version.tenant == user.tenant, Version.id == legacy_version_id))
            if not version:
                fail(404, "PUBLISHED_PIN_NOT_FOUND")
            published_pin(db, user, version.policy_id, version.id)
            if active_pins and active_pins[0].version_id != legacy_version_id:
                fail(409, "LEGACY_SURVIVOR_MISMATCH")
            _bump(db, user, state)
            assignment = db.get(Assignment, user.tenant, populate_existing=True)
            if assignment is None:
                assignment = Assignment(tenant=user.tenant)
                db.add(assignment)
            assignment.version_id = legacy_version_id
            for pin in active_pins:
                pin.active, pin.changed_revision = False, state.set_revision
                pin.updated_at, pin.updated_by = state.updated_at, user.user
                _event(db, user, state, "DEACTIVATE", ordinal, policy_id=pin.policy_id,
                       old_version_id=pin.version_id, new_version_id=pin.version_id, old_active=True, new_active=False)
                ordinal += 1
        state.mode = mode
        _event(db, user, state, "SET_MODE", ordinal, old_mode=old_mode, new_mode=mode)
        record_audit_event(db, user, "policy.mode." + mode.lower(), user.tenant)
        db.commit()
        return state.set_revision
    except Exception:
        db.rollback()
        raise


def guard_legacy(db, user):
    if schema_006(db):
        state = lock_workspace(db, user)
        if state.mode != "LEGACY":
            fail(409, "USE_API_V2")


def multi_mode(db, user):
    if not schema_006(db):
        return False
    state = db.get(State, user.tenant, populate_existing=True)
    return state is not None and state.mode == "MULTI"


def guard_v1_history(db, user, *, first=None, last=None, execution_id=None):
    """Never flatten aggregate history to a fictional single-policy record."""
    if not schema_006(db):
        return
    query = select(Execution006.id).where(Execution006.tenant == user.tenant, Execution006.execution_mode == "MULTI")
    if first is not None:
        query = query.where(Execution006.created >= first)
    if last is not None:
        query = query.where(Execution006.created < last)
    if execution_id is not None:
        query = query.where(Execution006.id == execution_id)
    if db.scalar(query.limit(1)) is not None:
        fail(409, "USE_API_V2")


def guard_lifecycle(db, user, policy_id, operation):
    """Hold the common mutation lock until the existing handler commits."""
    if not schema_006(db):
        return
    state = lock_workspace(db, user)
    if state.mode == "MULTI":
        if operation == "activate":
            fail(409, "USE_API_V2")
        if operation in {"disable", "archive", "delete"}:
            pin = db.get(Pin, (user.tenant, policy_id), populate_existing=True)
            if pin and pin.active:
                fail(409, "DEACTIVATE_POLICY_FIRST")
    return state


def legacy_assignment_changed(db, user, state, previous_version_id, version):
    if state is None or state.mode != "LEGACY" or previous_version_id == version.id:
        return
    previous = db.get(Version, previous_version_id) if previous_version_id else None
    if previous_version_id and (previous is None or previous.tenant != user.tenant):
        fail(503, "POLICY_SET_INCONSISTENT")
    previous_policy = db.scalar(select(Policy).where(Policy.tenant == user.tenant, Policy.id == previous.policy_id)
                                .execution_options(populate_existing=True)) if previous else None
    if previous and previous_policy is None:
        fail(503, "POLICY_SET_INCONSISTENT")
    _bump(db, user, state)
    if previous and previous.policy_id == version.policy_id:
        _event(db, user, state, "REPIN", policy_id=version.policy_id,
               old_version_id=previous.id, new_version_id=version.id, old_active=True, new_active=True)
    else:
        ordinal = 1
        if previous and previous_policy.enabled and previous_policy.status not in {"ARCHIVED", "DELETED"}:
            _event(db, user, state, "DEACTIVATE", ordinal, policy_id=previous.policy_id,
                   old_version_id=previous.id, new_version_id=previous.id, old_active=True, new_active=False)
            ordinal += 1
        _event(db, user, state, "ACTIVATE", ordinal, policy_id=version.policy_id,
               new_version_id=version.id, new_active=True)


def legacy_eligibility_changed(db, user, state, policy, previous_enabled):
    if state is None or state.mode != "LEGACY" or bool(previous_enabled) == bool(policy.enabled):
        return
    assignment = db.get(Assignment, user.tenant, populate_existing=True)
    version = db.get(Version, assignment.version_id) if assignment else None
    if version is None or version.policy_id != policy.id:
        return
    if version.tenant != user.tenant:
        fail(503, "POLICY_SET_INCONSISTENT")
    _bump(db, user, state)
    enabled = bool(policy.enabled)
    _event(db, user, state, "ACTIVATE" if enabled else "DEACTIVATE", policy_id=policy.id,
           old_version_id=version.id, new_version_id=version.id,
           old_active=not enabled, new_active=enabled)


def reconcile_expired(db, user):
    """Explicit admin action; expiry alone never unblocks a mode transition."""
    require_role(user, "Admin")
    try:
        if not schema_006(db):
            fail(503, "SCHEMA_006_REQUIRED")
        lock_workspace(db, user)
        current = database_now(db)
        rows = list(db.scalars(select(InferenceUsage).where(InferenceUsage.tenant == user.tenant,
                          InferenceUsage.status == "RESERVED").execution_options(populate_existing=True)))
        count = 0
        for row in rows:
            try:
                expiry = datetime.fromisoformat(row.expires)
            except (ValueError, TypeError):
                fail(503, "INVALID_RESERVATION_EXPIRY")
            if expiry.tzinfo is None:
                fail(503, "INVALID_RESERVATION_EXPIRY")
            if expiry <= current:
                row.status, row.finished = "EXPIRED", current.isoformat()
                record_audit_event(db, user, "governance.reservation.expired", row.id)
                count += 1
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
