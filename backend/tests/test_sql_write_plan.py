"""Mock-only write-test safety contracts; no live SQL or local DDL/DML is executed."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session


@pytest.fixture
def script():
    path = Path(__file__).resolve().parents[2] / "scripts/test_azure_sql_writes.py"
    spec = importlib.util.spec_from_file_location("write_plan_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def scope(script):
    return script.scope_for("11111111-2222-4333-8444-555555555555")


def test_scope_is_reproducible_unique_and_bounded(script, scope):
    assert scope == script.scope_for(scope["run_id"])
    assert len(scope["ids"]) == 9 and len(set(scope["ids"].values())) == 9
    assert len(scope["tenant"]) <= 80
    assert all(len(value) == 36 for value in scope["ids"].values())
    assert scope != script.scope_for("99999999-2222-4333-8444-555555555555")


def test_collision_and_unknown_counts_stop(script):
    for counts in ({}, {"policies": 0}, {str(i): int(i == 0) for i in range(8)}):
        with pytest.raises(script.SafetyStop):
            script.require_absent(counts)
    script.require_absent({model.__tablename__: 0 for model in script.MODELS})


def test_collision_predicates_include_tenant_or_primary_keys(script, scope):
    for model in script.MODELS:
        sql = str(script.scoped_predicate(model, scope).compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))
        assert scope["tenant"] in sql
        if model is not script.Assignment:
            assert " OR " in sql
            assert all(value in sql for value in script.ids_for(model, scope))


def test_session_refuses_commit_and_foreign_dirty_objects(script, scope):
    session = Session()
    script.guard_session(session, scope)
    with pytest.raises(script.SafetyStop):
        session.commit()
    foreign = script.Policy(id=scope["ids"]["policy"], tenant="existing-tenant")
    session.add(foreign)
    # Dispatch only the safety hook, not a SQLAlchemy flush or SQL operation.
    with pytest.raises(script.SafetyStop):
        session.dispatch.before_flush(session, None, None)
    session.close()


def test_session_refuses_immutable_mutations_and_non_draft_delete(script, scope):
    class FakeSession:
        pass

    # Use the captured callback to test dirty/deleted collections without a database.
    callbacks = {}
    original = event.listen
    try:
        event.listen = lambda target, name, callback: callbacks.update({name: callback})
        script.guard_session(FakeSession(), scope)
    finally:
        event.listen = original
    audit = script.Audit(id=scope["ids"]["audit"], tenant=scope["tenant"])
    with pytest.raises(script.SafetyStop):
        callbacks["before_flush"](SimpleNamespace(new=[], dirty=[audit], deleted=[]), None, None)
    policy = script.Policy(id=scope["ids"]["policy"], tenant=scope["tenant"])
    with pytest.raises(script.SafetyStop):
        callbacks["before_flush"](SimpleNamespace(new=[], dirty=[], deleted=[policy]), None, None)


def test_failure_rolls_back_and_never_calls_exercise_on_collision(script, scope, monkeypatch):
    connection = MagicMock()
    transaction = connection.begin.return_value
    transaction.is_active = True
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(script, "count_records", lambda connection, scope: {str(i): 1 for i in range(8)})
    exercise = Mock()
    with pytest.raises(script.SafetyStop):
        script.transactional_test(engine, scope, Mock(), exercise)
    transaction.rollback.assert_called_once()
    transaction.commit.assert_not_called()
    exercise.assert_not_called()


def test_offline_default_never_creates_engine(script, monkeypatch, capsys):
    factory = Mock(side_effect=AssertionError("No connection allowed"))
    monkeypatch.setattr(script, "create_azure_sql_engine", factory)
    forbidden = [Mock(side_effect=AssertionError("Offline mode cannot mutate or run a worker")) for _ in range(3)]
    monkeypatch.setattr(script, "run_worker", forbidden[0])
    monkeypatch.setattr(script.subprocess, "run", forbidden[1])
    monkeypatch.setattr(Path, "write_text", forbidden[2])
    monkeypatch.setattr("sys.argv", ["test_azure_sql_writes.py"])
    assert script.main() == 0
    assert '"connection_attempted": false' in capsys.readouterr().out
    factory.assert_not_called()
    for operation in forbidden:
        operation.assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [["--execute-approved-write-test"], ["--verify-only"], ["--database", "other"], ["--server", "other"], ["--run-id", "invalid"]],
)
def test_missing_approval_scope_or_wrong_target_never_connects(script, monkeypatch, arguments):
    factory = Mock()
    monkeypatch.setattr(script, "create_azure_sql_engine", factory)
    monkeypatch.setattr("sys.argv", ["test_azure_sql_writes.py", *arguments])
    with pytest.raises(SystemExit):
        script.main()
    factory.assert_not_called()


def worker_args(execute=True):
    return SimpleNamespace(run_id="11111111-2222-4333-8444-555555555555", cli_config_dir="/tmp", execute_approved_write_test=execute)


def setup_worker(script, monkeypatch, absent=True):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.side_effect = [script.DATABASE, "dbo"]
    monkeypatch.setattr(script, "create_azure_sql_engine", Mock(return_value=engine))
    monkeypatch.setattr(script, "inventory_module", lambda: SimpleNamespace(install_query_timeout=Mock()))
    monkeypatch.setattr(script.event, "listen", Mock())
    monkeypatch.setattr(
        script, "count_records", lambda connection, scope: {model.__tablename__: 0 if absent else 1 for model in script.MODELS}
    )
    return engine


def test_worker_disposes_before_independent_absence_check(script, monkeypatch):
    engine = setup_worker(script, monkeypatch)
    exercise = Mock(return_value=valid_operations())
    monkeypatch.setattr(script, "transactional_test", exercise)
    report = script.run_worker(worker_args())
    assert report["verification"] == "WRITE_TEST_PASSED"
    assert report["cleanup_status"] == "VERIFIED_ABSENT_ON_NEW_CONNECTION"
    calls = [call[0] for call in engine.mock_calls]
    assert calls.index("dispose") < calls.index("connect")
    exercise.assert_called_once()


def test_failed_write_stays_failed_after_successful_rollback_check(script, monkeypatch):
    setup_worker(script, monkeypatch)
    monkeypatch.setattr(script, "transactional_test", Mock(side_effect=RuntimeError("private error")))
    report = script.run_worker(worker_args())
    assert report["verification"] == "FAILED" and report["error_type"] == "RuntimeError"
    assert report["cleanup_status"] == "VERIFIED_ABSENT_ON_NEW_CONNECTION"
    assert "private error" not in str(report)


def test_residual_records_fail_without_automatic_deletion(script, monkeypatch):
    setup_worker(script, monkeypatch, absent=False)
    writer = Mock()
    monkeypatch.setattr(script, "transactional_test", writer)
    report = script.run_worker(worker_args(execute=False))
    assert report["verification"] == "FAILED"
    assert report["cleanup_status"] == "RECORDS_PRESENT_REVIEW_REQUIRED"
    writer.assert_not_called()


def test_timeout_never_claims_rollback_or_retries(script, monkeypatch, capsys):
    runner = Mock(side_effect=script.subprocess.TimeoutExpired("worker", 15))
    monkeypatch.setattr(script.subprocess, "run", runner)
    monkeypatch.setattr("sys.argv", ["test_azure_sql_writes.py", "--execute-approved-write-test", "--run-id", worker_args().run_id])
    assert script.main() == 2
    assert "UNKNOWN_NOT_VERIFIED" in capsys.readouterr().out
    runner.assert_called_once()


def test_success_path_binds_one_connection_and_rolls_back(script, scope, monkeypatch):
    engine, connection = MagicMock(), MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    transaction = connection.begin.return_value
    transaction.is_active = True
    connection.connection.driver_connection.autocommit = False
    connection.execute.return_value.one.return_value = (1, 1)
    factory = MagicMock()
    monkeypatch.setattr(script, "Session", factory)
    monkeypatch.setattr(script, "guard_session", Mock())
    monkeypatch.setattr(script, "count_records", lambda connection, scope: {model.__tablename__: 0 for model in script.MODELS})
    exercise = Mock(return_value={"inserted": 10})
    assert script.transactional_test(engine, scope, Mock(), exercise) == {"inserted": 10}
    assert factory.call_args.kwargs["bind"] is connection
    assert factory.call_args.kwargs["join_transaction_mode"] == "rollback_only"
    transaction.rollback.assert_called_once()
    transaction.commit.assert_not_called()
    exercise.assert_called_once()


def test_mid_write_failure_always_rolls_back(script, scope, monkeypatch):
    engine, connection = MagicMock(), MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    transaction = connection.begin.return_value
    transaction.is_active = True
    connection.connection.driver_connection.autocommit = False
    connection.execute.return_value.one.return_value = (1, 1)
    monkeypatch.setattr(script, "Session", MagicMock())
    monkeypatch.setattr(script, "guard_session", Mock())
    monkeypatch.setattr(script, "count_records", lambda connection, scope: {model.__tablename__: 0 for model in script.MODELS})
    with pytest.raises(RuntimeError):
        script.transactional_test(engine, scope, Mock(), Mock(side_effect=RuntimeError("synthetic failure")))
    transaction.rollback.assert_called_once()
    transaction.commit.assert_not_called()


@pytest.mark.parametrize("problem", ["trigger", "identity", "computed", "extra_column", "revision", "extra_fk"])
def test_preflight_stops_schema_drift(script, monkeypatch, problem):
    checks = {name: {"status": "MATCHES_CHECKED_REQUIREMENTS"} for name in ("columns", "indexes", "foreign_keys")}
    report = {
        "inventory_status": "COMPLETED",
        "context": {"database_name": script.DATABASE, "default_schema": "dbo", "database_principal": "dbo"},
        "alembic_history": {"revisions": ["002"] if problem == "revision" else ["003"], "matches_expected_heads": True},
        "required_tables": {model.__tablename__: {"status": "VISIBLE", "checks": checks} for model in script.MODELS},
    }
    inventory = SimpleNamespace(collect_inventory=lambda connection, database: report)
    connection = Mock()
    connection.scalar.side_effect = [1 if problem == "trigger" else 0, 5 if problem == "extra_fk" else 4]
    inspector = Mock()

    def columns(name, schema):
        values = [{"name": column.name} for column in script.Base.metadata.tables[name].columns]
        if problem in ("identity", "computed"):
            values[0][problem] = {"unexpected": True}
        if problem == "extra_column":
            values.append({"name": "unexpected"})
        return values

    inspector.get_columns.side_effect = columns
    monkeypatch.setattr(script, "inspect", lambda connection: inspector)
    with pytest.raises(script.SafetyStop):
        script._historical_preflight_003(connection, inventory)


def test_retired_protocol_never_queries_database(script):
    connection, inventory = Mock(), Mock()
    with pytest.raises(script.SafetyStop, match="Retired"):
        script.preflight(connection, inventory)
    assert not connection.mock_calls and not inventory.mock_calls


def valid_operations():
    return {"inserted": 10, "selected_tables": 8, "updated_tables": 4, "deleted_synthetic_drafts": 1, "concurrency_counters_verified": True}


def test_read_only_result_never_claims_write_success(script, monkeypatch):
    setup_worker(script, monkeypatch)
    writer = Mock(side_effect=AssertionError("No writes in read-only mode"))
    monkeypatch.setattr(script, "transactional_test", writer)
    report = script.run_worker(worker_args(execute=False))
    assert report["mode"] == "READ_ONLY_ABSENCE_VERIFICATION"
    assert report["verification"] == "ABSENCE_VERIFIED"
    assert "operations" not in report
    assert script.successful_report(report, execute=False)
    assert not script.successful_report(report, execute=True)
    writer.assert_not_called()


@pytest.mark.parametrize("field", list(valid_operations()))
@pytest.mark.parametrize("variant", ["missing", "incorrect"])
def test_missing_or_incorrect_operations_fail_after_cleanup(script, monkeypatch, field, variant):
    setup_worker(script, monkeypatch)
    operations = valid_operations()
    if variant == "missing":
        del operations[field]
    else:
        operations[field] = False if field == "concurrency_counters_verified" else 999
    monkeypatch.setattr(script, "transactional_test", Mock(return_value=operations))
    report = script.run_worker(worker_args())
    assert report["verification"] == "FAILED"
    assert report["cleanup_status"] == "VERIFIED_ABSENT_ON_NEW_CONNECTION"
    assert not script.successful_report(report, execute=True)


@pytest.mark.parametrize(
    "operations",
    [None, {}, {**valid_operations(), "deleted_synthetic_drafts": True}, {**valid_operations(), "concurrency_counters_verified": 1}],
)
def test_invalid_operation_types_are_not_accepted(script, monkeypatch, operations):
    setup_worker(script, monkeypatch)
    monkeypatch.setattr(script, "transactional_test", Mock(return_value=operations))
    report = script.run_worker(worker_args())
    assert report["verification"] == "FAILED"


@pytest.mark.parametrize("execute", [True, False])
def test_residual_records_fail_in_both_modes(script, monkeypatch, execute):
    setup_worker(script, monkeypatch, absent=False)
    writer = Mock(return_value=valid_operations())
    monkeypatch.setattr(script, "transactional_test", writer)
    report = script.run_worker(worker_args(execute=execute))
    assert report["verification"] == "FAILED"
    assert not script.successful_report(report, execute=execute)


def test_commit_event_does_not_intercept_rollback_dispatch(script):
    from sqlalchemy import create_engine

    engine = create_engine("sqlite://")  # Engine construction only; never connect.
    connection = Mock()
    rollback = Mock()
    event.listen(engine, "commit", script.forbid_commit)
    event.listen(engine, "rollback", rollback)
    with pytest.raises(script.SafetyStop):
        engine.dispatch.commit(connection)
    engine.dispatch.rollback(connection)
    rollback.assert_called_once_with(connection)
    engine.dispose()


@pytest.mark.parametrize("execute", [True, False])
def test_parent_rejects_cross_mode_worker_success(script, monkeypatch, capsys, execute):
    import json

    report = {
        "mode": "READ_ONLY_ABSENCE_VERIFICATION",
        "verification": "ABSENCE_VERIFIED",
        "cleanup_status": "VERIFIED_ABSENT_ON_NEW_CONNECTION",
        "remaining_synthetic_records": {model.__tablename__: 0 for model in script.MODELS},
    }
    if not execute:
        report.update(mode="ORM_WRITE_TEST", verification="WRITE_TEST_PASSED", operations=valid_operations())
    runner = Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps(report)))
    monkeypatch.setattr(script.subprocess, "run", runner)
    flag = "--execute-approved-write-test" if execute else "--verify-only"
    monkeypatch.setattr("sys.argv", ["test_azure_sql_writes.py", flag, "--run-id", worker_args().run_id])
    assert script.main() == 2
    assert json.loads(capsys.readouterr().out)["verification"] == "FAILED"
    runner.assert_called_once()


@pytest.mark.parametrize("problem", ["operation", "cleanup", "residual", "missing_table"])
def test_parent_rechecks_write_acceptance(script, monkeypatch, capsys, problem):
    import json

    report = {
        "mode": "ORM_WRITE_TEST",
        "verification": "WRITE_TEST_PASSED",
        "operations": valid_operations(),
        "cleanup_status": "VERIFIED_ABSENT_ON_NEW_CONNECTION",
        "remaining_synthetic_records": {model.__tablename__: 0 for model in script.MODELS},
    }
    if problem == "operation":
        del report["operations"]["inserted"]
    elif problem == "cleanup":
        report["cleanup_status"] = "UNKNOWN_NOT_VERIFIED"
    elif problem == "residual":
        report["remaining_synthetic_records"]["policies"] = 1
    else:
        del report["remaining_synthetic_records"]["policies"]
    monkeypatch.setattr(script.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps(report))))
    monkeypatch.setattr("sys.argv", ["test_azure_sql_writes.py", "--execute-approved-write-test", "--run-id", worker_args().run_id])
    assert script.main() == 2
    assert json.loads(capsys.readouterr().out)["verification"] == "FAILED"


def test_real_transaction_rollback_and_read_only_with_mock_dbapi(script):
    # Real SQLAlchemy engine/transaction machinery over a fake DBAPI; no database exists.
    from sqlalchemy import text
    from sqlalchemy.engine import Engine, URL
    from sqlalchemy.engine.default import DefaultDialect
    from sqlalchemy.pool import StaticPool

    native = MagicMock()
    native.cursor.return_value.description = [("value", None, None, None, None, None, None)]
    native.cursor.return_value.fetchone.return_value = (1,)
    engine = Engine(StaticPool(lambda: native), DefaultDialect(), URL.create("mock"))
    event.listen(engine, "commit", script.forbid_commit)
    with engine.connect() as connection:
        transaction = connection.begin()
        assert connection.scalar(text("SELECT 1")) == 1
        transaction.rollback()
    native.rollback.assert_called()
    native.commit.assert_not_called()
    engine.dispose()


@pytest.mark.parametrize("execute", [True, False])
def test_timeout_result_is_mode_specific_and_unverified(script, monkeypatch, capsys, execute):
    import json

    runner = Mock(side_effect=script.subprocess.TimeoutExpired("worker", 15))
    monkeypatch.setattr(script.subprocess, "run", runner)
    flag = "--execute-approved-write-test" if execute else "--verify-only"
    monkeypatch.setattr("sys.argv", ["test_azure_sql_writes.py", flag, "--run-id", worker_args().run_id])
    assert script.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["verification"] == "FAILED"
    assert report["cleanup_status"] == "UNKNOWN_NOT_VERIFIED"
    assert report["mode"] == ("ORM_WRITE_TEST" if execute else "READ_ONLY_ABSENCE_VERIFICATION")
    assert not script.successful_report(report, execute)
    runner.assert_called_once()
