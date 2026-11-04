"""Inventory contracts use catalog fixtures only; never connect to Azure or run migrations."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError


# Import the standalone script without calling its explicit connection entry point.
@pytest.fixture
def inventory():
    path = Path(__file__).resolve().parents[2] / "scripts" / "inventory_azure_sql.py"
    specification = importlib.util.spec_from_file_location("inventory_azure_sql_test", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


# Build a SELECT-only fake connection with individually configurable metadata visibility.
def catalog_connection(module, broad=False, history=None):
    responses = {
        module.CONTEXT_SQL: [{"database_name": module.TARGET_DATABASE, "database_principal": "fixture-user", "default_schema": "dbo"}],
        module.PERMISSIONS_SQL: [{"database_connect": 1, "database_view_definition": int(broad), "dbo_view_definition": 0}],
        module.SCHEMAS_SQL: [{"schema_name": "dbo"}],
        module.TABLES_SQL: [],
        module.COLUMNS_SQL: [],
        module.INDEXES_SQL: [],
        module.FOREIGN_KEYS_SQL: [],
        module.HISTORY_ACCESS_SQL: [{"object_id": None, "can_select": None}],
        module.HISTORY_SQL: [],
    }
    if history is not None:
        responses[module.HISTORY_ACCESS_SQL] = [history]
    connection = Mock()

    # Fail a test immediately if the script submits an unapproved or mutating statement.
    def execute(query):
        sql = str(query)
        assert sql in module.READ_ONLY_QUERIES and sql.lstrip().upper().startswith("SELECT")
        result = responses[sql]
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: result))

    connection.execute.side_effect = execute
    return connection, responses


# Restricted empty catalogs never become claims that tables or the database do not exist.
def test_restricted_empty_metadata_is_unknown(inventory):
    connection, _ = catalog_connection(inventory)
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["inventory_status"] == "COMPLETED_WITH_LIMITATIONS"
    assert len(report["required_tables"]) == 14
    assert all(table["status"] == "UNKNOWN_NOT_VISIBLE" for table in report["required_tables"].values())
    assert report["alembic_history"]["status"] == "UNKNOWN_NOT_VISIBLE"
    assert "database_is_empty" not in report
    assert report["database_mutations_occurred"] is False


# Broad metadata permission changes confidence, without inventing a revision or an empty-database verdict.
def test_missing_history_with_broad_visibility(inventory):
    connection, _ = catalog_connection(inventory, broad=True)
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["inventory_status"] == "COMPLETED"
    assert report["alembic_history"]["status"] == "NOT_FOUND_WITH_BROAD_METADATA_PERMISSION"
    assert "revisions" not in report["alembic_history"]
    assert all(table["status"] == "NOT_FOUND_WITH_BROAD_METADATA_PERMISSION" for table in report["required_tables"].values())


# Visible Alembic history without SELECT remains unreadable; no history query is attempted.
def test_visible_history_not_readable(inventory):
    connection, _ = catalog_connection(inventory, broad=True, history={"object_id": 7, "can_select": 0})
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["alembic_history"]["status"] == "EXISTS_BUT_NOT_READABLE"
    assert all(str(call.args[0]) != inventory.HISTORY_SQL for call in connection.execute.call_args_list)


# An existing but empty bookkeeping table is distinct from a missing history table.
def test_readable_history_without_revision(inventory):
    connection, _ = catalog_connection(inventory, broad=True, history={"object_id": 7, "can_select": 1})
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["alembic_history"] == {"status": "READABLE_NO_REVISION", "revisions": []}


# Report the actual revision when access permits, rather than assuming the head was applied.
def test_existing_alembic_revision(inventory):
    connection, responses = catalog_connection(inventory, broad=True, history={"object_id": 7, "can_select": 1})
    responses[inventory.HISTORY_SQL] = [{"version_num": "002"}]
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["alembic_history"] == {"status": "READABLE", "revisions": ["002"], "matches_expected_heads": False}
    assert report["expected_alembic_heads"] == ["004"]


# Per-section errors are sanitized and leave metadata unknown instead of absent.
def test_metadata_permission_error_is_sanitized(inventory):
    connection, responses = catalog_connection(inventory, broad=True)
    responses[inventory.TABLES_SQL] = OperationalError("private-sql", {"access_token": "do-not-print"}, Exception("private-error"))
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["inventory_status"] == "COMPLETED_WITH_LIMITATIONS"
    assert all(table["status"] == "UNKNOWN_NOT_VISIBLE" for table in report["required_tables"].values())
    assert "do-not-print" not in json.dumps(report) and "private-error" not in json.dumps(report)


# A wrong database aborts before collecting permissions or table metadata.
def test_wrong_database_stops_inspection(inventory):
    connection, responses = catalog_connection(inventory)
    responses[inventory.CONTEXT_SQL][0]["database_name"] = "other-db"
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["inventory_status"] == "WRONG_DATABASE_STOPPED"
    assert connection.execute.call_count == 1


# Large/truncated catalogs cannot be used as proof that an unlisted object is absent.
def test_truncated_metadata_remains_unknown(inventory, monkeypatch):
    monkeypatch.setattr(inventory, "ROW_LIMIT", 1)
    connection, responses = catalog_connection(inventory, broad=True)
    responses[inventory.TABLES_SQL] = [{"schema_name": "dbo", "table_name": "other-one"}, {"schema_name": "dbo", "table_name": "other-two"}]
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["inventory_status"] == "COMPLETED_WITH_LIMITATIONS"
    assert all(table["status"] == "UNKNOWN_NOT_VISIBLE" for table in report["required_tables"].values())


# Only frozen SELECT statements are accepted by the metadata reader.
def test_non_allowlisted_sql_is_rejected(inventory):
    connection = Mock()
    errors = []
    report = inventory.read_section(connection, "SELECT value INTO dbo.new_table FROM dbo.old_table", errors, "invalid")
    assert report["status"] == "UNAVAILABLE" and errors[0]["error_type"] == "ReadOnlyQueryRejected"
    connection.execute.assert_not_called()


# Read migration declarations without importing a migration or calling upgrade functions.
def test_migration_inventory_matches_current_chain(inventory):
    revisions = inventory.migration_inventory()
    assert [revision["revision"] for revision in revisions] == ["001", "002", "003", "004"]
    assert set(revisions[0]["creates_tables"]) | set(revisions[3]["creates_tables"]) == set(inventory.expected_schema())
    assert revisions[1]["adds_columns_to"] == ["policies"]
    assert revisions[2]["adds_columns_to"] == ["human_review_cases"]


# Compare a fully visible schema, then detect a missing index and disabled foreign key.
def test_required_columns_indexes_and_foreign_keys(inventory):
    connection, responses = catalog_connection(inventory, broad=True, history={"object_id": 7, "can_select": 1})
    manifest = inventory.expected_schema()
    for table, expected in manifest.items():
        responses[inventory.TABLES_SQL].append({"schema_name": "dbo", "table_name": table})
        for column in expected["columns"]:
            family = column["family"]
            responses[inventory.COLUMNS_SQL].append(
                {
                    "schema_name": "dbo",
                    "table_name": table,
                    "column_name": column["name"],
                    "type_name": "int" if family == "integer" else "varchar",
                    "max_length": -1 if family == "text" else (column["length"] or 4),
                    "is_nullable": column["nullable"],
                }
            )
        for number, index in enumerate(expected["indexes"]):
            for ordinal, column in enumerate(index["columns"], 1):
                responses[inventory.INDEXES_SQL].append(
                    {
                        "schema_name": "dbo",
                        "table_name": table,
                        "index_name": f"index_{table}_{number}",
                        "column_name": column,
                        "key_ordinal": ordinal,
                        "is_included_column": False,
                        "is_unique": index["unique"],
                        "is_primary_key": index["kind"] == "primary_key",
                        "is_unique_constraint": index["kind"] == "unique",
                        "is_disabled": False,
                        "has_filter": False,
                    }
                )
        for number, foreign_key in enumerate(expected["foreign_keys"]):
            for ordinal, (column, referred_column) in enumerate(
                zip(foreign_key["columns"], foreign_key["referred_columns"], strict=True), 1
            ):
                responses[inventory.FOREIGN_KEYS_SQL].append(
                    {
                        "schema_name": "dbo",
                        "table_name": table,
                        "constraint_name": f"fk_{table}_{number}",
                        "column_name": column,
                        "constraint_column_id": ordinal,
                        "referred_schema": "dbo",
                        "referred_table": foreign_key["referred_table"],
                        "referred_column": referred_column,
                        "is_disabled": False,
                        "is_not_trusted": False,
                        "on_delete": "NO_ACTION",
                        "on_update": "NO_ACTION",
                    }
                )
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert all(
        check["status"] == "MATCHES_CHECKED_REQUIREMENTS"
        for table in report["required_tables"].values()
        for check in table["checks"].values()
    )
    responses[inventory.INDEXES_SQL] = [
        row for row in responses[inventory.INDEXES_SQL] if not (row["table_name"] == "policies" and row["column_name"] == "tenant")
    ]
    responses[inventory.FOREIGN_KEYS_SQL][0]["is_disabled"] = True
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["required_tables"]["policies"]["checks"]["indexes"]["status"] == "DIFFERENCES_FOUND"
    assert any(table["checks"]["foreign_keys"]["status"] == "DIFFERENCES_FOUND" for table in report["required_tables"].values())


# Detect incompatible column lengths, types and nullability; understand NVARCHAR byte lengths.
def test_column_compatibility(inventory):
    expected = {"family": "string", "length": 36, "nullable": False}
    assert inventory.column_mismatches(expected, {"type_name": "nvarchar", "max_length": 72, "is_nullable": False}) == []
    assert inventory.column_mismatches(expected, {"type_name": "varchar", "max_length": 10, "is_nullable": True}) == [
        "INSUFFICIENT_LENGTH",
        "NULLABILITY",
    ]
    assert inventory.column_mismatches(
        {"family": "integer", "length": None, "nullable": False}, {"type_name": "varchar", "max_length": 40, "is_nullable": False}
    ) == ["TYPE_FAMILY"]


# If the worker never responds, terminate it and return without an indefinite join.
def test_wall_clock_timeout_terminates_worker(inventory, monkeypatch):
    receiver = Mock()
    receiver.poll.return_value = False
    sender = Mock()
    process = Mock()
    process.is_alive.side_effect = [True, False]
    context = Mock()
    context.Pipe.return_value = (receiver, sender)
    context.Process.return_value = process
    monkeypatch.setattr(inventory.multiprocessing, "get_context", Mock(return_value=context))
    report = inventory.run_bounded_inventory({"timeout_seconds": 5})
    assert report["inventory_status"] == "TIMED_OUT" and report["database_mutations_occurred"] is False
    receiver.poll.assert_called_once_with(5)
    process.terminate.assert_called_once_with()
    assert all(call.kwargs["timeout"] == 1 for call in process.join.call_args_list)


# Help/imports do not connect, and invocation without explicit --connect fails safely.
def test_cli_requires_explicit_connect(inventory, monkeypatch):
    runner = Mock()
    monkeypatch.setattr(inventory, "run_bounded_inventory", runner)
    monkeypatch.setattr("sys.argv", ["inventory_azure_sql.py"])
    with pytest.raises(SystemExit) as error:
        inventory.main()
    assert error.value.code == 2
    runner.assert_not_called()


# Missing native/auth prerequisites never expose raw errors or initiate interactive login.
def test_worker_sanitizes_errors_and_preserves_environment(inventory, monkeypatch, tmp_path):
    sender = Mock()
    engine_factory = Mock(side_effect=RuntimeError("credential-secret-do-not-print"))
    monkeypatch.setattr(inventory, "create_azure_sql_engine", engine_factory)
    monkeypatch.setenv("AZURE_CONFIG_DIR", "previous-cache")
    inventory.inventory_worker(
        sender,
        {
            "cli_config_dir": str(tmp_path),
            "server": inventory.TARGET_SERVER,
            "database": inventory.TARGET_DATABASE,
            "query_timeout_seconds": 5,
        },
    )
    report = sender.send.call_args.args[0]
    assert report["inventory_status"] == "FAILED" and "credential-secret" not in json.dumps(report)
    assert report["active_application_database_changed"] is False


# Query timeout is applied before connection initialization and catalog work.
def test_installs_query_timeout(inventory, monkeypatch):
    from sqlalchemy import event

    listen = Mock()
    monkeypatch.setattr(event, "listen", listen)
    engine = Mock()
    inventory.install_query_timeout(engine, 5)
    callback = listen.call_args.args[2]
    connection = SimpleNamespace(timeout=0)
    callback(connection, None)
    assert connection.timeout == 5 and listen.call_args.kwargs["insert"] is True


# A visible table with unobserved related metadata stays unknown under restricted access.
def test_restricted_visible_table_details_are_not_assumed_missing(inventory):
    connection, responses = catalog_connection(inventory)
    responses[inventory.TABLES_SQL] = [{"schema_name": "dbo", "table_name": "policies"}]
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    checks = report["required_tables"]["policies"]["checks"]
    assert checks["columns"]["status"] == "UNKNOWN_MISSING_OR_HIDDEN_METADATA"
    assert "missing_required" not in checks["columns"]
    assert checks["indexes"]["status"] == "UNKNOWN_MISSING_OR_HIDDEN_METADATA"


# History SELECT failure is reported without claiming the database has no revision.
def test_alembic_select_denied(inventory):
    connection, responses = catalog_connection(inventory, broad=True, history={"object_id": 7, "can_select": 1})
    responses[inventory.HISTORY_SQL] = OperationalError("private-query", {}, Exception("private-error"))
    report = inventory.collect_inventory(connection, inventory.TARGET_DATABASE)
    assert report["alembic_history"]["status"] == "EXISTS_BUT_REVISION_UNAVAILABLE"
    assert report["inventory_status"] == "COMPLETED_WITH_LIMITATIONS"
    assert "private-error" not in json.dumps(report)


# Exercise actual process spawning and JSON output with a nonexistent cache, without network access.
def test_standalone_cli_missing_cache_is_bounded_and_network_free(tmp_path):
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(root / "scripts" / "inventory_azure_sql.py"),
            "--connect",
            "--cli-config-dir",
            str(tmp_path / "nonexistent-cache"),
            "--timeout-seconds",
            "5",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["inventory_status"] == "CLI_CACHE_UNAVAILABLE"
    assert report["database_mutations_occurred"] is False
