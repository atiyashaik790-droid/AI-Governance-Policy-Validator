"""Migration/recovery/concurrency acceptance against disposable local databases."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text, select, func
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from app import exports, providers, usage
from app.config import Settings, settings
from app.database import create_database_engine
from app.models import Base, ExportJob, InferenceUsage, Execution
from app.schemas import ExportRequest
from app.security import Identity

BACKEND = Path(__file__).resolve().parents[1]


def migrate(path, revision):
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{path}"},
        check=True,
        capture_output=True,
    )


def test_upgrade_existing_003_preserves_rows_and_protects_history(tmp_path):
    path = tmp_path / "existing.db"
    migrate(path, "003")
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_events (id,tenant,actor,action,resource,created) VALUES ('existing','one','fixture','fixture','fixture','2026-01-01')"
            )
        )
    migrate(path, "head")
    migrate(path, "head")
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "004"
        assert connection.execute(text("SELECT id FROM audit_events")).scalar() == "existing"
    for statement in ("UPDATE audit_events SET actor='changed'", "DELETE FROM audit_events"):
        with engine.begin() as connection:
            with pytest.raises(DBAPIError, match="append-only"):
                connection.execute(text(statement))
    assert "ix_execution_tenant_created" in {item["name"] for item in inspect(engine).get_indexes("validation_executions")}
    engine.dispose()


def test_concurrent_export_same_key_one_upload(tmp_path, monkeypatch):
    engine = create_database_engine(Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'exports.db'}"))
    Base.metadata.create_all(engine)
    entered, release = Event(), Event()
    uploads = []

    def upload(path, content):
        uploads.append((path, content))
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(providers, "upload_report", upload)
    payload = ExportRequest(idempotency_key="concurrent-example-1")

    def request():
        with Session(engine, expire_on_commit=False) as db:
            return exports.create(db, Identity("admin", "one", "Admin"), payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(request)
        assert entered.wait(5)
        second = pool.submit(request).result(timeout=5)
        release.set()
        completed = first.result(timeout=5)
    assert second["id"] == completed["id"] and len(uploads) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ExportJob)) == 1
    engine.dispose()


def test_concurrent_reservations_never_exceed_quota(tmp_path, monkeypatch):
    engine = create_database_engine(Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'limits.db'}"))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "inference_daily_quota", 1)

    def request():
        with Session(engine) as db:
            try:
                return usage.reserve(db, Identity("admin", "one", "Admin"))
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert sum(isinstance(value, str) for value in results) == 1 and results.count(429) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(InferenceUsage)) == 1
    engine.dispose()


def test_large_dataset_aggregation_and_bounded_exports(client, monkeypatch):
    from app import main

    dependency = main.app.dependency_overrides[main.get_database]()
    db = next(dependency)
    created = datetime.now(timezone.utc).isoformat()
    metadata = json.dumps({"input": {"score": 100, "breakdown": {"pii_detection": "SATISFIED"}, "contributions": {"pii_detection": 25}}})
    try:
        db.add_all(
            [
                Execution(
                    tenant=tenant,
                    actor="fixture",
                    policy_id="fixture",
                    version=1,
                    model="fixture",
                    decision="ALLOW",
                    metadata_json=metadata,
                    created=created,
                )
                for tenant, count in (("one", 2000), ("two", 500))
                for _ in range(count)
            ]
        )
        db.commit()
    finally:
        dependency.close()
    result = client.get("/api/analytics/overview").json()
    assert result["total_validations"] == 2000 and len(result["trends"]) == 100
    assert result["contributions"]["pii_detection"] == 50000
    monkeypatch.setattr(settings, "export_max_records", 100)
    upload = Mock()
    monkeypatch.setattr(providers, "upload_report", upload)
    assert client.post("/api/reports/export", json={}).status_code == 413
    upload.assert_not_called()


def test_disposable_sqlite_backup_restore_drill(tmp_path):
    import sqlite3

    source, backup = tmp_path / "source.db", tmp_path / "restore.db"
    migrate(source, "head")
    with sqlite3.connect(source) as db:
        db.execute(
            "INSERT INTO audit_events (id,tenant,actor,action,resource,created) VALUES ('restore-fixture','one','fixture','fixture','fixture','2026-10-31')"
        )
        with sqlite3.connect(backup) as destination:
            db.commit()
            db.backup(destination)
    with sqlite3.connect(backup) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert restored.execute("SELECT id FROM audit_events").fetchone() == ("restore-fixture",)
        assert restored.execute("SELECT version_num FROM alembic_version").fetchone() == ("004",)
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            restored.execute("DELETE FROM audit_events")
