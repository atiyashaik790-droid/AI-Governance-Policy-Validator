"""Record authenticated actor roles on future audit events only."""

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"


def upgrade():
    op.add_column("audit_events", sa.Column("actor_role", sa.String(30), nullable=True))


def downgrade():
    op.drop_column("audit_events", "actor_role")
