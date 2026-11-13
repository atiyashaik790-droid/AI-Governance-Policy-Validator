"""Authenticated bounded attachments reuse the existing single-dispatch gateways."""
import asyncio
import base64
import binascii
import json
import os
from pathlib import Path
import sys
import threading
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

from .. import usage
from ..protected_reviews import ensure_ready
from ..user_access import UserGovernanceResult
from ..config import settings
from ..dependencies import DB, USER
from ..schemas import StrictModel, TextRequest, GovernanceResult, AttachmentMetadata
from ..security import Identity, require_role
from ..services.governance import governance
from ..services.multi_policy_governance import execute
from ..services.policy_sets import guard_legacy
from .workspace_v2 import revision_header, read_state

router = APIRouter(tags=["Governed document uploads"])
MAX_FILE = 256 * 1024
UPLOAD_BODY_LIMIT = 400000
SLOTS = threading.BoundedSemaphore(2)
TYPES = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "txt": "text/plain"}


class DocumentRequest(StrictModel):
    text: str = Field(strict=True, max_length=12000)
    source_review_id: str | None = Field(None, min_length=36, max_length=36)
    conversation_id: str | None = Field(None, min_length=36, max_length=36)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="", max_length=150)
    content_base64: str = Field(max_length=349528)


class DocumentGovernanceResult(GovernanceResult):
    attachment: AttachmentMetadata


async def extract(payload):
    kind = payload.filename.rsplit(".", 1)[-1].lower()
    if kind not in TYPES or payload.content_type not in ("", "application/octet-stream", TYPES.get(kind)):
        raise HTTPException(415, "Attach a PDF, DOCX or UTF-8 TXT document with a matching type")
    try:
        raw = base64.b64decode(payload.content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, "Attachment encoding is invalid") from None
    if not raw or len(raw) > MAX_FILE:
        raise HTTPException(413, "File must contain 1 to 262144 bytes (256 KiB)")
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(503, "Document extraction capacity unavailable; nothing released")
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-B", str(Path(__file__).resolve().parents[1] / "document_worker.py"), kind,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(raw), timeout=5)
        except TimeoutError:
            raise HTTPException(422, "Document extraction timed out; nothing released") from None
        if process.returncode or len(output) > 70000:
            raise HTTPException(422, "Document extraction could not complete; nothing released")
        extracted = json.loads(output)
        if "error" in extracted:
            raise HTTPException(422, extracted["error"])
        text = extracted["text"]
        if not isinstance(text, str) or not text.strip() or len(text) > 10000:
            raise HTTPException(422, "Document extraction could not complete; nothing released")
        marker = uuid4().hex
        combined = f"USER PROMPT:\n{payload.text}\n\nUNTRUSTED DOCUMENT DATA {marker} BEGIN\n{text}\nUNTRUSTED DOCUMENT DATA {marker} END"
        if len(combined) > 12000:
            raise HTTPException(413, "Prompt, document and boundaries must fit within 12000 characters; shorten the prompt or document")
        return TextRequest(text=combined, source_review_id=payload.source_review_id,
                           conversation_id=payload.conversation_id), {
            "type": kind, "size_bytes": len(raw), "extracted_characters": len(text),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Document extraction unavailable; nothing released") from None
    finally:
        try:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await asyncio.shield(process.wait())
        finally:
            SLOTS.release()


def admission_check(db, user):
    require_role(user, "Admin", "Developer", "Policy Owner", "User")
    ensure_ready(db)
    # Extraction has its own persistent rate bucket, including failed files.
    usage.claim_action(db, user, "document-extraction", min(5, settings.inference_user_per_minute))
    db.commit()


@router.post("/api/governance/generate-document", response_model=DocumentGovernanceResult | UserGovernanceResult)
async def legacy_document(payload: DocumentRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Developer", "Policy Owner", "User")
    if payload.conversation_id:
        from ..chat_history import require_conversation
        require_conversation(db, user, payload.conversation_id)
    guard_legacy(db, user)
    admission_check(db, user)
    text, metadata = await extract(payload)
    return await governance("generate", text, db, user, attachment=metadata, original_prompt=payload.text)


@router.post("/api/v2/governance/generate-document")
async def multi_document(payload: DocumentRequest, db: Session = DB, user: Identity = USER,
                         if_match: str | None = Header(None, alias="If-Match")):
    require_role(user, "Admin", "Developer", "Policy Owner", "User")
    if payload.conversation_id:
        from ..chat_history import require_conversation
        require_conversation(db, user, payload.conversation_id)
    revision = revision_header(if_match)
    available, mode, current = read_state(db, user)
    if not available:
        raise HTTPException(503, "SCHEMA_006_REQUIRED")
    if mode != "MULTI":
        raise HTTPException(409, "WORKSPACE_MODE_CONFLICT")
    if str(current) != revision:
        raise HTTPException(412, "POLICY_SET_PRECONDITION_FAILED")
    admission_check(db, user)
    text, metadata = await extract(payload)
    result = await execute("generate", text, db, user, expected_revision=revision, attachment=metadata, original_prompt=payload.text)
    return {**result, "schema_version": "2.0", "execution_mode": "MULTI", "provider_mode": settings.provider_mode}
