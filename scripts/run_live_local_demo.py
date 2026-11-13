"""Run a local workspace with the configured live AI providers.

Startup creates local SQLite data and makes no provider requests. Each governed
generation requested in the browser can contact OpenAI Moderation and Azure OpenAI.
"""

import argparse
from contextlib import nullcontext
import json
import os
import signal
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from run_offline_demo import ROOT, offline_environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--frontend-origin", default="http://localhost:5176")
    parser.add_argument("--persistent-local", action="store_true",
                        help="Keep local chat history in private/live-local-chat across restarts")
    parser.add_argument("--sso", action="store_true",
                        help="Microsoft Entra sign-in via the HTTPS form of --frontend-origin (requires --persistent-local)")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged port from 1024 to 65535")
    if args.sso and not args.persistent_local:
        parser.error("--sso requires --persistent-local, where the approved SSO memberships are stored")

    sys.path.insert(0, str(ROOT / "backend"))
    from app import config

    configured = config.Settings()
    if not (configured.azure_openai_endpoint and configured.azure_openai_deployment):
        parser.error("Azure OpenAI endpoint and deployment must be configured in .env")
    if not configured.openai_api_key:
        parser.error("OpenAI Moderation API key must be configured in .env")
    if args.sso and not (configured.entra_tenant_id and configured.entra_client_id and configured.entra_client_secret):
        parser.error("ENTRA_TENANT_ID, ENTRA_CLIENT_ID and ENTRA_CLIENT_SECRET must be configured in .env for --sso")

    persistent_directory = ROOT / "private" / "live-local-chat"
    if args.persistent_local:
        if persistent_directory.is_symlink():
            parser.error("Persistent local chat directory must not be a symlink")
        existing = persistent_directory.exists()
        if existing and not ((persistent_directory / "offline.db").is_file()
                             and (persistent_directory / ".demo-tokens.json").is_file()):
            parser.error("Persistent local chat directory is incomplete; no data was changed")
        persistent_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory_context = nullcontext(str(persistent_directory))
    else:
        existing = False
        directory_context = tempfile.TemporaryDirectory(prefix="governance-live-local-", dir="/tmp")

    with directory_context as temporary:
        directory = Path(temporary)
        local = offline_environment(directory, args.frontend_origin, reuse_credentials=existing)
        local.update(
            PROVIDER_MODE="live",
            DEMO_SESSION_UNLIMITED_LOCAL="true",
            AZURE_OPENAI_ENDPOINT=configured.azure_openai_endpoint,
            AZURE_OPENAI_DEPLOYMENT=configured.azure_openai_deployment,
            AZURE_OPENAI_API_VERSION=configured.azure_openai_api_version,
            AZURE_OPENAI_API_KEY=configured.azure_openai_api_key,
            OPENAI_API_KEY=configured.openai_api_key,
            PROVIDER_TIMEOUT=str(configured.provider_timeout),
        )
        if args.sso:
            # The SPA proxies /api on the same HTTPS origin, so __Host- Secure cookies apply.
            https_origin = "https://" + urlsplit(args.frontend_origin).netloc
            local.update(
                SSO_ENABLED="true",
                DEMO_BROWSER_LOGIN_ENABLED="false",
                ENTRA_TENANT_ID=configured.entra_tenant_id,
                ENTRA_CLIENT_ID=configured.entra_client_id,
                ENTRA_CLIENT_SECRET=configured.entra_client_secret,
                SSO_PUBLIC_ORIGIN=https_origin,
                CORS_ORIGIN=https_origin,
            )
        os.environ.update(local)
        config.settings = config.Settings()

        # Import only after the isolated database and live provider selection exist.
        import uvicorn
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from app.database import engine
        from app.models import Policy
        from app.schemas import PolicyDocument
        from app.services.category_catalog import sync_draft_categories
        from prepare_fresh_demo import seed_local

        def graceful_exit(*_) -> None:
            raise KeyboardInterrupt

        previous_term = signal.signal(signal.SIGTERM, graceful_exit)
        try:
            migration_config = Config(str(ROOT / "backend" / "alembic.ini"))
            migration_config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
            if existing:
                with sqlite3.connect(f"file:{(directory / 'offline.db').resolve()}?mode=ro", uri=True) as saved:
                    revision = saved.execute("SELECT version_num FROM alembic_version").fetchone()
                if revision != ("011",):
                    parser.error("Existing persistent local chat database is not revision 011; no migration was run")
            else:
                command.upgrade(migration_config, "head")
                with Session(engine, expire_on_commit=False) as db:
                    seed_local(db, persistent_live_chat=args.persistent_local)
                    for policy in db.scalars(select(Policy)).all():
                        sync_draft_categories(
                            db, policy.tenant, policy.id, PolicyDocument.model_validate_json(policy.draft)
                        )
                    db.commit()
            print(
                json.dumps(
                    {
                        "mode": "PERSISTENT_LOCAL_LIVE_AI" if args.persistent_local else "DISPOSABLE_LOCAL_LIVE_AI",
                        "credential_file": str(directory / ".demo-tokens.json"),
                        "database": "persistent local SQLite" if args.persistent_local else "disposable SQLite; removed on graceful exit",
                        "provider_mode": "live",
                        "sign_in": f"Microsoft Entra SSO at {local['SSO_PUBLIC_ORIGIN']}" if args.sso else "local demo token",
                        "azure_deployment": configured.azure_openai_deployment,
                        "moderation_model": "omni-moderation-latest",
                        "port": args.port,
                    }
                ),
                flush=True,
            )
            uvicorn.run(
                "app.main:app", host="127.0.0.1", port=args.port, workers=1,
                log_level="warning", access_log=False,
            )
        finally:
            engine.dispose()
            signal.signal(signal.SIGTERM, previous_term)


if __name__ == "__main__":
    main()
