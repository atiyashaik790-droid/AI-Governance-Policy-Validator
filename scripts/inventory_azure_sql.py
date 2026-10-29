"""Bounded, SELECT-only Azure SQL inventory. No migrations, grants or .env changes."""

import argparse
import ast
import logging
import multiprocessing
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.azure_sql import create_azure_sql_engine
from app.config import settings
from app.models import Base
from sqlalchemy import Integer, Text, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

TARGET_SERVER = "sql-governance-validator-dev-atiya.database.windows.net"
TARGET_DATABASE = "sqldb-governance-validator-dev"
ROW_LIMIT = 10000

CONTEXT_SQL = "SELECT DB_NAME() AS database_name, USER_NAME() AS database_principal, SCHEMA_NAME() AS default_schema"
PERMISSIONS_SQL = """SELECT
 HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONNECT') AS database_connect,
 HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','VIEW DEFINITION') AS database_view_definition,
 HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL') AS database_control,
 HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CREATE TABLE') AS database_create_table,
 HAS_PERMS_BY_NAME('dbo','SCHEMA','VIEW DEFINITION') AS dbo_view_definition,
 HAS_PERMS_BY_NAME('dbo','SCHEMA','CONTROL') AS dbo_control,
 HAS_PERMS_BY_NAME('dbo','SCHEMA','ALTER') AS dbo_alter,
 HAS_PERMS_BY_NAME('dbo','SCHEMA','REFERENCES') AS dbo_references"""
SCHEMAS_SQL = "SELECT TOP (10001) name AS schema_name FROM sys.schemas ORDER BY name"
TABLES_SQL = """SELECT TOP (10001) s.name AS schema_name,t.name AS table_name
 FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id
 WHERE t.is_ms_shipped=0 ORDER BY s.name,t.name"""
COLUMNS_SQL = """SELECT TOP (10001) s.name AS schema_name,t.name AS table_name,
 c.name AS column_name,ty.name AS type_name,c.max_length,c.is_nullable
 FROM sys.columns c JOIN sys.tables t ON c.object_id=t.object_id
 JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.types ty ON c.user_type_id=ty.user_type_id
 WHERE t.is_ms_shipped=0 ORDER BY s.name,t.name,c.column_id"""
INDEXES_SQL = """SELECT TOP (10001) s.name AS schema_name,t.name AS table_name,i.name AS index_name,
 i.is_unique,i.is_primary_key,i.is_unique_constraint,i.is_disabled,i.has_filter,
 c.name AS column_name,ic.key_ordinal,ic.is_included_column
 FROM sys.indexes i JOIN sys.tables t ON i.object_id=t.object_id
 JOIN sys.schemas s ON s.schema_id=t.schema_id
 JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
 JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
 WHERE t.is_ms_shipped=0 AND i.index_id>0 ORDER BY s.name,t.name,i.name,ic.key_ordinal"""
FOREIGN_KEYS_SQL = """SELECT TOP (10001) s.name AS schema_name,t.name AS table_name,
 fk.name AS constraint_name,c.name AS column_name,rs.name AS referred_schema,
 rt.name AS referred_table,rc.name AS referred_column,fkc.constraint_column_id,
 fk.is_disabled,fk.is_not_trusted,fk.delete_referential_action_desc AS on_delete,
 fk.update_referential_action_desc AS on_update
 FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fk.object_id=fkc.constraint_object_id
 JOIN sys.tables t ON t.object_id=fk.parent_object_id JOIN sys.schemas s ON s.schema_id=t.schema_id
 JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=fkc.parent_column_id
 JOIN sys.tables rt ON rt.object_id=fk.referenced_object_id JOIN sys.schemas rs ON rs.schema_id=rt.schema_id
 JOIN sys.columns rc ON rc.object_id=rt.object_id AND rc.column_id=fkc.referenced_column_id
 WHERE t.is_ms_shipped=0 ORDER BY s.name,t.name,fk.name,fkc.constraint_column_id"""
HISTORY_ACCESS_SQL = """SELECT OBJECT_ID('dbo.alembic_version','U') AS object_id,
 HAS_PERMS_BY_NAME('dbo.alembic_version','OBJECT','SELECT') AS can_select"""
HISTORY_SQL = (
    "SELECT TOP (101) version_num FROM dbo.alembic_version ORDER BY version_num"
)

READ_ONLY_QUERIES = frozenset(
    (
        CONTEXT_SQL,
        PERMISSIONS_SQL,
        SCHEMAS_SQL,
        TABLES_SQL,
        COLUMNS_SQL,
        INDEXES_SQL,
        FOREIGN_KEYS_SQL,
        HISTORY_ACCESS_SQL,
        HISTORY_SQL,
    )
)


# Describe the current ORM schema without invoking any migration or database operation.
def expected_schema() -> dict:
    manifest = {}
    for table in Base.metadata.sorted_tables:
        columns = []
        for column in table.columns:
            family = (
                "integer"
                if isinstance(column.type, Integer)
                else ("text" if isinstance(column.type, Text) else "string")
            )
            columns.append(
                {
                    "name": column.name,
                    "family": family,
                    "length": getattr(column.type, "length", None),
                    "nullable": column.nullable,
                }
            )
        indexes = [
            {
                "kind": "primary_key",
                "columns": list(table.primary_key.columns.keys()),
                "unique": True,
            }
        ]
        for constraint in table.constraints:
            if type(constraint).__name__ == "UniqueConstraint":
                indexes.append(
                    {
                        "kind": "unique",
                        "columns": list(constraint.columns.keys()),
                        "unique": True,
                    }
                )
        indexes.extend(
            {
                "kind": "index",
                "name": index.name,
                "columns": list(index.columns.keys()),
                "unique": bool(index.unique),
            }
            for index in sorted(table.indexes, key=lambda item: item.name)
        )
        foreign_keys = []
        for constraint in table.foreign_key_constraints:
            foreign_keys.append(
                {
                    "columns": list(constraint.columns.keys()),
                    "referred_schema": "dbo",
                    "referred_table": constraint.referred_table.name,
                    "referred_columns": [
                        element.column.name for element in constraint.elements
                    ],
                    "on_delete": constraint.ondelete or "NO_ACTION",
                    "on_update": constraint.onupdate or "NO_ACTION",
                }
            )
        manifest[table.name] = {
            "columns": columns,
            "indexes": indexes,
            "foreign_keys": foreign_keys,
        }
    return manifest


# Read revision identifiers and operations as syntax only; never import or run migrations.
def migration_inventory() -> list[dict]:
    revisions = []
    for path in sorted((ROOT / "backend" / "migrations" / "versions").glob("*.py")):
        tree = ast.parse(path.read_text())
        revision = {"file": path.name, "creates_tables": [], "adds_columns_to": []}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in (
                        "revision",
                        "down_revision",
                    ):
                        revision[target.id] = node.value.value
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                for call in ast.walk(node):
                    if (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and call.args
                    ):
                        operation = {
                            "create_table": "creates_tables",
                            "add_column": "adds_columns_to",
                        }.get(call.func.attr)
                        if operation and isinstance(call.args[0], ast.Constant):
                            revision[operation].append(call.args[0].value)
        revisions.append(revision)
    return revisions


# Fetch only bounded SELECT results and preserve unavailable metadata as unknown.
def read_section(connection: Any, sql: str, errors: list, section: str) -> dict:
    if sql not in READ_ONLY_QUERIES:
        errors.append({"section": section, "error_type": "ReadOnlyQueryRejected"})
        return {"status": "UNAVAILABLE", "rows": [], "truncated": False}
    try:
        rows = [dict(row) for row in connection.execute(text(sql)).mappings().all()]
        return {
            "status": "OK",
            "rows": rows[:ROW_LIMIT],
            "truncated": len(rows) > ROW_LIMIT,
        }
    except (SQLAlchemyError, TimeoutError) as error:
        errors.append({"section": section, "error_type": type(error).__name__})
        return {"status": "UNAVAILABLE", "rows": [], "truncated": False}


# Convert index catalog rows into complete ordered key definitions, ignoring included columns.
def observed_indexes(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[row["index_name"]].append(row)
    result = []
    for name, entries in groups.items():
        first = entries[0]
        keys = sorted(
            (
                entry
                for entry in entries
                if not entry["is_included_column"] and entry["key_ordinal"] > 0
            ),
            key=lambda entry: entry["key_ordinal"],
        )
        result.append(
            {
                "name": name,
                "columns": [entry["column_name"] for entry in keys],
                "unique": bool(first["is_unique"]),
                "primary_key": bool(first["is_primary_key"]),
                "disabled": bool(first["is_disabled"]),
                "filtered": bool(first["has_filter"]),
            }
        )
    return result


# Preserve foreign-key column ordering and validation/enforcement state.
def observed_foreign_keys(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[row["constraint_name"]].append(row)
    result = []
    for name, entries in groups.items():
        ordered = sorted(entries, key=lambda entry: entry["constraint_column_id"])
        first = ordered[0]
        result.append(
            {
                "name": name,
                "columns": [entry["column_name"] for entry in ordered],
                "referred_schema": first["referred_schema"],
                "referred_table": first["referred_table"],
                "referred_columns": [entry["referred_column"] for entry in ordered],
                "disabled": bool(first["is_disabled"]),
                "not_trusted": bool(first["is_not_trusted"]),
                "on_delete": first["on_delete"],
                "on_update": first["on_update"],
            }
        )
    return result


# Check compatible SQL Server type families, lengths and nullability without claiming full DDL equivalence.
def column_mismatches(expected: dict, observed: dict) -> list[str]:
    problems = []
    actual_type = observed["type_name"].lower()
    length = observed["max_length"]
    if (
        expected["family"] == "integer"
        and actual_type != "int"
        or expected["family"] == "text"
        and not (
            actual_type in ("text", "ntext")
            or (actual_type in ("varchar", "nvarchar") and length == -1)
        )
    ):
        problems.append("TYPE_FAMILY")
    elif expected["family"] == "string":
        if actual_type not in ("varchar", "nvarchar", "char", "nchar"):
            problems.append("TYPE_FAMILY")
        elif expected["length"] and length != -1:
            characters = length // 2 if actual_type in ("nvarchar", "nchar") else length
            if characters < expected["length"]:
                problems.append("INSUFFICIENT_LENGTH")
    if bool(observed["is_nullable"]) != expected["nullable"]:
        problems.append("NULLABILITY")
    return problems


# Compare only visible metadata; absent catalog rows with limited visibility remain unknown.
def compare_tables(sections: dict, broad_visibility: bool) -> dict:
    required = expected_schema()
    tables = sections["tables"]
    visible = {(row["schema_name"], row["table_name"]) for row in tables["rows"]}
    report = {}
    for name, expected in required.items():
        if ("dbo", name) not in visible:
            conclusive_scope = (
                tables["status"] == "OK"
                and not tables["truncated"]
                and broad_visibility
            )
            report[name] = {
                "status": "NOT_FOUND_WITH_BROAD_METADATA_PERMISSION"
                if conclusive_scope
                else "UNKNOWN_NOT_VISIBLE",
                "expected": expected,
            }
            continue
        table_report = {"status": "VISIBLE", "expected": expected, "checks": {}}
        for section in ("columns", "indexes", "foreign_keys"):
            data = sections[section]
            entries = [
                row
                for row in data["rows"]
                if row["schema_name"] == "dbo" and row["table_name"] == name
            ]
            if data["status"] != "OK" or data["truncated"]:
                table_report["checks"][section] = {
                    "status": "UNKNOWN_INCOMPLETE_METADATA"
                }
                continue
            if section == "columns":
                by_name = {row["column_name"]: row for row in entries}
                missing = [
                    column["name"]
                    for column in expected["columns"]
                    if column["name"] not in by_name
                ]
                mismatches = [
                    {
                        "column": column["name"],
                        "issues": column_mismatches(column, by_name[column["name"]]),
                    }
                    for column in expected["columns"]
                    if column["name"] in by_name
                ]
                mismatches = [item for item in mismatches if item["issues"]]
                check = {
                    "observed": entries,
                    "missing_required": missing,
                    "mismatches": mismatches,
                }
            elif section == "indexes":
                observed = observed_indexes(entries)
                missing = [
                    index
                    for index in expected["indexes"]
                    if not any(
                        actual["columns"] == index["columns"]
                        and actual["unique"] == index["unique"]
                        and actual["primary_key"] == (index["kind"] == "primary_key")
                        and not actual["disabled"]
                        and not actual["filtered"]
                        for actual in observed
                    )
                ]
                check = {"observed": observed, "missing_required": missing}
            else:
                observed = observed_foreign_keys(entries)
                fields = (
                    "columns",
                    "referred_schema",
                    "referred_table",
                    "referred_columns",
                    "on_delete",
                    "on_update",
                )
                missing = [
                    foreign_key
                    for foreign_key in expected["foreign_keys"]
                    if not any(
                        all(actual[key] == foreign_key[key] for key in fields)
                        and not actual["disabled"]
                        and not actual["not_trusted"]
                        for actual in observed
                    )
                ]
                check = {"observed": observed, "missing_required": missing}
            if check.get("mismatches"):
                check["status"] = "DIFFERENCES_FOUND"
            elif check["missing_required"]:
                check["status"] = (
                    "DIFFERENCES_FOUND"
                    if broad_visibility
                    else "UNKNOWN_MISSING_OR_HIDDEN_METADATA"
                )
                if not broad_visibility:
                    check["unobserved_required"] = check.pop("missing_required")
            else:
                check["status"] = "MATCHES_CHECKED_REQUIREMENTS"
            table_report["checks"][section] = check
        report[name] = table_report
    return report


# Read Alembic bookkeeping only when the history table is visible and SELECT is granted.
def inspect_history(connection: Any, broad_visibility: bool, errors: list) -> dict:
    access = read_section(connection, HISTORY_ACCESS_SQL, errors, "alembic_access")
    if access["status"] != "OK" or len(access["rows"]) != 1:
        return {"status": "UNKNOWN_ACCESS_CHECK_FAILED"}
    row = access["rows"][0]
    if row["object_id"] is None:
        return {
            "status": "NOT_FOUND_WITH_BROAD_METADATA_PERMISSION"
            if broad_visibility
            else "UNKNOWN_NOT_VISIBLE"
        }
    if row["can_select"] != 1:
        return {"status": "EXISTS_BUT_NOT_READABLE"}
    history = read_section(connection, HISTORY_SQL, errors, "alembic_revision")
    if history["status"] != "OK":
        return {"status": "EXISTS_BUT_REVISION_UNAVAILABLE"}
    revisions = [row["version_num"] for row in history["rows"]]
    if len(revisions) > 100:
        return {"status": "UNEXPECTED_HISTORY_ROW_COUNT", "revisions": revisions[:100]}
    return {
        "status": "READABLE" if revisions else "READABLE_NO_REVISION",
        "revisions": revisions,
    }


# Inventory a single authenticated connection with fixed SELECT-only catalog queries.
def collect_inventory(connection: Any, expected_database: str) -> dict:
    errors = []
    context = read_section(connection, CONTEXT_SQL, errors, "context")
    report = {
        "connection_status": "CONNECTED",
        "database_mutations_occurred": False,
        "migrations_executed": False,
        "active_application_database_changed": False,
        "errors": errors,
    }
    if context["status"] != "OK" or len(context["rows"]) != 1:
        return {**report, "inventory_status": "CONTEXT_UNAVAILABLE"}
    report["context"] = context["rows"][0]
    if report["context"]["database_name"] != expected_database:
        return {**report, "inventory_status": "WRONG_DATABASE_STOPPED"}
    permissions = read_section(connection, PERMISSIONS_SQL, errors, "permissions")
    permission_row = (
        permissions["rows"][0]
        if permissions["status"] == "OK" and len(permissions["rows"]) == 1
        else {}
    )
    broad = any(
        permission_row.get(key) == 1
        for key in (
            "database_view_definition",
            "database_control",
            "dbo_view_definition",
            "dbo_control",
        )
    )
    report["permissions"] = {
        "status": permissions["status"],
        "effective": permission_row,
    }
    report["metadata_visibility"] = {
        "dbo_broad_permission_present": broad,
        "warning": "Catalog results are permission-filtered. Empty results do not prove an empty database; explicit denials may also limit visibility.",
    }
    queries = {
        "schemas": SCHEMAS_SQL,
        "tables": TABLES_SQL,
        "columns": COLUMNS_SQL,
        "indexes": INDEXES_SQL,
        "foreign_keys": FOREIGN_KEYS_SQL,
    }
    sections = {
        name: read_section(connection, sql, errors, name)
        for name, sql in queries.items()
    }
    report["visible_schemas"] = sections["schemas"]
    report["visible_user_tables"] = sections["tables"]
    report["required_tables"] = compare_tables(sections, broad)
    report["alembic_history"] = inspect_history(connection, broad, errors)
    report["migration_scripts"] = migration_inventory()
    parents = {
        revision.get("down_revision") for revision in report["migration_scripts"]
    }
    report["expected_alembic_heads"] = sorted(
        revision["revision"]
        for revision in report["migration_scripts"]
        if revision["revision"] not in parents
    )
    if report["alembic_history"].get("status") == "READABLE":
        report["alembic_history"]["matches_expected_heads"] = (
            sorted(report["alembic_history"]["revisions"])
            == report["expected_alembic_heads"]
        )
    report["inventory_status"] = (
        "COMPLETED_WITH_LIMITATIONS"
        if errors
        or not broad
        or report["alembic_history"]["status"]
        in (
            "UNKNOWN_ACCESS_CHECK_FAILED",
            "UNKNOWN_NOT_VISIBLE",
            "EXISTS_BUT_NOT_READABLE",
            "EXISTS_BUT_REVISION_UNAVAILABLE",
            "UNEXPECTED_HISTORY_ROW_COUNT",
        )
        or any(section["truncated"] for section in sections.values())
        else "COMPLETED"
    )
    report["migration_approval_required"] = True
    report["readiness_notes"] = []
    if report["context"].get("default_schema") != "dbo":
        report["readiness_notes"].append(
            "Default schema differs from dbo; existing migrations do not specify schema. Review before approval."
        )
    return report


# Bound every catalog cursor's query duration independently of the overall process deadline.
def install_query_timeout(engine: Any, seconds: int) -> None:
    from sqlalchemy import event

    # Set pyodbc's connection-level query timeout before any command uses a cursor.
    def set_timeout(connection, record) -> None:
        connection.timeout = seconds

    event.listen(engine, "connect", set_timeout, insert=True)


# Perform inventory in an isolated worker so an unresponsive driver can be terminated.
def inventory_worker(sender: Any, arguments: dict) -> None:
    import json

    logging.getLogger("azure.identity").setLevel(logging.CRITICAL)
    engine = None
    try:
        cache = Path(arguments["cli_config_dir"]).resolve()
        if not cache.is_dir():
            sender.send(
                {
                    "connection_status": "NOT_CONNECTED",
                    "inventory_status": "CLI_CACHE_UNAVAILABLE",
                    "database_mutations_occurred": False,
                }
            )
            return
        os.environ["AZURE_CONFIG_DIR"] = str(cache)
        url = URL.create(
            "mssql+pyodbc", host=arguments["server"], database=arguments["database"]
        )
        engine = create_azure_sql_engine(
            url, settings.azure_sql_tenant_id, settings.azure_sql_user_object_id
        )
        install_query_timeout(engine, arguments["query_timeout_seconds"])
        with engine.connect() as connection:
            report = collect_inventory(connection, arguments["database"])
        # Test JSON serializability before sending; no tokens or connection URLs enter the report.
        json.dumps(report)
        sender.send(report)
    except Exception as error:  # noqa: BLE001 - sanitize all errors at the isolated worker boundary
        sender.send(
            {
                "connection_status": "NOT_CONNECTED"
                if engine is None
                else "FAILED_OR_INTERRUPTED",
                "inventory_status": "FAILED",
                "error_type": type(error).__name__,
                "detail": "Inventory unavailable; check local organizational login, driver, network and metadata access. No interactive login or mutation was attempted.",
                "database_mutations_occurred": False,
                "migrations_executed": False,
                "active_application_database_changed": False,
            }
        )
    finally:
        sender.close()
        if engine is not None:
            engine.dispose()


# Enforce a wall-clock deadline including authentication, network work and driver cleanup.
def run_bounded_inventory(arguments: dict) -> dict:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=inventory_worker, args=(sender, arguments), daemon=True
    )
    process.start()
    sender.close()
    try:
        if receiver.poll(arguments["timeout_seconds"]):
            try:
                return receiver.recv()
            except EOFError:
                return {
                    "inventory_status": "WORKER_EXITED",
                    "connection_status": "UNKNOWN",
                    "database_mutations_occurred": False,
                }
        return {
            "inventory_status": "TIMED_OUT",
            "connection_status": "UNKNOWN",
            "database_mutations_occurred": False,
            "migrations_executed": False,
            "active_application_database_changed": False,
        }
    finally:
        receiver.close()
        process.join(timeout=1)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)


# Require explicit read-only connection consent; help and imports never contact Azure SQL.
def main() -> int:
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=TARGET_SERVER)
    parser.add_argument("--database", default=TARGET_DATABASE)
    parser.add_argument("--cli-config-dir", default=str(ROOT / ".azure-sql-cli"))
    parser.add_argument("--connect", action="store_true")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        choices=range(5, 181),
        metavar="5..180",
    )
    parser.add_argument(
        "--query-timeout-seconds",
        type=int,
        default=5,
        choices=range(1, 31),
        metavar="1..30",
    )
    arguments = parser.parse_args()
    if not arguments.connect:
        parser.error("--connect is required; no network request was made")
    report = run_bounded_inventory(vars(arguments))
    print(json.dumps(report, indent=2))
    return (
        0
        if report.get("inventory_status") == "COMPLETED"
        else (
            3 if report.get("inventory_status") == "COMPLETED_WITH_LIMITATIONS" else 2
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
