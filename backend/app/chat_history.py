"""Authenticated User chat history containing only governed display content."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .chat_models import ChatConversation, ChatMessage
from .dependencies import DB, USER
from .models import now
from .security import Identity, require_role

router = APIRouter(prefix="/api/chat/conversations", tags=["User chatbot history"])

BLOCK_MESSAGE = "Sorry, I can't process that request because it contains restricted information."
REVIEW_MESSAGE = "This request requires review and cannot proceed yet."
UNAVAILABLE_MESSAGE = "I couldn't complete that request. Please try again later."


def require_chat_schema(db: Session) -> None:
    if db.scalar(text("SELECT version_num FROM alembic_version")) != "011":
        raise HTTPException(503, "Conversation history requires database revision 011")


def require_conversation(db: Session, user: Identity, conversation_id: str) -> ChatConversation:
    require_role(user, "User")
    try:
        identifier = str(UUID(conversation_id))
    except (ValueError, TypeError):
        raise HTTPException(404, "Conversation not found") from None
    require_chat_schema(db)
    conversation = db.scalar(
        select(ChatConversation).where(
            ChatConversation.id == identifier,
            ChatConversation.tenant == user.tenant,
            ChatConversation.actor == user.user,
        )
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return conversation


def display_message(result: dict) -> str:
    if result.get("provider_error") or result.get("generation_status") == "FAILED":
        return UNAVAILABLE_MESSAGE
    if result.get("decision") == "HUMAN_REVIEW":
        return REVIEW_MESSAGE
    if result.get("decision") == "BLOCK":
        return BLOCK_MESSAGE
    output = result.get("output")
    if (
        result.get("decision") in {"ALLOW", "REDACT"}
        and isinstance(output, dict)
        and output.get("decision") in {"ALLOW", "REDACT"}
        and output.get("inspection_status") != "INCOMPLETE"
        and "UNKNOWN" not in (output.get("breakdown") or {}).values()
        and (output.get("decision") != "REDACT" or output.get("revalidated") is True)
        and isinstance(result.get("safe_response"), str)
        and result["safe_response"].strip()
    ):
        return result["safe_response"]
    return UNAVAILABLE_MESSAGE


def record_turn(db: Session, user: Identity, conversation_id: str | None, result: dict) -> None:
    if conversation_id is None:
        return
    conversation = require_conversation(db, user, conversation_id)
    inspected = result.get("input") or {}
    safe_prompt = (
        inspected.get("safe_text")
        if result.get("decision") in {"ALLOW", "REDACT"}
        and inspected.get("decision") in {"ALLOW", "REDACT"}
        else None
    )
    # Attachments may include extracted document text in safe_text; never retain it as chat history.
    if result.get("attachment"):
        safe_prompt = None
    prompt_display = safe_prompt if isinstance(safe_prompt, str) and safe_prompt.strip() else "Request submitted"
    answer_display = display_message(result)
    stamp = now()
    if conversation.title == "New conversation":
        if prompt_display != "Request submitted":
            conversation.title = " ".join(prompt_display.split())[:80]
        elif result.get("attachment"):
            conversation.title = "Document conversation"
        else:
            conversation.title = (
                "Review request" if result.get("decision") == "HUMAN_REVIEW"
                else "Restricted request" if result.get("decision") == "BLOCK" and not result.get("provider_error")
                else "Conversation"
            )
    db.add_all([
        ChatMessage(conversation_id=conversation.id, tenant=user.tenant, actor=user.user,
                    role="user", ordinal=0, content=prompt_display, decision=result["decision"], created_at=stamp),
        ChatMessage(conversation_id=conversation.id, tenant=user.tenant, actor=user.user,
                    role="assistant", ordinal=1, content=answer_display, decision=result["decision"], created_at=stamp),
    ])
    conversation.updated_at = stamp


def serialize_conversation(row: ChatConversation) -> dict:
    return {"id": row.id, "title": row.title, "created_at": row.created_at, "updated_at": row.updated_at}


@router.post("", status_code=201)
def create_conversation(db: Session = DB, user: Identity = USER):
    require_role(user, "User")
    require_chat_schema(db)
    row = ChatConversation(tenant=user.tenant, actor=user.user)
    db.add(row)
    db.commit()
    return serialize_conversation(row)


@router.get("")
def list_conversations(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100),
                       db: Session = DB, user: Identity = USER):
    require_role(user, "User")
    require_chat_schema(db)
    rows = db.scalars(select(ChatConversation).where(
        ChatConversation.tenant == user.tenant, ChatConversation.actor == user.user,
    ).order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc()).offset(offset).limit(limit)).all()
    return [serialize_conversation(row) for row in rows]


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = DB, user: Identity = USER):
    row = require_conversation(db, user, conversation_id)
    messages = db.scalars(select(ChatMessage).where(
        ChatMessage.conversation_id == row.id,
        ChatMessage.tenant == user.tenant,
        ChatMessage.actor == user.user,
    ).order_by(ChatMessage.created_at, ChatMessage.ordinal, ChatMessage.id)).all()
    return {**serialize_conversation(row), "messages": [
        {"id": message.id, "role": message.role, "content": message.content, "decision": message.decision}
        for message in messages
    ]}
