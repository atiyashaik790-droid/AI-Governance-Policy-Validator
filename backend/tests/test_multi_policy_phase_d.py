"""Phase D evaluator and internal orchestration; no live provider transport."""

import asyncio
import json
import shutil
import time
from dataclasses import replace
from hashlib import sha256
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import engine, engine_multi_policy as evaluator, providers
from app.config import settings
from app.models import InferenceUsage, Policy, Review, Version
from app.models_multi_policy import Execution006, ExecutionPolicyEvidence
from app.schemas import PolicyDocument, TextRequest
from app.security import Identity
from app.services import multi_policy_governance as gateway, policy_sets as domain
import test_multi_policy_phase_b as phase_b

templates = phase_b.templates


@pytest.fixture
def engine006(templates, tmp_path, monkeypatch):
    """Run current orchestration against a disposable current-schema database."""
    path = tmp_path / "orchestration.db"
    shutil.copyfile(templates["006"], path)
    phase_b.migrate(path, "010")
    monkeypatch.setattr(settings, "inference_daily_quota", 100000)
    monkeypatch.setattr(settings, "inference_tenant_per_minute", 100000)
    monkeypatch.setattr(settings, "inference_user_per_minute", 100000)
    engine = phase_b.fixture_engine(path)
    yield engine
    engine.dispose()


def document(name="Policy", *, keyword=None, action="BLOCK", moderation=False, categories=None):
    return PolicyDocument(name=name, rules={
        "secret_detection": {"enabled": False}, "pii_detection": {"enabled": False},
        "blocked_keywords": {"enabled": keyword is not None, "values": [keyword] if keyword else [], "action": action},
        "moderation": {"enabled": moderation, "categories": categories, "action": "BLOCK"},
    })


def pin(doc, index=1, number=1):
    encoded = doc.model_dump_json()
    return domain.PublishedPin(f"policy-{index:04}", f"version-{index:04}-{number}", number, encoded, sha256(encoded.encode()).hexdigest())


def setup_workspace(db, documents, user=phase_b.ADMIN):
    revision = domain.change_mode(db, user, "MULTI", expected_revision=1, seed_legacy_assignment=False)
    pairs = []
    for doc in documents:
        p = Policy(tenant=user.tenant, name=doc.name, draft=doc.model_dump_json(), status="PUBLISHED", enabled=1)
        db.add(p)
        db.flush()
        v = Version(tenant=user.tenant, policy_id=p.id, number=1, document=doc.model_dump_json())
        db.add(v)
        db.commit()
        revision = domain.change_assignment(db, user, p.id, active=True, version_id=v.id, expected_revision=revision)
        pairs.append((p.id, v.id))
    return pairs, revision


@pytest.mark.parametrize("count", [1, 6, 105])
async def test_every_policy_has_evidence_and_unique_control_is_evaluated(monkeypatch, count):
    detector = Mock(return_value=[])
    monkeypatch.setattr(engine, "bounded_detection", detector)
    pins = tuple(pin(document(keyword=f"marker-{i}"), i) for i in range(count))
    result = await evaluator.evaluate_policy_set("Benign text", pins)
    assert result["policy_count"] == len(result["policies"]) == detector.call_count == count
    assert result["decision"] == "ALLOW" and result["safe_text"] == "Benign text"
    assert all(p["inspection_status"] == "COMPLETE" for p in result["policies"])
    assert {p["version_id"] for p in result["policies"]} == {p.version_id for p in pins}


@pytest.mark.parametrize("actions,expected", [
    (["REDACT", "BLOCK"], "BLOCK"), (["REDACT", "HUMAN_REVIEW"], "HUMAN_REVIEW"),
    (["HUMAN_REVIEW", "BLOCK", "REDACT"], "BLOCK"), (["REDACT", "REDACT"], "REDACT"),
])
async def test_precedence_independence_and_original_holds(actions, expected):
    pins = tuple(pin(document(keyword="private", action=action), i) for i, action in enumerate(actions))
    a = await evaluator.evaluate_policy_set("private data", pins)
    b = await evaluator.evaluate_policy_set("private data", tuple(reversed(pins)))
    assert a == b and a["decision"] == expected
    assert [p["local"]["decision"] for p in a["policies"]] == actions
    assert (a["safe_text"] is not None) == (expected == "REDACT")


async def test_common_cross_policy_redaction_reinspection_and_privacy(monkeypatch):
    moderate = AsyncMock(return_value={"violence": False})
    monkeypatch.setattr(evaluator, "moderation_evidence", moderate)
    pins = (pin(document(keyword="abcde", action="REDACT", moderation=True, categories=["violence"]), 1),
            pin(document(keyword="defgh", action="REDACT", moderation=True, categories=["violence"]), 2))
    result = await evaluator.evaluate_policy_set("abcdefgh public", pins)
    assert result["decision"] == "REDACT" and result["safe_text"] == "[REDACTED] public"
    assert all(p["reinspection"]["decision"] == "ALLOW" for p in result["policies"])
    moderate.assert_awaited_once_with("[REDACTED] public", {"violence"})
    metadata = json.dumps({k: v for k, v in result.items() if k != "safe_text"})
    assert "abcdefgh" not in metadata and "abcde" not in metadata and "defgh" not in metadata


async def test_redaction_with_moderation_hold_is_not_marked_safe_revalidation(monkeypatch):
    monkeypatch.setattr(evaluator, "moderation_evidence", AsyncMock(return_value={"violence": True}))
    result = await evaluator.evaluate_policy_set("private", (
        pin(document(keyword="private", action="REDACT", moderation=True, categories=["violence"])),))
    assert result["decision"] == "BLOCK" and result["safe_text"] is None and not result["revalidated"]


async def test_reinspection_new_cross_policy_violation_is_held(monkeypatch):
    moderate = AsyncMock()
    monkeypatch.setattr(evaluator, "moderation_evidence", moderate)
    pins = (pin(document(keyword="private", action="REDACT"), 1),
            pin(document(keyword="[REDACTED]", moderation=True), 2))
    result = await evaluator.evaluate_policy_set("private", pins)
    assert result["decision"] == "BLOCK" and result["safe_text"] is None
    assert result["policies"][1]["reinspection"]["decision"] == "BLOCK"
    moderate.assert_not_awaited()


async def test_residual_redaction_is_not_repeated_or_released():
    result = await evaluator.evaluate_policy_set("private", (pin(document(keyword="private", action="REDACT")),
                                                             pin(document(keyword="[REDACTED]", action="REDACT"), 2)))
    assert result["decision"] == "BLOCK" and result["safe_text"] is None


@pytest.mark.parametrize("action", ["BLOCK", "HUMAN_REVIEW"])
async def test_all_local_controls_precede_external_and_holds_never_leave(monkeypatch, action):
    moderate = AsyncMock(side_effect=AssertionError("Held content must remain local"))
    monkeypatch.setattr(evaluator, "moderation_evidence", moderate)
    pins = (pin(document(moderation=True), 1), pin(document(keyword="private", action=action), 2),
            pin(document(keyword="private", action="REDACT"), 3))
    result = await evaluator.evaluate_policy_set("private", pins)
    assert result["decision"] == action and result["safe_text"] is None
    assert result["policies"][0]["moderation"]["status"] == "WITHHELD_LOCAL_HOLD"
    assert result["policies"][2]["local"]["findings"][0]["count"] == 1
    moderate.assert_not_awaited()


@pytest.mark.parametrize("bad", [None, [], {}, {"violence": "false"}, {"not-a-category": False}])
async def test_missing_or_malformed_moderation_coverage_fails_closed(monkeypatch, bad):
    monkeypatch.setattr(evaluator, "moderation_evidence", AsyncMock(return_value=bad))
    result = await evaluator.evaluate_policy_set("Benign text", (pin(document(moderation=True, categories=["violence"])),))
    assert result["decision"] == "BLOCK" and result["safe_text"] is None
    assert result["inspection_status"] == "INCOMPLETE"


async def test_default_moderation_requires_all_categories_and_union_is_complete(monkeypatch):
    moderate = AsyncMock(return_value={c: False for c in evaluator.KNOWN_CATEGORIES})
    monkeypatch.setattr(evaluator, "moderation_evidence", moderate)
    pins = (pin(document(moderation=True), 1), pin(document(moderation=True, categories=["violence"]), 2))
    result = await evaluator.evaluate_policy_set("Benign text", pins)
    assert result["decision"] == "ALLOW"
    moderate.assert_awaited_once_with("Benign text", set(evaluator.KNOWN_CATEGORIES))


async def test_moderation_categories_have_independent_per_policy_decisions(monkeypatch):
    monkeypatch.setattr(evaluator, "moderation_evidence", AsyncMock(return_value={"violence": True, "hate": False}))
    result = await evaluator.evaluate_policy_set("Benign text", (
        pin(document(moderation=True, categories=["violence"]), 1), pin(document(moderation=True, categories=["hate"]), 2)))
    assert [p["decision"] for p in result["policies"]] == ["BLOCK", "ALLOW"]


async def test_missing_category_in_real_adapter_response_is_not_assumed_false(monkeypatch):
    monkeypatch.setattr(settings, "provider_mode", "live")
    monkeypatch.setattr(settings, "openai_api_key", "synthetic-not-sent")
    response = httpx.Response(200, json={"results": [{"flagged": False, "categories": {"violence": False}}]},
                              request=httpx.Request("POST", "https://fixture.invalid"))
    client = AsyncMock()
    client.post.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(providers.httpx, "AsyncClient", Mock(return_value=context))
    result = await evaluator.evaluate_policy_set("Benign text", (pin(document(moderation=True)),))
    assert result["decision"] == "BLOCK" and result["safe_text"] is None
    assert set(client.post.call_args.kwargs["json"]) == {"model", "input"}


@pytest.mark.parametrize("bad", [None, [(0, 999)], [(True, 2)], [(2, 1)], "invalid"])
async def test_malformed_detector_result_fails_closed(monkeypatch, bad):
    monkeypatch.setattr(engine, "bounded_detection", Mock(return_value=bad))
    result = await evaluator.evaluate_policy_set("private", (pin(document(keyword="private")),))
    assert result["decision"] == "BLOCK" and result["safe_text"] is None
    assert result["policies"][0]["local"]["breakdown"]["blocked_keywords"] == "UNKNOWN"


async def test_missing_detector_and_timeout_preserve_full_evidence_cardinality(monkeypatch):
    monkeypatch.setattr(engine, "bounded_detection", Mock(side_effect=RuntimeError("Missing recognizer with private details")))
    pins = tuple(pin(document(keyword=f"control {i}"), i) for i in range(6))
    result = await evaluator.evaluate_policy_set("Benign", pins)
    assert len(result["policies"]) == 6 and result["decision"] == "BLOCK"
    assert "private details" not in json.dumps(result)
    result = await evaluator.evaluate_policy_set("Benign", pins, deadline=time.monotonic() - 1)
    assert len(result["policies"]) == 6 and result["decision"] == "BLOCK" and result["safe_text"] is None


async def test_detector_and_moderator_timeouts_fail_closed(monkeypatch):
    monkeypatch.setattr(settings, "provider_timeout", 0.01)
    def slow_detector(*_args):
        time.sleep(0.04)
        return []
    monkeypatch.setattr(engine, "bounded_detection", slow_detector)
    result = await evaluator.evaluate_policy_set("Benign", (pin(document(keyword="private")),))
    assert result["decision"] == "BLOCK"
    async def slow_moderator(*_args):
        await asyncio.sleep(0.1)
        return {"violence": False}
    monkeypatch.setattr(evaluator, "moderation_evidence", slow_moderator)
    result = await evaluator.evaluate_policy_set("Benign", (pin(document(moderation=True, categories=["violence"])),))
    assert result["decision"] == "BLOCK" and result["safe_text"] is None


async def test_only_equivalent_detector_work_is_reused_and_cache_is_request_scoped(monkeypatch):
    detector = Mock(return_value=[])
    monkeypatch.setattr(engine, "bounded_detection", detector)
    pins = tuple(pin(document(keyword="private", action="BLOCK" if i % 2 else "HUMAN_REVIEW"), i) for i in range(6))
    await evaluator.evaluate_policy_set("Benign", pins)
    assert detector.call_count == 1
    await evaluator.evaluate_policy_set("Different text", pins)
    assert detector.call_count == 2
    await evaluator.evaluate_policy_set("Benign", (pins[0], pin(document(keyword="other"), 10)))
    assert detector.call_count == 4


@pytest.mark.parametrize("kind", ["empty", "duplicate", "digest"])
async def test_invalid_snapshots_cannot_allow(kind):
    p = pin(document())
    pins = () if kind == "empty" else (p, p) if kind == "duplicate" else (replace(p, document_sha256="0" * 64),)
    with pytest.raises(ValueError):
        await evaluator.evaluate_policy_set("Benign", pins)


async def test_generation_uses_same_explicit_version_pins_for_input_and_output(engine006, monkeypatch):
    generate = AsyncMock(return_value="public reply")
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    async def inline_detector(function, *args):
        return function(*args)
    monkeypatch.setattr(evaluator.asyncio, "to_thread", inline_detector)
    with Session(engine006, expire_on_commit=False) as db:
        pairs, revision = setup_workspace(db, [document(name="Old snapshot", keyword="old-only"), document(name="Other snapshot", keyword="other-only")])
        p = db.get(Policy, pairs[0][0])
        db.add(Version(tenant="one", policy_id=p.id, number=2, document=document(name="New snapshot", keyword="public").model_dump_json()))
        db.commit()
        result = await gateway.execute("generate", TextRequest(text="Benign"), db, phase_b.ADMIN, expected_revision=revision)
        assert result["decision"] == "ALLOW" and result["safe_response"] == "public reply"
        generate.assert_awaited_once_with("Benign")
        for stage in ["input", "output"]:
            assert {p["version_id"] for p in result[stage]["policies"]} == {v for _, v in pairs}
            assert {p["policy_name"] for p in result[stage]["policies"]} == {"Old snapshot", "Other snapshot"}
            assert {p["version"] for p in result[stage]["policies"]} == {1}
        execution = db.get(Execution006, result["request_id"])
        assert execution.execution_mode == "MULTI" and execution.policy_id is None and execution.version is None
        assert db.scalar(select(func.count()).select_from(ExecutionPolicyEvidence)) == 2
        assert db.scalar(select(InferenceUsage.status)) == "SUCCEEDED"
        assert "Benign" not in execution.metadata_json and "public reply" not in execution.metadata_json


@pytest.mark.parametrize("count", [1, 6, 105])
async def test_all_active_database_assignments_generate_once_and_persist_every_pin(engine006, monkeypatch, count):
    generate = AsyncMock(return_value="public reply")
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    with Session(engine006, expire_on_commit=False) as db:
        pairs, revision = setup_workspace(db, [document(name=f"Policy {i}") for i in range(count)])
        result = await gateway.execute("generate", TextRequest(text="Benign"), db, phase_b.ADMIN, expected_revision=revision)
        assert result["decision"] == "ALLOW" and result["safe_response"] == "public reply"
        for stage in ["input", "output"]:
            assert result[stage]["policy_count"] == len(result[stage]["policies"]) == count
            assert {p["version_id"] for p in result[stage]["policies"]} == {v for _, v in pairs}
            assert {p["policy_name"] for p in result[stage]["policies"]} == {f"Policy {i}" for i in range(count)}
        assert db.scalar(select(func.count()).select_from(ExecutionPolicyEvidence)) == count
        generate.assert_awaited_once_with("Benign")


@pytest.mark.parametrize("stage", ["input", "output"])
async def test_orchestration_releases_only_common_sanitized_text(engine006, monkeypatch, stage):
    generate = AsyncMock(return_value="private response" if stage == "output" else "public response")
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    with Session(engine006, expire_on_commit=False) as db:
        setup_workspace(db, [document(keyword="private", action="REDACT"), document()])
        result = await gateway.execute("generate", TextRequest(text="private prompt" if stage == "input" else "public prompt"), db, phase_b.ADMIN)
        generate.assert_awaited_once_with("[REDACTED] prompt" if stage == "input" else "public prompt")
        assert result["decision"] == "REDACT"
        assert result["safe_response"] == ("[REDACTED] response" if stage == "output" else "public response")
        assert "private prompt" not in db.scalar(select(Execution006.metadata_json))
        assert "private response" not in db.scalar(select(Execution006.metadata_json))


async def test_missing_selected_local_recognizer_blocks_without_external_call(monkeypatch):
    monkeypatch.setattr(settings, "pii_mode", "regex")
    doc = document(moderation=True)
    doc.rules.pii_detection.enabled = True
    doc.rules.pii_detection.entities = ["PERSON"]
    moderate = AsyncMock()
    monkeypatch.setattr(evaluator, "moderation_evidence", moderate)
    result = await evaluator.evaluate_policy_set("Benign", (pin(doc),))
    assert result["decision"] == "BLOCK"
    assert result["policies"][0]["local"]["breakdown"]["pii_detection"] == "UNKNOWN"
    moderate.assert_not_awaited()


@pytest.mark.parametrize("bad", [None, {}, ["unknown"], ["violence", "violence"], "violence"])
async def test_malformed_adapter_flags_fail_closed(monkeypatch, bad):
    monkeypatch.setattr(providers, "moderate_user_prompt", AsyncMock(return_value=bad))
    result = await evaluator.evaluate_policy_set("Benign", (pin(document(moderation=True)),))
    assert result["decision"] == "BLOCK" and result["inspection_status"] == "INCOMPLETE"


async def test_pii_selector_differences_are_not_reused(monkeypatch):
    detector = Mock(return_value=[])
    monkeypatch.setattr(engine, "bounded_detection", detector)
    docs = [document(), document(), document()]
    for doc, entities in zip(docs, [["EMAIL_ADDRESS"], ["PHONE_NUMBER"], ["EMAIL_ADDRESS"]]):
        doc.rules.pii_detection.enabled = True
        doc.rules.pii_detection.entities = entities
    result = await evaluator.evaluate_policy_set("Benign", tuple(pin(doc, i) for i, doc in enumerate(docs)))
    assert result["decision"] == "ALLOW" and detector.call_count == 2


@pytest.mark.parametrize("failure", ["error", "timeout", "empty", "malformed"])
async def test_generation_failure_never_retries_or_releases(engine006, monkeypatch, failure):
    async def generate(_text):
        if failure == "timeout":
            await asyncio.sleep(0.1)
        if failure == "error":
            raise providers.ProviderUnavailable("ambiguous response with raw private content")
        return "" if failure == "empty" else {"content": "bad"}
    provider = AsyncMock(side_effect=generate)
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    monkeypatch.setattr(settings, "provider_timeout", 0.01)
    with Session(engine006, expire_on_commit=False) as db:
        setup_workspace(db, [document()])
        result = await gateway.execute("generate", TextRequest(text="Benign"), db, phase_b.ADMIN)
        assert result["decision"] == "BLOCK" and result["safe_response"] is None
        assert result["generation_status"] == "FAILED" and provider.await_count == 1
        if failure == "error":
            assert result["provider_diagnostics"]["code"] == "PROVIDER_UNAVAILABLE"
        assert "raw private" not in db.scalar(select(Execution006.metadata_json))


@pytest.mark.parametrize("when", ["before_generation", "before_release"])
async def test_concurrent_assignment_change_fences_dispatch_or_release(engine006, monkeypatch, when):
    with Session(engine006, expire_on_commit=False) as db:
        pairs, revision = setup_workspace(db, [document()])
        pid, _ = pairs[0]
        async def change():
            with Session(engine006) as other:
                domain.change_assignment(other, phase_b.ADMIN, pid, active=False, expected_revision=revision)
        original = gateway.evaluate_policy_set
        async def inspect(*args, **kwargs):
            result = await original(*args, **kwargs)
            if when == "before_generation":
                await change()
            return result
        async def generate(_text):
            if when == "before_release":
                await change()
            return "Never released"
        provider = AsyncMock(side_effect=generate)
        monkeypatch.setattr(gateway, "evaluate_policy_set", inspect)
        monkeypatch.setattr(providers, "generate_ai_response", provider)
        with pytest.raises(HTTPException) as error:
            await gateway.execute("generate", TextRequest(text="Benign"), db, phase_b.ADMIN)
        assert error.value.status_code == 409 and error.value.detail == "POLICY_SET_CHANGED"
        assert provider.await_count == (0 if when == "before_generation" else 1)
        # Phase E retains a failed request and all captured evidence after fencing.
        assert db.scalar(select(func.count()).select_from(Execution006)) == 1
        assert db.scalar(select(Execution006.decision)) == "BLOCK"
        assert db.scalar(select(InferenceUsage.status)) == "FAILED"


@pytest.mark.parametrize("reconcile", [False, True])
async def test_expired_or_reconciled_reservation_cannot_release(engine006, monkeypatch, reconcile):
    async def generate(_text):
        with Session(engine006) as other:
            row = other.scalar(select(InferenceUsage))
            row.expires = "2000-01-01T00:00:00+00:00"
            other.commit()
            if reconcile:
                assert domain.reconcile_expired(other, phase_b.ADMIN) == 1
        return "Never released"
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(side_effect=generate))
    with Session(engine006, expire_on_commit=False) as db:
        setup_workspace(db, [document()])
        with pytest.raises(HTTPException) as error:
            await gateway.execute("generate", TextRequest(text="Benign"), db, phase_b.ADMIN)
        assert error.value.detail == "RESERVATION_FENCED"
        assert db.scalar(select(func.count()).select_from(Execution006)) == 1
        assert db.scalar(select(Execution006.decision)) == "BLOCK"
        assert db.scalar(select(InferenceUsage.status)) == ("EXPIRED" if reconcile else "FAILED")


async def test_human_review_is_metadata_only_and_resubmission_rechecks(engine006, monkeypatch):
    generate = AsyncMock(side_effect=AssertionError("Held content must not generate"))
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    with Session(engine006, expire_on_commit=False) as db:
        setup_workspace(db, [document(keyword="private", action="HUMAN_REVIEW")])
        result = await gateway.execute("generate", TextRequest(text="private original secret payload"), db, phase_b.ADMIN)
        assert result["decision"] == "HUMAN_REVIEW" and result["safe_response"] is None
        review = db.get(Review, result["review_id"])
        assert review.status == "PENDING"
        assert "private original" not in db.scalar(select(Execution006.metadata_json))
        assert "private original" not in db.scalar(select(ExecutionPolicyEvidence.evidence_json))
        with pytest.raises(HTTPException) as error:
            await gateway.execute("generate", TextRequest(text="public", source_review_id=review.id), db, phase_b.ADMIN)
        assert error.value.status_code == 409
        review.status = "APPROVED_RESUBMIT_REQUIRED"
        db.commit()
        resubmitted = await gateway.execute("generate", TextRequest(text="private revised", source_review_id=review.id), db, phase_b.ADMIN)
        assert resubmitted["decision"] == "HUMAN_REVIEW"
        generate.assert_not_awaited()


async def test_tenants_roles_and_public_boundaries(engine006):
    from app.main import app
    with Session(engine006, expire_on_commit=False) as db:
        setup_workspace(db, [document(keyword="tenant-one")])
        user = Identity("foreign", "two", "Admin")
        foreign_pairs, _ = setup_workspace(db, [document(keyword="tenant-two")], user)
        result = await gateway.execute("validate-input", TextRequest(text="tenant-one"), db, user)
        assert result["decision"] == "ALLOW"
        assert {p["policy_id"] for p in result["input"]["policies"]} == {p for p, _ in foreign_pairs}
        assert db.get(Execution006, result["request_id"]).tenant == "two"
        with pytest.raises(HTTPException) as error:
            await gateway.execute("validate-input", TextRequest(text="Benign"), db, Identity("auditor", "one", "Auditor"))
        assert error.value.status_code == 403
    assert {path for path in app.openapi()["paths"] if path.startswith("/api/v2/governance")} == {
        "/api/v2/governance/generate", "/api/v2/governance/generate-document", "/api/v2/governance/validate-input", "/api/v2/governance/validate-output"}


async def test_evidence_audit_and_reservation_commit_atomically(engine006, monkeypatch):
    def fail(*_args):
        raise RuntimeError("synthetic audit failure")
    monkeypatch.setattr(gateway, "record_audit_event", fail)
    with Session(engine006, expire_on_commit=False) as db:
        setup_workspace(db, [document()])
        with pytest.raises(RuntimeError):
            await gateway.execute("validate-output", TextRequest(text="Benign"), db, phase_b.ADMIN)
        assert db.scalar(select(func.count()).select_from(Execution006)) == 0
        assert db.scalar(select(func.count()).select_from(ExecutionPolicyEvidence)) == 0
        assert db.scalar(select(InferenceUsage.status)) == "FAILED"


async def test_whole_request_deadline_cannot_release(engine006, monkeypatch):
    original = gateway.evaluate_policy_set
    async def slow(*args, **kwargs):
        await asyncio.sleep(0.04)
        return await original(*args, **kwargs)
    monkeypatch.setattr(gateway, "evaluate_policy_set", slow)
    monkeypatch.setattr(settings, "inference_deadline", 0.01)
    with Session(engine006, expire_on_commit=False) as db:
        setup_workspace(db, [document()])
        with pytest.raises(HTTPException) as error:
            await gateway.execute("generate", TextRequest(text="Benign"), db, phase_b.ADMIN)
        assert error.value.status_code == 504
        assert db.scalar(select(InferenceUsage.status)) == "FAILED"
