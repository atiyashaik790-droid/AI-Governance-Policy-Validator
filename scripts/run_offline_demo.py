"""Run the existing application on disposable SQLite with cloud adapters disabled."""

import argparse
import hashlib
import json
import os
import secrets
import signal
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def offline_environment(directory: Path, origin: str) -> dict[str, str]:
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("localhost", "127.0.0.1")
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
    ):
        raise ValueError("Use an HTTP loopback frontend origin without a path")
    accounts, tokens = [], {}
    for role in ("Admin", "Policy Owner", "Developer", "Reviewer", "Auditor"):
        token = secrets.token_urlsafe(32)
        tokens[role] = token
        accounts.append(
            {
                "user": "offline-" + role.lower().replace(" ", "-"),
                "tenant": "offline-demo",
                "role": role,
                "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            }
        )
    credential_path = directory / ".demo-tokens.json"
    fd = os.open(
        credential_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(fd, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(tokens, output)
    return {
        "DATABASE_URL": "sqlite:///" + str(directory / "offline.db"),
        "PROVIDER_MODE": "fixture",
        "PII_MODE": "regex",
        "CORS_ORIGIN": origin,
        "DEMO_ACCOUNTS_JSON": json.dumps(accounts),
        "AZURE_SQL_TENANT_ID": "",
        "AZURE_SQL_USER_OBJECT_ID": "",
        "AZURE_OPENAI_ENDPOINT": "",
        "AZURE_OPENAI_DEPLOYMENT": "",
        "AZURE_OPENAI_API_KEY": "",
        "AZURE_OPENAI_API_VERSION": "v1",
        "OPENAI_API_KEY": "",
        "ADLS_ACCOUNT_URL": "",
        "ADLS_FILE_SYSTEM": "",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--frontend-origin", default="http://localhost:5174")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged port from 1024 to 65535")
    # Import app configuration only AFTER all database/provider overrides exist.
    with tempfile.TemporaryDirectory(prefix="governance-offline-demo-") as temporary:
        directory = Path(temporary)
        os.environ.update(offline_environment(directory, args.frontend_origin))
        sys.path.insert(0, str(ROOT / "backend"))
        import uvicorn
        from app.database import engine
        from app.models import Base

        def graceful_exit(*_):
            raise KeyboardInterrupt

        # Uvicorn replays SIGTERM after shutdown; turn that replay into normal cleanup.
        previous_term = signal.signal(signal.SIGTERM, graceful_exit)
        try:
            Base.metadata.create_all(
                engine
            )  # Only this new disposable database; no Alembic or existing DB access.
            print(
                json.dumps(
                    {
                        "mode": "DISPOSABLE_LOCAL_FIXTURE",
                        "credential_file": str(directory / ".demo-tokens.json"),
                        "database": "disposable SQLite; removed on graceful exit",
                        "port": args.port,
                    }
                ),
                flush=True,
            )
            uvicorn.run(
                "app.main:app",
                host="127.0.0.1",
                port=args.port,
                workers=1,
                log_level="warning",
                access_log=False,
            )
        finally:
            engine.dispose()
            signal.signal(signal.SIGTERM, previous_term)


if __name__ == "__main__":
    main()
