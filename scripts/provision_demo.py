"""Create private local demo credentials; never echo tokens or load cloud secrets."""

import hashlib
import json
import os
import secrets
from pathlib import Path


# Create local authentication material without overwriting an existing environment.
def provision_demo() -> None:
    root = Path(__file__).resolve().parents[1]
    environment = root / ".env"
    if environment.exists():
        raise SystemExit(
            ".env already exists; retain it and provision accounts manually"
        )
    roles = ["Admin", "Policy Owner", "Reviewer", "Auditor", "Developer"]
    accounts, tokens = [], {}
    for role in roles:
        token = secrets.token_urlsafe(36)
        tokens[role] = token
        accounts.append(
            {
                "user": role.lower().replace(" ", "-"),
                "tenant": "demo",
                "role": role,
                "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            }
        )
    os.umask(0o077)
    environment.write_text(
        "DATABASE_URL=sqlite:///./governance.db\nPROVIDER_MODE=fixture\nPII_MODE=presidio\nDEMO_ACCOUNTS_JSON='"
        + json.dumps(accounts)
        + "'\n"
    )
    (root / ".demo-tokens.json").write_text(json.dumps(tokens, indent=2))
    print(
        "Created private .env and .demo-tokens.json. Fixture providers and Presidio PII are enabled explicitly."
    )


if __name__ == "__main__":
    provision_demo()
