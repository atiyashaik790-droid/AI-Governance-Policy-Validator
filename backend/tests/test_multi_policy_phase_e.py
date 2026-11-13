"""Durable metadata/report contracts, disposable databases and mocked storage."""

import csv
import io
import json
from hashlib import sha256
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, func, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session

from app import providers, sso
from app.config import settings
from app.database import get_database
from app.main import app
from app.models import Audit, Execution, Export, ExportJob, InferenceUsage, Review, SsoMembership
from app.models_multi_policy import Execution006, ExecutionPolicyEvidence as Evidence
from app.schemas import TextRequest
from app.services import multi_policy_governance as gateway, policy_sets as domain
import test_multi_policy_bridge as bridge_module
import test_multi_policy_phase_b as phase_b
import test_multi_policy_phase_d as phase_d

templates = phase_b.templates
template010 = phase_b.template010
engine006 = phase_b.engine010
bridge = bridge_module.bridge
SENSITIVE = "SyntheticOriginalSensitiveValue9XYZ"


async def request(db, count=6, **kwargs):
    pairs, revision = phase_d.setup_workspace(db, [phase_d.document(name=f"Policy {i}") for i in range(count)])
    result = await gateway.execute("validate-input", TextRequest(text=SENSITIVE), db, phase_b.ADMIN, **kwargs)
    return result, pairs, revision


@pytest.mark.parametrize("count", [6, 105])
async def test_one_request_every_pin_and_separate_analytics_counts(bridge, engine006, count):
    with Session(engine006, expire_on_commit=False) as db:
        result, pairs, _ = await request(db, count)
        assert db.scalar(select(func.count()).select_from(Execution006)) == 1
        assert db.scalar(select(func.count()).select_from(Evidence)) == count
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action.startswith("governance.multi."))) == 1
    detail = bridge.get("/api/v2/audit/executions/" + result["request_id"])
    assert detail.status_code == 200
    body = detail.json()
    assert body["execution_mode"] == "MULTI" and body["legacy"] is None
    assert len(body["policy_evidence"]) == body["policy_evaluation_count"] == count
    assert {e["version_id"] for e in body["policy_evidence"]} == {v for _, v in pairs}
    assert all(len(e["document_sha256"]) == 64 for e in body["policy_evidence"])
    assert SENSITIVE not in detail.text
    overview = bridge.get("/api/v2/analytics/overview").json()
    assert overview["request_count"] == 1 and overview["policy_evaluation_count"] == count
    assert overview["active_policy_count"] == count
    assert bridge.get("/api/v2/audit/executions?limit=1").json()["total"] == 1


@pytest.mark.parametrize("fault", ["missing", "duplicate", "pin"])
async def test_partial_or_invalid_evidence_is_reconciled_and_withheld(engine006, monkeypatch, fault):
    original = gateway.evaluate_policy_set
    async def incomplete(*args, **kwargs):
        value = await original(*args, **kwargs)
        if fault == "missing":
            value["policies"].pop()
        elif fault == "duplicate":
            value["policies"][-1] = value["policies"][0]
        else:
            value["policies"][-1]["version_id"] = "wrong-pin"
        return value
    monkeypatch.setattr(gateway, "evaluate_policy_set", incomplete)
    generate = AsyncMock(side_effect=AssertionError("Incomplete input cannot generate"))
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    with Session(engine006, expire_on_commit=False) as db:
        pairs, _ = phase_d.setup_workspace(db, [phase_d.document() for _ in range(6)])
        result = await gateway.execute("generate", TextRequest(text=SENSITIVE), db, phase_b.ADMIN)
        assert result["decision"] == "BLOCK" and result["safe_response"] is None
        rows = list(db.scalars(select(Evidence)))
        assert len(rows) == 6 and {e.version_id for e in rows} == {v for _, v in pairs}
        assert any(e.inspection_status == "INCOMPLETE" for e in rows)
        assert any(any(reason in e.evidence_json for reason in ["EVIDENCE_MISSING", "PIN_MISMATCH"]) for e in rows)
        generate.assert_not_awaited()


async def test_only_allowlisted_inspection_metadata_is_persisted_and_exposed(bridge, engine006, monkeypatch):
    original = gateway.evaluate_policy_set
    async def extra(*args, **kwargs):
        value = await original(*args, **kwargs)
        value["raw_prompt"] = SENSITIVE
        value["policies"][0]["raw_provider_result"] = SENSITIVE
        value["policies"][0]["local"]["findings"] = [{"category": "blocked_keywords", "count": 0, "matched_text": SENSITIVE}]
        return value
    monkeypatch.setattr(gateway, "evaluate_policy_set", extra)
    with Session(engine006, expire_on_commit=False) as db:
        result, _, _ = await request(db)
        assert SENSITIVE not in db.scalar(select(Execution006.metadata_json))
        assert all(SENSITIVE not in e for e in db.scalars(select(Evidence.evidence_json)))
    assert SENSITIVE not in bridge.get("/api/v2/audit/executions/" + result["request_id"]).text


async def test_timeout_records_every_skipped_pin_and_failure_reason(engine006, monkeypatch):
    monkeypatch.setattr(gateway, "evaluate_policy_set", AsyncMock(side_effect=TimeoutError))
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, [phase_d.document() for _ in range(6)])
        with pytest.raises(HTTPException) as error:
            await gateway.execute("generate", TextRequest(text=SENSITIVE), db, phase_b.ADMIN)
        assert error.value.status_code == 504
        assert db.scalar(select(func.count()).select_from(Execution006)) == 1
        rows = list(db.scalars(select(Evidence)))
        assert len(rows) == 6 and all(e.inspection_status == "INCOMPLETE" for e in rows)
        assert all("REQUEST_TIMEOUT" in e.evidence_json and "NOT_RUN" in e.evidence_json for e in rows)
        assert db.scalar(select(InferenceUsage.status)) == "FAILED"


@pytest.mark.parametrize("failure", ["audit", "evidence", "commit"])
async def test_database_failures_rollback_everything_and_never_release(engine006, monkeypatch, failure):
    generate = AsyncMock(return_value=SENSITIVE)
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    def fail(*_args):
        raise SQLAlchemyError("synthetic database outage")
    if failure == "audit":
        monkeypatch.setattr(gateway, "record_audit_event", fail)
    if failure == "evidence":
        event.listen(Evidence, "before_insert", fail)
    try:
        with Session(engine006, expire_on_commit=False) as db:
            phase_d.setup_workspace(db, [phase_d.document() for _ in range(6)])
            if failure == "commit":
                original = db.commit
                calls = 0
                def commit():
                    nonlocal calls
                    calls += 1
                    if calls == 3:  # admission, pre-generation fence, then durable result.
                        fail()
                    original()
                monkeypatch.setattr(db, "commit", commit)
            with pytest.raises(SQLAlchemyError):
                await gateway.execute("generate", TextRequest(text="public"), db, phase_b.ADMIN)
            assert db.scalar(select(func.count()).select_from(Execution006)) == 0
            assert db.scalar(select(func.count()).select_from(Evidence)) == 0
            assert db.scalar(select(func.count()).select_from(Review)) == 0
            assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action.startswith("governance.multi."))) == 0
            assert db.scalar(select(InferenceUsage.status)) == "FAILED"
            generate.assert_awaited_once()
    finally:
        if failure == "evidence":
            event.remove(Evidence, "before_insert", fail)


async def test_review_failure_rolls_back_request_evidence_audit_and_review(engine006):
    def fail(*_args):
        raise SQLAlchemyError("synthetic review persistence failure")
    event.listen(Review, "before_insert", fail)
    try:
        with Session(engine006, expire_on_commit=False) as db:
            phase_d.setup_workspace(db, [phase_d.document(keyword="held", action="HUMAN_REVIEW") for _ in range(6)])
            with pytest.raises(SQLAlchemyError):
                await gateway.execute("generate", TextRequest(text="held"), db, phase_b.ADMIN)
            assert db.scalar(select(func.count()).select_from(Execution006)) == 0
            assert db.scalar(select(func.count()).select_from(Evidence)) == 0
            assert db.scalar(select(func.count()).select_from(Review)) == 0
            assert db.scalar(select(func.count()).select_from(Audit).where(Audit.action.startswith("governance.multi."))) == 0
    finally:
        event.remove(Review, "before_insert", fail)


async def test_evidence_and_audit_are_immutable_at_database_boundary(engine006):
    with Session(engine006, expire_on_commit=False) as db:
        await request(db)
        for statement in ["UPDATE execution_policy_evidence SET effective_decision='BLOCK'", "DELETE FROM execution_policy_evidence", "DELETE FROM audit_events"]:
            with pytest.raises(IntegrityError):
                db.execute(text(statement))
            db.rollback()


async def test_historical_modes_and_legacy_metadata_remain_intact(bridge, engine006):
    with Session(engine006, expire_on_commit=False) as db:
        p, v = phase_b.legacy(db)
        encoded = json.dumps({"input": {"decision": "ALLOW", "breakdown": {}, "raw_prompt": SENSITIVE}})
        old = Execution(tenant="one", actor="admin", policy_id=p.id, version=v.number, model="fixture", decision="ALLOW", metadata_json=encoded)
        db.add(old)
        db.commit()
        old_id, old_pid = old.id, p.id
        result, pairs, revision = await request(db, 1)
        domain.change_mode(db, phase_b.ADMIN, "LEGACY", expected_revision=revision, legacy_version_id=pairs[0][1])
        assert db.get(Execution, old_id).metadata_json == encoded
    old = bridge.get("/api/v2/audit/executions/" + old_id).json()
    multi = bridge.get("/api/v2/audit/executions/" + result["request_id"]).json()
    assert old["execution_mode"] == "LEGACY" and old["legacy"] == {"policy_id": old_pid, "version": 1}
    assert multi["execution_mode"] == "MULTI" and multi["legacy"] is None
    assert SENSITIVE not in json.dumps(old)
    for path in ["/api/audit/executions", "/api/analytics/overview"]:
        assert bridge.get(path).status_code == 409
    assert bridge.post("/api/reports/export", json={}).status_code == 409
    overview = bridge.get("/api/v2/analytics/overview").json()
    assert overview["request_count"] == overview["policy_evaluation_count"] == 2
    assert overview["requests_by_mode"] == {"LEGACY": 1, "MULTI": 1}
    assert overview["active_policy_count"] == 1


async def test_original_phase_d_evidence_shape_remains_readable_without_rewrite(bridge, engine006):
    with Session(engine006, expire_on_commit=False) as db:
        phase_d.setup_workspace(db, [phase_d.document() for _ in range(6)])
        admission = domain.admit(db, phase_b.ADMIN)
        inspected = await gateway.evaluate_policy_set("public", admission.pins)
        old_metadata = json.dumps({"input": {k: v for k, v in inspected.items() if k != "safe_text"}, "decision": "ALLOW"})
        row = Execution006(tenant="one", actor="admin", execution_mode="MULTI", policy_id=None, version=None,
                           model="fixture", decision="ALLOW", metadata_json=old_metadata)
        db.add(row)
        db.flush()
        old_documents = {}
        for pin in admission.pins:
            policy = next(p for p in inspected["policies"] if p["policy_id"] == pin.policy_id)
            old_documents[pin.policy_id] = json.dumps({"input": policy})  # Original Phase D shape, no schema_version.
            db.add(Evidence(tenant="one", execution_id=row.id, policy_id=pin.policy_id, version_id=pin.version_id,
                            document_sha256=pin.document_sha256, set_revision=admission.set_revision,
                            effective_decision="ALLOW", inspection_status="COMPLETE", evidence_json=old_documents[pin.policy_id]))
        domain.finish_admission(db, phase_b.ADMIN, admission, "INSPECTED", commit=False)
        db.commit()
        identifier = row.id
    detail = bridge.get("/api/v2/audit/executions/" + identifier)
    assert detail.status_code == 200 and detail.json()["cardinality_complete"] is True
    assert detail.json()["captured_policy_count"] == len(detail.json()["policy_evidence"]) == 6
    assert all(e["inspections"]["input"]["decision"] == "ALLOW" for e in detail.json()["policy_evidence"])
    with Session(engine006) as db:
        assert db.get(Execution006, identifier).metadata_json == old_metadata
        assert {e.policy_id: e.evidence_json for e in db.scalars(select(Evidence))} == old_documents


async def test_review_one_case_all_contributors_and_current_policy_resubmission(bridge, engine006):
    with Session(engine006, expire_on_commit=False) as db:
        docs = [phase_d.document(keyword="held", action="HUMAN_REVIEW") for _ in range(2)] + [phase_d.document() for _ in range(4)]
        pairs, revision = phase_d.setup_workspace(db, docs)
        result = await gateway.execute("generate", TextRequest(text="held original"), db, phase_b.ADMIN)
        rid = result["review_id"]
        assert db.scalar(select(func.count()).select_from(Review)) == 1
    detail = bridge.get("/api/v2/reviews/" + rid)
    assert detail.status_code == 200 and len(detail.json()["execution"]["policy_evidence"]) == 6
    assert set(detail.json()["contributing_policy_ids"]) == {p for p, _ in pairs[:2]}
    assert "held original" not in detail.text
    assert bridge.get("/api/reviews/" + rid).status_code == 409
    bridge.headers["Authorization"] = "Bearer developer"
    assert bridge.get("/api/v2/reviews/" + rid).status_code == 404
    bridge.headers["Authorization"] = "Bearer reviewer"
    assert bridge.put("/api/v2/reviews/" + rid + "/assignment", json={"assigned_reviewer": "reviewer"}).status_code == 200
    response = bridge.post("/api/v2/reviews/" + rid + "/approve", json={"reason": "Reviewed policy requirements"})
    assert response.status_code == 200 and response.json()["status"] == "APPROVED_RESUBMIT_REQUIRED"
    assert "safe_response" not in response.json()
    with Session(engine006, expire_on_commit=False) as db:
        for pid, _ in pairs[:2]:
            revision = domain.change_assignment(db, phase_b.ADMIN, pid, active=False, expected_revision=revision)
        submitted = await gateway.execute("validate-input", TextRequest(text="held revised", source_review_id=rid), db, phase_b.ADMIN)
        assert submitted["decision"] == "ALLOW" and submitted["input"]["policy_count"] == 4


async def test_history_tenant_isolation_and_pagination(bridge, engine006):
    with Session(engine006, expire_on_commit=False) as db:
        result, _, _ = await request(db)
        await gateway.execute("validate-input", TextRequest(text="public"), db, phase_b.ADMIN)
    a = bridge.get("/api/v2/audit/executions?limit=1").json()
    b = bridge.get("/api/v2/audit/executions?limit=1&offset=1").json()
    assert a["total"] == b["total"] == 2 and a["items"][0]["request_id"] != b["items"][0]["request_id"]
    assert len(bridge.get("/api/v2/audit/events?limit=1").json()["items"]) == 1
    bridge.headers["Authorization"] = "Bearer foreign"
    assert bridge.get("/api/v2/audit/executions?tenant=one").json()["total"] == 0
    assert bridge.get("/api/v2/audit/events").json()["total"] == 0
    assert bridge.get("/api/v2/audit/executions/" + result["request_id"]).status_code == 404
    assert bridge.get("/api/v2/analytics/overview").json()["policy_evaluation_count"] == 0
    bridge.headers.pop("Authorization")
    assert bridge.get("/api/v2/audit/executions").status_code == 401


@pytest.mark.parametrize("format", ["json", "csv"])
async def test_versioned_export_preserves_all_105_pins_and_immutable_snapshot(bridge, engine006, monkeypatch, format):
    upload = Mock()
    monkeypatch.setattr(providers, "upload_report", upload)
    monkeypatch.setattr(settings, "export_max_records", 1)  # Request limit must not truncate policy evidence.
    with Session(engine006, expire_on_commit=False) as db:
        result, _, _ = await request(db, 105)
    body = {"schema_version": "2.0", "format": format, "idempotency_key": "snapshot"}
    response = bridge.post("/api/v2/reports/export", json=body)
    assert response.status_code == 201 and response.json()["state"] == "COMPLETED", response.text
    identifier = response.json()["id"]
    with Session(engine006) as db:
        job = db.get(ExportJob, identifier)
        snapshot, checksum = job.content, job.content_hash
        assert checksum == sha256(snapshot.encode()).hexdigest()
    assert SENSITIVE not in snapshot
    if format == "json":
        data = json.loads(snapshot)
        assert data["schema_version"] == "2.0" and data["request_count"] == 1 and data["policy_evaluation_count"] == 105
        assert len(data["requests"][0]["policy_evidence"]) == 105
    else:
        rows = list(csv.DictReader(io.StringIO(snapshot)))
        assert len([r for r in rows if r["row_type"] == "request"]) == 1
        assert len([r for r in rows if r["row_type"] == "policy_evidence"]) == 105
    assert bridge.post("/api/v2/reports/export", json=body).json()["id"] == identifier
    assert bridge.post("/api/v2/reports/export", json={**body, "format": "csv" if format == "json" else "json"}).status_code == 409
    assert upload.call_count == 1
    assert bridge.get("/api/v2/reports/exports?limit=1").json()["total"] == 1
    with Session(engine006) as db:
        assert db.get(ExportJob, identifier).content == snapshot and db.get(ExportJob, identifier).content_hash == checksum


async def test_legacy_export_snapshot_hash_preserved_and_v2_recovery_uses_exact_bytes(bridge, engine006, monkeypatch):
    upload = Mock()
    monkeypatch.setattr(providers, "upload_report", upload)
    old = bridge.post("/api/reports/export", json={"idempotency_key": "legacy-snapshot"}).json()
    with Session(engine006) as db:
        legacy_job = db.get(ExportJob, old["id"])
        before = legacy_job.content, legacy_job.content_hash
        # Simulate an older operator-created job. Public v1 validation correctly
        # rejects colons in keys and must stay unchanged.
        historical = Export(tenant="one", status="SUCCEEDED", path="synthetic-legacy.json")
        db.add(historical)
        db.flush()
        db.add(ExportJob(id=historical.id, tenant="one", idempotency_key="v2:legacy-direct", request_hash="0" * 64,
                         content=before[0], content_hash=before[1], state="COMPLETED"))
        historical_id = historical.id
        db.commit()
    with Session(engine006, expire_on_commit=False) as db:
        await request(db)
    upload.side_effect = providers.ProviderUnavailable("synthetic storage ambiguity")
    exported = bridge.post("/api/v2/reports/export", json={"idempotency_key": "new-snapshot"})
    assert exported.status_code == 201 and exported.json()["state"] == "FAILED"
    identifier = exported.json()["id"]
    with Session(engine006) as db:
        checksum = db.get(ExportJob, identifier).content_hash
    digest = Mock(return_value=checksum)
    monkeypatch.setattr(providers, "report_digest", digest)
    recovered = bridge.post(f"/api/v2/reports/exports/{identifier}/reconcile")
    assert recovered.status_code == 200 and recovered.json()["state"] == "COMPLETED"
    assert upload.call_count == 2  # legacy upload + failed v2 upload; recovery verifies instead of replaying.
    assert bridge.post("/api/reports/export", json={"idempotency_key": "legacy-snapshot"}).json()["id"] == old["id"]
    assert bridge.get("/api/v2/reports/exports").json()["total"] == 1
    assert bridge.post(f"/api/v2/reports/exports/{historical_id}/reconcile").status_code == 404
    with Session(engine006) as db:
        row = db.get(ExportJob, old["id"])
        assert (row.content, row.content_hash) == before
    bridge.headers["Authorization"] = "Bearer foreign"
    assert bridge.post(f"/api/v2/reports/exports/{identifier}/reconcile").status_code == 404


@pytest.mark.parametrize("token", ["developer", "reviewer"])
def test_reporting_mutation_rbac_and_request_contract(bridge, token):
    bridge.headers["Authorization"] = "Bearer " + token
    assert bridge.post("/api/v2/reports/export", json={}).status_code == 403
    assert bridge.post("/api/v2/reports/exports/unknown/reconcile").status_code == 403


@pytest.mark.parametrize("payload", [{"schema_version": "1.0"}, {"tenant": "two"}, {"format": "other"}])
def test_versioned_export_rejects_unapproved_contract_fields(bridge, payload):
    assert bridge.post("/api/v2/reports/export", json=payload).status_code == 422


def test_v2_pagination_bounds_and_no_governance_routes(bridge):
    for path in ["audit/executions", "audit/events", "reviews", "reports/exports"]:
        assert bridge.get("/api/v2/" + path + "?limit=101").status_code == 422
        assert bridge.get("/api/v2/" + path + "?offset=-1").status_code == 422
    assert {p for p in app.openapi()["paths"] if p.startswith("/api/v2/governance")} == {
        "/api/v2/governance/generate", "/api/v2/governance/generate-document", "/api/v2/governance/validate-input", "/api/v2/governance/validate-output"}


def test_schema_005_versioned_reporting_does_not_query_006(client, templates, tmp_path, monkeypatch):
    import shutil
    path = tmp_path / "005.db"
    shutil.copyfile(templates["005"], path)
    engine = phase_b.fixture_engine(path)
    statements = []
    @event.listens_for(engine, "before_cursor_execute")
    def capture(_conn, _cursor, sql, *_args):
        statements.append(sql.lower())
    def dependency():
        with Session(engine, expire_on_commit=False) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_database] = dependency
    monkeypatch.setattr(providers, "upload_report", Mock())
    with Session(engine, expire_on_commit=False) as db:
        p, v = phase_b.legacy(db)
        db.add(Execution(tenant="one", actor="admin", policy_id=p.id, version=v.number, model="fixture", decision="ALLOW", metadata_json="{}"))
        db.commit()
    assert client.get("/api/v2/audit/executions").json()["items"][0]["execution_mode"] == "LEGACY"
    assert client.get("/api/v2/analytics/overview").json()["policy_evaluation_count"] == 1
    assert client.get("/api/v2/reviews").status_code == 200
    assert client.post("/api/v2/reports/export", json={}).status_code == 201
    assert not any(any(n in sql for n in ["workspace_policy_states", "workspace_policy_assignments", "execution_policy_evidence"]) for sql in statements)
    engine.dispose()


@pytest.mark.parametrize("role,expected", [("Admin", 201), ("Reviewer", 403)])
def test_sso_csrf_and_roles_apply_to_versioned_exports(bridge, engine006, monkeypatch, role, expected):
    directory = "11111111-1111-4111-8111-111111111111"
    oid = "33333333-3333-4333-8333-333333333333"
    for key, value in {"sso_enabled": True, "demo_browser_login_enabled": False, "entra_tenant_id": directory,
                       "entra_client_id": "22222222-2222-4222-8222-222222222222", "entra_client_secret": "synthetic-only",
                       "sso_public_origin": "https://testserver"}.items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(providers, "upload_report", Mock())
    with Session(engine006) as db:
        db.add(SsoMembership(directory_tenant=directory, object_id=oid, tenant="one", actor="sso-user", role=role))
        db.commit()
    monkeypatch.setattr(sso, "metadata", AsyncMock(return_value={"authorization_endpoint": f"https://login.microsoftonline.com/{directory}/oauth2/v2.0/authorize"}))
    monkeypatch.setattr(sso, "exchange_code", AsyncMock(return_value={"tid": directory, "oid": oid}))
    bridge.headers.pop("Authorization")
    bridge.base_url = httpx.URL("https://testserver")
    login = bridge.get("/api/sso/login", follow_redirects=False)
    nonce = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    assert bridge.get("/api/sso/callback", params={"state": nonce, "code": "fixture"}, follow_redirects=False).status_code == 303
    csrf = bridge.get("/api/sso/me").json()["csrf_token"]
    assert bridge.get("/api/v2/audit/executions").status_code == 200
    assert bridge.post("/api/v2/reports/export", json={}).status_code == 403
    headers = {"Origin": "https://testserver", "X-CSRF-Token": csrf}
    assert bridge.post("/api/v2/reports/export", json={}, headers=headers).status_code == expected
