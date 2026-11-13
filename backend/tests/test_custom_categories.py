"""Custom rules use existing JSON snapshots, local fixtures and enforcement paths."""
import json
from hashlib import sha256
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app import custom_rules, engine
from app.engine_multi_policy import evaluate_policy_set
from app.schemas import PolicyDocument
from app.config import settings
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models_multi_policy import ExecutionPolicyEvidence
import test_multi_policy_bridge as phase_bridge
import test_multi_policy_phase_b as phase_b
import test_multi_policy_phase_d as phase_d

templates = phase_b.templates
template010 = phase_b.template010
engine006 = phase_b.engine010
bridge = phase_bridge.bridge


def document(action="BLOCK", detection="keyword", values=None, **changes):
    return PolicyDocument.model_validate({"name": "Custom policy", "rules": {"moderation": {"enabled": False}},
        "custom_categories": [{"id": "finance", "name": "Finance", "description": "Private finance terms",
            "action": action, "detection": detection, "values": values or ["private finance"], **changes}]})


def pin(doc, identifier="one"):
    raw = doc.model_dump_json()
    return SimpleNamespace(policy_id=identifier, version_id=identifier, number=1,
                           document_json=raw, document_sha256=sha256(raw.encode()).hexdigest())


@pytest.mark.parametrize("action", ["BLOCK", "HUMAN_REVIEW", "REDACT"])
@pytest.mark.parametrize("detection,values,text", [("keyword", ["private finance"], "PRIVATE FINANCE"),
    ("regex", [r"INV-\d{3}"], "invoice INV-123")])
async def test_both_engines_enforce_custom_categories(action, detection, values, text):
    doc = document(action, detection, values)
    legacy = await engine.inspect_text(text, doc)
    multi = await evaluate_policy_set(text, [pin(doc)])
    assert legacy["decision"] == multi["decision"] == action
    assert legacy["score"] < 100 and legacy["contributions"]["custom:finance"] == 0
    assert legacy["findings"][-1] == {"category": "custom:finance", "count": 1, "action": action}
    assert multi["policies"][0]["local"]["breakdown"]["custom:finance"] == "FAILED"
    if action == "REDACT":
        assert "[REDACTED]" in legacy["safe_text"] and "[REDACTED]" in multi["safe_text"]
        assert legacy["revalidated"] and multi["revalidated"]
    else:
        assert legacy["safe_text"] is multi["safe_text"] is None


async def test_disabled_and_old_documents_remain_compatible():
    doc = document(enabled=False)
    assert (await engine.inspect_text("private finance", doc))["decision"] == "ALLOW"
    assert (await evaluate_policy_set("private finance", [pin(doc)]))["decision"] == "ALLOW"
    assert PolicyDocument(name="Old document").custom_categories == []


@pytest.mark.parametrize("pattern", ["(", "(a+)+$", "a|b", r"\1", "a{999999999}", "a{,999999999}", "a*", "[bad"])
def test_unsafe_or_invalid_patterns_rejected(pattern):
    with pytest.raises(ValidationError):
        document(detection="regex", values=[pattern])


async def test_timeout_fails_closed_in_both_engines(monkeypatch):
    def unavailable(*args):
        raise TimeoutError("Synthetic detector timeout")
    monkeypatch.setattr(custom_rules, "detect", unavailable)
    doc = document(action="REDACT")
    for result in [await engine.inspect_text("public", doc), await evaluate_policy_set("public", [pin(doc)])]:
        assert result["decision"] == "BLOCK" and result["safe_text"] is None
    assert (await engine.inspect_text("public", doc))["breakdown"]["custom:finance"] == "UNKNOWN"


async def test_multi_cache_separates_same_id_different_patterns():
    one, two = document(values=["absent"]), document(values=["present"])
    result = await evaluate_policy_set("present", [pin(one), pin(two, "two")])
    assert result["decision"] == "BLOCK"
    assert [p["local"]["breakdown"]["custom:finance"] for p in result["policies"]] == ["SATISFIED", "FAILED"]


def owner(monkeypatch):
    accounts = json.loads(settings.demo_accounts_json)
    for account in accounts:
        if account["user"] == "admin":
            account["role"] = "Policy Owner"
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))


def test_admin_draft_versions_simulation_and_owner_permissions(client, monkeypatch):
    doc = document()
    result = client.post("/api/policies", json=doc.model_dump())
    assert result.status_code == 201
    pid = result.json()["id"]
    for operation in ["submit", "approve", "publish", "activate"]:
        assert client.post(f"/api/policies/{pid}/{operation}").status_code == 200
    assert client.post(f"/api/policies/{pid}/simulate", json={"text": "private finance"}).json()["decision"] == "BLOCK"
    assert client.post("/api/governance/validate-input", json={"text": "private finance"}).json()["decision"] == "BLOCK"
    old = client.get(f"/api/policies/{pid}/versions").json()
    owner(monkeypatch)
    assert client.post("/api/policies", json=doc.model_dump()).status_code == 403
    row = client.get(f"/api/policies/{pid}").json()
    payload = doc.model_dump()
    payload["description"] = "Owner can edit other fields"
    assert client.put(f"/api/policies/{pid}", json=payload, headers={"If-Match": str(row["row_version"])}).status_code == 200
    row = client.get(f"/api/policies/{pid}").json()
    payload["custom_categories"] = []
    assert client.put(f"/api/policies/{pid}", json=payload, headers={"If-Match": str(row["row_version"])}).status_code == 403
    client.headers["Authorization"] = "Bearer foreign"
    assert client.get(f"/api/policies/{pid}").status_code == 404
    client.headers["Authorization"] = "Bearer admin"
    assert client.get(f"/api/policies/{pid}/versions").json() == old


async def test_missing_custom_evidence_blocks_release_and_retains_counts():
    from app.services.multi_policy_evidence import validate_stage
    doc = document()
    pins = [pin(doc)]
    raw = await evaluate_policy_set("private finance", pins)
    assert validate_stage(raw, pins)["policies"][0]["local"]["findings"][-1]["category"] == "custom:finance"
    raw = await evaluate_policy_set("public", pins)
    del raw["policies"][0]["local"]["breakdown"]["custom:finance"]
    checked = validate_stage(raw, pins)
    assert checked["decision"] == "BLOCK" and checked["safe_text"] is None
    assert "DETECTOR_UNAVAILABLE" in checked["policies"][0]["failure_reasons"]


def test_regex_runtime_budget_and_zero_width_fail_closed():
    with pytest.raises((TimeoutError, ValueError)):
        custom_rules.detect("a" * 11999 + "!", document(detection="regex", values=["a+a+$"]).custom_categories[0])
    with pytest.raises(ValueError):
        custom_rules.detect("public", document(detection="regex", values=[r"\b"]).custom_categories[0])


def test_admin_can_edit_remove_and_owner_cannot_restore_categories(client, monkeypatch):
    doc = document()
    row = client.post("/api/policies", json=doc.model_dump()).json()
    pid = row["id"]
    for operation in ["submit", "approve", "publish"]:
        assert client.post(f"/api/policies/{pid}/{operation}").status_code == 200
    row = client.get(f"/api/policies/{pid}").json()
    doc.custom_categories[0].enabled = False
    doc.custom_categories[0].description = "Changed by Admin"
    response = client.put(f"/api/policies/{pid}", json=doc.model_dump(), headers={"If-Match": str(row["row_version"])})
    assert response.status_code == 200
    row = response.json()
    doc.custom_categories = []
    assert client.put(f"/api/policies/{pid}", json=doc.model_dump(), headers={"If-Match": str(row["row_version"])}).status_code == 200
    owner(monkeypatch)
    assert client.post(f"/api/policies/{pid}/rollback", json={"version": 1}).status_code == 403
    versions = client.get(f"/api/policies/{pid}/versions").json()
    assert json.loads(versions[0]["document"])["custom_categories"][0]["enabled"] is True


@pytest.mark.parametrize("action", ["BLOCK", "REDACT", "HUMAN_REVIEW"])
def test_public_multi_custom_enforcement_persists_sanitized_evidence(bridge, engine006, action):
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, [document(action)])
    etag = bridge.get("/api/v2/workspace/policy-state").headers["etag"]
    response = bridge.post("/api/v2/governance/validate-input", json={"text": "private finance"}, headers={"If-Match": etag})
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == action
    with Session(engine006) as db:
        evidence = db.scalar(select(ExecutionPolicyEvidence))
        stored = json.loads(evidence.evidence_json)
        assert stored["input"]["local"]["findings"][-1] == {"category": "custom:finance", "count": 1, "action": action}
        assert "private finance" not in evidence.evidence_json
    detail = bridge.get("/api/v2/audit/executions/" + response.json()["request_id"])
    assert detail.status_code == 200 and "custom:finance" in detail.text
