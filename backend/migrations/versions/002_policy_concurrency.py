"""Optimistic concurrency for lifecycle operations on existing databases."""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


# Upgrade older initial databases while tolerating the initial metadata-based baseline.
def upgrade():
    columns = sa.inspect(op.get_bind()).get_columns("policies")
    if "row_version" not in {column["name"] for column in columns}:
        op.add_column("policies", sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"))


# Retain a harmless version column rather than risk rewriting SQLite tables.
def downgrade():
    raise RuntimeError("Destructive schema downgrades require a separately reviewed migration")
