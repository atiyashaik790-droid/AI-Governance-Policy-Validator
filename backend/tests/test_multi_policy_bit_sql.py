"""Actual MSSQL compilation of statements used by MULTI transitions; local DB only."""
import json
import re
from types import SimpleNamespace

import pytest
from sqlalchemy import event, select
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models_multi_policy import WorkspacePolicyAssignment as Pin
from test_multi_policy_bridge import bridge  # noqa: F401
from test_multi_policy_phase_b import engine006, templates, legacy  # noqa: F401


def test_old_bit_predicate_reproduces_invalid_mssql_syntax():
    sql = str(select(Pin).where(Pin.active.is_(True)).compile(dialect=mssql.dialect()))
    assert "workspace_policy_assignments.active IS 1" in sql


def test_seeded_multi_transition_capture_count_and_list_emit_bit_equality(bridge, engine006):  # noqa: F811
    with Session(engine006) as db:
        policy, version = legacy(db)
        pid = policy.id
    statements = []

    def verify_sql(connection, clause, multiparams, params, options):
        sql = str(clause.compile(dialect=mssql.dialect()))
        assert not re.search(r"\.active IS (?:1|0)\b", sql), sql
        if "workspace_policy_assignments.active = 1" in sql:
            statements.append(sql)

    event.listen(engine006, "before_execute", verify_sql)
    try:
        initial = bridge.get("/api/v2/workspace/policy-state")
        changed = bridge.put("/api/v2/workspace/policy-mode", headers={"If-Match": initial.headers["etag"]},
                             json={"mode": "MULTI", "seed_legacy_assignment": True})
        assert changed.status_code == 200, changed.text
        current = bridge.get("/api/v2/workspace/policy-state")
        assert current.status_code == 200 and current.json()["active_policy_count"] == 1
        listing = bridge.get("/api/policies")
        assert listing.status_code == 200 and any(row["id"] == pid and row["is_active"] for row in listing.json())
        generated = bridge.post("/api/v2/governance/generate", headers={"If-Match": current.headers["etag"]}, json={"text": "Explain governance"})
        assert generated.status_code == 200 and generated.json()["decision"] == "ALLOW", generated.text
        assert len(statements) >= 4  # transition, active count, list, admission capture
    finally:
        event.remove(engine006, "before_execute", verify_sql)


@pytest.mark.asyncio
async def test_database_failure_logs_only_sanitized_code_and_keeps_public_503(monkeypatch):
    from app.exception_handlers import database_failure
    from app.middleware import logger

    records = []
    monkeypatch.setattr(logger, "warning", records.append)
    request = Request({"type": "http", "route": SimpleNamespace(path="/api/v2/workspace/policy-mode")})
    error = ProgrammingError("secret SQL text", {"secret": "credential"}, RuntimeError("42000", "secret connection string (102)"))
    response = await database_failure(request, error)
    assert response.status_code == 503
    assert json.loads(response.body) == {"detail": "Database operation unavailable; nothing released"}
    assert len(records) == 1
    diagnostic = json.loads(records[0])
    assert diagnostic["native_code"] == 102 and diagnostic["sqlstate"] == "42000"
    assert diagnostic["event"] == "database.failed"
    assert "secret" not in records[0] and "credential" not in records[0]
