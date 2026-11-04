"""Real HTTP/SQL recovery tests on disposable data; every external operation is mocked."""

import asyncio
import hashlib
from unittest.mock import Mock, AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.exc import OperationalError
from app import main, providers, exports, usage
from app.config import settings
from app.models import DemoSession, ExportJob, InferenceUsage, Execution
from app.security import Identity
from test_governance import activate


def session_for(client):
    dependency = main.app.dependency_overrides[main.get_database]()
    return dependency, next(dependency)


@pytest.mark.parametrize("text", ["", " ", "\n\t", True, 1, [], {}])
def test_strict_prompt_validation(client, text):
    assert client.post("/api/governance/generate", json={"text": text}).status_code == 422


@pytest.mark.parametrize("rating", [True, False, "5", 0, 6, 1.5, None])
def test_strict_feedback_validation(client, rating):
    assert client.post("/api/feedback", json={"execution_id": "synthetic", "rating": rating}).status_code == 422


@pytest.mark.parametrize("name", [" ", "\t", "\n", True, 9])
def test_strict_policy_name(client, name):
    assert client.post("/api/policies", json={"name": name}).status_code == 422


def test_malformed_and_oversized_payload(client):
    assert client.post("/api/policies", content="{broken", headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/api/policies", content="x" * 65000).status_code == 413
    assert client.post("/api/policies", json={"name": "Valid", "rules": {"pii_detection": {"enabled": "true"}}}).status_code == 422


def test_expiring_demo_login_logout_and_revocation(client):
    response = client.post("/api/auth/session")
    assert response.status_code == 201
    token = response.json()["access_token"]
    digest = hashlib.sha256(token.encode()).hexdigest()
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/settings").status_code == 200
    assert client.post("/api/auth/session").status_code == 409
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/settings").status_code == 401
    client.headers["Authorization"] = "Bearer admin"
    token = client.post("/api/auth/session").json()["access_token"]
    dependency, db = session_for(client)
    try:
        expired_digest = hashlib.sha256(token.encode()).hexdigest()
        db.execute(update(DemoSession).where(DemoSession.id == expired_digest).values(expires="2000-01-01T00:00:00+00:00"))
        db.commit()
        assert db.get(DemoSession, digest).revoked == 1
    finally:
        dependency.close()
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/settings").status_code == 401


def test_admin_revokes_session_and_foreign_cannot(client):
    token = client.post("/api/auth/session").json()["access_token"]
    identifier = hashlib.sha256(token.encode()).hexdigest()
    client.headers["Authorization"] = "Bearer foreign"
    assert client.post(f"/api/auth/sessions/{identifier}/revoke").status_code == 404
    client.headers["Authorization"] = "Bearer developer"
    assert client.post(f"/api/auth/sessions/{identifier}/revoke").status_code == 403
    client.headers["Authorization"] = "Bearer admin"
    assert client.post(f"/api/auth/sessions/{identifier}/revoke").status_code == 200
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/policies").status_code == 401


def test_credential_removal_invalidates_sessions(client, monkeypatch):
    token = client.post("/api/auth/session").json()["access_token"]
    monkeypatch.setattr(settings, "demo_accounts_json", "[]")
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/settings").status_code == 401


@pytest.mark.parametrize("token", ["", "forged.jwt.signature", "unknown"])
def test_invalid_credentials(client, token):
    assert client.post("/api/auth/session", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("setting", ["inference_user_per_minute", "inference_tenant_per_minute", "inference_daily_quota"])
def test_quota_exhaustion_prevents_provider(client, monkeypatch, setting):
    activate(client)
    monkeypatch.setattr(settings, setting, 1)
    provider = AsyncMock(return_value="Safe answer")
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    assert client.post("/api/governance/generate", json={"text": "safe"}).status_code == 200
    response = client.post("/api/governance/generate", json={"text": "safe"})
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    provider.assert_awaited_once()
    summary = client.get("/api/usage").json()
    assert summary["reserved_today"] == 1


def test_concurrency_lease_and_recovery(client, monkeypatch):
    monkeypatch.setattr(settings, "inference_concurrency", 1)
    dependency, db = session_for(client)
    try:
        user = Identity("admin", "one", "Admin")
        identifier = usage.reserve(db, user)
        with pytest.raises(HTTPException) as caught:
            usage.reserve(db, user)
        assert caught.value.status_code == 429
        db.execute(update(InferenceUsage).where(InferenceUsage.id == identifier).values(expires="2000-01-01T00:00:00+00:00"))
        db.commit()
        assert usage.reserve(db, user) != identifier
    finally:
        dependency.close()


@pytest.mark.asyncio
async def test_total_request_deadline_no_release(client, monkeypatch):
    activate(client)
    monkeypatch.setattr(settings, "inference_deadline", 0.01)

    async def delayed(_):
        await asyncio.sleep(0.2)
        return "Must never release"

    monkeypatch.setattr(providers, "generate_ai_response", delayed)
    response = client.post("/api/governance/generate", json={"text": "safe"})
    assert response.status_code == 504 and "Must never" not in response.text
    dependency, db = session_for(client)
    try:
        assert db.scalar(select(InferenceUsage.status)) == "FAILED"
        assert db.scalar(select(func.count()).select_from(Execution)) == 0
    finally:
        dependency.close()


def test_export_idempotency_and_tenant_scope(client, monkeypatch):
    upload = Mock()
    monkeypatch.setattr(providers, "upload_report", upload)
    payload = {"format": "json", "idempotency_key": "request-example-1"}
    first = client.post("/api/reports/export", json=payload)
    assert first.status_code == 201 and first.json()["state"] == "COMPLETED"
    assert client.post("/api/reports/export", json=payload).json()["id"] == first.json()["id"]
    assert client.post("/api/reports/export", json={**payload, "format": "csv"}).status_code == 409
    upload.assert_called_once()
    client.headers["Authorization"] = "Bearer foreign"
    assert client.post(f"/api/reports/exports/{first.json()['id']}/reconcile").status_code == 404


def test_export_failed_retry_checks_storage_and_is_bounded(client, monkeypatch):
    upload = Mock(side_effect=providers.ProviderUnavailable())
    monkeypatch.setattr(providers, "upload_report", upload)
    monkeypatch.setattr(providers, "report_digest", Mock(return_value=None))
    report = client.post("/api/reports/export", json={}).json()
    assert report["state"] == "FAILED"
    for _ in range(4):
        report = client.post(f"/api/reports/exports/{report['id']}/reconcile").json()
    assert upload.call_count == settings.export_max_attempts
    assert report["error_code"] == "EXPORT_ATTEMPT_LIMIT"


def test_database_failure_after_upload_is_recoverable(client, monkeypatch):
    dependency, db = session_for(client)
    stored = {}
    monkeypatch.setattr(
        providers, "upload_report", lambda path, content: stored.update({path: hashlib.sha256(content.encode()).hexdigest()})
    )
    real_commit = db.commit
    count = 0

    def fail_final_commit():
        nonlocal count
        count += 1
        if count == 3:
            raise OperationalError("synthetic", {}, Exception("synthetic"))
        real_commit()

    monkeypatch.setattr(db, "commit", fail_final_commit)
    try:
        with pytest.raises(OperationalError):
            exports.create(db, Identity("admin", "one", "Admin"), main.ExportRequest(idempotency_key="crash-example-1"))
        db.rollback()
        job = db.scalar(select(ExportJob))
        assert job.state == "UPLOADING" and stored
        identifier = job.id
        db.execute(update(ExportJob).where(ExportJob.id == identifier).values(lease_until="2000-01-01T00:00:00+00:00"))
        real_commit()
    finally:
        dependency.close()
    monkeypatch.setattr(providers, "report_digest", lambda path, _: stored.get(path))
    upload = Mock(side_effect=AssertionError("Must not upload the same object again"))
    monkeypatch.setattr(providers, "upload_report", upload)
    response = client.post(f"/api/reports/exports/{identifier}/reconcile")
    assert response.status_code == 200 and response.json()["state"] == "COMPLETED"
    upload.assert_not_called()


def test_crash_before_upload_and_active_claim(client, monkeypatch):
    dependency, db = session_for(client)
    monkeypatch.setattr(providers, "upload_report", Mock(side_effect=SystemExit("simulated process interruption")))
    try:
        with pytest.raises(SystemExit):
            exports.create(db, Identity("admin", "one", "Admin"), main.ExportRequest())
        db.rollback()
        job = db.scalar(select(ExportJob))
        identifier = job.id
        assert job.state == "UPLOADING"
        with pytest.raises(HTTPException) as error:
            exports.process(db, Identity("admin", "one", "Admin"), identifier)
        assert error.value.status_code == 409
        db.execute(update(ExportJob).where(ExportJob.id == identifier).values(lease_until="2000-01-01T00:00:00+00:00"))
        db.commit()
    finally:
        dependency.close()
    monkeypatch.setattr(providers, "report_digest", Mock(return_value=None))
    upload = Mock()
    monkeypatch.setattr(providers, "upload_report", upload)
    assert client.post(f"/api/reports/exports/{identifier}/reconcile").json()["state"] == "COMPLETED"
    upload.assert_called_once()


def test_reconciliation_refuses_content_mismatch(client, monkeypatch):
    monkeypatch.setattr(providers, "upload_report", Mock(side_effect=providers.ProviderUnavailable()))
    report = client.post("/api/reports/export", json={}).json()
    monkeypatch.setattr(providers, "report_digest", Mock(return_value="incorrect-checksum"))
    upload = Mock()
    monkeypatch.setattr(providers, "upload_report", upload)
    response = client.post(f"/api/reports/exports/{report['id']}/reconcile")
    assert response.json()["error_code"] == "EXPORT_CONTENT_MISMATCH"
    upload.assert_not_called()


def test_export_size_and_dates(client, monkeypatch):
    activate(client)
    for _ in range(2):
        client.post("/api/governance/generate", json={"text": "safe"})
    monkeypatch.setattr(settings, "export_max_records", 1)
    upload = Mock()
    monkeypatch.setattr(providers, "upload_report", upload)
    assert client.post("/api/reports/export", json={}).status_code == 413
    for payload in ({"start_date": "2026-02-30"}, {"start_date": "2020-01-01", "end_date": "2026-01-01"}):
        assert client.post("/api/reports/export", json=payload).status_code == 422
    upload.assert_not_called()


def test_server_search_filters_and_literal_sql_injection(client):
    for index in range(24):
        client.post("/api/policies", json={"name": f"Policy {index:02}"})
    assert len(client.get("/api/policies?limit=20").json()) == 20
    results = client.get("/api/policies", params={"search": "Policy 00", "limit": 1}).json()
    assert len(results) == 1 and results[0]["name"] == "Policy 00"
    assert client.get("/api/policies", params={"search": "%' OR 1=1 --"}).json() == []
    identifier = results[0]["id"]
    client.post(f"/api/policies/{identifier}/disable")
    assert len(client.get("/api/policies?enabled=false").json()) == 1
    assert client.get("/api/policies?status=invalid").status_code == 422


def test_policy_rejection_and_rollback_reapproval(client):
    identifier, _ = activate(client)
    original = client.get(f"/api/policies/{identifier}/versions").json()[0]
    client.put(
        f"/api/policies/{identifier}",
        json={"name": "Edited"},
        headers={"If-Match": str(client.get(f"/api/policies/{identifier}").json()["row_version"])},
    )
    client.post(f"/api/policies/{identifier}/submit")
    assert client.post(f"/api/policies/{identifier}/reject").json()["status"] == "DRAFT"
    restored = client.post(f"/api/policies/{identifier}/rollback", json={"version": 1})
    assert restored.json()["status"] == "DRAFT"
    assert client.post(f"/api/policies/{identifier}/activate").status_code == 409
    assert client.get(f"/api/policies/{identifier}/versions").json()[0] == original
    client.headers["Authorization"] = "Bearer foreign"
    assert client.post(f"/api/policies/{identifier}/rollback", json={"version": 1}).status_code == 404


def test_review_assignment_history_and_no_release(client):
    activate(client, {"blocked_keywords": "HUMAN_REVIEW"})
    review = client.post("/api/governance/generate", json={"text": "internal-only"}).json()
    identifier = review["review_id"]
    assert (
        client.put(
            f"/api/reviews/{identifier}/assignment", json={"assigned_reviewer": "reviewer", "reason": "Synthetic policy decision"}
        ).status_code
        == 200
    )
    client.headers["Authorization"] = "Bearer reviewer"
    resolved = client.post(f"/api/reviews/{identifier}/approve", json={"reason": "Revise and resubmit"})
    assert resolved.json()["status"] == "APPROVED_RESUBMIT_REQUIRED" and "safe_response" not in resolved.json()
    detail = client.get(f"/api/reviews/{identifier}").json()
    assert [item["action"] for item in detail["decision_history"]] == ["assigned", "approve"]
    assert detail["assignment"]["assigned_reviewer"] == "reviewer"


def test_security_headers_and_correlation(client):
    response = client.get("/api/settings", headers={"X-Request-ID": "synthetic-correlation-1"})
    assert response.headers["X-Request-ID"] == "synthetic-correlation-1"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_stale_export_owner_cannot_finalize_new_lease(client, monkeypatch):
    dependency, db = session_for(client)

    def takeover(path, content):
        db.execute(update(ExportJob).values(lease_until="2099-01-01T00:00:00+00:00"))
        db.commit()

    monkeypatch.setattr(providers, "upload_report", takeover)
    try:
        with pytest.raises(HTTPException) as captured:
            exports.create(db, Identity("admin", "one", "Admin"), main.ExportRequest())
        assert captured.value.status_code == 409
        db.rollback()
        assert db.scalar(select(ExportJob.state)) == "UPLOADING"
    finally:
        dependency.close()


def test_linked_resubmission_is_scoped_and_reinspected(client):
    activate(client, {"blocked_keywords": "HUMAN_REVIEW"})
    case = client.post("/api/governance/generate", json={"text": "internal-only"}).json()["review_id"]
    assert client.post("/api/governance/generate", json={"text": "safe", "source_review_id": case}).status_code == 409
    client.post(f"/api/reviews/{case}/approve")
    result = client.post("/api/governance/generate", json={"text": "internal-only", "source_review_id": case}).json()
    assert result["decision"] == "HUMAN_REVIEW" and result["source_review_id"] == case
    safe = client.post("/api/governance/generate", json={"text": "revised safe text", "source_review_id": case}).json()
    assert safe["decision"] == "ALLOW" and safe["source_review_id"] == case


def test_reassignment_invalidates_stale_reviewer_disposition(client):
    from sqlalchemy.orm import Session
    from sqlalchemy.orm.exc import StaleDataError
    from app.models import Review

    activate(client, {"blocked_keywords": "HUMAN_REVIEW"})
    identifier = client.post("/api/governance/generate", json={"text": "internal-only"}).json()["review_id"]
    dependency, db = session_for(client)
    try:
        with Session(db.bind) as stale:
            review = stale.get(Review, identifier)
            assert client.put(f"/api/reviews/{identifier}/assignment", json={"assigned_reviewer": "reviewer"}).status_code == 200
            review.status = "REJECTED"
            with pytest.raises(StaleDataError):
                stale.commit()
    finally:
        dependency.close()
