"""Disposable HTTPS browser fixture with a mocked provider. Never deploy this file."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--revision", choices=["004", "005", "006", "007"], default="005")
    parser.add_argument("--demo-only", action="store_true")
    parser.add_argument("--role", choices=["Admin", "User", "Reviewer", "Auditor", "Developer", "Policy Owner"], default="Auditor")
    parser.add_argument("--protected-content", action="store_true")
    parser.add_argument("--seed-policy", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if args.protected_content and args.revision != "007":
        parser.error("Protected fixture content requires revision 007")
    origin = f"https://localhost:{args.port}"
    directory_id = "11111111-1111-4111-8111-111111111111"
    object_id = "33333333-3333-4333-8333-333333333333"
    with tempfile.TemporaryDirectory(prefix="governance-sso-browser-") as temporary:
        directory = Path(temporary)
        os.environ.update(
            {
                "DATABASE_URL": "sqlite:///" + str(directory / "browser.db"),
                "PROVIDER_MODE": "fixture",
                "PII_MODE": "regex",
                "SSO_ENABLED": "false" if args.demo_only or args.revision == "004" else "true",
                "DEMO_BROWSER_LOGIN_ENABLED": "true" if args.demo_only else "false",
                "ENTRA_TENANT_ID": directory_id,
                "ENTRA_CLIENT_ID": "22222222-2222-4222-8222-222222222222",
                "ENTRA_CLIENT_SECRET": "synthetic-browser-only",
                "SSO_PUBLIC_ORIGIN": origin,
                "SSO_SESSION_MINUTES": "120",
                "REVIEW_CAPTURE_ENABLED": str(args.protected_content).lower(),
                "REVIEW_CLEANUP_ENABLED": str(args.protected_content).lower(),
                "REVIEW_CONTENT_ACTIVE_KEY_ID": "ephemeral-test",
                "REVIEW_CONTENT_KEYS_JSON": json.dumps({"ephemeral-test": __import__("base64").b64encode(os.urandom(32)).decode()}),
                "INFERENCE_DAILY_QUOTA": "10000",
                "INFERENCE_USER_PER_MINUTE": "1000",
                "INFERENCE_TENANT_PER_MINUTE": "1000",
                "CORS_ORIGIN": origin,
                "DEMO_ACCOUNTS_JSON": json.dumps(
                    [
                        {
                            "user": "browser-auditor",
                            "tenant": "browser-fixture",
                            "role": "Auditor",
                            "token_hash": hashlib.sha256(b"synthetic-browser-demo").hexdigest(),
                        }
                    ]
                )
                if args.demo_only
                else "[]",
                "AZURE_OPENAI_ENDPOINT": "",
                "AZURE_OPENAI_API_KEY": "",
                "OPENAI_API_KEY": "",
                "ADLS_ACCOUNT_URL": "",
                "ADLS_FILE_SYSTEM": "",
            }
        )
        sys.path.insert(0, str(root / "backend"))
        from app.main import app
        from app.database import SessionLocal
        from app.models import SsoMembership
        from app import sso
        from app.web_assets import mount_frontend
        from fastapi import Request
        from fastapi.responses import RedirectResponse
        import uvicorn

        from alembic.config import Config
        from alembic import command

        migration = Config(str(root / "backend/alembic.ini"))
        migration.set_main_option("script_location", str(root / "backend/migrations"))
        command.upgrade(migration, args.revision)
        if not args.demo_only and args.revision in {"005", "006", "007"}:
            with SessionLocal.begin() as db:
                db.add(
                    SsoMembership(
                        directory_tenant=directory_id, object_id=object_id, tenant="browser-fixture", actor="Synthetic User", role=args.role
                    )
                )

        if args.seed_policy:
            from app.models import Policy, Version, Assignment
            from app.schemas import PolicyDocument
            document = PolicyDocument(name="Phase 5 Seed Policy", rules={"blocked_keywords": {"enabled": True, "values": ["internal-only"], "action": "HUMAN_REVIEW"}}).model_dump_json()
            with SessionLocal.begin() as db:
                policy = Policy(tenant="browser-fixture", name="Phase 5 Seed Policy", draft=document, status="PUBLISHED", enabled=1)
                db.add(policy)
                db.flush()
                version = Version(tenant="browser-fixture", policy_id=policy.id, number=1, document=document)
                db.add(version)
                db.flush()
                db.add(Assignment(tenant="browser-fixture", version_id=version.id))

        async def mock_metadata():
            return {"authorization_endpoint": origin + "/mock-oidc/authorize"}

        async def mock_exchange(code, transaction):
            if code != "synthetic-code":
                raise ValueError
            return {"tid": directory_id, "oid": object_id}

        sso.metadata, sso.exchange_code = mock_metadata, mock_exchange

        @app.get("/mock-oidc/authorize")
        def authorize(request: Request):
            assert request.query_params["code_challenge_method"] == "S256"
            return RedirectResponse(
                origin + "/api/sso/callback?" + urlencode({"state": request.query_params["state"], "code": "synthetic-code"})
            )

        mount_frontend(app, root / "frontend/dist")
        # Ephemeral, test-only HTTPS certificate. No production credentials used.
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        from datetime import datetime, timedelta, timezone

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(key, hashes.SHA256())
        )
        private = directory / "test.key"
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        private.chmod(0o600)
        certificate = directory / "test.crt"
        certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            ssl_keyfile=str(private),
            ssl_certfile=str(certificate),
            access_log=False,
            log_level="error",
        )


if __name__ == "__main__":
    main()
