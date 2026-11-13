"""Real 008 HUMAN_REVIEW persistence/deadline and sanitized timing regressions."""
import json
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, text

from app import providers, stage_timing
from app.models import Audit, Execution, Review, InferenceUsage
from app.models_review_content import ProtectedReviewContent
from app.services import governance
import test_execution_008_application as application008
import test_protected_reviews as reviews

protected = application008.protected
template007 = application008.template007


@pytest.fixture
def stage_records():
    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(json.loads(record.getMessage()))
    stage_timing.logger.addHandler(handler)
    try:
        yield records
    finally:
        stage_timing.logger.removeHandler(handler)


def test_capture_over_budget_still_rolls_back_and_withholds(protected, monkeypatch):
    client, _, factory = protected
    reviews.install(factory)
    provider = AsyncMock(side_effect=AssertionError("real provider forbidden"))
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    original = governance.capture
    clock = [time.monotonic()]

    def slow_capture(*args):
        original(*args)
        clock[0] += 91  # Synchronous SQL work crosses unchanged 90-second budget.

    monkeypatch.setattr(governance, "capture", slow_capture)
    monkeypatch.setattr(governance, "time", SimpleNamespace(monotonic=lambda: clock[0], perf_counter=time.perf_counter))
    response = client.post("/api/governance/generate", json={"text": "internal-only synthetic prompt MUST_NOT_LOG"})
    assert response.status_code == 504
    assert response.json() == {"detail": "Governance deadline exceeded; response withheld"}
    provider.assert_not_awaited()
    with factory() as db:
        assert db.scalar(select(Execution)) is None
        assert db.scalar(select(Review)) is None
        assert db.scalar(select(ProtectedReviewContent)) is None
        assert db.scalar(select(Audit).where(Audit.action == "review.content.retained")) is None
        assert db.scalar(select(InferenceUsage.status)) == "FAILED"


def test_stage_diagnostics_are_sanitized_and_observational(protected, stage_records):
    _, _, factory = protected
    secret = "MUST_NOT_LOG prompt key nonce SQL parameter tenant actor"
    token = stage_timing.correlation.set("synthetic-request-123")
    try:
        with factory() as db:
            with pytest.raises(RuntimeError, match="MUST_NOT_LOG"):
                with stage_timing.stage("review.capture", db, deadline=time.monotonic() - 1):
                    assert db.scalar(text("SELECT :secret"), {"secret": secret}) == secret
                    raise RuntimeError(secret)
    finally:
        stage_timing.correlation.reset(token)
    records = stage_records
    record = records[-1]
    assert record["outcome"] == "error" and record["sql_count"] == 1
    assert record["deadline_remaining_ms"] < 0
    assert record["correlation_id"] == "synthetic-request-123"
    assert record["duration_ms"] >= 0 and record["connection_acquire_ms"] >= 0
    assert secret not in json.dumps(records)


def test_successful_review_retains_checks_and_emits_stage_trace(protected, stage_records):
    client, _, factory = protected
    reviews.install(factory)
    result = reviews.submit(client, prompt="internal-only synthetic original MUST_NOT_LOG")
    assert result["decision"] == "HUMAN_REVIEW"
    stages = stage_records
    names = [record["stage"] for record in stages]
    assert names.count("review.schema") == 2  # Preflight AND capture revalidate.
    assert {"authentication", "policy.admission", "inspection", "execution.persistence", "review.persistence", "review.capture", "execution.commit"} <= set(names)
    assert all("MUST_NOT_LOG" not in json.dumps(record) for record in stages)
    with factory() as db:
        row = db.scalar(select(ProtectedReviewContent))
        assert row and b"internal-only" not in row.ciphertext
        assert row.expires_at - row.created_at == 604800
        assert db.scalar(select(Audit).where(Audit.action == "review.content.retained")) is not None
