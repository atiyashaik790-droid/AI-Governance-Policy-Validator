"""Approval A extracted-package tests, real guarded SQL Server transport and SQL runtime impersonation. Synthetic OIDC/keys and fixture providers only."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit


def tenant_gate(directory, database_path, revision, recovery=False, preserve_only=False):
    directory = Path(directory).resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import phase6b_approval_a as harness

    harness.guard(database=database_path)
    identity = {}
    with (harness.ROOT / ".env").open() as source:
        for line in source:
            key, separator, value = line.partition("=")
            if separator and key.strip() in {"AZURE_SQL_TENANT_ID", "AZURE_SQL_USER_OBJECT_ID"}:
                identity[key.strip()] = value.strip().strip("\"'")
    # Only the public operator identifiers above are inherited from local config.
    from pydantic_settings.sources import DotEnvSettingsSource

    DotEnvSettingsSource._read_env_files = lambda self: {}
    sys.path.insert(0, str(directory))
    origin = "https://package.example.test"
    tenant_id = "11111111-1111-4111-8111-111111111111"
    object_id = "33333333-3333-4333-8333-333333333" + revision
    os.environ.update(
        {
            "DATABASE_URL": "mssql+pyodbc://"
            + harness.SERVER
            + ".database.windows.net/"
            + harness.DB,
            "AZURE_SQL_AUTH_MODE": "managed_identity",
            "AZURE_SQL_TENANT_ID": identity["AZURE_SQL_TENANT_ID"],
            "AZURE_SQL_USER_OBJECT_ID": identity["AZURE_SQL_USER_OBJECT_ID"],
            "PROVIDER_MODE": "live",
            "PII_MODE": "presidio",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "fixture",
            "OPENAI_API_KEY": "synthetic-never-used",
            "AZURE_OPENAI_API_KEY": "",
            "ADLS_ACCOUNT_URL": "https://example.dfs.core.windows.net",
            "ADLS_FILE_SYSTEM": "synthetic" + revision,
            "CORS_ORIGIN": origin,
            "SSO_PUBLIC_ORIGIN": origin,
            "SSO_ENABLED": str(revision != "004").lower(),
            "ENTRA_TENANT_ID": tenant_id,
            "ENTRA_CLIENT_ID": "22222222-2222-4222-8222-222222222222",
            "ENTRA_CLIENT_SECRET": "synthetic-never-used",
            "SSO_SESSION_MINUTES": "120",
            "DEMO_BROWSER_LOGIN_ENABLED": "true",
            "ALLOW_LEGACY_API_CREDENTIALS": "false",
            "DEMO_ACCOUNTS_JSON": json.dumps(
                [
                    {
                        "user": "probe",
                        "tenant": "synthetic" + revision,
                        "role": "Admin",
                        "token_hash": hashlib.sha256(
                            b"synthetic-probe-token"
                        ).hexdigest(),
                    }
                ]
            ),
            "REVIEW_CAPTURE_ENABLED": "false",
            "REVIEW_CLEANUP_ENABLED": "false",
            "REVIEW_CONTENT_KEYS_JSON": "{}",
            "REVIEW_CONTENT_ACTIVE_KEY_ID": "",
            "INFERENCE_DAILY_QUOTA": "10000",
            "INFERENCE_USER_PER_MINUTE": "1000",
            "INFERENCE_TENANT_PER_MINUTE": "1000",
        }
    )
    # Pinned hosting code, actual SQL Server transport with EXECUTE AS test context.
    from sqlalchemy import select, text
    from app import azure_sql

    # Fail closed before application startup if any real provider path is reached.
    # SQL uses native ODBC and CLI authentication, independently of these clients.
    import httpx
    from app import providers

    def deny_provider(*args, **kwargs):
        raise AssertionError("Approval A forbids real provider/storage calls")

    httpx.AsyncClient.send = AsyncMock(side_effect=deny_provider)
    providers.upload_report = deny_provider
    providers.report_digest = deny_provider

    engine = harness.engine(runtime=True)
    azure_sql.create_azure_sql_engine = lambda *_args, **_kwargs: engine
    from app.hosting import app
    from app.config import settings
    from app.models import SsoMembership, Audit
    from app.database import SessionLocal
    from app import sso, protected_reviews as secure
    from fastapi.testclient import TestClient

    assert Path(__import__("app").__file__).resolve().parent == directory / "app"
    assert settings.sso_session_minutes == 120
    settings.provider_mode, settings.pii_mode = "fixture", "regex"
    settings.sso_enabled = False
    settings.review_capture_enabled = revision == "007" and not recovery
    settings.review_cleanup_enabled = revision == "007"
    if revision == "007":
        settings.review_content_active_key_id = "synthetic-local"
        settings.review_content_keys_json = json.dumps(
            {"synthetic-local": base64.b64encode(b"x" * 32).decode()}
        )
    from sqlalchemy.exc import DBAPIError
    import re
    accounts = []
    for actor, tenant in [("tenant-a006", "tenant-a006"), ("tenant-b006", "tenant-b006")]:
        accounts.append({"user": actor, "tenant": tenant, "role": "Admin", "token_hash": hashlib.sha256(actor.encode()).hexdigest()})
    settings.demo_accounts_json = json.dumps(accounts)
    with TestClient(app, base_url=origin) as client:
        login = client.post("/api/auth/session", headers={"Authorization": "Bearer tenant-a006"})
        assert login.status_code == 201
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        created = client.post("/api/policies", json={"name": "Tenant gate 006", "rules": {"blocked_keywords": {"enabled": True, "values": ["synthetic-only"], "action": "HUMAN_REVIEW"}}})
        assert created.status_code == 201
        pid = created.json()["id"]
        assert client.get("/api/policies/" + pid).status_code == 200
        for operation in ["submit", "approve", "publish"]:
            assert client.post(f"/api/policies/{pid}/{operation}").status_code == 200
        with SessionLocal() as db:
            version = db.scalar(text("SELECT id FROM policy_versions WHERE policy_id=:policy"), {"policy": pid})
            assert version
        login = client.post("/api/auth/session", headers={"Authorization": "Bearer tenant-b006"})
        assert login.status_code == 201
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        assert client.get("/api/policies/" + pid).status_code == 404
        state = client.get("/api/v2/workspace/policy-state")
        assert state.status_code == 200
        with SessionLocal() as db:
            try:
                db.execute(text("INSERT INTO workspace_policy_assignments(tenant,policy_id,version_id,active,changed_revision,updated_by) VALUES(:tenant,:policy,:version,1,1,'tenant-gate006')"), {"tenant": "tenant-b006", "policy": pid, "version": version})
                db.commit()
            except DBAPIError as error:
                assert re.search(r"\(547\)", str(error.orig))
                db.rollback()
            else:
                raise AssertionError("Cross-tenant assignment accepted")
            assert db.scalar(text("SELECT COUNT(*) FROM workspace_policy_assignments WHERE tenant=:tenant AND policy_id=:policy"), {"tenant": "tenant-b006", "policy": pid}) == 0
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "006"
    engine.dispose()
    return {"passed": True, "revision": "006", "same_tenant_read": 200, "foreign_tenant_read": 404, "cross_tenant_fk_native_code": 547, "failed_insert_retained_rows": 0}

if __name__ == "__main__":
    import tempfile
    import zipfile
    import os
    os.environ["PHASE6B_APPROVAL_A_WINDOW"] = "retry-4"
    os.environ["AZURE_CONFIG_DIR"] = str(Path(__file__).resolve().parents[3] / ".azure-sql-cli")
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "scripts"))
    evidence = Path(__file__).resolve().parent
    try:
        with tempfile.TemporaryDirectory(prefix="phase6b-tenant006-") as directory:
            package = root / "artifacts/phase6b-multi-fix-2026-11-06/candidate.zip"
            with zipfile.ZipFile(package) as archive:
                assert archive.testzip() is None
                archive.extractall(directory)
            result = tenant_gate(directory, "sqldb-gpv-mig-20261106-a1", "006")
        (evidence / "tenant-006-result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    except BaseException:
        raise  # Parent harness owns stop and finally cleanup for this sequential gate.
