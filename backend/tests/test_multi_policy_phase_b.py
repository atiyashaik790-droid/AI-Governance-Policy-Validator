"""Disposable SQLite + SQL compilation only. No cloud/provider transport."""

import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event as ThreadEvent
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.dialects import mssql, sqlite
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable, CreateIndex

from app.models import Base, Assignment, Execution, InferenceUsage, Policy, Version, Review, Feedback
from app.models_multi_policy import (
    MultiPolicyBase, Execution006, ExecutionPolicyEvidence as Evidence,
    WorkspacePolicyState as State, WorkspacePolicyAssignment as Pin,
    WorkspacePolicyAssignmentEvent as AssignmentEvent, MULTI_TABLES, MULTI_HISTORY,
)
from app.schema_compatibility import inspect_schema
from app.schema_006_verification import canonical_check
from app.schemas import PolicyDocument, TextRequest, ModerationCategory
from app.multi_policy_contracts import inspection_contract, STAGES
from app.security import Identity
from app.services import policy_sets as domain
from app.config import settings

ROOT = Path(__file__).resolve().parents[2]
ADMIN = Identity("admin", "one", "Admin")
FOREIGN = Identity("foreign", "two", "Admin")


def migration_module():
    spec = importlib.util.spec_from_file_location("migration_006_test", ROOT / "backend/migrations/versions/006_multi_policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(path, target):
    result = subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", target],
                            cwd=ROOT / "backend", env={**os.environ, "DATABASE_URL": "sqlite:///" + str(path)},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module")
def templates(tmp_path_factory):
    root = tmp_path_factory.mktemp("multi-policy-templates")
    paths = {}
    for revision in ("005", "006"):
        paths[revision] = root / (revision + ".db")
        migrate(paths[revision], revision)
    return paths


def fixture_engine(path):
    engine = create_engine("sqlite:///" + str(path), connect_args={"timeout": 10, "check_same_thread": False})

    @event.listens_for(engine, "connect")
    def fk_on(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


@pytest.fixture
def engine006(templates, tmp_path, monkeypatch):
    path = tmp_path / "006.db"
    shutil.copyfile(templates["006"], path)
    monkeypatch.setattr(settings, "inference_daily_quota", 100000)
    monkeypatch.setattr(settings, "inference_tenant_per_minute", 100000)
    monkeypatch.setattr(settings, "inference_user_per_minute", 100000)
    engine = fixture_engine(path)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def template010(templates, tmp_path_factory):
    path = tmp_path_factory.mktemp("current-schema-template") / "010.db"
    shutil.copyfile(templates["006"], path)
    migrate(path, "010")
    return path


@pytest.fixture
def engine010(template010, tmp_path, monkeypatch):
    path = tmp_path / "current-schema.db"
    shutil.copyfile(template010, path)
    monkeypatch.setattr(settings, "inference_daily_quota", 100000)
    monkeypatch.setattr(settings, "inference_tenant_per_minute", 100000)
    monkeypatch.setattr(settings, "inference_user_per_minute", 100000)
    engine = fixture_engine(path)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine006):
    with Session(engine006, expire_on_commit=False) as session:
        yield session


def policy(db, user=ADMIN, *, number=1, name="Published policy"):
    document = PolicyDocument(name=name).model_dump_json()
    p = Policy(tenant=user.tenant, name=name, draft=document, status="PUBLISHED", enabled=1)
    db.add(p)
    db.flush()
    v = Version(tenant=user.tenant, policy_id=p.id, number=number, document=document)
    db.add(v)
    db.flush()
    db.commit()
    return p, v


def legacy(db):
    p, v = policy(db)
    db.add(Assignment(tenant=ADMIN.tenant, version_id=v.id))
    db.commit()
    return p, v


def multi(db):
    return domain.change_mode(db, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=False)


def activate(db, p, v, revision):
    return domain.change_assignment(db, ADMIN, p.id, active=True, version_id=v.id, expected_revision=revision)


def assert_error(status, code, function, *args, **kwargs):
    with pytest.raises(HTTPException) as caught:
        function(*args, **kwargs)
    assert (caught.value.status_code, caught.value.detail) == (status, code)


def test_005_mapping_is_frozen(templates, tmp_path):
    assert not MULTI_TABLES & Base.metadata.tables.keys()
    assert "execution_mode" not in Execution.__table__.c
    assert not Execution.__table__.c.policy_id.nullable
    path = tmp_path / "005.db"
    shutil.copyfile(templates["005"], path)
    engine = fixture_engine(path)
    with Session(engine) as session:
        assert inspect_schema(session, require_sso=True)["revision"] == "005"
        p, v = legacy(session)
        session.add(Execution(tenant="one", actor="admin", policy_id=p.id, version=v.number,
                              model="fixture", decision="ALLOW", metadata_json="{}"))
        session.commit()
        assert session.scalar(select(Execution)).policy_id == p.id
    engine.dispose()


def test_006_manifest_and_legacy_insert(db):
    assert inspect_schema(db, require_sso=True) == {"revision": "006", "versioned": True, "sso_schema": True}
    p, v = legacy(db)
    record = Execution(tenant="one", actor="admin", policy_id=p.id, version=v.number,
                       model="fixture", decision="ALLOW", metadata_json="{}")
    db.add(record)
    db.commit()
    assert db.scalar(select(Execution006.execution_mode).where(Execution006.id == record.id)) == "LEGACY"


def test_006_sqlserver_frozen_ddl_and_types():
    migration = migration_module()
    assert migration.revision == "006" and migration.down_revision == "005"
    for dialect_name, dialect in (("mssql", mssql.dialect()), ("sqlite", sqlite.dialect())):
        compiled = []
        for table in MultiPolicyBase.metadata.sorted_tables:
            if table.name in MULTI_TABLES:
                compiled.append(str(CreateTable(table).compile(dialect=dialect)).strip())
                compiled.extend(str(CreateIndex(i).compile(dialect=dialect)) for i in sorted(table.indexes, key=lambda i: i.name))
        assert compiled == migration.DDL[dialect_name]["tables"]
    evidence = str(CreateTable(Evidence.__table__).compile(dialect=mssql.dialect()))
    assert "NVARCHAR(max)" in evidence and "DATETIME2(7)" in evidence and "CHAR(64)" in evidence
    state = str(CreateTable(State.__table__).compile(dialect=mssql.dialect()))
    assert "BIGINT" in state and "SYSUTCDATETIME()" in state
    assert "BIT" in str(CreateTable(Pin.__table__).compile(dialect=mssql.dialect()))


def test_sqlserver_upgrade_compiles_without_connecting():
    stream = io.StringIO()
    context = MigrationContext.configure(dialect_name="mssql", opts={"as_sql": True, "output_buffer": stream})
    with Operations.context(context):
        migration_module().upgrade()
    sql = stream.getvalue()
    assert "ALTER COLUMN policy_id VARCHAR(36) NULL" in sql
    assert "ck_execution_mode_identity" in sql
    assert "CREATE TRIGGER dbo.immutable_execution_policy_evidence" in sql
    assert "sso_memberships" in sql  # SELECT identifiers only, not SSO DDL.
    assert "CREATE TABLE sso_" not in sql


@pytest.mark.parametrize("mode,pid,version,valid", [
    ("LEGACY", "real-policy", 1, True), ("MULTI", None, None, True),
    ("MULTI", "__MULTI__", 0, False), ("LEGACY", None, 1, False),
    ("LEGACY", "real-policy", None, False), ("LEGACY", "real-policy", 0, False),
    ("MULTI", "real-policy", None, False), ("MULTI", None, 1, False),
    ("INVALID", None, None, False),
])
def test_execution_identity_constraint(db, mode, pid, version, valid):
    record = Execution006(tenant="one", actor="admin", policy_id=pid, version=version,
                          execution_mode=mode, model="fixture", decision="ALLOW", metadata_json="{}")
    db.add(record)
    if valid:
        db.commit()
    else:
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@pytest.mark.parametrize("fields", [
    {"event_type": "SET_MODE", "old_mode": None, "new_mode": "MULTI"},
    {"event_type": "SET_MODE", "old_mode": "LEGACY", "new_mode": None},
    {"event_type": "INITIALIZE", "new_mode": None},
    {"event_type": "ACTIVATE", "old_active": True, "new_active": True},
    {"event_type": "DEACTIVATE", "old_active": None, "new_active": False},
    {"event_type": "REPIN", "old_active": None, "new_active": True},
])
def test_nullable_event_fields_cannot_bypass_check(db, fields):
    p, v = legacy(db)
    domain.guard_legacy(db, ADMIN)
    db.commit()
    values = dict(tenant="one", set_revision=2, event_ordinal=1, actor="admin", **fields)
    if fields["event_type"] in {"ACTIVATE", "DEACTIVATE", "REPIN"}:
        values.update(policy_id=p.id, old_version_id=v.id, new_version_id=v.id)
    db.add(AssignmentEvent(**values))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize("reference", ["policy", "version", "execution"])
def test_evidence_composite_foreign_keys(db, reference):
    p, v = policy(db)
    foreign_p, foreign_v = policy(db, FOREIGN)
    execution = Execution006(tenant="one", actor="admin", execution_mode="MULTI", policy_id=None,
                             version=None, model="fixture", decision="BLOCK", metadata_json="{}")
    foreign_execution = Execution006(tenant="two", actor="foreign", execution_mode="MULTI", policy_id=None,
                                     version=None, model="fixture", decision="BLOCK", metadata_json="{}")
    db.add_all([execution, foreign_execution])
    db.commit()
    values = dict(tenant="one", execution_id=execution.id, policy_id=p.id, version_id=v.id,
                  set_revision=1, document_sha256="a" * 64, effective_decision="BLOCK",
                  inspection_status="COMPLETE", evidence_json="{}")
    if reference == "policy":
        values.update(policy_id=foreign_p.id, version_id=foreign_v.id)
    elif reference == "version":
        values["version_id"] = foreign_v.id
    else:
        values["execution_id"] = foreign_execution.id
    db.add(Evidence(**values))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize("table", MULTI_HISTORY)
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_history_database_triggers(db, table, operation):
    if table == "workspace_policy_assignment_events":
        multi(db)
    else:
        p, v = policy(db)
        execution = Execution006(tenant="one", actor="admin", execution_mode="MULTI", policy_id=None,
                                 version=None, model="fixture", decision="BLOCK", metadata_json="{}")
        db.add(execution)
        db.flush()
        db.add(Evidence(tenant="one", execution_id=execution.id, policy_id=p.id, version_id=v.id,
                        set_revision=1, document_sha256="a" * 64, effective_decision="BLOCK",
                        inspection_status="COMPLETE", evidence_json="{}"))
        db.commit()
    sql = f"DELETE FROM {table}" if operation == "DELETE" else f"UPDATE {table} SET tenant=tenant"
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text(sql))
    db.rollback()


def test_event_orm_history_protection(db):
    multi(db)
    row = db.scalar(select(AssignmentEvent))
    row.actor = "changed"
    with pytest.raises(ValueError, match="append-only"):
        db.commit()
    db.rollback()


def test_independent_assignments_and_noop_etag(db):
    p1, v1 = policy(db)
    p2, v2 = policy(db)
    revision = activate(db, p1, v1, multi(db))
    revision = activate(db, p2, v2, revision)
    assert db.scalar(select(State.set_revision)) == revision
    assert len(list(db.scalars(select(Pin).where(Pin.active.is_(True))))) == 2
    assert activate(db, p2, v2, revision) == revision
    assert_error(412, "POLICY_SET_PRECONDITION_FAILED", activate, db, p2, v2, revision - 1)
    revision = domain.change_assignment(db, ADMIN, p1.id, active=False, expected_revision=revision)
    assert db.get(Pin, ("one", p2.id)).active
    assert not db.get(Pin, ("one", p1.id)).active


def test_published_pin_survives_draft_edit_and_new_publication(db):
    p, v = policy(db)
    revision = activate(db, p, v, multi(db))
    p.status, p.name = "DRAFT", "Edited draft"
    db.add(Version(tenant="one", policy_id=p.id, number=2, document=PolicyDocument(name="New version").model_dump_json()))
    db.commit()
    admitted = domain.admit(db, ADMIN)
    assert admitted.pins[0].version_id == v.id and admitted.pins[0].number == 1
    assert admitted.set_revision == revision
    domain.finish_admission(db, ADMIN, admitted, "INSPECTED")


@pytest.mark.parametrize("role", ["Developer", "Policy Owner", "Reviewer", "Auditor"])
def test_admin_required_for_mode_and_assignments(db, role):
    user = Identity("other", "one", role)
    assert_error(403, "Role does not permit this operation", domain.change_mode, db, user, "MULTI", expected_revision=1, seed_legacy_assignment=False)
    assert_error(403, "Role does not permit this operation", domain.change_assignment, db, user, "missing", active=False, expected_revision=1)


def test_empty_multi_set_fails_closed(db):
    multi(db)
    assert_error(409, "NO_ACTIVE_POLICIES", domain.admit, db, ADMIN)
    assert db.scalar(select(InferenceUsage.id)) is None


def test_transition_requires_resolved_reservation_even_after_expiry(db):
    legacy(db)
    admitted = domain.admit(db, ADMIN, legacy_only=True)
    row = db.get(InferenceUsage, admitted.reservation_id)
    row.expires = (domain.database_now(db) - timedelta(seconds=1)).isoformat()
    db.commit()
    assert_error(409, "TRANSITION_BUSY", domain.change_mode, db, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=True)
    assert domain.reconcile_expired(db, ADMIN) == 1
    domain.change_mode(db, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=True)
    assert_error(409, "RESERVATION_FENCED", domain.fence, db, ADMIN, admitted)
    assert domain.finish_admission(db, ADMIN, admitted, "SUCCEEDED") is False
    assert db.get(InferenceUsage, admitted.reservation_id, populate_existing=True).status == "EXPIRED"


def test_multistep_mode_transition_and_no_silent_restoration(db):
    p, v = legacy(db)
    revision = domain.change_mode(db, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=True)
    assert db.get(Pin, ("one", p.id)).version_id == v.id
    revision = domain.change_mode(db, ADMIN, "LEGACY", expected_revision=revision, legacy_version_id=v.id)
    assert not db.get(Pin, ("one", p.id)).active
    domain.change_mode(db, ADMIN, "MULTI", expected_revision=revision, seed_legacy_assignment=False)
    assert not db.get(Pin, ("one", p.id)).active


def test_multiple_active_policies_prevent_legacy_transition(db):
    p1, v1 = policy(db)
    p2, v2 = policy(db)
    revision = activate(db, p1, v1, multi(db))
    revision = activate(db, p2, v2, revision)
    assert_error(409, "DEACTIVATE_OTHER_POLICIES_FIRST", domain.change_mode, db, ADMIN, "LEGACY", expected_revision=revision, legacy_version_id=v1.id)


def test_revision_change_fences_inflight_multi_request(db):
    p, v = policy(db)
    revision = activate(db, p, v, multi(db))
    admitted = domain.admit(db, ADMIN)
    domain.change_assignment(db, ADMIN, p.id, active=False, expected_revision=revision)
    assert_error(409, "POLICY_SET_CHANGED", domain.fence, db, ADMIN, admitted)


def test_foreign_reservation_cannot_be_used(db):
    legacy(db)
    admitted = domain.admit(db, ADMIN)
    assert_error(403, "RESERVATION_OWNER_MISMATCH", domain.fence, db, FOREIGN, admitted)


def test_admission_and_transition_share_atomic_gate(engine006, monkeypatch):
    with Session(engine006, expire_on_commit=False) as session:
        legacy(session)
    captured, resume, transition_started = ThreadEvent(), ThreadEvent(), ThreadEvent()
    original_capture = domain.capture

    def paused_capture(*args, **kwargs):
        result = original_capture(*args, **kwargs)
        captured.set()
        assert resume.wait(10)
        return result

    monkeypatch.setattr(domain, "capture", paused_capture)

    def admission():
        with Session(engine006, expire_on_commit=False) as session:
            return domain.admit(session, ADMIN, legacy_only=True)

    def transition():
        with Session(engine006, expire_on_commit=False) as session:
            transition_started.set()
            try:
                return domain.change_mode(session, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=True)
            except HTTPException as error:
                return error.detail

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(admission)
        assert captured.wait(10)
        second = workers.submit(transition)
        assert transition_started.wait(10)
        assert not second.done()
        resume.set()
        assert first.result(timeout=10).mode == "LEGACY"
        assert second.result(timeout=10) == "TRANSITION_BUSY"


def test_same_etag_concurrent_activation_one_winner(engine006):
    with Session(engine006, expire_on_commit=False) as session:
        p1, v1 = policy(session)
        p2, v2 = policy(session)
        revision = multi(session)
        pairs = [(p1.id, v1.id), (p2.id, v2.id)]

    def change(pair):
        with Session(engine006, expire_on_commit=False) as session:
            try:
                return domain.change_assignment(session, ADMIN, pair[0], active=True, version_id=pair[1], expected_revision=revision)
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(change, pairs))
    assert sorted(results) == [revision + 1, 412]
    with Session(engine006) as session:
        assert len(list(session.scalars(select(Pin).where(Pin.active.is_(True))))) == 1


@pytest.mark.parametrize("operation", ["activate", "disable", "archive", "delete"])
def test_existing_lifecycle_guard_blocks_multi_bypasses(db, operation):
    p, v = policy(db)
    activate(db, p, v, multi(db))
    expected = "USE_API_V2" if operation == "activate" else "DEACTIVATE_POLICY_FIRST"
    assert_error(409, expected, domain.guard_lifecycle, db, ADMIN, p.id, operation)
    db.rollback()


def test_legacy_governance_and_simulation_cannot_enter_multi(db, monkeypatch):
    from app.services.governance import governance
    from app.routers.policies import simulate_policy
    import asyncio
    from app import providers
    p, v = policy(db)
    activate(db, p, v, multi(db))
    generate = AsyncMock(side_effect=AssertionError("Provider must not run"))
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    for operation in ("generate", "validate-input", "validate-output"):
        with pytest.raises(HTTPException) as caught:
            asyncio.run(governance(operation, TextRequest(text="Safe text"), db, ADMIN))
        assert (caught.value.status_code, caught.value.detail) == (409, "USE_API_V2")
    with pytest.raises(HTTPException) as caught:
        asyncio.run(simulate_policy(p.id, TextRequest(text="Safe text"), db, ADMIN))
    assert caught.value.detail == "USE_API_V2"
    generate.assert_not_awaited()


def test_more_than_100_policies_are_captured(db):
    # One seed transaction, then actual independent assignment transactions.
    pairs = [policy(db, name=f"Policy {i}") for i in range(101)]
    revision = multi(db)
    for p, v in pairs:
        revision = activate(db, p, v, revision)
    admitted = domain.admit(db, ADMIN)
    assert len(admitted.pins) == 101
    assert len({p.policy_id for p in admitted.pins}) == 101


def test_inspection_contract_is_staged_and_requires_full_default_coverage():
    from typing import get_args
    document = PolicyDocument(name="Published policy")
    contract = inspection_contract((document,))
    assert contract.stages == STAGES
    assert contract.moderation_categories == frozenset(get_args(ModerationCategory))
    assert contract.unknown_required_control_withholds and contract.held_text_must_not_leave_process


@pytest.mark.parametrize("actual,expected", [
    ("([mode]='MULTI' OR [mode]='LEGACY')", "mode IN ('LEGACY','MULTI')"),
    ("(([version]>=(1)))", "version >= 1"),
    ("([new_mode] IS NOT NULL AND ([old_mode]<>[new_mode]))", "old_mode <> new_mode AND new_mode IS NOT NULL"),
])
def test_check_normalization_accepts_sqlserver_rewrites(actual, expected):
    assert canonical_check(actual) == canonical_check(expected)


@pytest.mark.parametrize("drift", ["missing_check", "weakened_check", "missing_trigger", "wrong_marker", "partial_execution"])
def test_006_schema_drift_is_rejected(engine006, drift):
    with engine006.begin() as connection:
        if drift in {"missing_check", "weakened_check"}:
            # Disposable fixture only: alter sqlite's stored DDL and reopen engine.
            connection.exec_driver_sql("PRAGMA writable_schema=ON")
            definition = connection.scalar(text("SELECT sql FROM sqlite_master WHERE name='workspace_policy_states'"))
            replacement = definition.replace("set_revision >= 1", "set_revision >= 0") if drift == "weakened_check" else definition.replace("ck_wps_revision", "unexpected_check")
            connection.execute(text("UPDATE sqlite_master SET sql=:sql WHERE name='workspace_policy_states'"), {"sql": replacement})
            connection.exec_driver_sql("PRAGMA writable_schema=OFF")
        elif drift == "missing_trigger":
            connection.exec_driver_sql("DROP TRIGGER immutable_execution_policy_evidence_delete")
        elif drift == "wrong_marker":
            connection.exec_driver_sql("UPDATE alembic_version SET version_num='005'")
        else:
            for name in MULTI_TABLES:
                connection.exec_driver_sql(f"DROP TABLE {name}")
            connection.exec_driver_sql("UPDATE alembic_version SET version_num='005'")
    engine006.dispose()
    with Session(engine006) as session, pytest.raises(HTTPException) as caught:
        inspect_schema(session)
    assert caught.value.status_code == 503


def test_actual_upgrade_preserves_execution_review_feedback_and_legacy_identity(templates, tmp_path):
    path = tmp_path / "retained.db"
    shutil.copyfile(templates["005"], path)
    engine = fixture_engine(path)
    with Session(engine) as session:
        p, v = legacy(session)
        execution = Execution(tenant="one", actor="admin", policy_id=p.id, version=v.number,
                              model="fixture", decision="HUMAN_REVIEW", metadata_json='{"kept":true}')
        session.add(execution)
        session.flush()
        session.add_all([Review(tenant="one", execution_id=execution.id), Feedback(tenant="one", execution_id=execution.id, rating=5)])
        session.commit()
        before = session.execute(text("SELECT * FROM validation_executions")).one()._asdict()
    engine.dispose()
    migrate(path, "006")
    engine = fixture_engine(path)
    with Session(engine) as session:
        after = session.execute(text("SELECT * FROM validation_executions")).one()._asdict()
        assert after.pop("execution_mode") == "LEGACY"
        assert before == after
        assert session.scalar(select(Review.execution_id)) == before["id"]
        assert session.scalar(select(Feedback.execution_id)) == before["id"]
        assert session.execute(text("PRAGMA foreign_key_check")).all() == []
        assert inspect_schema(session, require_sso=True)["revision"] == "006"
        assert session.scalar(select(State.mode)) == "LEGACY"
        assert session.scalar(select(Pin)) is None
    engine.dispose()


def test_invalid_existing_identity_blocks_migration_without_partial_objects(templates, tmp_path):
    path = tmp_path / "invalid.db"
    shutil.copyfile(templates["005"], path)
    engine = fixture_engine(path)
    with Session(engine) as session:
        session.add(Execution(tenant="one", actor="admin", policy_id="old", version=0,
                              model="fixture", decision="BLOCK", metadata_json="{}"))
        session.commit()
    result = subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", "006"], cwd=ROOT / "backend",
                            env={**os.environ, "DATABASE_URL": "sqlite:///" + str(path)}, capture_output=True, text=True)
    assert result.returncode != 0 and "LEGACY execution identities" in result.stderr
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "005"
        assert not MULTI_TABLES & set(inspect(connection).get_table_names())
    engine.dispose()


def test_admission_failure_rolls_back_snapshot_initialization_and_quota(db, monkeypatch):
    from app import usage
    from app.models import RateBucket
    legacy(db)

    def fail_reservation(*args, **kwargs):
        raise RuntimeError("Synthetic reservation failure")

    monkeypatch.setattr(usage, "reserve", fail_reservation)
    with pytest.raises(RuntimeError, match="Synthetic"):
        domain.admit(db, ADMIN, legacy_only=True)
    assert db.scalar(select(State)) is None
    assert db.scalar(select(AssignmentEvent)) is None
    assert db.scalar(select(InferenceUsage)) is None
    assert db.scalar(select(RateBucket)) is None


def test_assignment_event_failure_rolls_back_entire_change(db, monkeypatch):
    p, v = policy(db)
    revision = multi(db)

    def reject_event(*args, **kwargs):
        raise RuntimeError("Synthetic event failure")

    monkeypatch.setattr(domain, "_event", reject_event)
    with pytest.raises(RuntimeError, match="Synthetic"):
        activate(db, p, v, revision)
    assert db.scalar(select(State.set_revision)) == revision
    assert db.scalar(select(Pin)) is None


def test_repin_and_deactivation_same_etag_are_serialized(engine006):
    with Session(engine006, expire_on_commit=False) as session:
        p, v = policy(session)
        revision = activate(session, p, v, multi(session))
        v2 = Version(tenant="one", policy_id=p.id, number=2, document=v.document)
        session.add(v2)
        session.commit()
        pid, first_id, second_id = p.id, v.id, v2.id

    def change(repin):
        with Session(engine006, expire_on_commit=False) as session:
            try:
                return domain.change_assignment(session, ADMIN, pid, active=repin,
                    version_id=second_id if repin else None, expected_revision=revision)
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(change, [True, False]))
    assert sorted(results) == [revision + 1, 412]
    with Session(engine006) as session:
        pin = session.get(Pin, ("one", pid))
        assert (pin.active and pin.version_id == second_id) or (not pin.active and pin.version_id == first_id)


def test_activation_racing_disable_never_leaves_invalid_active_pin(engine006):
    from app.services.policies import transition_policy
    with Session(engine006, expire_on_commit=False) as session:
        p, v = policy(session)
        revision = multi(session)
        pid, vid = p.id, v.id

    def change(activate_pin):
        with Session(engine006, expire_on_commit=False) as session:
            try:
                if activate_pin:
                    domain.change_assignment(session, ADMIN, pid, active=True, version_id=vid, expected_revision=revision)
                else:
                    transition_policy(pid, "disable", session, ADMIN)
                    session.commit()
                return "SUCCESS"
            except HTTPException as error:
                session.rollback()
                return error.detail

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(change, [True, False]))
    assert results.count("SUCCESS") == 1
    with Session(engine006) as session:
        p = session.get(Policy, pid)
        pin = session.get(Pin, ("one", pid))
        assert not (pin and pin.active and not p.enabled)


def test_final_fence_holds_transition_until_completion_commit(engine006):
    with Session(engine006, expire_on_commit=False) as session:
        p, v = legacy(session)
        admitted = domain.admit(session, ADMIN, legacy_only=True)
    fenced, release, attempted = ThreadEvent(), ThreadEvent(), ThreadEvent()

    def completion():
        with Session(engine006, expire_on_commit=False) as session:
            domain.fence(session, ADMIN, admitted, hold=True)
            fenced.set()
            assert release.wait(10)
            domain.finish_admission(session, ADMIN, admitted, "INSPECTED", commit=False)
            session.commit()

    def transition():
        with Session(engine006, expire_on_commit=False) as session:
            attempted.set()
            return domain.change_mode(session, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=True)

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(completion)
        assert fenced.wait(10)
        second = workers.submit(transition)
        assert attempted.wait(10) and not second.done()
        release.set()
        first.result(timeout=10)
        assert second.result(timeout=10) == 2


def test_expired_unreconciled_reservation_cannot_complete_successfully(db):
    legacy(db)
    admitted = domain.admit(db, ADMIN, legacy_only=True)
    row = db.get(InferenceUsage, admitted.reservation_id)
    row.expires = "2000-01-01T00:00:00+00:00"
    db.commit()
    assert_error(409, "RESERVATION_FENCED", domain.finish_admission, db, ADMIN, admitted, "SUCCEEDED")
    assert db.get(InferenceUsage, admitted.reservation_id).status == "RESERVED"


def test_legacy_assignment_and_eligibility_changes_invalidate_workspace_etag(db):
    from app.services.policies import transition_policy
    legacy(db)
    domain.guard_legacy(db, ADMIN)
    db.commit()
    p2, _ = policy(db)
    transition_policy(p2.id, "activate", db, ADMIN)
    db.commit()
    assert db.scalar(select(State.set_revision)) == 2
    assert_error(412, "POLICY_SET_PRECONDITION_FAILED", domain.change_mode, db, ADMIN,
                 "MULTI", expected_revision=1, seed_legacy_assignment=True)
    transition_policy(p2.id, "disable", db, ADMIN)
    db.commit()
    assert db.scalar(select(State.set_revision)) == 3
    transition_policy(p2.id, "enable", db, ADMIN)
    db.commit()
    assert db.scalar(select(State.set_revision)) == 4
    events = list(db.scalars(select(AssignmentEvent).order_by(AssignmentEvent.set_revision, AssignmentEvent.event_ordinal)))
    assert [row.event_type for row in events] == ["INITIALIZE", "DEACTIVATE", "ACTIVATE", "DEACTIVATE", "ACTIVATE"]


def test_replacing_disabled_legacy_pointer_does_not_duplicate_deactivation(db):
    from app.services.policies import transition_policy
    p1, _ = legacy(db)
    transition_policy(p1.id, "disable", db, ADMIN)
    db.commit()
    p2, _ = policy(db)
    transition_policy(p2.id, "activate", db, ADMIN)
    db.commit()
    events = list(db.scalars(select(AssignmentEvent).order_by(AssignmentEvent.set_revision, AssignmentEvent.event_ordinal)))
    assert [row.event_type for row in events] == ["INITIALIZE", "DEACTIVATE", "ACTIVATE"]
