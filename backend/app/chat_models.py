"""User chat display history, separate from metadata-only governance and audit records."""

from sqlalchemy.dialects import mssql
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Integer, MetaData, String, UnicodeText
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import new_id, now


class ChatBase(DeclarativeBase):
    metadata = MetaData()


class ChatConversation(ChatBase):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("ix_chat_conversations_owner_activity", "tenant", "actor", "updated_at"),
        Index("ux_chat_conversations_owner_id", "tenant", "actor", "id", unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(120).with_variant(mssql.NVARCHAR(120), "mssql"), nullable=False, default="New conversation")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now)


class ChatMessage(ChatBase):
    __tablename__ = "chat_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant", "actor", "conversation_id"],
            ["chat_conversations.tenant", "chat_conversations.actor", "chat_conversations.id"],
            name="fk_chat_message_owner_conversation",
        ),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
        Index("ix_chat_messages_conversation_created", "conversation_id", "created_at", "ordinal", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tenant: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now)
