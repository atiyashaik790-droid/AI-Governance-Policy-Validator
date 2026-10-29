"""Ensure simultaneous reviewers cannot overwrite one another's disposition."""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"


# Guard review status updates with an optimistic concurrency counter.
def upgrade():
    op.add_column("human_review_cases", sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"))


# Require an explicit reviewed migration for any schema downgrade.
def downgrade():
    raise RuntimeError("Destructive schema downgrades require a separately reviewed migration")
