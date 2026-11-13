"""Static, versioned messages never inspect or interpolate original content."""
import json
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import providers
from app.config import settings
from app.decision_messages import decision_notice
from app.schemas import PolicyDocument
import test_multi_policy_bridge as phase_bridge
import test_multi_policy_phase_b as phase_b
import test_multi_policy_phase_d as phase_d
import test_document_uploads as uploads

templates = phase_b.templates
template010 = phase_b.template010
engine006 = phase_b.engine010
bridge = phase_bridge.bridge


def result(decision="BLOCK", category="pii_detection", **changes):
    return {"decision": decision, "model_invoked": False, "input": {"findings": [{"category": category, "action": decision, "count": 1}]}, **changes}


@pytest.mark.parametrize("category,expected", [("pii_detection", "personal"), ("secret_detection", "secret"),
    ("blocked_keywords", "confidential"), ("moderation", "unsafe"), ("custom:private", "custom"), ("unknown", "generic")])
def test_safe_defaults_do_not_interpolate_evidence(category, expected):
    raw = result(category=category)
    raw["input"]["findings"][0].update(value="SensitiveOriginal", pattern="ConfidentialPattern", text="OriginalUpload")
    notice = decision_notice(raw, {})
    assert notice["category"] == expected and notice["kind"] == "policy"
    assert "cannot be processed" in notice["message"]
    assert all(value not in json.dumps(notice) for value in ["SensitiveOriginal", "ConfidentialPattern", "OriginalUpload"])


@pytest.mark.parametrize("decision", ["BLOCK", "HUMAN_REVIEW", "REDACT", "ALLOW"])
def test_decision_messages_preserve_codes_and_review_contract(decision):
    raw = result(decision)
    notice = decision_notice(raw, {})
    assert raw["decision"] == decision
    if decision == "HUMAN_REVIEW":
        assert "has not been sent" in notice["message"]
        assert "metadata-only" in notice["next_action"] and "resubmit under current policies" in notice["next_action"]
    if decision == "REDACT":
        assert "removed" in notice["message"] and "output governance succeeds" in notice["message"]
    if decision == "ALLOW":
        assert notice["kind"] == "success"


def test_output_review_never_claims_model_was_not_invoked():
    notice = decision_notice(result("HUMAN_REVIEW", model_invoked=True), {})
    assert "was invoked" in notice["message"] and "has not been sent" not in notice["message"]


def test_aggregate_contributor_beats_lower_priority_finding_and_selects_pinned_template():
    doc = PolicyDocument(name="Pinned", decision_messages={"BLOCK": "contact_admin"})
    raw = result()
    raw["input"] = {"policies": [
        {"policy_id": "p", "local": {"findings": [{"category": "pii_detection", "action": "REDACT", "count": 1}]}},
        {"policy_id": "q", "local": {"findings": [{"category": "custom:private", "action": "BLOCK", "count": 1}]}},
    ]}
    notice = decision_notice(raw, {"p": PolicyDocument(name="Other"), "q": doc})
    assert notice["category"] == "custom" and "Contact your policy administrator" in notice["next_action"]


@pytest.mark.parametrize("changes", [
    {"generation_status": "FAILED"}, {"provider_error": "SensitiveProviderError"},
    {"failure_reasons": ["REQUEST_TIMEOUT"]},
    {"input": {"breakdown": {"pii_detection": "UNKNOWN"}}},
    {"input": {"policies": [{"failure_reasons": ["DETECTOR_UNAVAILABLE"], "local": {}}]}},
])
def test_technical_failures_are_not_policy_violations(changes):
    notice = decision_notice(result(**changes), {})
    assert notice["kind"] == "technical" and "SensitiveProviderError" not in json.dumps(notice)


def test_configuration_accepts_only_safe_templates_and_old_policies():
    assert PolicyDocument(name="Old").decision_messages == {}
    with pytest.raises(ValidationError):
        PolicyDocument(name="Unsafe", decision_messages={"BLOCK": "<script>secret</script>"})
    with pytest.raises(ValidationError):
        PolicyDocument(name="Unsafe", decision_messages={"ALLOW": "revise"})


def test_admin_configuration_immutable_publication_and_owner_create_edit_rollback_protection(client, monkeypatch):
    doc = PolicyDocument(name="Messages", decision_messages={"BLOCK": "contact_admin"})
    row = client.post("/api/policies", json=doc.model_dump()).json()
    pid = row["id"]
    for operation in ["submit", "approve", "publish", "activate"]:
        assert client.post(f"/api/policies/{pid}/{operation}").status_code == 200
    row = client.get(f"/api/policies/{pid}").json()
    original = client.get(f"/api/policies/{pid}/versions").json()
    doc.decision_messages = {"BLOCK": "public_example"}
    assert client.put(f"/api/policies/{pid}", json=doc.model_dump(), headers={"If-Match": str(row["row_version"])}).status_code == 200
    # Draft guidance never overrides the active immutable version.
    blocked = client.post("/api/governance/generate", json={"text": "internal-only"})
    assert blocked.json()["decision_notice"]["next_action"].startswith("Contact your policy administrator")
    assert client.get(f"/api/policies/{pid}/versions").json() == original
    accounts = json.loads(settings.demo_accounts_json)
    for account in accounts:
        if account["user"] == "admin":
            account["role"] = "Policy Owner"
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    assert client.post("/api/policies", json=doc.model_dump()).status_code == 403
    row = client.get(f"/api/policies/{pid}").json()
    doc.decision_messages = {}
    assert client.put(f"/api/policies/{pid}", json=doc.model_dump(), headers={"If-Match": str(row["row_version"])}).status_code == 403
    assert client.post(f"/api/policies/{pid}/rollback", json={"version": 1}).status_code == 403
    doc.decision_messages = {"BLOCK": "public_example"}
    doc.description = "Owner may edit unrelated fields"
    assert client.put(f"/api/policies/{pid}", json=doc.model_dump(), headers={"If-Match": str(row["row_version"])}).status_code == 200


@pytest.mark.parametrize("mode", ["LEGACY", "MULTI"])
@pytest.mark.parametrize("attachment", [False, True])
@pytest.mark.parametrize("decision,calls", [("BLOCK", 0), ("HUMAN_REVIEW", 0), ("REDACT", 1), ("ALLOW", 1)])
def test_public_messages_for_prompt_and_upload_preserve_enforcement(bridge, engine006, monkeypatch, mode, attachment, decision, calls):
    doc = uploads.policy("BLOCK" if decision == "ALLOW" else decision)
    doc.decision_messages = {"BLOCK": "public_example"}
    if mode == "MULTI":
        with Session(engine006, expire_on_commit=False) as db:
            phase_d.setup_workspace(db, [doc, phase_d.document(name="Second policy")])
        prefix = "/api/v2"
        headers = {"If-Match": bridge.get("/api/v2/workspace/policy-state").headers["etag"]}
    else:
        row = bridge.post("/api/policies", json=doc.model_dump()).json()
        for operation in ["submit", "approve", "publish", "activate"]:
            assert bridge.post(f"/api/policies/{row['id']}/{operation}").status_code == 200
        prefix, headers = "/api", {}
    provider = AsyncMock(return_value="public response")
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    text = "public" if decision == "ALLOW" else "private finance"
    response = bridge.post(prefix + "/governance/" + ("generate-document" if attachment else "generate"),
                           json=uploads.payload(text=text) if attachment else {"text": text}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"] == decision and provider.await_count == calls
    assert body["decision_notice"]["kind"] == ("success" if decision == "ALLOW" else "policy")
    assert "private finance" not in json.dumps(body["decision_notice"])
    if decision == "HUMAN_REVIEW":
        assert "has not been sent" in body["decision_notice"]["message"] and body["review_id"]
    assert bool(body["safe_response"]) == bool(calls)


def test_incomplete_review_keeps_review_and_resubmission_guidance():
    notice = decision_notice(result("HUMAN_REVIEW", input={"breakdown": {"pii_detection": "UNKNOWN"}}), {})
    assert notice["kind"] == "technical"
    assert "has not been sent" in notice["message"] and "Human review is required" in notice["message"]
    assert "resubmission under current policies" in notice["next_action"]


@pytest.mark.parametrize("mode", ["LEGACY", "MULTI"])
@pytest.mark.parametrize("failure", ["provider", "inspection", "output_review"])
def test_public_failure_and_output_review_messages_are_accurate(bridge, engine006, monkeypatch, mode, failure):
    doc = uploads.policy("HUMAN_REVIEW")
    if mode == "MULTI":
        with Session(engine006, expire_on_commit=False) as db:
            phase_d.setup_workspace(db, [doc])
        prefix = "/api/v2"
        headers = {"If-Match": bridge.get("/api/v2/workspace/policy-state").headers["etag"]}
    else:
        row = bridge.post("/api/policies", json=doc.model_dump()).json()
        for operation in ["submit", "approve", "publish", "activate"]:
            assert bridge.post(f"/api/policies/{row['id']}/{operation}").status_code == 200
        prefix, headers = "/api", {}
    if failure == "provider":
        provider = AsyncMock(side_effect=providers.ProviderUnavailable("SensitiveOriginalProviderError"))
    else:
        provider = AsyncMock(return_value="private finance")
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    if failure == "inspection":
        def unavailable(*args):
            raise TimeoutError("SensitiveOriginalDetectorError")
        monkeypatch.setattr("app.custom_rules.detect", unavailable)
    response = bridge.post(prefix + "/governance/generate", json={"text": "public"}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    notice = body["decision_notice"]
    assert "SensitiveOriginal" not in json.dumps(notice) and body["safe_response"] is None
    if failure == "output_review":
        assert body["decision"] == "HUMAN_REVIEW" and provider.await_count == 1
        assert "was invoked" in notice["message"] and "has not been sent" not in notice["message"]
    else:
        assert body["decision"] == "BLOCK" and notice["kind"] == "technical"
        assert provider.await_count == (1 if failure == "provider" else 0)
