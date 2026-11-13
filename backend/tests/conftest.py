import hashlib
import json
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Keep application imports and subprocesses on disposable database configuration.
_PRESERVED_DB = (Path(__file__).resolve().parents[2] / "private/demo-preserved/offline.db").resolve()
os.environ["DATABASE_URL"] = "sqlite://"


def _guard_preserved_database(event, args):
    if event != "sqlite3.connect" or not args:
        return
    target = str(args[0])
    if target.startswith("file:"):
        path, _, query = target[5:].partition("?")
        if "mode=ro" in query.split("&"):
            return
    else:
        path = target
    if Path(path).resolve() == _PRESERVED_DB:
        raise RuntimeError("Automated tests cannot write to the preserved demo database")


sys.addaudithook(_guard_preserved_database)

from app.models import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.database import get_database  # noqa: E402
from app.config import settings  # noqa: E402


# Provide independent disposable databases and server-side test identities.
@pytest.fixture
def client(monkeypatch):
    accounts = [
        {"user": token, "tenant": tenant, "role": role, "token_hash": hashlib.sha256(token.encode()).hexdigest()}
        for token, tenant, role in [
            ("admin", "one", "Admin"),
            ("developer", "one", "Developer"),
            ("auditor", "one", "Auditor"),
            ("reviewer", "one", "Reviewer"),
            ("foreign", "two", "Admin"),
        ]
    ]
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    monkeypatch.setattr(settings, "pii_mode", "regex")
    # Existing operator/adapter contracts explicitly exercise compatibility mode.
    monkeypatch.setattr(settings, "allow_legacy_api_credentials", True)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    # Roll back failed tests' requests exactly as the real session dependency does.
    def test_database():
        with Session(engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_database] = test_database
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers["Authorization"] = "Bearer admin"
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
