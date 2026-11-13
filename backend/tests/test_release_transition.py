"""005→006→007 rehearsal and extracted release contracts; disposable SQLite only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import zipfile

import pytest
from sqlalchemy import create_engine, event, text
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("transition_package", ROOT / "scripts/prepare_app_service.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def migrate(path, revision, check=True):
    return subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", revision], cwd=ROOT / "backend",
                          env={**os.environ, "DATABASE_URL": "sqlite:///" + str(path), "PROVIDER_MODE": "fixture", "PII_MODE": "regex"},
                          capture_output=True, text=True, check=check, timeout=60)


@pytest.fixture(scope="module")
def packaged(tmp_path_factory):
    directory = tmp_path_factory.mktemp("release-transition")
    dist = directory / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<script src="/assets/index-fixture.js"></script>')
    (dist / "assets/index-fixture.js").write_text("fetch('/health')")
    manifest = builder.package(ROOT, dist, directory / "candidate.zip")
    extracted = directory / "extracted"
    with zipfile.ZipFile(directory / "candidate.zip") as archive:
        assert archive.testzip() is None
        archive.extractall(extracted)
    return directory, dist, manifest, extracted


def test_release_identity_covers_source_and_schema_contract(packaged):
    directory, dist, manifest, _ = packaged
    again = builder.package(ROOT, dist, directory / "second.zip")
    assert again["release"]["build_version"] == manifest["release"]["build_version"]
    assert manifest["release"]["supported_migrations"] == ["004", "005", "006", "007", "008", "009"]
    expected = {"files": manifest["member_sha256"], "schema_contract": {
        key: manifest["release"][key] for key in ["required_migration", "supported_migrations", "sso_required_migration"]}}
    assert manifest["release"]["build_version"] == "1.2-" + hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()[:16]
    for name, digest in manifest["member_sha256"].items():
        with zipfile.ZipFile(directory / "candidate.zip") as archive:
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    assert "app/services/multi_policy_governance.py" in manifest["files"]
    assert "app/protected_reviews.py" in manifest["files"]


@pytest.mark.parametrize("revision", ["004", "005", "006", "007", "008", "009"])
def test_extracted_candidate_works_at_each_declared_revision(packaged, tmp_path, revision):
    _, _, _, extracted = packaged
    db = tmp_path / "candidate.db"
    migrate(db, revision)
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/tests/phase6a_package_probe.py"),
                             "--directory", str(extracted), "--database", str(db), "--revision", revision],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-5000:]
    assert json.loads(result.stdout.splitlines()[-1])["passed"]


def test_005_to_007_preserves_synthetic_records_and_history(tmp_path):
    db = tmp_path / "rehearsal.db"
    migrate(db, "005")
    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO audit_events(id,tenant,actor,action,resource,created) VALUES('retained','synthetic','probe','fixture','fixture','2026-01-01')")
        baseline = connection.execute("SELECT * FROM audit_events").fetchall()
    for revision in ["006", "007"]:
        migrate(db, revision)
        with sqlite3.connect(db) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (revision,)
            assert connection.execute("SELECT * FROM audit_events").fetchall() == baseline
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert not connection.execute("PRAGMA foreign_key_check").fetchall()
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute("DELETE FROM audit_events WHERE id='retained'")


def test_reserved_work_stops_006_before_schema_changes(tmp_path):
    db = tmp_path / "reserved.db"
    migrate(db, "005")
    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO inference_usage(id,tenant,actor,status,created,expires) VALUES('reserved','synthetic','probe','RESERVED','2026-01-01','2026-01-02')")
    result = migrate(db, "006", check=False)
    assert result.returncode != 0 and "drained and reconciled" in result.stderr
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("005",)
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='workspace_policy_states'").fetchone() == (0,)
        assert connection.execute("SELECT status FROM inference_usage").fetchone() == ("RESERVED",)


def test_007_ddl_failure_does_not_advance_marker_or_destroy_audit(tmp_path, monkeypatch):
    from app import database
    db = tmp_path / "failed007.db"
    migrate(db, "006")
    engine = create_engine("sqlite:///" + str(db))
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO audit_events(id,tenant,actor,action,resource,created) VALUES('retained','synthetic','probe','fixture','fixture','2026-01-01')"))
    @event.listens_for(engine, "before_cursor_execute")
    def fail_table(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "CREATE TABLE review_protected_content" in statement:
            raise RuntimeError("synthetic DDL interruption")
    monkeypatch.setattr(database, "engine", engine)
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend/migrations"))
    with pytest.raises(RuntimeError, match="synthetic DDL interruption"):
        command.upgrade(config, "007")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "006"
        assert connection.scalar(text("SELECT id FROM audit_events")) == "retained"
    engine.dispose()
    # An unchanged marker is not proof of an atomic DDL rollback. Operator inspection
    # is mandatory; the pre-table index may remain on SQLite. Never auto-retry here.


def test_frozen_fallback_executes_on007_with_capture_disabled(packaged, tmp_path):
    directory, _, _, _ = packaged
    fallback = tmp_path / "fallback.zip"
    shutil.copyfile(directory / "candidate.zip", fallback)
    extracted = tmp_path / "fallback"
    with zipfile.ZipFile(fallback) as archive:
        archive.extractall(extracted)
    db = tmp_path / "fallback.db"
    migrate(db, "007")
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/tests/phase6a_package_probe.py"),
                             "--directory", str(extracted), "--database", str(db), "--revision", "007", "--recovery"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-5000:]
    assert json.loads(result.stdout.splitlines()[-1])["recovery"]



def test_representative005_records_survive_both_migrations(packaged, tmp_path):
    _, _, _, extracted = packaged
    path = tmp_path / "representative.db"
    migrate(path, "005")
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/tests/phase6a_package_probe.py"),
                             "--directory", str(extracted), "--database", str(path), "--revision", "005"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-3000:]
    with sqlite3.connect(path) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'") if row[0] != "alembic_version"]
        columns = {table: [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')] for table in tables}
        snapshots = {table: sorted(connection.execute(f'SELECT * FROM "{table}"').fetchall(), key=repr) for table in tables}
        for table in ["policies", "policy_versions", "active_policy_assignments", "validation_executions", "human_review_cases", "audit_events", "sso_sessions"]:
            assert snapshots[table]
    for revision in ["006", "007"]:
        migrate(path, revision)
        with sqlite3.connect(path) as connection:
            for table in tables:
                projection = ",".join('"' + name + '"' for name in columns[table])
                assert sorted(connection.execute(f'SELECT {projection} FROM "{table}"').fetchall(), key=repr) == snapshots[table]
            assert not connection.execute("PRAGMA foreign_key_check").fetchall()
            assert connection.execute("SELECT DISTINCT execution_mode FROM validation_executions").fetchall() == [("LEGACY",)]
            if revision == "007":
                assert connection.execute("SELECT COUNT(*) FROM review_protected_content").fetchone() == (0,)


def test_fallback_preserves_pending_ciphertext_and_immutable_history(packaged, tmp_path):
    _, _, _, extracted = packaged
    path = tmp_path / "encrypted.db"
    migrate(path, "007")
    arguments = [sys.executable, "-B", str(ROOT / "scripts/tests/phase6a_package_probe.py"),
                 "--directory", str(extracted), "--database", str(path), "--revision", "007"]
    first = subprocess.run(arguments, cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert first.returncode == 0, first.stderr[-3000:]
    with sqlite3.connect(path) as connection:
        ciphertext = connection.execute("SELECT * FROM review_protected_content").fetchall()
        audit = connection.execute("SELECT * FROM audit_events ORDER BY id").fetchall()
        assert ciphertext and audit
    second = subprocess.run(arguments + ["--recovery", "--preserve-only"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert second.returncode == 0, second.stderr[-3000:]
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT * FROM review_protected_content").fetchall() == ciphertext
        assert connection.execute("SELECT * FROM audit_events ORDER BY id").fetchall() == audit


def test_bridge_process_and_existing_session_survive_ordered_maintenance_migrations(client, tmp_path, monkeypatch):
    from sqlalchemy.orm import Session
    from app.main import app
    from app.database import get_database, create_database_engine
    from app.config import settings, Settings

    path = tmp_path / "running-bridge.db"
    migrate(path, "005")
    engine = create_database_engine(Settings(_env_file=None, database_url="sqlite:///" + str(path)))
    monkeypatch.setattr(settings, "sso_enabled", False)
    monkeypatch.setattr(settings, "demo_browser_login_enabled", True)
    monkeypatch.setattr(settings, "review_capture_enabled", False)
    monkeypatch.setattr(settings, "review_cleanup_enabled", False)
    def dependency():
        with Session(engine, expire_on_commit=False) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_database] = dependency
    login = client.post("/api/auth/session")
    assert login.status_code == 201
    client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    created = client.post("/api/policies", json={"name": "Running bridge"})
    assert created.status_code == 201
    for operation in ["submit", "approve", "publish", "activate"]:
        assert client.post(f"/api/policies/{created.json()['id']}/{operation}").status_code == 200
    for revision in ["005", "006", "007"]:
        if revision != "005":
            # No requests in flight while the external operator applies migrations.
            migrate(path, revision)
        ready = client.get("/ready")
        assert ready.status_code == 200 and ready.json()["database_revision"] == revision
        result = client.post("/api/governance/generate", json={"text": "Explain governance"})
        assert result.status_code == 200 and result.json()["decision"] == "ALLOW"
    engine.dispose()
