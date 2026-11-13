"""Add isolated Entra memberships, one-use OIDC transactions and browser sessions."""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"


def upgrade():
    op.create_table(
        "sso_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("directory_tenant", sa.String(36), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("tenant", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.UniqueConstraint("directory_tenant", "object_id"),
        sa.UniqueConstraint("tenant", "actor"),
    )
    op.create_table(
        "sso_transactions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(100), nullable=False),
        sa.Column("verifier", sa.String(128), nullable=False),
        sa.Column("return_path", sa.String(500), nullable=False),
        sa.Column("expires", sa.String(40), nullable=False),
        sa.Column("consumed", sa.Integer(), nullable=False),
    )
    op.create_index("ix_sso_transactions_expires", "sso_transactions", ["expires"])
    op.create_table(
        "sso_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("membership_id", sa.String(36), sa.ForeignKey("sso_memberships.id"), nullable=False),
        sa.Column("expires", sa.String(40), nullable=False),
        sa.Column("revoked", sa.Integer(), nullable=False),
    )
    op.create_index("ix_sso_sessions_expires", "sso_sessions", ["expires"])


def downgrade():
    raise RuntimeError("Preserve identity/session evidence; roll back the application with SSO disabled, retaining additive tables")
