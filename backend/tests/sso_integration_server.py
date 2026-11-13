"""Loopback React/API fixture; synthetic OIDC only. Never deploy this module."""

import argparse
import json
import os
from pathlib import Path
import signal
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts"))
    from run_offline_demo import offline_environment

    with tempfile.TemporaryDirectory(prefix="governance-sso-integration-") as temporary:
        directory = Path(temporary)
        os.environ.update(offline_environment(directory, "http://localhost:5174"))
        os.environ.update(
            {
                "SSO_ENABLED": "true",
                "DEMO_BROWSER_LOGIN_ENABLED": "false",
                "ALLOW_LEGACY_API_CREDENTIALS": "false",
                "ENTRA_TENANT_ID": "11111111-1111-4111-8111-111111111111",
                "ENTRA_CLIENT_ID": "22222222-2222-4222-8222-222222222222",
                "ENTRA_CLIENT_SECRET": "synthetic-only",
                "SSO_PUBLIC_ORIGIN": "https://testserver",
            }
        )
        sys.path.insert(0, str(root / "backend"))
        from app.database import engine, SessionLocal
        from app.models import Base, SsoMembership
        from app.main import app
        from app import sso
        import uvicorn

        Base.metadata.create_all(engine)
        with SessionLocal.begin() as db:
            for role, object_id in [
                ("Admin", "33333333-3333-4333-8333-333333333333"),
                ("Reviewer", "44444444-4444-4444-8444-444444444444"),
            ]:
                db.add(
                    SsoMembership(
                        directory_tenant=os.environ["ENTRA_TENANT_ID"],
                        object_id=object_id,
                        actor="offline-" + role.lower(),
                        tenant="offline-demo",
                        role=role,
                    )
                )

        async def metadata():
            return {"authorization_endpoint": "https://testserver/mock-authorize"}

        async def exchange(code, transaction):
            if code != "synthetic-code":
                raise ValueError("Invalid fixture response")
            return {"tid": os.environ["ENTRA_TENANT_ID"], "oid": "33333333-3333-4333-8333-333333333333"}

        sso.metadata, sso.exchange_code = metadata, exchange

        def stop(*_):
            raise KeyboardInterrupt

        previous = signal.signal(signal.SIGTERM, stop)
        try:
            print(json.dumps({"mode": "DISPOSABLE_LOCAL_FIXTURE", "credential_file": str(directory / ".demo-tokens.json")}), flush=True)
            uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
        finally:
            engine.dispose()
            signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    main()
