"""Dashboard aggregation uses only stored request metadata."""

import json
from types import SimpleNamespace

from app.services.dashboard_findings import aggregate


def row(metadata, day="2026-11-10"):
    return SimpleNamespace(metadata_json=json.dumps(metadata), created=day + "T12:00:00")


def policy(status, finding=True):
    return {"local": {"breakdown": {"pii_detection": status},
                      "findings": [{"category": "pii_detection", "count": 1, "action": "BLOCK"}] if finding else []},
            "moderation": {"status": "NOT_APPLICABLE"}}


def test_multi_policy_duplicate_findings_count_once_and_block_is_not_failure():
    result = aggregate([row({"input": {"policies": [policy("FAILED"), policy("FAILED")]}, "decision": "BLOCK"})])
    assert result["score"] == 100
    assert result["violations"]["pii_detection"] == 1
    assert result["trends"] == [{"date": "2026-11-10", "score": 100.0}]


def test_incomplete_evidence_lowers_coverage_and_unknown_is_not_a_finding():
    result = aggregate([row({"input": {"policies": [policy("FAILED"), policy("UNKNOWN", False)]}})])
    assert result["score"] == 0
    assert result["incomplete_inspections"] >= 1
    assert result["violations"]["pii_detection"] == 1


def test_empty_and_missing_evidence_are_insufficient():
    assert aggregate([])["score"] is None
    result = aggregate([row({"decision": "BLOCK"})])
    assert result["score"] is None
    assert not result["findings_available"]
    assert all(value == 0 for value in result["violations"].values())
    assert aggregate([row({"input": {"policies": [policy("UNKNOWN", False)]}})])["score"] is None


def test_input_and_output_are_separate_findings_and_window_rows_only():
    result = aggregate([row({"input": {"policies": [policy("FAILED")]},
                             "output": {"policies": [policy("FAILED")]}})])
    assert result["violations"]["pii_detection"] == 2


def test_multiple_requests_pool_applicable_weights():
    result = aggregate([row({"input": {"breakdown": {"secret_detection": "SATISFIED"}}}),
                        row({"input": {"breakdown": {"pii_detection": "UNKNOWN"}}})])
    assert result["score"] == round(100 * 30 / 55, 2)


def test_failed_control_without_confirming_finding_is_unavailable():
    result = aggregate([row({"input": {"policies": [policy("FAILED", False)]}})])
    assert result["score"] == 100
    assert result["violations"]["pii_detection"] == 0
    assert result["findings_available"] is False
