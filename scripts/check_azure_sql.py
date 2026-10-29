"""Opt-in read-only Azure SQL probe. Never changes .env, schemas, grants or app selection."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.azure_sql import DatabaseConfigurationError, create_azure_sql_engine
from app.config import settings
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

RUNTIME_PERMISSIONS = {
    "policies": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "policy_versions": ("SELECT", "INSERT"),
    "active_policy_assignments": ("SELECT", "INSERT", "UPDATE"),
    "audit_events": ("SELECT", "INSERT"),
    "validation_executions": ("SELECT", "INSERT"),
    "human_review_cases": ("SELECT", "INSERT", "UPDATE"),
    "feedback_records": ("SELECT", "INSERT"),
    "evaluation_exports": ("SELECT", "INSERT", "UPDATE"),
}


# Check a fixed allowlist of effective object permissions using SELECT statements only.
def inspect_runtime_permissions(connection) -> list[dict]:
    checks = []
    query = text("SELECT HAS_PERMS_BY_NAME(:object_name, :object_class, :permission)")
    for table, permissions in RUNTIME_PERMISSIONS.items():
        for permission in permissions:
            granted = connection.scalar(
                query,
                {
                    "object_name": f"dbo.{table}",
                    "object_class": "OBJECT",
                    "permission": permission,
                },
            )
            checks.append(
                {
                    "object": f"dbo.{table}",
                    "permission": permission,
                    "status": "GRANTED"
                    if granted == 1
                    else "NOT_GRANTED_OR_OBJECT_NOT_VISIBLE",
                }
            )
    return checks


# Connect to the explicit probe target without replacing the application's SQLite URL.
def verify_read_only_connection(server: str, database: str) -> tuple[dict, int]:
    result = {
        "probe": "READ_ONLY_AZURE_SQL",
        "connection_status": "NOT_CONNECTED",
        "migrations_executed": False,
        "active_application_database_changed": False,
    }
    engine = None
    try:
        url = URL.create("mssql+pyodbc", host=server, database=database)
        engine = create_azure_sql_engine(
            url, settings.azure_sql_tenant_id, settings.azure_sql_user_object_id
        )
        with engine.connect() as connection:
            if connection.scalar(text("SELECT DB_NAME()")) != database:
                raise DatabaseConfigurationError(
                    "Azure SQL probe reached an unexpected database"
                )
            result["connection_status"] = "CONNECTED"
            result["runtime_permissions"] = inspect_runtime_permissions(connection)
            result["runtime_permissions_ready"] = all(
                check["status"] == "GRANTED" for check in result["runtime_permissions"]
            )
        return result, 0 if result["runtime_permissions_ready"] else 3
    except SQLAlchemyError as error:
        # Custom connection/auth/configuration errors are already sanitized; other SQL errors are not echoed.
        result["failure_type"] = type(error).__name__
        result["detail"] = (
            str(error)
            if type(error).__module__ == "app.azure_sql"
            else "Read-only SQL probe unavailable; no changes made"
        )
        return result, 2
    finally:
        if engine is not None:
            engine.dispose()


# Require an explicit connect flag so inspecting script help never contacts Azure.
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--connect",
        action="store_true",
        help="Explicitly permit a read-only connection attempt",
    )
    arguments = parser.parse_args()
    if not arguments.connect:
        parser.error("--connect is required; no network request was made")
    result, status = verify_read_only_connection(arguments.server, arguments.database)
    print(json.dumps(result, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
