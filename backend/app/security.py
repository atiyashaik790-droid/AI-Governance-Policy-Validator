"""Local demo bearer credentials map to server-controlled identities and roles."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings
from sqlalchemy.orm import Session
from .database import get_database
from .models import DemoSession, now

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    user: str
    tenant: str
    role: str
    session_id: str | None = None
    credential_hash: str = ""


def account_enabled(account: dict) -> bool:
    if account.get("disabled"):
        return False
    expiry = account.get("expires")
    if not expiry:
        return True
    try:
        timestamp = datetime.fromisoformat(expiry)
        return timestamp.tzinfo is not None and timestamp > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


# Authenticate against hashed, locally provisioned demo tokens, never client roles.
def authenticate(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_database, scope="function"),
) -> Identity:
    if credentials:
        digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        accounts = json.loads(settings.demo_accounts_json)
        for account in accounts:
            if hmac.compare_digest(digest, account["token_hash"]):
                if not account_enabled(account):
                    break
                if request.url.path != "/api/auth/session" and not settings.allow_legacy_api_credentials:
                    raise HTTPException(401, "Exchange your provisioned credential for an expiring session")
                return Identity(account["user"], account["tenant"], account["role"], credential_hash=digest)
        session = db.get(DemoSession, digest)
        if session and not session.revoked and session.expires > now():
            # Credential removal, role changes and disabling also invalidate its sessions.
            for account in accounts:
                if (
                    hmac.compare_digest(session.credential_hash, account["token_hash"])
                    and account_enabled(account)
                    and (session.actor, session.tenant, session.role) == (account["user"], account["tenant"], account["role"])
                ):
                    return Identity(session.actor, session.tenant, session.role, digest, session.credential_hash)
    raise HTTPException(401, "Valid unexpired demonstration session or provisioned credential required")


# Enforce a server-side role requirement for a sensitive action.
def require_role(identity: Identity, *roles: str) -> None:
    if identity.role not in roles:
        raise HTTPException(403, "Role does not permit this operation")
