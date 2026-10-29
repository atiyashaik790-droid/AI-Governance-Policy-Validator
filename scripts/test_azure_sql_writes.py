"""Review-gated, bounded synthetic ORM test. Default is an offline plan, never a connection."""

import argparse
import importlib.util
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.azure_sql import create_azure_sql_engine
from app.config import settings
from app.models import (
    Assignment,
    Audit,
    Base,
    Execution,
    Export,
    Feedback,
    Policy,
    Review,
    Version,
)
from sqlalchemy import event, func, inspect, or_, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

SERVER = "sql-governance-validator-dev-atiya.database.windows.net"
DATABASE = "sqldb-governance-validator-dev"
MODELS = (Policy, Version, Assignment, Audit, Execution, Review, Feedback, Export)


class SafetyStop(RuntimeError):
    """Fixed, sanitized failure; never contains database or account contents."""


def require(condition):
    if not condition:
        raise SafetyStop("Reviewed write-test safety condition failed")


def scope_for(run_id):
    run_id = str(UUID(run_id))
    namespace = UUID(run_id)
    return {
        "run_id": run_id,
        "tenant": "sql-write-test-" + run_id,
        "ids": {
            name: str(uuid5(namespace, name))
            for name in (
                "policy",
                "draft",
                "version1",
                "version2",
                "audit",
                "execution",
                "review",
                "feedback",
                "export",
            )
        },
    }


def ids_for(model, scope):
    keys = {
        Policy: ("policy", "draft"),
        Version: ("version1", "version2"),
        Audit: ("audit",),
        Execution: ("execution",),
        Review: ("review",),
        Feedback: ("feedback",),
        Export: ("export",),
    }
    return [scope["ids"][key] for key in keys.get(model, ())]


def scoped_predicate(model, scope):
    # OR intentionally catches a colliding PK even when its tenant differs.
    return (
        or_(model.tenant == scope["tenant"], model.id.in_(ids_for(model, scope)))
        if model is not Assignment
        else model.tenant == scope["tenant"]
    )


def count_records(connection, scope):
    return {
        model.__tablename__: connection.scalar(
            select(func.count())
            .select_from(model)
            .where(scoped_predicate(model, scope))
        )
        for model in MODELS
    }


def require_absent(counts):
    require(absence_verified(counts))


def absence_verified(counts):
    return (
        isinstance(counts, dict)
        and set(counts) == {model.__tablename__ for model in MODELS}
        and all(type(value) is int and value == 0 for value in counts.values())
    )


def write_criteria_met(report):
    operations = report.get("operations")
    expected = {
        "inserted": 10,
        "selected_tables": 8,
        "updated_tables": 4,
        "deleted_synthetic_drafts": 1,
    }
    return (
        isinstance(operations, dict)
        and all(
            type(operations.get(key)) is int and operations[key] == value
            for key, value in expected.items()
        )
        and operations.get("concurrency_counters_verified") is True
        and report.get("cleanup_status") == "VERIFIED_ABSENT_ON_NEW_CONNECTION"
        and absence_verified(report.get("remaining_synthetic_records"))
    )


def successful_report(report, execute):
    # Both worker and parent independently enforce mode-specific success semantics.
    if not isinstance(report, dict) or report.get("error_type"):
        return False
    if execute:
        return (
            report.get("mode") == "ORM_WRITE_TEST"
            and report.get("verification") == "WRITE_TEST_PASSED"
            and write_criteria_met(report)
        )
    return (
        report.get("mode") == "READ_ONLY_ABSENCE_VERIFICATION"
        and report.get("verification") == "ABSENCE_VERIFIED"
        and report.get("cleanup_status") == "VERIFIED_ABSENT_ON_NEW_CONNECTION"
        and absence_verified(report.get("remaining_synthetic_records"))
    )


def forbid_commit(*args, **kwargs):
    raise SafetyStop("Commit is prohibited in this rollback-only test")


def guard_session(session, scope):
    event.listen(session, "before_commit", forbid_commit)

    def only_synthetic(session, flush_context, instances):
        for collection in (session.new, session.dirty, session.deleted):
            for row in collection:
                model = type(row)
                require(model in MODELS and row.tenant == scope["tenant"])
                if model is not Assignment:
                    require(row.id in ids_for(model, scope))
                if row in session.deleted:
                    require(model is Policy and row.id == scope["ids"]["draft"])
                if row in session.dirty:
                    require(model in (Policy, Assignment, Review, Export))

    event.listen(session, "before_flush", only_synthetic)


def exercise_orm(session, scope):
    """Only freshly constructed synthetic instances enter this session. Never merge existing rows."""
    ids, tenant = scope["ids"], scope["tenant"]
    policy = Policy(
        id=ids["policy"],
        tenant=tenant,
        name="Synthetic write test",
        draft='{"synthetic":true}',
        status="DRAFT",
        enabled=1,
        revision=1,
        row_version=1,
    )
    draft = Policy(
        id=ids["draft"],
        tenant=tenant,
        name="Synthetic deletion test",
        draft="{}",
        status="DRAFT",
        enabled=1,
        revision=1,
        row_version=1,
    )
    session.add_all([policy, draft])
    session.flush()
    versions = [
        Version(
            id=ids[key],
            policy_id=policy.id,
            tenant=tenant,
            number=number,
            document='{"synthetic":true}',
        )
        for key, number in (("version1", 1), ("version2", 2))
    ]
    session.add_all(versions)
    session.flush()
    execution = Execution(
        id=ids["execution"],
        tenant=tenant,
        actor="synthetic-test",
        policy_id=policy.id,
        version=1,
        model="synthetic-no-provider",
        decision="ALLOW",
        metadata_json='{"synthetic":true}',
    )
    session.add(execution)
    session.flush()
    assignment = Assignment(tenant=tenant, version_id=versions[0].id)
    review = Review(
        id=ids["review"],
        tenant=tenant,
        execution_id=execution.id,
        status="PENDING",
        row_version=1,
    )
    feedback = Feedback(
        id=ids["feedback"], tenant=tenant, execution_id=execution.id, rating=1
    )
    audit = Audit(
        id=ids["audit"],
        tenant=tenant,
        actor="synthetic-test",
        action="synthetic.write_test",
        resource=policy.id,
    )
    export = Export(id=ids["export"], tenant=tenant, status="PENDING", path="")
    session.add_all([assignment, review, feedback, audit, export])
    session.flush()
    require(policy.row_version == 1 and review.row_version == 1)
    # Materialized database reads rather than identity-map lookups.
    rows = {
        model: session.scalars(select(model).where(model.tenant == tenant)).all()
        for model in MODELS
    }
    require(
        {model: len(items) for model, items in rows.items()}
        == {
            Policy: 2,
            Version: 2,
            Assignment: 1,
            Audit: 1,
            Execution: 1,
            Review: 1,
            Feedback: 1,
            Export: 1,
        }
    )
    policy.name, policy.revision = "Synthetic updated", 2
    assignment.version_id = versions[1].id
    review.status = "REJECTED"
    export.status, export.path = "SUCCEEDED", "synthetic/no-upload.json"
    session.flush()
    for row in (policy, assignment, review, export):
        session.refresh(row)
    require(
        policy.name == "Synthetic updated"
        and policy.revision == 2
        and policy.row_version == 2
    )
    require(
        assignment.version_id == versions[1].id
        and review.status == "REJECTED"
        and review.row_version == 2
    )
    require(export.status == "SUCCEEDED" and export.path == "synthetic/no-upload.json")
    session.delete(draft)
    session.flush()
    require(
        session.scalar(
            select(func.count())
            .select_from(Policy)
            .where(Policy.id == ids["draft"], Policy.tenant == tenant)
        )
        == 0
    )
    require(
        session.scalar(
            select(func.count())
            .select_from(Policy)
            .where(Policy.id == ids["policy"], Policy.tenant == tenant)
        )
        == 1
    )
    return {
        "inserted": 10,
        "selected_tables": 8,
        "updated_tables": 4,
        "deleted_synthetic_drafts": 1,
        "concurrency_counters_verified": True,
    }


def inventory_module():
    spec = importlib.util.spec_from_file_location(
        "write_test_inventory", ROOT / "scripts/inventory_azure_sql.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preflight(connection, inventory):
    report = inventory.collect_inventory(connection, DATABASE)
    require(report.get("inventory_status") == "COMPLETED")
    require(report.get("context", {}).get("database_name") == DATABASE)
    require(report["context"].get("default_schema") == "dbo")
    require(report["context"].get("database_principal") == "dbo")
    require(report.get("alembic_history", {}).get("revisions") == ["003"])
    require(report["alembic_history"].get("matches_expected_heads") is True)
    tables = report.get("required_tables", {})
    require(len(tables) == 8)
    for item in tables.values():
        require(
            item.get("status") == "VISIBLE"
            and set(item.get("checks", {})) == {"columns", "indexes", "foreign_keys"}
        )
        require(
            all(
                check.get("status") == "MATCHES_CHECKED_REQUIREMENTS"
                for check in item["checks"].values()
            )
        )
    # Unexpected DML triggers can affect other rows or break MSSQL OUTPUT; refuse them.
    require(
        connection.scalar(
            text(
                "SELECT COUNT_BIG(*) FROM sys.triggers WHERE parent_class=1 AND is_disabled=0"
            )
        )
        == 0
    )
    # Reject unreviewed incoming/outgoing FKs, including those from other schemas.
    names = ",".join("'" + model.__tablename__ + "'" for model in MODELS)
    targets = (
        "SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID('dbo') AND name IN ("
        + names
        + ")"
    )
    fk_count_sql = (
        "SELECT COUNT_BIG(*) FROM sys.foreign_keys WHERE parent_object_id IN ("
        + targets
        + ") OR referenced_object_id IN ("
        + targets
        + ")"
    )
    require(connection.scalar(text(fk_count_sql)) == 4)
    inspector = inspect(connection)
    for table in Base.metadata.sorted_tables:
        columns = inspector.get_columns(table.name, schema="dbo")
        require({column["name"] for column in columns} == set(table.columns.keys()))
        require(
            all(
                not column.get("identity") and not column.get("computed")
                for column in columns
            )
        )


def transactional_test(engine, scope, preflight_fn, exercise_fn=exercise_orm):
    # One externally owned transaction; no independent engine-bound session or HTTP calls.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.exec_driver_sql("SET LOCK_TIMEOUT 5000")
            connection.exec_driver_sql("SET XACT_ABORT ON")
            preflight_fn(connection)
            require_absent(count_records(connection, scope))
            require(connection.connection.driver_connection.autocommit is False)
            require(
                tuple(
                    connection.execute(text("SELECT @@TRANCOUNT, XACT_STATE()")).one()
                )
                == (1, 1)
            )
            with Session(
                bind=connection,
                join_transaction_mode="rollback_only",
                expire_on_commit=False,
            ) as session:
                guard_session(session, scope)
                operations = exercise_fn(session, scope)
                require(transaction.is_active)
                require(
                    tuple(
                        connection.execute(
                            text("SELECT @@TRANCOUNT, XACT_STATE()")
                        ).one()
                    )
                    == (1, 1)
                )
        finally:
            if transaction.is_active:
                transaction.rollback()
    return operations


def run_worker(arguments):
    logging.getLogger("azure.identity").setLevel(logging.CRITICAL)
    scope = scope_for(arguments.run_id)
    result = {
        "run_id": scope["run_id"],
        "database": DATABASE,
        "verification": "FAILED",
        "mode": "ORM_WRITE_TEST"
        if arguments.execute_approved_write_test
        else "READ_ONLY_ABSENCE_VERIFICATION",
        "cleanup_status": "UNKNOWN_NOT_VERIFIED",
        "writes_requested": arguments.execute_approved_write_test,
        "active_application_database_changed": False,
        "migrations_executed": False,
    }
    engine = None
    failure = None
    try:
        require(make_url(settings.database_url).get_backend_name() == "sqlite")
        cache = Path(arguments.cli_config_dir).resolve()
        require(cache.is_dir())
        os.environ["AZURE_CONFIG_DIR"] = str(cache)
        inventory = inventory_module()
        engine = create_azure_sql_engine(
            URL.create("mssql+pyodbc", host=SERVER, database=DATABASE),
            settings.azure_sql_tenant_id,
            settings.azure_sql_user_object_id,
        )
        inventory.install_query_timeout(engine, 5)
        # The commit event is separate from rollback/reset-on-return. Keep it on the
        # dedicated test engine only; no application engine is modified.
        event.listen(engine, "commit", forbid_commit)
        if arguments.execute_approved_write_test:
            try:
                result["operations"] = transactional_test(
                    engine, scope, lambda connection: preflight(connection, inventory)
                )
            except Exception as error:  # noqa: BLE001 - sanitize errors and always attempt read-only verification
                failure = type(error).__name__
        # Force a NEW physical connection after rollback; never verify absence inside the write transaction.
        engine.dispose()
        with engine.connect() as connection:
            require(connection.scalar(text("SELECT DB_NAME()")) == DATABASE)
            require(connection.scalar(text("SELECT SCHEMA_NAME()")) == "dbo")
            connection.exec_driver_sql("SET LOCK_TIMEOUT 5000")
            counts = count_records(connection, scope)
            result["remaining_synthetic_records"] = counts
            if any(value != 0 for value in counts.values()):
                result["cleanup_status"] = "RECORDS_PRESENT_REVIEW_REQUIRED"
            require_absent(counts)
            result["cleanup_status"] = "VERIFIED_ABSENT_ON_NEW_CONNECTION"
        if failure:
            result["error_type"] = failure
        else:
            if arguments.execute_approved_write_test:
                require(write_criteria_met(result))
                result["verification"] = "WRITE_TEST_PASSED"
            else:
                result["verification"] = "ABSENCE_VERIFIED"
    except Exception as error:  # noqa: BLE001 - sanitize errors and always attempt read-only verification
        result["error_type"] = type(error).__name__
    finally:
        if engine is not None:
            engine.dispose()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute-approved-write-test", action="store_true")
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="SELECT-only absence check for a recorded run UUID",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--server", choices=[SERVER], default=SERVER)
    parser.add_argument("--database", choices=[DATABASE], default=DATABASE)
    parser.add_argument("--cli-config-dir", default=str(ROOT / ".azure-sql-cli"))
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        choices=range(15, 121),
        default=90,
        metavar="15..120",
    )
    parser.add_argument(
        "--internal-worker", action="store_true", help=argparse.SUPPRESS
    )
    arguments = parser.parse_args()
    if (
        arguments.execute_approved_write_test or arguments.verify_only
    ) and not arguments.run_id:
        parser.error(
            "Supply a fresh --run-id UUID for execution, or the recorded UUID for verification"
        )
    try:
        scope = scope_for(arguments.run_id or str(uuid4()))
    except ValueError:
        parser.error("--run-id must be a UUID")
    if not (arguments.execute_approved_write_test or arguments.verify_only):
        print(
            json.dumps(
                {
                    "mode": "OFFLINE_PLAN_ONLY",
                    "database": DATABASE,
                    "scope": scope,
                    "writes_executed": False,
                    "connection_attempted": False,
                },
                indent=2,
            )
        )
        return 0
    if arguments.internal_worker:
        report = run_worker(arguments)
        print(json.dumps(report, indent=2))
        return (
            0 if successful_report(report, arguments.execute_approved_write_test) else 2
        )
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        *sys.argv[1:],
        "--internal-worker",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=arguments.timeout_seconds,
            check=False,
        )
        report = json.loads(completed.stdout)
        if not isinstance(report, dict):
            raise TypeError("Invalid worker report")
        accepted = completed.returncode == 0 and successful_report(
            report, arguments.execute_approved_write_test
        )
        if not accepted and report.get("verification") != "FAILED":
            report["verification"] = "FAILED"
            report["error_type"] = "InvalidWorkerAcceptanceReport"
        print(json.dumps(report, indent=2))
        return 0 if accepted else 2
    except (subprocess.TimeoutExpired, ValueError, TypeError):
        print(
            json.dumps(
                {
                    "verification": "FAILED",
                    "mode": "ORM_WRITE_TEST"
                    if arguments.execute_approved_write_test
                    else "READ_ONLY_ABSENCE_VERIFICATION",
                    "error_type": "WorkerTimeoutOrUnavailable",
                    "run_id": scope["run_id"],
                    "cleanup_status": "UNKNOWN_NOT_VERIFIED",
                    "instruction": "STOP; run the read-only --verify-only check with this UUID. Never retry writes automatically.",
                },
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
