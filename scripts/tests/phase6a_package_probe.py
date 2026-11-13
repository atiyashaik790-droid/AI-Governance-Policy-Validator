"""Local extracted-package acceptance. Synthetic keys/identities; fixture providers only."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit


def probe(directory, database_path, revision, recovery=False, preserve_only=False):
    directory = Path(directory).resolve()
    database_path = Path(database_path).resolve()
    assert database_path.is_file()
    sys.path.insert(0, str(directory))
    origin = "https://package.example.test"
    tenant_id = "11111111-1111-4111-8111-111111111111"
    object_id = "33333333-3333-4333-8333-333333333333"
    os.environ.update(
        {
            "DATABASE_URL": "mssql+pyodbc://example.database.windows.net/synthetic",
            "AZURE_SQL_AUTH_MODE": "managed_identity",
            "AZURE_SQL_TENANT_ID": tenant_id,
            "AZURE_SQL_USER_OBJECT_ID": object_id,
            "PROVIDER_MODE": "live",
            "PII_MODE": "presidio",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "fixture",
            "OPENAI_API_KEY": "synthetic-never-used",
            "AZURE_OPENAI_API_KEY": "",
            "ADLS_ACCOUNT_URL": "https://example.dfs.core.windows.net",
            "ADLS_FILE_SYSTEM": "synthetic",
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
                        "tenant": "synthetic",
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
    # Real hosting validation, with only the SQL transport substituted locally.
    from sqlalchemy import create_engine, event, select, text
    from app import azure_sql

    engine = create_engine(
        "sqlite:///" + str(database_path), connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

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
    settings.review_capture_enabled = revision in {"007", "008", "009"} and not recovery
    settings.review_cleanup_enabled = revision in {"007", "008", "009"}
    if revision in {"007", "008", "009"}:
        settings.review_content_active_key_id = "synthetic-local"
        settings.review_content_keys_json = json.dumps(
            {"synthetic-local": base64.b64encode(b"x" * 32).decode()}
        )
    checks = []
    session_evidence = None
    with TestClient(app, base_url=origin) as client:
        if revision in {"007", "008"}:
            for _ in range(100):
                if secure.health.healthy(engine):
                    break
                time.sleep(0.02)
            assert secure.health.healthy(engine)
        ready = client.get("/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["database_revision"] == revision
        assert ready.json()["release"]["supported_migrations"] == [
            "004",
            "005",
            "006",
            "007",
            "008",
            "009",
        ]
        assert client.get("/chat").status_code == 200
        assert client.get("/api/policies").status_code == 401
        checks.extend(
            [
                "extracted hosting import",
                "schema/readiness",
                "release contract",
                "SPA/auth boundary",
            ]
        )
        if preserve_only:
            assert recovery and revision in {"007", "008", "009"}
            from app.models_review_content import ProtectedReviewContent as Content
            from app.models import Review

            with SessionLocal() as db:
                rows = db.scalars(select(Content)).all()
                assert rows
                for row in rows:
                    assert secure.decrypt_prompt(
                        row, db.get(Review, row.review_id).execution_id
                    )
                assert not settings.review_capture_enabled
            return {
                "revision": revision,
                "recovery": True,
                "passed": True,
                "checks": checks
                + [
                    "retained ciphertext decryptable with stable synthetic key; capture disabled; cleanup healthy"
                ],
            }
        if revision != "004":
            with SessionLocal.begin() as db:
                member = db.scalar(
                    select(SsoMembership).where(SsoMembership.object_id == object_id)
                )
                if member is None:
                    db.add(
                        SsoMembership(
                            directory_tenant=tenant_id,
                            object_id=object_id,
                            tenant="synthetic",
                            actor="probe",
                            role="Admin",
                            enabled=1,
                        )
                    )
            settings.sso_enabled, settings.demo_browser_login_enabled = True, False
            sso.metadata = AsyncMock(
                return_value={"authorization_endpoint": origin + "/synthetic-authorize"}
            )
            sso.exchange_code = AsyncMock(
                return_value={"tid": tenant_id, "oid": object_id}
            )
            start = client.get(
                "/api/sso/login", params={"return_to": "/chat"}, follow_redirects=False
            )
            assert start.status_code == 302
            state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
            from session_contract import observe_issuance, verify_session
            from app.models import SsoSession

            with observe_issuance(sso, settings.sso_session_minutes) as issued:
                callback = client.get(
                    "/api/sso/callback",
                    params={"state": state, "code": "synthetic"},
                    follow_redirects=False,
                )
                assert callback.status_code == 303
            raw_cookie = client.cookies.get(sso.COOKIE)
            with SessionLocal() as db:
                persisted = db.get(SsoSession, sso.digest(raw_cookie)).expires
            me = client.get("/api/sso/me")
            assert me.status_code == 200
            print(
                json.dumps(
                    {
                        "event": "session.observation",
                        "configured_minutes": settings.sso_session_minutes,
                        "issued_before_utc": issued[0]["before"].isoformat(),
                        "issued_after_utc": issued[0]["after"].isoformat(),
                        "database_expires_utc": persisted,
                        "expires_at": me.json()["expires_at"],
                        "server_now": me.json()["server_now"],
                    }
                ),
                flush=True,
            )
            session_evidence = verify_session(
                sso, issued, callback, persisted, me.json()
            )
            with SessionLocal() as db:
                assert db.get(SsoSession, sso.digest(raw_cookie)).expires == persisted
            print(
                json.dumps({"event": "session.contract", **session_evidence}),
                flush=True,
            )
            settings.sso_enabled, settings.demo_browser_login_enabled = False, True
            client.cookies.clear()
            checks.append("mock SSO /chat callback and secure 120-minute session")
        token = client.post(
            "/api/auth/session",
            headers={"Authorization": "Bearer synthetic-probe-token"},
        )
        assert token.status_code == 201, token.text
        client.headers["Authorization"] = "Bearer " + token.json()["access_token"]
        doc = {
            "name": "Packaged transition",
            "rules": {
                "blocked_keywords": {
                    "enabled": True,
                    "values": ["internal-only"],
                    "action": "HUMAN_REVIEW",
                }
            },
        }
        created = client.post("/api/policies", json=doc)
        assert created.status_code == 201, created.text
        pid = created.json()["id"]
        for operation in ["submit", "approve", "publish", "activate"]:
            response = client.post(f"/api/policies/{pid}/{operation}")
            assert response.status_code == 200, response.text
        allowed = client.post(
            "/api/governance/generate", json={"text": "Explain safe governance"}
        )
        assert allowed.status_code == 200 and allowed.json()["decision"] == "ALLOW", (
            allowed.text
        )
        prompt = "internal-only synthetic original"
        held = client.post("/api/governance/generate", json={"text": prompt})
        assert held.status_code == 200 and held.json()["decision"] == "HUMAN_REVIEW", (
            held.text
        )
        checks.append("policy lifecycle and LEGACY ALLOW/HUMAN_REVIEW")
        if revision in {"007", "008", "009"}:
            from app.models_review_content import ProtectedReviewContent as Content

            with SessionLocal() as db:
                row = db.get(Content, ("synthetic", held.json()["review_id"]))
                if recovery:
                    assert row is None
                else:
                    assert row and prompt.encode() not in row.ciphertext
                    assert row.expires_at - row.created_at == 604800
                assert db.scalar(select(Audit.id).limit(1))
            checks.append(
                "capture disabled with healthy cleanup"
                if recovery
                else "encrypted capture, expiry and audit"
            )
        if revision in {"006", "007", "008", "009"}:
            state = client.get("/api/v2/workspace/policy-state")
            switched = client.put(
                "/api/v2/workspace/policy-mode",
                headers={"If-Match": state.headers["etag"]},
                json={"mode": "MULTI", "seed_legacy_assignment": True},
            )
            assert switched.status_code == 200, switched.text
            current = client.get("/api/v2/workspace/policy-state")
            result = client.post(
                "/api/v2/governance/generate",
                headers={"If-Match": current.headers["etag"]},
                json={"text": "Explain safe governance"},
            )
            assert result.status_code == 200 and result.json()["decision"] == "ALLOW", (
                result.text
            )
            assert (
                client.post(
                    "/api/governance/generate", json={"text": "safe"}
                ).status_code
                == 409
            )
            checks.append("MULTI transition, execution and v1 guard")
        with SessionLocal() as db:
            assert db.scalar(text("PRAGMA integrity_check")) == "ok"
            assert not db.execute(text("PRAGMA foreign_key_check")).all()
        checks.append("database integrity and retained foreign keys")
    engine.dispose()
    return {
        "revision": revision,
        "recovery": recovery,
        "checks": checks,
        "session_contract": session_evidence,
        "passed": True,
        "limits": "SQLite transport, synthetic keys/OIDC, fixture providers; no Azure SQL execution",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--revision", choices=["004", "005", "006", "007", "008", "009"], required=True
    )
    parser.add_argument("--recovery", action="store_true")
    parser.add_argument("--preserve-only", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            probe(
                args.directory,
                args.database,
                args.revision,
                args.recovery,
                args.preserve_only,
            )
        )
    )
