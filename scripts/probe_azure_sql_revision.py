"""Bounded read-only Azure SQL probe: SELECT 1, DB_NAME(), Alembic revision, 010/011 schema objects, counts.

Run from the repository root with AZURE_CONFIG_DIR=.azure-sql-cli. Issues SELECT statements only; never migrates or writes.
"""
import json, sys
from pathlib import Path
ROOT = Path.cwd(); sys.path.insert(0, str(ROOT / "backend"))
from app.azure_sql import create_azure_sql_engine
from app.config import settings
from sqlalchemy import text
from sqlalchemy.engine import URL
SERVER, DB = "sql-governance-validator-dev-atiya.database.windows.net", "sqldb-gpv-demo-v008-20261108"
out = {"server": SERVER, "database": DB, "writes": False, "migrations": False}
engine = None
try:
    engine = create_azure_sql_engine(URL.create("mssql+pyodbc", host=SERVER, database=DB),
                                     settings.azure_sql_tenant_id, settings.azure_sql_user_object_id)
    with engine.connect() as c:
        out["select_1"] = c.scalar(text("SELECT 1"))
        out["db_name"] = c.scalar(text("SELECT DB_NAME()"))
        has_alembic = c.scalar(text("SELECT OBJECT_ID('dbo.alembic_version')")) is not None
        out["alembic_version"] = c.scalar(text("SELECT version_num FROM dbo.alembic_version")) if has_alembic else None
        out["audit_actor_role_col_010"] = c.scalar(text("SELECT COL_LENGTH('dbo.audit_events','actor_role')")) is not None
        out["chat_tables_011"] = [n for n in ("chat_conversations", "chat_messages")
                                  if c.scalar(text(f"SELECT OBJECT_ID('dbo.{n}')")) is not None]
        out["policies"] = c.scalar(text("SELECT COUNT(*) FROM dbo.policies"))
        out["sso_memberships"] = c.scalar(text("SELECT COUNT(*) FROM dbo.sso_memberships"))
        c.rollback()
    out["status"] = "CONNECTED"
except Exception as e:
    out["status"] = "FAILED"; out["failure_type"] = type(e).__name__
    out["detail"] = str(e).splitlines()[0][:300] if type(e).__module__ == "app.azure_sql" else str(getattr(e, "orig", e)).splitlines()[0][:300]
finally:
    if engine is not None: engine.dispose()
print(json.dumps(out, indent=2))
