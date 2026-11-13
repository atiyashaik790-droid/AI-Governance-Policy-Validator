"""Authenticated MULTI governance; all enforcement/persistence stays in A–E services."""

from fastapi import APIRouter, Header
from sqlalchemy.orm import Session

from ..dependencies import DB, USER
from ..config import settings
from ..schemas import TextRequest
from ..security import Identity, require_role
from ..services.multi_policy_governance import execute
from .workspace_v2 import revision_header

router = APIRouter(prefix="/api/v2/governance", tags=["Multi-policy governance"])


def register(operation):
    async def govern(payload: TextRequest, db: Session = DB, user: Identity = USER,
                     if_match: str | None = Header(None, alias="If-Match")):
        require_role(user, "Admin", "Developer", "Policy Owner", "User")
        if payload.conversation_id:
            from ..chat_history import require_conversation
            require_conversation(db, user, payload.conversation_id)
        result = await execute(operation, payload, db, user, expected_revision=revision_header(if_match))
        return {**result, "schema_version": "2.0", "execution_mode": "MULTI", "provider_mode": settings.provider_mode}
    govern.__name__ = "multi_" + operation.replace("-", "_")
    router.add_api_route("/" + operation, govern, methods=["POST"])


for operation in ("generate", "validate-input", "validate-output"):
    register(operation)
