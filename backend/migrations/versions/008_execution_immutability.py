"""Close the execution-history SQL enforcement gap without changing frozen DDL."""
from alembic import op

revision = "008"
down_revision = "007"


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER immutable_validation_executions_{action.lower()} "
                f"BEFORE {action} ON validation_executions BEGIN "
                "SELECT RAISE(ABORT, 'Historical records are append-only'); END"
            )
    elif dialect == "mssql":
        op.execute("IF COALESCE(SCHEMA_NAME(), '') <> 'dbo' THROW 51000, '008 requires dbo default schema', 1;")
        op.execute(
            "CREATE TRIGGER dbo.immutable_validation_executions ON dbo.validation_executions "
            "INSTEAD OF UPDATE, DELETE AS BEGIN SET NOCOUNT ON; "
            "THROW 51000, 'Historical records are append-only', 1; END"
        )
    else:
        raise RuntimeError("008 supports only SQLite and SQL Server")


def downgrade():
    raise RuntimeError("Execution history protection must not be removed; use a reviewed forward migration")
