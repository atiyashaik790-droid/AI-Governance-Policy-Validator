"""Read-only preflight for the approved Azure SQL 008 -> 011 upgrade.

Run from the repository root with AZURE_CONFIG_DIR=.azure-sql-cli inside an approved firewall window.
Issues SELECT statements only. Exits non-zero (and the migration must not run) unless the target is the
expected database at revision 008, the runtime role exists, and migration 009's category extraction
would not hit its conflicting-definition guard.
"""
import json
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.azure_sql import create_azure_sql_engine  # noqa: E402
from app.config import settings  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import URL  # noqa: E402

SERVER = "sql-governance-validator-dev-atiya.database.windows.net"
DATABASE = "sqldb-gpv-demo-v008-20261108"
COUNTED = ("policies", "policy_versions", "workspace_policy_assignments", "workspace_policy_assignment_events",
           "audit_events", "validation_executions", "execution_policy_evidence", "sso_memberships",
           "human_review_cases", "review_protected_content")


def main() -> int:
    result = {"server": SERVER, "database": DATABASE, "writes": False, "ready": False}
    engine = create_azure_sql_engine(URL.create("mssql+pyodbc", host=SERVER, database=DATABASE),
                                     settings.azure_sql_tenant_id, settings.azure_sql_user_object_id)
    try:
        with engine.connect() as c:
            result["db_name"] = c.scalar(text("SELECT DB_NAME()"))
            result["revision"] = c.scalar(text("SELECT version_num FROM dbo.alembic_version"))
            result["runtime_role_exists"] = c.scalar(
                text("SELECT DATABASE_PRINCIPAL_ID('governance_validator_web_runtime')")) is not None
            result["objects_already_present"] = [
                name for name in ("governance_categories", "policy_categories", "chat_conversations", "chat_messages")
                if c.scalar(text(f"SELECT OBJECT_ID('dbo.{name}')")) is not None
            ]
            result["counts"] = {t: c.scalar(text(f"SELECT COUNT(*) FROM dbo.{t}")) for t in COUNTED
                                if c.scalar(text(f"SELECT OBJECT_ID('dbo.{t}')")) is not None}
            # Mirror migration 009's extraction to predict its guard without writing anything.
            known, conflicts, embedded = {}, [], 0
            for row in c.execute(text("SELECT id, tenant, draft FROM dbo.policies WHERE status <> 'DELETED'")).mappings():
                for rule in json.loads(row["draft"]).get("custom_categories", []):
                    embedded += 1
                    category_id = str(uuid5(NAMESPACE_URL, f"gpv-category:{row['tenant']}:{rule['id']}"))
                    attributes = (rule["name"], rule.get("description", ""), int(rule.get("enabled", True)),
                                  rule.get("action", "BLOCK"), rule["detection"], json.dumps(rule["values"]))
                    if known.setdefault(category_id, attributes) != attributes:
                        conflicts.append(category_id)
            result["embedded_custom_categories"] = embedded
            result["category_conflicts"] = len(conflicts)
            c.rollback()
        result["ready"] = (result["db_name"] == DATABASE and result["revision"] == "008"
                           and result["runtime_role_exists"] and not result["objects_already_present"]
                           and not conflicts)
    finally:
        engine.dispose()
    print(json.dumps(result, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
