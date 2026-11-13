"""New audit roles are authenticated facts; older events remain unattributed."""
import os
import sqlite3
import subprocess
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.repositories import record_audit_event
from app.routers.audit import audit_events
from app.routers.reporting_v2 import events
from app.security import Identity
from app.schema_compatibility import inspect_schema

ROOT = Path(__file__).resolve().parents[2]


def test_local_010_migration_and_audit_api_preserve_historical_unknown(tmp_path):
    database = tmp_path / "audit-role.db"
    environment = {**os.environ, "DATABASE_URL": "sqlite:///" + str(database), "PROVIDER_MODE": "fixture"}
    command = [str(ROOT / ".venv/bin/alembic"), "-c", str(ROOT / "backend/alembic.ini"), "upgrade"]
    subprocess.run(command + ["009"], cwd=ROOT / "backend", env=environment, check=True, capture_output=True)
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO audit_events (id, tenant, actor, action, resource, created) VALUES (?, ?, ?, ?, ?, ?)",
                       ("old-event", "tenant-one", "synthetic-admin", "policy.created", "missing-policy", "2026-01-01T00:00:00+00:00"))
    connection.commit()
    connection.close()
    subprocess.run(command + ["010"], cwd=ROOT / "backend", env=environment, check=True, capture_output=True)
    engine = create_engine("sqlite:///" + str(database))
    admin = Identity(user="offline-admin", tenant="tenant-one", role="Admin")
    other = Identity(user="other", tenant="other-tenant", role="User")
    with Session(engine) as db:
        assert inspect_schema(db)["revision"] == "010"
        record_audit_event(db, admin, "policy.created", "missing-policy")
        db.commit()
        rows = audit_events(offset=0, limit=10, category="policy", db=db, user=admin)
        assert len(rows) == 2
        assert {row["actor"]: row["actor_role"] for row in rows} == {
            "offline-admin": "Admin", "synthetic-admin": "Not recorded"
        }
        result = events(offset=0, limit=10, category="policy", db=db, user=admin)
        assert result["total"] == 2
        assert {row["actor"]: row["actor_role"] for row in result["items"]} == {
            "offline-admin": "Admin", "synthetic-admin": "Not recorded"
        }
        assert events(offset=0, limit=10, category="policy", db=db, user=other)["items"] == []
    engine.dispose()
