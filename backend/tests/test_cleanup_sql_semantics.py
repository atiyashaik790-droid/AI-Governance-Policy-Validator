"""Guarded SQL latency/ODBC contracts locally; not an Azure execution claim."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session

from app import protected_reviews as secure
from app.models import Audit, Execution, Policy, Review
from app.models_review_content import ProtectedReviewContent as Content
import test_execution_008_application as application008
import test_protected_reviews as reviews

protected = application008.protected
template007 = application008.template007


def seed(factory, expiries):
    reviews.install(factory)
    ids = []
    with factory() as db:
        policy = db.scalar(select(Policy))
        for tenant, expiry in expiries:
            execution = Execution(tenant=tenant, actor="fixture", policy_id=policy.id, version=1,
                                  model="fixture", decision="HUMAN_REVIEW", metadata_json="{}")
            db.add(execution)
            db.flush()
            review = Review(tenant=tenant, execution_id=execution.id)
            db.add(review)
            db.flush()
            db.add(secure.encrypt_prompt("synthetic expiry", tenant, review.id, execution.id,
                                         expiry - secure.RETENTION))
            ids.append(review.id)
        db.commit()
    return ids


def test_exact_retry8_code_starves_before_delete_and_fixed_worker_progresses(protected, monkeypatch, capsys):
    _, engine, factory = protected
    expired, boundary, unexpired = seed(factory, [("one", 99), ("two", 100), ("one", 101)])
    elapsed, statements = [0.0], []
    monkeypatch.setattr(secure, "time", SimpleNamespace(monotonic=lambda: elapsed[0]))
    monkeypatch.setattr(secure, "clock", lambda db: 100)

    def guarded_latency(conn, cursor, statement, parameters, context, executemany):
        # Charge guarded SQL round trips without sleeping or pretending this is TDS.
        elapsed[0] += 0.8
        statements.append(statement.split()[0].upper())
    event.listen(engine, "before_cursor_execute", guarded_latency)
    try:
        archive = Path(__file__).resolve().parents[2] / "artifacts/final-demo-readiness-2026-11-07/candidate.zip"
        with zipfile.ZipFile(archive) as z:
            module = ast.parse(z.read("app/protected_reviews.py"))
        old_function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "cleanup_once")
        namespace = dict(vars(secure))
        exec(compile(ast.Module(body=[old_function], type_ignores=[]), "retry8-frozen-cleanup", "exec"), namespace)
        old = namespace["cleanup_once"](engine, factory)
        assert old == {"removed": 0, "healthy": False}
        assert "DELETE" not in statements
        assert not secure.health.healthy(engine)
        # First pass makes real atomic progress; backlog must remain unhealthy.
        fixed = secure.cleanup_once(engine, factory)
        assert fixed == {"removed": 1, "healthy": False}
        assert not secure.health.healthy(engine)
        finished = secure.cleanup_once(engine, factory)
        assert finished == {"removed": 1, "healthy": True}
        assert secure.health.healthy(engine)
    finally:
        event.remove(engine, "before_cursor_execute", guarded_latency)
    with factory() as db:
        assert db.scalar(select(Content.review_id)) == unexpired
        assert set(db.scalars(select(Audit.resource).where(Audit.action == "review.content.expired"))) == {expired, boundary}
    print(json.dumps({"reproduction": "frozen retry8 under guarded latency", "old": old, "fixed": fixed, "finished": finished}))


@pytest.mark.parametrize("failure", ["select", "delete", "audit", "commit"])
def test_failures_rollback_and_clear_health_without_counting_uncommitted_rows(protected, monkeypatch, failure):
    _, engine, factory = protected
    (rid,) = seed(factory, [("one", 99)])
    monkeypatch.setattr(secure, "clock", lambda db: 100)
    commits = Session.commit

    def deny(conn, cursor, statement, parameters, context, executemany):
        text = statement.lower()
        if ((failure == "select" and text.startswith("select") and "review_protected_content" in text)
                or (failure == "delete" and text.startswith("delete"))
                or (failure == "audit" and text.startswith("insert into audit_events"))):
            raise PermissionError("synthetic private error MUST_NOT_LOG")

    def commit(db):
        if failure == "commit":
            raise RuntimeError("synthetic commit denial MUST_NOT_LOG")
        return commits(db)

    event.listen(engine, "before_cursor_execute", deny)
    monkeypatch.setattr(Session, "commit", commit)
    try:
        assert secure.cleanup_once(engine, factory) == {"removed": 0, "healthy": False}
        assert not secure.health.healthy(engine)
    finally:
        event.remove(engine, "before_cursor_execute", deny)
        monkeypatch.setattr(Session, "commit", commits)
    with factory() as db:
        assert db.get(Content, ("one", rid)) is not None
        assert db.scalar(select(Audit.id).where(Audit.action == "review.content.expired")) is None
    assert secure.cleanup_once(engine, factory) == {"removed": 1, "healthy": True}


def test_sql_server_delete_returns_only_identity_with_expiry_and_tenant_fences():
    statement = delete(Content).where(Content.tenant == "one", Content.review_id == "r", Content.expires_at <= 100)
    sql = str(statement.returning(Content.review_id).compile(dialect=mssql.dialect()))
    assert "OUTPUT deleted.review_id" in sql
    assert "tenant =" in sql and "review_id =" in sql and "expires_at <=" in sql
    assert "ciphertext" not in sql and "nonce" not in sql


def test_delete_confirmation_ignores_unknown_odbc_rowcount_and_empty_results():
    class UnknownRowcount:
        rowcount = -1
        def __init__(self, rows):
            self.rows = rows
        def __iter__(self):
            return iter(self.rows)
    for actual in [[], ["r"]]:
        db = SimpleNamespace(scalars=lambda statement: UnknownRowcount(actual))
        assert secure.delete_content(db, Content.tenant == "one") == actual


def test_sql_server_clock_uses_utc_integer_seconds_without_datetime_comparison():
    from datetime import datetime, timezone
    from app.services.policy_sets import database_now
    utc = datetime(2026, 11, 7, 9, 43, 57, 999999)
    statements = []
    def scalar(statement):
        statements.append(str(statement))
        return utc
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="mssql")), scalar=scalar)
    assert database_now(db).tzinfo == timezone.utc
    assert secure.clock(db) == int(utc.replace(tzinfo=timezone.utc).timestamp())
    assert statements == ["SELECT SYSUTCDATETIME()", "SELECT SYSUTCDATETIME()"]


def test_cleanup_diagnostic_exposes_failure_stage_without_sensitive_error(monkeypatch):
    messages = []
    engine = object()
    health = secure.CleanupHealth()
    health.start(engine)
    monkeypatch.setattr(secure, "health", health)
    monkeypatch.setattr(secure.logger, "info", messages.append)
    def denied():
        raise PermissionError("secret token ciphertext MUST_NOT_LOG")
    assert secure.cleanup_once(engine, denied) == {"removed": 0, "healthy": False}
    diagnostic = json.loads(messages[-1])
    assert diagnostic["event"] == "cleanup.pass"
    assert diagnostic["reason"] == "SQL_FAILURE" and diagnostic["stage"] == "schema"
    assert not health.healthy(engine) and health.wait_for_first_pass(engine, 0)
    assert all(value not in messages[-1] for value in ["secret", "token", "ciphertext", "MUST_NOT_LOG"])
