import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.models import Base
from app.main import app
from app.database import get_database
from app.config import settings


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
