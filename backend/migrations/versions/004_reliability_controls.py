"""Add durable exports, demo sessions, inference limits and review annotations. No data reset."""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"


def upgrade():
    op.create_table(
        "demo_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("credential_hash", sa.String(length=64), nullable=False),
        sa.Column("expires", sa.String(length=40), nullable=False),
        sa.Column("revoked", sa.Integer(), nullable=False),
        sa.Column("created", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_demo_sessions_expires", "demo_sessions", ["expires"], unique=False)
    op.create_index("ix_demo_sessions_tenant", "demo_sessions", ["tenant"], unique=False)
    op.create_table(
        "inference_rate_buckets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("expires", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inference_rate_buckets_expires", "inference_rate_buckets", ["expires"], unique=False)
    op.create_table(
        "inference_usage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expires", sa.String(length=40), nullable=False),
        sa.Column("created", sa.String(length=40), nullable=False),
        sa.Column("finished", sa.String(length=40), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inference_usage_actor", "inference_usage", ["actor"], unique=False)
    op.create_index("ix_inference_usage_expires", "inference_usage", ["expires"], unique=False)
    op.create_index("ix_inference_usage_tenant", "inference_usage", ["tenant"], unique=False)
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.String(length=40), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=False),
        sa.Column("created", sa.String(length=40), nullable=False),
        sa.Column("updated", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["evaluation_exports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant", "idempotency_key"),
    )
    op.create_index("ix_export_jobs_state", "export_jobs", ["state"], unique=False)
    op.create_index("ix_export_jobs_tenant", "export_jobs", ["tenant"], unique=False)
    op.create_table(
        "review_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant", sa.String(length=80), nullable=False),
        sa.Column("assigned_reviewer", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("updated", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["human_review_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_assignments_tenant", "review_assignments", ["tenant"], unique=False)
    op.create_table(
        "review_notes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("tenant", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("created", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["human_review_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_notes_review_id", "review_notes", ["review_id"], unique=False)
    op.create_index("ix_review_notes_tenant", "review_notes", ["tenant"], unique=False)
    op.create_index("ix_execution_tenant_created", "validation_executions", ["tenant", "created", "id"], unique=False)
    bind = op.get_bind()
    for table in ("audit_events", "policy_versions", "review_notes"):
        if bind.dialect.name == "sqlite":
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER immutable_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Historical records are append-only'); END"
                )
        elif bind.dialect.name == "mssql":
            op.execute(
                f"CREATE TRIGGER dbo.immutable_{table} ON dbo.{table} INSTEAD OF UPDATE, DELETE AS BEGIN SET NOCOUNT ON; THROW 51000, 'Historical records are append-only', 1; END"
            )


def downgrade():
    raise RuntimeError("Preserve session/export/review evidence; use an explicitly reviewed rollback migration")
