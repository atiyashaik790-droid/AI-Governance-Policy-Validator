"""Local demo bearer credentials map to server-controlled identities and roles."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    user: str
    tenant: str
    role: str


# Authenticate against hashed, locally provisioned demo tokens, never client roles.
def authenticate(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Identity:
    if credentials:
        digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        for account in json.loads(settings.demo_accounts_json):
            if hmac.compare_digest(digest, account["token_hash"]):
                return Identity(account["user"], account["tenant"], account["role"])
    raise HTTPException(401, "Valid local demonstration bearer token required")


# Enforce a server-side role requirement for a sensitive action.
def require_role(identity: Identity, *roles: str) -> None:
    if identity.role not in roles:
        raise HTTPException(403, "Role does not permit this operation")
