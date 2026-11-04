"""Regressions for reproduced audit defects; only disposable stores and synthetic content."""

import asyncio
import time
from unittest.mock import AsyncMock
import httpx
import pytest
from app import engine, providers
from app.config import settings
from app.schemas import PolicyDocument


def publish(client, document=None):
    document = document or PolicyDocument(name="Audit regression").model_dump()
    identifier = client.post("/api/policies", json=document).json()["id"]
    for action in ("submit", "approve", "publish", "activate"):
        assert client.post(f"/api/policies/{identifier}/{action}").status_code == 200
    return identifier


def test_stale_editor_cannot_overwrite_committed_edit(client):
    identifier = publish(client)
    path = f"/api/policies/{identifier}"
    version = client.get(path).json()["row_version"]
    newer = {"name": "Newer policy"}
    assert client.put(path, json=newer).status_code == 428
    assert client.put(path, json=newer, headers={"If-Match": f'"{version}"'}).status_code == 200
    assert client.put(path, json={"name": "Stale policy"}, headers={"If-Match": str(version)}).status_code == 412
    assert client.get(path).json()["name"] == "Newer policy"


def test_input_failure_survives_clean_output_in_analytics(client):
    publish(client)
    response = client.post("/api/governance/generate", json={"text": "Contact synthetic.person@example.com"})
    assert response.json()["decision"] == "REDACT"
    summary = client.get("/api/analytics/overview").json()
    assert summary["violations"]["pii_detection"] == 1
    assert summary["contributions"].get("pii_detection", 0) == 0
    assert summary["trends"][0]["score"] == response.json()["input"]["score"]


def test_reviewer_cannot_steal_assigned_case(client):
    document = PolicyDocument(name="Assigned review").model_dump()
    document["rules"]["blocked_keywords"]["action"] = "HUMAN_REVIEW"
    publish(client, document)
    case = client.post("/api/governance/generate", json={"text": "internal-only"}).json()["review_id"]
    path = f"/api/reviews/{case}"
    assert client.put(path + "/assignment", json={"assigned_reviewer": "admin"}).status_code == 200
    client.headers["Authorization"] = "Bearer reviewer"
    assert client.put(path + "/assignment", json={"assigned_reviewer": "reviewer"}).status_code == 403
    assert client.post(path + "/approve").status_code == 403


def test_default_root_credentials_only_exchange_for_session(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_legacy_api_credentials", False)
    assert client.get("/api/settings").status_code == 401
    token = client.post("/api/auth/session").json()["access_token"]
    client.headers["Authorization"] = "Bearer " + token
    assert client.get("/api/settings").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/settings").status_code == 401


@pytest.mark.parametrize(
    "category,text",
    [
        ("secret_detection", "s\u200bk-synthetic012345678901234567890"),
        ("blocked_keywords", "inter\u200bnal-only"),
    ],
)
def test_unicode_obfuscation_detected_and_redacted_in_source_positions(category, text):
    policy = PolicyDocument(name="Normalized detection")
    spans = engine.detect_sensitive_information(text, category, policy)
    assert spans
    assert engine.redact_personal_information(text, spans) == "[REDACTED]"


def test_slow_detector_times_out_without_content_release(client, monkeypatch):
    document = PolicyDocument(name="Deadline").model_dump()
    document["rules"]["moderation"]["enabled"] = False
    publish(client, document)
    original = engine.detect_sensitive_information

    def slow(*args):
        time.sleep(0.08)
        return original(*args)

    monkeypatch.setattr(engine, "detect_sensitive_information", slow)
    monkeypatch.setattr(settings, "inference_deadline", 0.01)
    response = client.post("/api/governance/validate-input", json={"text": "Synthetic safe text"})
    assert response.status_code == 504
    assert "safe_text" not in response.text
    assert client.get("/api/audit/executions").json() == []


@pytest.mark.asyncio
async def test_inspection_yields_during_blocking_detection(monkeypatch):
    policy = PolicyDocument(name="Responsive event loop")
    policy.rules.moderation.enabled = False
    monkeypatch.setattr(engine, "detect_sensitive_information", lambda *_: (time.sleep(0.06), [])[1])
    task = asyncio.create_task(engine.inspect_text("safe", policy))
    await asyncio.sleep(0.01)
    assert not task.done()
    assert (await task)["decision"] == "ALLOW"


def test_review_reason_redacts_sensitive_metadata(client):
    document = PolicyDocument(name="Metadata").model_dump()
    document["rules"]["blocked_keywords"]["action"] = "HUMAN_REVIEW"
    publish(client, document)
    case = client.post("/api/governance/generate", json={"text": "internal-only"}).json()["review_id"]
    path = f"/api/reviews/{case}"
    assert client.post(path + "/approve", json={"reason": "Contact person@example.com"}).status_code == 200
    detail = client.get(path)
    assert "person@example.com" not in detail.text
    assert "[REDACTED]" in detail.text


@pytest.mark.asyncio
async def test_unknown_flagged_moderation_category_fails_closed(monkeypatch):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = httpx.Response(
        200, json={"results": [{"flagged": True, "categories": {"unknown": True}}]}, request=httpx.Request("POST", "https://api.openai.com")
    )
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **_: client)
    monkeypatch.setattr(settings, "provider_mode", "live")
    monkeypatch.setattr(settings, "openai_api_key", "synthetic")
    with pytest.raises(providers.ProviderUnavailable):
        await providers.moderate_user_prompt("synthetic", ["hate"])


def test_duplicate_actor_feedback_does_not_change_aggregate(client):
    publish(client)
    execution = client.post("/api/governance/generate", json={"text": "Safe synthetic prompt"}).json()["request_id"]
    assert client.post("/api/feedback", json={"execution_id": execution, "rating": 1}).status_code == 201
    assert client.post("/api/feedback", json={"execution_id": execution, "rating": 5}).status_code == 409
    assert client.get("/api/feedback/summary").json() == {"count": 1, "average": 1.0}
    client.headers["Authorization"] = "Bearer developer"
    assert client.post("/api/feedback", json={"execution_id": execution, "rating": 5}).status_code == 201
    assert client.get("/api/feedback/summary").json() == {"count": 2, "average": 3.0}


def test_session_creation_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "session_per_minute", 1)
    assert client.post("/api/auth/session").status_code == 201
    response = client.post("/api/auth/session")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


def test_author_can_track_own_review_without_reviewer_privileges(client):
    document = PolicyDocument(name="Author review").model_dump()
    document["rules"]["blocked_keywords"]["action"] = "HUMAN_REVIEW"
    publish(client, document)
    client.headers["Authorization"] = "Bearer developer"
    review = client.post("/api/governance/generate", json={"text": "internal-only"}).json()["review_id"]
    assert client.get(f"/api/reviews/{review}").status_code == 200
    assert len(client.get("/api/reviews").json()) == 1
    assert client.post(f"/api/reviews/{review}/approve").status_code == 403
    client.headers["Authorization"] = "Bearer admin"
    assert client.post(f"/api/reviews/{review}/approve").status_code == 200
    client.headers["Authorization"] = "Bearer developer"
    response = client.post("/api/governance/generate", json={"text": "Revised safe text", "source_review_id": review})
    assert response.status_code == 200 and response.json()["decision"] == "ALLOW"


def test_maintenance_preserves_business_history_and_feedback_markers(client):
    from app import main
    from app.models import RateBucket, DemoSession, Audit, InferenceUsage
    from app.maintenance import apply_bookkeeping
    from sqlalchemy import select

    dependency = main.app.dependency_overrides[main.get_database]()
    db = next(dependency)
    try:
        db.add_all(
            [
                RateBucket(id="expired", used=1, expires="2000-01-01"),
                RateBucket(id="permanent-feedback", used=1, expires="9999-12-31"),
                RateBucket(id="concurrency-gate", used=0, expires="2000-01-01"),
                DemoSession(
                    id="expired-session", tenant="one", actor="admin", role="Admin", credential_hash="synthetic", expires="2000-01-01"
                ),
                InferenceUsage(tenant="one", actor="admin", expires="2000-01-01"),
                Audit(tenant="one", actor="admin", action="preserve", resource="synthetic"),
            ]
        )
        db.commit()
        result = apply_bookkeeping(db)
        assert result["sessions_removed"] == 1 and result["rate_buckets_removed"] == 1
        assert result["leases_expired"] == 1
        assert db.get(RateBucket, "permanent-feedback") and db.get(RateBucket, "concurrency-gate")
        assert db.scalar(select(Audit.action)) == "preserve"
    finally:
        dependency.close()


def test_capabilities_and_maintenance_are_scoped(client):
    assert "EMAIL_ADDRESS" in client.get("/api/capabilities").json()["available_pii_entities"]
    assert client.get("/api/maintenance").json()["mode"] == "READ_ONLY_PLAN"
    client.headers["Authorization"] = "Bearer developer"
    assert client.get("/api/maintenance").status_code == 403


@pytest.mark.asyncio
async def test_missing_selected_moderation_category_fails_closed(monkeypatch):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = httpx.Response(
        200,
        json={"results": [{"flagged": False, "categories": {"violence": False}}]},
        request=httpx.Request("POST", "https://api.openai.com"),
    )
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **_: client)
    monkeypatch.setattr(settings, "provider_mode", "live")
    monkeypatch.setattr(settings, "openai_api_key", "synthetic")
    policy = PolicyDocument(name="Selected moderation", rules={"moderation": {"categories": ["hate"]}})
    result = await engine.inspect_text("Ordinary safe prose", policy)
    assert result["decision"] == "BLOCK" and result["breakdown"]["moderation"] == "UNKNOWN"


def test_unavailable_pii_entity_cannot_be_submitted(client):
    document = PolicyDocument(name="Unavailable recognizer", rules={"pii_detection": {"entities": ["PERSON"]}}).model_dump()
    identifier = client.post("/api/policies", json=document).json()["id"]
    assert client.post(f"/api/policies/{identifier}/submit").status_code == 422
    assert client.get(f"/api/policies/{identifier}").json()["status"] == "DRAFT"


def test_usage_separates_expired_and_active_leases_without_expression_grouping(client):
    from app import main, usage
    from app.models import InferenceUsage
    from app.security import Identity

    dependency = main.app.dependency_overrides[main.get_database]()
    db = next(dependency)
    try:
        db.add_all(
            [
                InferenceUsage(tenant="one", actor="admin", expires="2000-01-01", status="RESERVED"),
                InferenceUsage(tenant="one", actor="admin", expires="9999-01-01", status="RESERVED"),
                InferenceUsage(tenant="one", actor="admin", expires="2000-01-01", status="EXPIRED"),
                InferenceUsage(tenant="two", actor="foreign", expires="2000-01-01", status="RESERVED"),
            ]
        )
        db.commit()
        result = usage.summary(db, Identity("admin", "one", "Admin"))
        assert result["statuses"] == {"RESERVED": 1, "EXPIRED": 2}
    finally:
        dependency.close()
