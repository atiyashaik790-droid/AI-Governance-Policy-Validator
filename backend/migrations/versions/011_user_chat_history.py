"""Store only governed, display-safe User chatbot history."""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"


def upgrade():
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_chat_conversations_owner_activity", "chat_conversations", ["tenant", "actor", "updated_at"])
    op.create_index("ux_chat_conversations_owner_id", "chat_conversations", ["tenant", "actor", "id"], unique=True)
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("tenant", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.UnicodeText(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant", "actor", "conversation_id"],
            ["chat_conversations.tenant", "chat_conversations.actor", "chat_conversations.id"],
            name="fk_chat_message_owner_conversation",
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
    )
    op.create_index("ix_chat_messages_conversation_created", "chat_messages", ["conversation_id", "created_at", "ordinal", "id"])


def downgrade():
    op.drop_index("ix_chat_messages_conversation_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ux_chat_conversations_owner_id", table_name="chat_conversations")
    op.drop_index("ix_chat_conversations_owner_activity", table_name="chat_conversations")
    op.drop_table("chat_conversations")
