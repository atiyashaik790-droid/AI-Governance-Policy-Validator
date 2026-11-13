"""Additive execution-history repair: disposable SQLite and offline MSSQL only."""
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app.schema_compatibility import inspect_schema, verify_runtime_permissions, SchemaCheckError
from app.schema_manifests import history_for_revision
import test_multi_policy_phase_b as phase_b

ROOT = Path(__file__).resolve().parents[2]


def migration():
    spec = importlib.util.spec_from_file_location("execution008", ROOT / "backend/migrations/versions/008_execution_immutability.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repaired(tmp_path):
    path = tmp_path / "execution.db"
    phase_b.migrate(path, "007")
    engine = phase_b.fixture_engine(path)
    with engine.begin() as c:
        # Reproduce the exact Azure failure before the additive repair.
        for tenant in ("one", "two"):
            c.execute(text("INSERT INTO validation_executions(id,tenant,actor,model,decision,metadata_json,created,execution_mode) VALUES (:id,:tenant,'fixture','fixture','ALLOW','{}','2026-11-07','MULTI')"), {"id": tenant, "tenant": tenant})
        c.execute(text("UPDATE validation_executions SET tenant=tenant"))
        before = c.execute(text("SELECT * FROM validation_executions ORDER BY id")).all()
    phase_b.migrate(path, "008")
    with engine.connect() as c:
        assert c.execute(text("SELECT * FROM validation_executions ORDER BY id")).all() == before
    yield engine
    engine.dispose()


@pytest.mark.parametrize("statement", [
    "UPDATE validation_executions SET tenant=tenant",
    "UPDATE validation_executions SET tenant='two' WHERE id='one'",
    "UPDATE validation_executions SET metadata_json='changed' WHERE id='one'",
    "DELETE FROM validation_executions WHERE tenant='one'",
    "DELETE FROM validation_executions",
])
def test_raw_sql_cannot_change_or_delete_execution_history(repaired, statement):
    with repaired.begin() as c:
        with pytest.raises(DBAPIError, match="append-only"):
            c.execute(text(statement))
    with repaired.connect() as c:
        assert c.execute(text("SELECT id,tenant,metadata_json FROM validation_executions ORDER BY id")).all() == [("one", "one", "{}"), ("two", "two", "{}")]


def test_insert_and_readiness_work_without_widening_tenant_fk(repaired):
    with Session(repaired) as db:
        policy, version = phase_b.policy(db)
        policy_id, version_id = policy.id, version.id
    with repaired.begin() as c:
        c.execute(text("INSERT INTO validation_executions(id,tenant,actor,model,decision,metadata_json,created,execution_mode) VALUES ('new','one','fixture','fixture','ALLOW','{}','2026-11-07','MULTI')"))
        with pytest.raises(DBAPIError, match="FOREIGN KEY"):
            c.execute(text("INSERT INTO execution_policy_evidence(tenant,execution_id,policy_id,version_id,set_revision,document_sha256,effective_decision,inspection_status,evidence_json) VALUES ('two','new',:policy,:version,1,:digest,'ALLOW','COMPLETE','{}')"), {"digest": "a" * 64, "policy": policy_id, "version": version_id})
    with Session(repaired) as db:
        assert inspect_schema(db, require_sso=True)["revision"] == "008"
    assert "validation_executions" not in history_for_revision("007")
    assert "validation_executions" in history_for_revision("008")


@pytest.mark.parametrize("action", ["update", "delete"])
def test_008_missing_trigger_fails_closed(repaired, action):
    with repaired.begin() as c:
        c.exec_driver_sql(f"DROP TRIGGER immutable_validation_executions_{action}")
    with Session(repaired) as db:
        with pytest.raises(HTTPException) as error:
            inspect_schema(db)
        assert error.value.status_code == 503
        assert error.value.safe_diagnostic["category"] == "HISTORY_TRIGGER_MISSING"


def test_frozen_chain_hashes_unchanged():
    pins = json.loads((ROOT / "docs/evidence/phase6b-consolidated-local-2026-11-06/local-artifacts.json").read_text())
    import hashlib
    for name, expected in pins["migration_hashes"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected


def test_mssql_008_offline_ddl_and_downgrade_refusal(monkeypatch):
    output = io.StringIO()
    context = MigrationContext.configure(dialect_name="mssql", opts={"as_sql": True, "output_buffer": output})
    module = migration()
    monkeypatch.setattr(module, "op", Operations(context))
    module.upgrade()
    ddl = output.getvalue()
    assert "008 requires dbo default schema" in ddl
    assert "CREATE TRIGGER dbo.immutable_validation_executions ON dbo.validation_executions INSTEAD OF UPDATE, DELETE" in ddl
    assert "THROW 51000" in ddl and "append-only" in ddl
    assert "DROP" not in ddl and "ALTER TABLE" not in ddl
    assert module.down_revision == "007"
    with pytest.raises(RuntimeError, match="must not be removed"):
        module.downgrade()


@pytest.mark.parametrize("effective", [1, None])
def test_008_runtime_mutation_grants_or_unknown_fail_closed(effective):
    connection = SimpleNamespace(scalar=lambda *_args, **_kwargs: effective)
    with pytest.raises(SchemaCheckError, match="EXECUTION_MUTATION_PERMISSION_NOT_DENIED"):
        verify_runtime_permissions(connection, require_sso=True, revision="008")


def test_008_missing_required_grant_fails_closed():
    connection = SimpleNamespace(scalar=lambda *_args, **_kwargs: 0)
    with pytest.raises(SchemaCheckError, match="REQUIRED_EFFECTIVE_PERMISSION_MISSING"):
        verify_runtime_permissions(connection, require_sso=True, revision="008")
