from pathlib import Path
import subprocess
import os
import sys
from sqlalchemy import create_engine, inspect
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
import pytest
from app.models import Base, Policy, Version, Audit


# Compile every table and index using the SQL Server dialect; this is not live execution.
def test_sql_server_schema_compiles():
    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=mssql.dialect()))
        for index in table.indexes:
            assert str(CreateIndex(index).compile(dialect=mssql.dialect()))


# Apply actual migrations to a disposable SQLite file, including a repeated upgrade.
def test_migrations_on_fresh_sqlite(tmp_path):
    database = tmp_path / "migration.db"
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{database}"}
    for _ in range(2):
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            check=True,
            capture_output=True,
        )
    engine = create_engine(f"sqlite:///{database}")
    assert {"policies", "policy_versions", "audit_events", "validation_executions"} <= set(inspect(engine).get_table_names())
    engine.dispose()


# Concurrent draft edits invalidate a stale lifecycle update at the database write boundary.
def test_optimistic_policy_concurrency():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        policy = Policy(tenant="one", name="Original", draft="{}")
        session.add(policy)
        session.commit()
        policy_id = policy.id
    with Session(engine) as first, Session(engine) as second:
        first_policy = first.get(Policy, policy_id)
        second_policy = second.get(Policy, policy_id)
        first_policy.name = "New draft"
        first.commit()
        second_policy.status = "APPROVED"
        with pytest.raises(StaleDataError):
            second.commit()
    engine.dispose()


# Historical ORM records reject update and deletion operations.
@pytest.mark.parametrize("record_type", [Version, Audit])
def test_append_only_history(record_type):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        policy = Policy(tenant="one", name="Policy", draft="{}")
        session.add(policy)
        session.flush()
        record = (
            Version(tenant="one", policy_id=policy.id, number=1, document="{}")
            if record_type is Version
            else Audit(tenant="one", actor="admin", action="created", resource=policy.id)
        )
        session.add(record)
        session.commit()
        session.delete(record)
        with pytest.raises(ValueError, match="append-only"):
            session.commit()
    engine.dispose()


# Two reviewers cannot both resolve the same pending case from a stale snapshot.
def test_optimistic_review_concurrency():
    from app.models import Review, Execution

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        execution = Execution(
            tenant="one", actor="admin", policy_id="policy", version=1, model="fixture", decision="HUMAN_REVIEW", metadata_json="{}"
        )
        session.add(execution)
        session.flush()
        review = Review(tenant="one", execution_id=execution.id)
        session.add(review)
        session.commit()
        review_id = review.id
    with Session(engine) as first, Session(engine) as second:
        approved = first.get(Review, review_id)
        rejected = second.get(Review, review_id)
        approved.status = "APPROVED_RESUBMIT_REQUIRED"
        first.commit()
        rejected.status = "REJECTED"
        with pytest.raises(StaleDataError):
            second.commit()
    engine.dispose()
