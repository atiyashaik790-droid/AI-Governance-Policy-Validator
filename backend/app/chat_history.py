"""Authenticated User chat history containing only governed display content."""

import re
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
SUBMITTED_PLACEHOLDER = "Request submitted"
DEFAULT_TITLE = "New conversation"

# Document requests are inspected as one text: the typed question, then the extracted
# document between boundaries carrying a per-request random marker (document_uploads.extract).
_DOCUMENT_BOUNDARY = re.compile(r"\n\nUNTRUSTED DOCUMENT DATA ([0-9a-f]{32}) BEGIN\n")
_ACRONYMS = {"ai", "api", "aws", "crm", "csv", "erp", "gcp", "gdpr", "hr", "json", "kpi", "llm", "ml",
             "pdf", "pii", "sql", "sso", "ui", "ux", "docx", "txt", "rbac", "oauth", "saas", "ci", "cd"}
_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "vs", "with"}
_FILLER_WORDS = _SMALL_WORDS | {"i", "me", "my", "we", "our", "you", "your", "it", "this", "that", "is", "are", "was",
                                "be", "please", "use", "call", "email", "phone", "number", "name", "here", "there"}
_DOCUMENT_KINDS = ("resume", "cv", "invoice", "contract", "agreement", "report", "policy", "proposal",
                   "statement", "paper", "article", "presentation", "notes", "letter", "manual", "specification")
_LEADING_FILLER = re.compile(
    r"^(?:(?:hi|hello|hey)[,!.]?\s+)?(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
    r"(?:(?:explain|describe|tell me about|tell me|give me|show me|help me understand|help me with|help me|"
    r"i want to know about|i want to know|i need|i would like|teach me|walk me through|list|outline)\s+)?",
    re.I,
)
_TRAILING_FILLER = re.compile(r"\s+(?:for me|please|in detail|in simple terms|briefly|in short)$", re.I)
_UNSAFE_TOKEN = re.compile(r"\[redacted[^\]]*\]|<[^>]+>|\S*@\S*|\S*\d{3,}\S*|\S*[=:/\\]\S*|\S{25,}", re.I)


def document_question(safe_text: str) -> str | None:
    """Return the governed typed question from a combined document request, or None."""
    if not safe_text.startswith("USER PROMPT:\n"):
        return None
    boundary = _DOCUMENT_BOUNDARY.search(safe_text)
    if boundary is None or not safe_text.endswith(f"\nUNTRUSTED DOCUMENT DATA {boundary.group(1)} END"):
        return None
    return safe_text[len("USER PROMPT:\n"):boundary.start()]


def conversation_title(prompt: str | None, attachment_type: str | None = None) -> str:
    """Deterministic short title from governed display text; never calls a model."""
    text = " ".join((prompt or "").split())
    # Removed tokens split the sentence; keep the segment carrying the most meaningful words.
    segments = [" ".join(s.split()).strip(" .,;!?-'\"") for s in _UNSAFE_TOKEN.split(text)]
    lowered = " ".join(segments).lower()
    text = max(segments, key=lambda s: (sum(w.lower().strip(".,;!?") not in _FILLER_WORDS for w in s.split()),
                                        segments.index(s)), default="")
    text = re.sub(r"^(?:(?:about|on|to|for|with|and|or|is|are|was)\s+)+", "", text, flags=re.I)
    if attachment_type and re.search(r"\b(summari[sz]e|summary|overview|key points|tl;?dr)\b", lowered):
        kind = next((k for k in _DOCUMENT_KINDS if re.search(rf"\b{k}s?\b", lowered)), None)
        return (kind.upper() if kind == "cv" else kind.capitalize()) + " Summary" if kind else "Document Summary"
    understanding = re.match(r"^(?:what(?:'s| is| are| does)|define|meaning of)\s+(.+?)(?:\s+mean)?$", text, re.I)
    if understanding:
        text = "Understanding " + re.sub(r"^(?:the|a|an)\s+", "", understanding.group(1), flags=re.I)
    else:
        text = _LEADING_FILLER.sub("", text)
        embedded = re.match(r"^what\s+(?:a|an|the)?\s*(.+?)\s+(?:is|are|means)$", text.strip(" .?!"), re.I)
        if embedded:
            text = "Understanding " + embedded.group(1)
        text = re.sub(r"^(?:how (?:do|does|can|should) (?:i|we|you)\s+)", "How to ", text, flags=re.I)
        text = re.sub(r"^(?:the|a|an|this|these|my|our)\s+", "", text, flags=re.I)
    text = _TRAILING_FILLER.sub("", text).strip(" .,;!?-'\"")
    words = [w.strip(".,;!?\"'()") for w in text.split()][:7]
    words = [w for w in words if w]
    while words and words[-1].lower() in _SMALL_WORDS:
        words.pop()
    if not words:
        return f"{attachment_type.upper()} Document" if attachment_type else DEFAULT_TITLE
    titled = []
    for index, word in enumerate(words):
        if word.lower() in _ACRONYMS:
            titled.append(word.upper())
        elif word != word.lower():
            titled.append(word)  # Keep author capitalization such as "FastAPI" or "Python".
        elif index and word in _SMALL_WORDS:
            titled.append(word)
        else:
            titled.append(word[:1].upper() + word[1:])
    return " ".join(titled)[:80]


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
    attachment = result.get("attachment") or {}
    attachment_type = attachment.get("type") if attachment.get("type") in {"pdf", "docx", "txt"} else None
    # Attachment safe_text also holds extracted document text; keep only the governed typed question.
    if attachment:
        safe_prompt = document_question(safe_prompt) if isinstance(safe_prompt, str) else None
    has_prompt = isinstance(safe_prompt, str) and bool(safe_prompt.strip())
    prompt_display = safe_prompt.strip() if has_prompt else SUBMITTED_PLACEHOLDER
    if attachment_type and safe_prompt is not None:
        # Type only; the filename can itself be personal data and is never stored.
        prompt_display = (prompt_display + "\n\n" if has_prompt else "") + f"Attachment: {attachment_type.upper()} document"
    answer_display = display_message(result)
    stamp = now()
    if conversation.title == DEFAULT_TITLE:
        if has_prompt or (attachment_type and safe_prompt is not None):
            conversation.title = conversation_title(safe_prompt, attachment_type)
        elif attachment:
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
