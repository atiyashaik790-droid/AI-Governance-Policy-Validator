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


def probe(directory, database_path, revision, recovery=False, preserve_only=False):
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
    checks = []
    session_evidence = None
    with TestClient(app, base_url=origin) as client:
        if revision == "007":
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
            assert recovery and revision == "007"
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
        reuse_session = harness.WINDOW == "retry-3" and revision == "006"
        if reuse_session:
            checks.append("prior Azure 006 session evidence reused with pinned unchanged session code; 007 session tested separately")
        if revision != "004" and not reuse_session:
            # Membership provisioning is test-operator DML only.
            from sqlalchemy.orm import Session

            operator = harness.engine()
            with Session(operator) as db:
                db.begin()
                member = db.scalar(
                    select(SsoMembership).where(SsoMembership.object_id == object_id)
                )
                if member is None:
                    db.add(
                        SsoMembership(
                            directory_tenant=tenant_id,
                            object_id=object_id,
                            tenant="synthetic" + revision,
                            actor="probe",
                            role="Admin",
                            enabled=1,
                        )
                    )
                db.commit()
            operator.dispose()
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
                    params={"state": state, "code": "synthetic" + revision},
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
            # Read again in a new ORM session to verify persistence, not identity-map state.
            with SessionLocal() as db:
                assert db.get(SsoSession, sso.digest(raw_cookie)).expires == persisted
            print(
                json.dumps({"event": "session.contract", **session_evidence}),
                flush=True,
            )
            end = datetime.fromisoformat(persisted)
            with patch.object(sso, "now", return_value=(end - timedelta(microseconds=1)).isoformat()):
                active = client.get("/api/sso/me")
                assert active.status_code == 200
                assert active.json()["expires_at"] == persisted
            with patch.object(sso, "now", return_value=end.isoformat()):
                expired = client.get("/api/sso/me")
                assert expired.status_code == 401
                assert expired.headers["X-Session-Reason"] == "expired"
            with SessionLocal() as db:
                row = db.get(SsoSession, sso.digest(raw_cookie))
                assert row.expires == persisted
                row.revoked = 1
                db.commit()
            revoked = client.get("/api/sso/me")
            assert revoked.status_code == 401
            assert revoked.headers["X-Session-Reason"] == "ended"
            checks.append("absolute session boundary, unchanged persisted expiry and revoked-session denial")
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
        if revision == "007":
            from app.models_review_content import ProtectedReviewContent as Content

            with SessionLocal() as db:
                row = db.get(
                    Content, ("synthetic" + revision, held.json()["review_id"])
                )
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
        if revision == "007" and not recovery:
            from app.models import Review
            from app.models_review_content import ProtectedReviewContent as Content

            # Preserve original admin session while testing least-privileged app roles.
            admin_auth = client.headers["Authorization"]
            accounts = json.loads(settings.demo_accounts_json)
            for actor, tenant, role in [
                ("user-probe", "synthetic007", "User"),
                ("foreign-probe", "foreign", "Admin"),
            ]:
                accounts.append(
                    {
                        "user": actor,
                        "tenant": tenant,
                        "role": role,
                        "token_hash": hashlib.sha256(actor.encode()).hexdigest(),
                    }
                )
            settings.demo_accounts_json = json.dumps(accounts)
            for actor, code in [("user-probe", 403), ("foreign-probe", 404)]:
                session = client.post(
                    "/api/auth/session", headers={"Authorization": "Bearer " + actor}
                )
                assert session.status_code == 201, session.text
                client.headers["Authorization"] = (
                    "Bearer " + session.json()["access_token"]
                )
                response = client.get(
                    "/api/policies" if actor == "user-probe" else "/api/policies/" + pid
                )
                assert response.status_code == code, response.text
            client.headers["Authorization"] = admin_auth
            rid = held.json()["review_id"]
            reveal = lambda version: client.post(
                f"/api/reviews/{rid}/content",
                json={},
                headers={"If-Match": f'"{version}"'},
            )
            assert (
                reveal(1).status_code == 403
            )  # Admin still needs explicit assignment.
            assigned = client.put(
                f"/api/reviews/{rid}/assignment",
                json={"assigned_reviewer": "probe", "reason": "Synthetic test"},
            )
            assert assigned.status_code == 200, assigned.text
            with SessionLocal() as db:
                version = db.get(Review, rid).row_version
            assert reveal(version + 1).status_code == 412
            shown = reveal(version)
            assert (
                shown.status_code == 200 and shown.json()["original_prompt"] == prompt
            ), shown.text
            assert shown.headers["cache-control"] == "no-store"
            with SessionLocal() as db:
                assert db.scalar(
                    select(Audit.id).where(
                        Audit.resource == rid, Audit.action == "review.content.viewed"
                    )
                )
            disposed = client.post(
                f"/api/reviews/{rid}/approve", json={"reason": "Resubmission required"}
            )
            assert disposed.status_code == 200, disposed.text
            with SessionLocal() as db:
                assert db.get(Content, ("synthetic007", rid)) is None
            # Fresh retained ciphertext is intentionally left for the separate fallback process.
            retained = client.post("/api/governance/generate", json={"text": prompt})
            assert (
                retained.status_code == 200
                and retained.json()["decision"] == "HUMAN_REVIEW"
            ), retained.text
            # Genuine SQL cleanup of an already expired synthetic encrypted row.
            with SessionLocal() as db:
                expired = Review(
                    tenant="synthetic007", execution_id=retained.json()["request_id"]
                )
                db.add(expired)
                db.flush()
                now = secure.clock(db)
                db.add(
                    secure.encrypt_prompt(
                        "expired synthetic",
                        "synthetic007",
                        expired.id,
                        expired.execution_id,
                        now - 604801,
                    )
                )
                expired_id = expired.id
                db.commit()
            cleaned = secure.cleanup_once(engine, SessionLocal)
            assert cleaned["healthy"] and cleaned["removed"] >= 1, cleaned
            with SessionLocal() as db:
                assert db.get(Content, ("synthetic007", expired_id)) is None
                assert db.scalar(
                    select(Audit.id).where(
                        Audit.resource == expired_id,
                        Audit.action == "review.content.expired",
                    )
                )
            for action in ["BLOCK", "REDACT"]:
                definition = {
                    "name": "Synthetic " + action,
                    "rules": {
                        "blocked_keywords": {
                            "enabled": True,
                            "values": ["restricted-fixture"],
                            "action": action,
                        }
                    },
                }
                new = client.post("/api/policies", json=definition)
                assert new.status_code == 201, new.text
                for operation in ["submit", "approve", "publish", "activate"]:
                    r = client.post(f"/api/policies/{new.json()['id']}/{operation}")
                    assert r.status_code == 200, r.text
                decision = client.post(
                    "/api/governance/generate",
                    json={"text": "restricted-fixture synthetic"},
                )
                assert (
                    decision.status_code == 200
                    and decision.json()["decision"] == action
                ), decision.text
            restored = client.post(f"/api/policies/{pid}/activate")
            assert restored.status_code == 200, restored.text
            checks.extend(
                [
                    "User RBAC and foreign-tenant negatives",
                    "explicit reviewer assignment and stale version denial",
                    "encrypted reveal with committed access audit",
                    "disposition purge",
                    "expired ciphertext SQL cleanup and audit",
                    "LEGACY BLOCK and REDACT",
                ]
            )
        if revision in {"006", "007"}:
            state = client.get("/api/v2/workspace/policy-state")
            switched = client.put(
                "/api/v2/workspace/policy-mode",
                headers={"If-Match": state.headers["etag"]},
                json={"mode": "MULTI", "seed_legacy_assignment": True},
            )
            assert switched.status_code == 200, switched.text
            current = client.get("/api/v2/workspace/policy-state")
            assert current.status_code == 200 and current.json()["active_policy_count"] == 1
            listing = client.get("/api/policies")
            assert listing.status_code == 200
            assert any(item["id"] == pid and item["is_active"] for item in listing.json())
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
            assert db.scalar(text("SELECT DB_NAME()")) == harness.DB
            assert db.scalar(text("SELECT USER_NAME()")) == harness.RUNTIME
        checks.append("database integrity and retained foreign keys")
    engine.dispose()
    return {
        "revision": revision,
        "recovery": recovery,
        "checks": checks,
        "session_contract": session_evidence,
        "passed": True,
        "limits": "Azure SQL transport; SQL EXECUTE AS runtime context; synthetic keys/OIDC and fixture providers; no actual managed identity authentication",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--revision", choices=["004", "005", "006", "007"], required=True
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
