"""Add encrypted, expiring original prompts; operator execution only."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = "007"
down_revision = "006"


def upgrade():
    op.create_index("ux_review_cases_tenant_id", "human_review_cases", ["tenant", "id"], unique=True)
    op.create_table(
        "review_protected_content",
        sa.Column("tenant", sa.String(80), primary_key=True),
        sa.Column("review_id", sa.String(36), primary_key=True),
        sa.Column("content_kind", sa.String(20), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("nonce", sa.LargeBinary(12).with_variant(mssql.VARBINARY(12), "mssql"), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary().with_variant(mssql.VARBINARY(None), "mssql"), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["tenant", "review_id"], ["human_review_cases.tenant", "human_review_cases.id"], name="fk_rpc_review_tenant"),
        sa.CheckConstraint("content_kind = 'original_prompt' AND format_version = 1", name="ck_rpc_format"),
        sa.CheckConstraint("expires_at > created_at AND expires_at <= created_at + 604800", name="ck_rpc_retention"),
        sa.CheckConstraint("length(nonce) = 12 AND length(ciphertext) >= 16 AND length(ciphertext) <= 48016", name="ck_rpc_bytes")
        if op.get_bind().dialect.name == "sqlite" else
        sa.CheckConstraint("DATALENGTH(nonce) = 12 AND DATALENGTH(ciphertext) >= 16 AND DATALENGTH(ciphertext) <= 48016", name="ck_rpc_bytes"),
    )
    op.create_index("ux_rpc_key_nonce", "review_protected_content", ["key_id", "nonce"], unique=True)
    op.create_index("ix_rpc_expiry", "review_protected_content", ["expires_at", "tenant", "review_id"])

    if op.get_bind().dialect.name == "sqlite":
        op.execute("CREATE TRIGGER immutable_review_content_update BEFORE UPDATE ON review_protected_content BEGIN SELECT RAISE(ABORT, 'Protected review content is immutable'); END")
    else:
        op.execute("CREATE TRIGGER immutable_review_content_update ON dbo.review_protected_content AFTER UPDATE AS BEGIN SET NOCOUNT ON; THROW 51000, 'Protected review content is immutable', 1; END")


def downgrade():
    # Application rollback disables capture/retrieval while retaining expiry cleanup.
    # Dropping keys/tables or relabelling live ciphertext as 006 is not a safe rollback.
    raise RuntimeError("Protected content must not be destroyed by downgrade; disable the feature and retain cleanup")
