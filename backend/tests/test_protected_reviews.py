"""Synthetic keys, disposable revision 007, fixture providers only."""
import base64
import hashlib
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import sessionmaker

from app import database, protected_reviews as secure, providers
from app.config import settings
from app.database import get_database
from app.main import app
from app.models import Assignment, Audit, Execution, Policy, Review, ReviewAssignment, Version
from app.models_review_content import ProtectedReviewContent as Content
import test_multi_policy_phase_b as phase_b
import test_multi_policy_phase_d as phase_d
import test_document_uploads as uploads


@pytest.fixture(scope="module")
def template007(tmp_path_factory):
    path = tmp_path_factory.mktemp("protected-review-template") / "007.db"
    phase_b.migrate(path, "007")
    return path


@pytest.fixture
def protected(template007, tmp_path, monkeypatch, request):
    path = tmp_path / "review.db"
    shutil.copyfile(template007, path)
    if request.node.name != "test_migration007_binary_tenant_fk_and_safe_downgrade_refusal":
        phase_b.migrate(path, "010")
    engine = phase_b.fixture_engine(path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    accounts = [{"user": actor, "tenant": tenant, "role": role, "token_hash": hashlib.sha256(actor.encode()).hexdigest()}
                for actor, tenant, role in [("admin", "one", "Admin"), ("reviewer", "one", "Reviewer"), ("foreign", "two", "Admin"),
                                           ("auditor", "one", "Auditor"), ("developer", "one", "Developer"), ("owner", "one", "Policy Owner"), ("user", "one", "User")]]
    for key, value in {
        "review_capture_enabled": True, "review_cleanup_enabled": True,
        "review_content_active_key_id": "synthetic-v1", "review_content_keys_json": json.dumps({"synthetic-v1": base64.b64encode(b"a" * 32).decode()}),
        "demo_accounts_json": json.dumps(accounts), "provider_mode": "fixture", "pii_mode": "regex", "sso_enabled": False,
        "allow_legacy_api_credentials": True, "demo_browser_login_enabled": True,
        "inference_daily_quota": 100000, "inference_tenant_per_minute": 100000, "inference_user_per_minute": 100000,
    }.items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(database, "SessionLocal", factory)

    def dependency():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_database] = dependency
    with TestClient(app, raise_server_exceptions=False) as client:
        for _ in range(100):
            if secure.health.healthy(engine):
                break
            time.sleep(.02)
        assert secure.health.healthy(engine), "startup cleanup did not become healthy"
        client.headers["Authorization"] = "Bearer admin"
        yield client, engine, factory
    assert not secure.health.healthy(engine)
    app.dependency_overrides.clear()
    engine.dispose()


def install(factory, *, multi=False, action="HUMAN_REVIEW", keyword="internal-only"):
    doc = phase_d.document("Review policy", keyword=keyword, action=action)
    with factory() as db:
        if multi:
            phase_d.setup_workspace(db, [doc, phase_d.document("Second policy")])
        else:
            p = Policy(tenant="one", name=doc.name, draft=doc.model_dump_json(), status="PUBLISHED", enabled=1)
            db.add(p)
            db.flush()
            v = Version(tenant="one", policy_id=p.id, number=1, document=doc.model_dump_json())
            db.add(v)
            db.flush()
            db.add(Assignment(tenant="one", version_id=v.id))
            db.commit()


def submit(client, *, multi=False, prompt="  Please share internal-only records.\n雪  ", attachment=None):
    path = ("/api/v2" if multi else "/api") + "/governance/" + ("generate-document" if attachment else "generate")
    headers = {"If-Match": client.get("/api/v2/workspace/policy-state").headers["etag"]} if multi else {}
    result = client.post(path, headers=headers, json=uploads.payload(attachment, text="internal-only document MUST_NOT_RETAIN", prompt=prompt) if attachment else {"text": prompt})
    assert result.status_code == 200, result.text
    return result.json()


def login(client, actor="reviewer"):
    client.headers["Authorization"] = "Bearer " + actor
    result = client.post("/api/auth/session")
    assert result.status_code == 201, result.text
    client.headers["Authorization"] = "Bearer " + result.json()["access_token"]


def assign(factory, review_id, actor="reviewer"):
    with factory() as db:
        db.add(ReviewAssignment(tenant="one", id=review_id, assigned_reviewer=actor))
        db.commit()
        return db.get(Review, review_id).row_version


def reveal(client, review_id, version=1):
    return client.post(f"/api/reviews/{review_id}/content", json={}, headers={"If-Match": f'"{version}"'})


@pytest.mark.parametrize("multi", [False, True])
@pytest.mark.parametrize("attachment", [None, "txt", "pdf", "docx"])
def test_capture_exact_prompt_only_on_hold_and_reveal_is_separate(protected, monkeypatch, multi, attachment):
    client, engine, factory = protected
    install(factory, multi=multi)
    provider = AsyncMock(side_effect=AssertionError("Held input must not generate"))
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    prompt = "  Please share internal-only records.\n雪  "
    result = submit(client, multi=multi, prompt=prompt, attachment=attachment)
    assert result["decision"] == "HUMAN_REVIEW"
    provider.assert_not_awaited()
    rid = result["review_id"]
    with factory() as db:
        row = db.scalar(select(Content))
        assert row and row.expires_at - row.created_at == secure.RETENTION
        assert prompt.encode() not in row.ciphertext and len(row.nonce) == 12
        assert secure.decrypt_prompt(row, db.get(Review, rid).execution_id) == prompt
    version = assign(factory, rid)
    login(client)
    detail = client.get(("/api/v2" if multi else "/api") + f"/reviews/{rid}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["review_trigger"] == "INPUT"
    assert not detail.json()["attachment_contents_retained"]
    assert detail.json()["attachment_present"] == bool(attachment)
    assert prompt not in detail.text and "MUST_NOT_RETAIN" not in detail.text
    response = reveal(client, rid, version)
    assert response.status_code == 200, response.text
    assert response.json()["original_prompt"] == prompt
    assert response.headers["cache-control"] == "no-store"
    with factory() as db:
        events = list(db.scalars(select(Audit.action).where(Audit.resource == rid)))
        assert "review.content.viewed" in events
        assert "MUST_NOT_RETAIN" not in str(list(db.scalars(select(Audit.resource))))
    assert "original_prompt" not in client.get(("/api/v2" if multi else "/api") + "/reviews").text


@pytest.mark.parametrize("actor", ["admin", "auditor", "developer", "owner", "user", "foreign"])
def test_only_explicitly_assigned_same_tenant_reviewer_session(protected, actor):
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    login(client, actor)
    response = reveal(client, rid, version)
    assert response.status_code in (403, 404), response.text
    assert "Please share" not in response.text


def test_bearer_session_version_assignment_and_resolution(protected):
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    client.headers["Authorization"] = "Bearer reviewer"
    assert reveal(client, rid, version).status_code == 403
    login(client)
    assert client.post(f"/api/reviews/{rid}/content", json={}).status_code == 428
    assert reveal(client, rid, version + 1).status_code == 412
    assert client.post(f"/api/reviews/{rid}/content", json={"text": "do not echo"}).status_code == 422
    assert client.post(f"/api/reviews/{rid}/approve", json={"reason": "sensitive customer content"}).status_code == 422
    response = client.post(f"/api/reviews/{rid}/approve", json={"reason": "Resubmission required"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED_RESUBMIT_REQUIRED"
    with factory() as db:
        assert db.scalar(select(Content)) is None
    detail = client.get(f"/api/reviews/{rid}").json()
    assert detail["protected_content"]["availability"] == "PURGED"
    assert reveal(client, rid, version).status_code == 412


@pytest.mark.parametrize("field", ["tenant", "review_id", "expires_at", "nonce", "ciphertext", "key_id", "format_version", "execution"])
def test_authenticated_encryption_rejects_tampering(protected, field):
    secure.keyring()
    row = secure.encrypt_prompt("exact\n秘密", "one", "r", "e", 100)
    assert secure.decrypt_prompt(row, "e") == "exact\n秘密"
    if field == "execution":
        execution = "other"
    else:
        execution = "e"
        current = getattr(row, field)
        setattr(row, field, current + 1 if isinstance(current, int) else b"x" + current[1:] if isinstance(current, bytes) else "other")
    with pytest.raises(HTTPException) as caught:
        secure.decrypt_prompt(row, execution)
    assert caught.value.status_code == 503 and "秘密" not in str(caught.value.detail)


def test_nonce_uniqueness_rotation_and_invalid_configuration(protected, monkeypatch):
    first = secure.encrypt_prompt("original", "one", "r", "e", 100)
    second = secure.encrypt_prompt("original", "one", "r", "e", 100)
    assert first.nonce != second.nonce
    keys = json.loads(settings.review_content_keys_json)
    keys["synthetic-v2"] = base64.b64encode(b"b" * 32).decode()
    monkeypatch.setattr(settings, "review_content_keys_json", json.dumps(keys))
    monkeypatch.setattr(settings, "review_content_active_key_id", "synthetic-v2")
    assert secure.decrypt_prompt(first, "e") == "original"
    assert secure.encrypt_prompt("new", "one", "r2", "e2", 100).key_id == "synthetic-v2"
    for value in ['{}', '{"duplicate":"a","duplicate":"b"}', '{"bad":"invalid"}']:
        monkeypatch.setattr(settings, "review_content_keys_json", value)
        with pytest.raises(HTTPException):
            secure.keyring()


@pytest.mark.parametrize("failure", ["unhealthy", "overdue", "key", "stopped"])
def test_unhealthy_capture_fails_before_generation(protected, monkeypatch, failure):
    client, engine, factory = protected
    install(factory)
    provider = AsyncMock(side_effect=AssertionError("admission must fail"))
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    if failure == "key":
        monkeypatch.setattr(settings, "review_content_keys_json", "{}")
    elif failure == "stopped":
        secure.health.stop()
    elif failure == "overdue":
        secure.health.success_at = time.monotonic() - 1000
    else:
        secure.health.record(engine, False)
    response = client.post("/api/governance/generate", json={"text": "ordinary"})
    assert response.status_code == 503, response.text
    provider.assert_not_awaited()
    with factory() as db:
        assert db.scalar(select(Content)) is None
        assert db.scalar(select(Execution)) is None


def test_expiry_immediate_and_concurrent_cleanup_idempotent(protected, monkeypatch):
    client, engine, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    login(client)
    with factory() as db:
        expiry = db.scalar(select(Content.expires_at))
    monkeypatch.setattr(secure, "clock", lambda db: expiry)
    assert reveal(client, rid, version).status_code == 410
    with factory() as db:
        assert db.scalar(select(Content)) is not None  # Retrieval denied before physical deletion.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: secure.cleanup_once(engine, factory), range(2)))
    assert sum(result["removed"] for result in results) == 1
    assert secure.cleanup_once(engine, factory)["healthy"]
    with factory() as db:
        assert db.scalar(select(Content)) is None
        assert len(list(db.scalars(select(Audit).where(Audit.action == "review.content.expired")))) == 1
    assert client.get(f"/api/reviews/{rid}").json()["protected_content"]["availability"] == "EXPIRED"


def test_audit_commit_failure_never_returns_plaintext(protected, monkeypatch):
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    login(client)
    original = secure.record_audit_event
    def fail(db, user, action, resource):
        if action == "review.content.viewed":
            raise RuntimeError("synthetic audit unavailable")
        return original(db, user, action, resource)
    monkeypatch.setattr(secure, "record_audit_event", fail)
    response = reveal(client, rid, version)
    assert response.status_code == 500 and "Please share" not in response.text


@pytest.mark.parametrize("multi", [False, True])
def test_output_hold_retains_original_input_not_generated_content(protected, monkeypatch, multi):
    client, _, factory = protected
    install(factory, multi=multi)
    provider = AsyncMock(return_value="internal-only generated output")
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    result = submit(client, multi=multi, prompt="typed original safe request")
    assert result["decision"] == "HUMAN_REVIEW" and not result["safe_response"]
    assert provider.await_count == 1
    detail = client.get(("/api/v2" if multi else "/api") + f"/reviews/{result['review_id']}")
    assert detail.json()["review_trigger"] == "OUTPUT"
    with factory() as db:
        row = db.scalar(select(Content))
        assert secure.decrypt_prompt(row, db.get(Review, result["review_id"]).execution_id) == "typed original safe request"


@pytest.mark.parametrize("action", ["BLOCK", "REDACT", "ALLOW"])
def test_other_decisions_do_not_capture(protected, monkeypatch, action):
    client, _, factory = protected
    install(factory, action="BLOCK" if action == "ALLOW" else action)
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(return_value="safe response"))
    result = submit(client, prompt="ordinary" if action == "ALLOW" else "internal-only")
    assert result["decision"] == action
    with factory() as db:
        assert db.scalar(select(Content)) is None


def test_migration007_binary_tenant_fk_and_safe_downgrade_refusal(protected):
    _, engine, factory = protected
    with factory() as db:
        assert secure.schema_available(db)
    columns = inspect(engine).get_columns("review_protected_content")
    assert {c["name"] for c in columns} == {"tenant", "review_id", "content_kind", "format_version", "key_id", "nonce", "ciphertext", "created_at", "expires_at"}
    assert inspect(engine).get_foreign_keys("review_protected_content")[0]["constrained_columns"] == ["tenant", "review_id"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("migration007", phase_b.ROOT / "backend/migrations/versions/007_protected_review_content.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="must not be destroyed"):
        module.downgrade()
    # Seed protected content directly on revision 007. Current HTTP writes require
    # the later audit-role column, but this test exercises the 007 downgrade gate.
    with factory() as db:
        policy, version = phase_b.policy(db)
        execution = Execution(tenant="one", actor="admin", policy_id=policy.id,
                              version=version.number, model="fixture", decision="HUMAN_REVIEW", metadata_json="{}")
        db.add(execution)
        db.flush()
        review = Review(tenant="one", execution_id=execution.id)
        db.add(review)
        db.flush()
        rid = review.id
        db.add(secure.encrypt_prompt("synthetic held prompt", "one", rid, execution.id, secure.clock(db)))
        db.commit()
    import os
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-B", "-m", "alembic", "downgrade", "006"], cwd=phase_b.ROOT / "backend",
                            env={**os.environ, "DATABASE_URL": str(engine.url)}, capture_output=True, text=True)
    assert result.returncode != 0 and "must not be destroyed" in result.stderr
    with factory() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "007"
        assert db.scalar(select(Content.review_id)) == rid


@pytest.mark.parametrize("multi", [False, True])
def test_capture_failure_rolls_back_review_execution_and_ciphertext(protected, monkeypatch, multi):
    client, _, factory = protected
    install(factory, multi=multi)
    original = secure.record_audit_event
    def fail(db, user, action, resource):
        if action == "review.content.retained":
            raise RuntimeError("synthetic persistence failure")
        return original(db, user, action, resource)
    monkeypatch.setattr(secure, "record_audit_event", fail)
    provider = AsyncMock(side_effect=AssertionError("no dispatch"))
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    headers = {"If-Match": client.get("/api/v2/workspace/policy-state").headers["etag"]} if multi else {}
    response = client.post(("/api/v2" if multi else "/api") + "/governance/generate", json={"text": "internal-only"}, headers=headers)
    assert response.status_code in (500, 503), response.text
    provider.assert_not_awaited()
    with factory() as db:
        assert db.scalar(select(Content)) is None
        assert db.scalar(select(Review)) is None
        assert db.scalar(select(Execution)) is None


def test_resolution_failure_preserves_pending_content_atomically(protected, monkeypatch):
    from app.services import reviews
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    assign(factory, rid)
    login(client)
    def fail(*args):
        raise RuntimeError("synthetic disposition failure")
    monkeypatch.setattr(reviews, "record_audit_event", fail)
    assert client.post(f"/api/reviews/{rid}/reject", json={"reason": "Policy restriction confirmed"}).status_code == 500
    with factory() as db:
        assert db.get(Review, rid).status == "PENDING"
        assert db.scalar(select(Content)) is not None
        assert not list(db.scalars(select(Audit).where(Audit.action == "review.content.purged")))


def test_reassignment_revokes_old_reviewer_and_admin_must_be_assigned(protected):
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    login(client)
    assert reveal(client, rid, version).status_code == 200
    login(client, "admin")
    assert reveal(client, rid, version).status_code == 403
    response = client.put(f"/api/reviews/{rid}/assignment", json={"assigned_reviewer": "admin", "reason": "Assigned for review"})
    assert response.status_code == 200, response.text
    with factory() as db:
        new_version = db.get(Review, rid).row_version
    assert new_version > version
    assert reveal(client, rid, new_version).status_code == 200
    login(client)
    assert reveal(client, rid, new_version).status_code == 403


def test_cleanup_failure_closes_capture_and_recovery_restores_health(protected):
    _, engine, factory = protected
    def broken():
        raise RuntimeError("synthetic database outage")
    assert not secure.cleanup_once(engine, broken)["healthy"]
    assert not secure.health.healthy(engine)
    assert secure.cleanup_once(engine, factory)["healthy"]
    assert secure.health.healthy(engine)


def test_missing_historical_key_no_plaintext_fallback(protected, monkeypatch):
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    login(client)
    monkeypatch.setattr(settings, "review_content_active_key_id", "new")
    monkeypatch.setattr(settings, "review_content_keys_json", json.dumps({"new": base64.b64encode(b"b" * 32).decode()}))
    response = reveal(client, rid, version)
    assert response.status_code == 503 and "Please share" not in response.text
    with factory() as db:
        assert db.scalar(select(Content)) is not None


def test_ciphertext_cannot_be_updated_and_tenant_fk_is_enforced(protected):
    from sqlalchemy.exc import IntegrityError
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    with factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE review_protected_content SET key_id='replacement'"))
        db.rollback()
        row = secure.encrypt_prompt("foreign", "two", rid, "e", secure.clock(db))
        db.add(row)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_sso_csrf_membership_disable_and_access_audit(protected, monkeypatch):
    from urllib.parse import parse_qs, urlsplit
    import httpx
    from app import sso
    from app.models import SsoMembership
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    directory = "11111111-1111-4111-8111-111111111111"
    oid = "33333333-3333-4333-8333-333333333333"
    for key, value in {"sso_enabled": True, "demo_browser_login_enabled": False,
        "entra_tenant_id": directory, "entra_client_id": "22222222-2222-4222-8222-222222222222",
        "entra_client_secret": "synthetic-only", "sso_public_origin": "https://testserver"}.items():
        monkeypatch.setattr(settings, key, value)
    with factory() as db:
        membership = SsoMembership(directory_tenant=directory, object_id=oid, tenant="one", actor="reviewer", role="Reviewer")
        db.add(membership)
        db.commit()
        membership_id = membership.id
    monkeypatch.setattr(sso, "metadata", AsyncMock(return_value={"authorization_endpoint": f"https://login.microsoftonline.com/{directory}/oauth2/v2.0/authorize"}))
    monkeypatch.setattr(sso, "exchange_code", AsyncMock(return_value={"tid": directory, "oid": oid}))
    client.headers.pop("Authorization")
    client.base_url = httpx.URL("https://testserver")
    response = client.get("/api/sso/login", follow_redirects=False)
    state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    assert client.get("/api/sso/callback", params={"state": state, "code": "synthetic"}, follow_redirects=False).status_code == 303
    me = client.get("/api/sso/me").json()
    assert reveal(client, rid, version).status_code == 403
    headers = {"If-Match": f'"{version}"', "Origin": "https://testserver", "X-CSRF-Token": me["csrf_token"]}
    assert client.post(f"/api/reviews/{rid}/content", json={}, headers={**headers, "Origin": "https://foreign.invalid"}).status_code == 403
    response = client.post(f"/api/reviews/{rid}/content", json={}, headers=headers)
    assert response.status_code == 200, response.text
    with factory() as db:
        member = db.get(SsoMembership, membership_id)
        member.enabled = 0
        db.commit()
    assert client.post(f"/api/reviews/{rid}/content", json={}, headers=headers).status_code == 401


def test_mssql007_binary_ddl_is_bounded_and_indexable():
    from sqlalchemy.schema import CreateTable, CreateIndex
    from sqlalchemy.dialects import mssql
    ddl = str(CreateTable(Content.__table__).compile(dialect=mssql.dialect()))
    assert "nonce VARBINARY(12)" in ddl and "ciphertext VARBINARY(max)" in ddl
    assert "IMAGE" not in ddl and "NVARCHAR" not in ddl
    indexes = " ".join(str(CreateIndex(index).compile(dialect=mssql.dialect())) for index in Content.__table__.indexes)
    assert "UNIQUE INDEX ux_rpc_key_nonce" in indexes


@pytest.mark.parametrize("multi", [False, True])
def test_custom_category_holds_are_captured_and_not_exposed_in_exports(protected, monkeypatch, multi):
    from app.schemas import PolicyDocument
    from app.services import reporting_v2
    from app.security import Identity
    client, _, factory = protected
    doc = PolicyDocument.model_validate({"name": "Private custom policy", "rules": {"moderation": {"enabled": False}},
        "custom_categories": [{"id": "private", "name": "Private", "action": "HUMAN_REVIEW", "detection": "keyword", "values": ["custom-needle"]}]})
    with factory() as db:
        if multi:
            phase_d.setup_workspace(db, [doc])
        else:
            p = Policy(tenant="one", name=doc.name, draft=doc.model_dump_json(), status="PUBLISHED", enabled=1)
            db.add(p)
            db.flush()
            v = Version(tenant="one", policy_id=p.id, number=1, document=doc.model_dump_json())
            db.add(v)
            db.flush()
            db.add(Assignment(tenant="one", version_id=v.id))
            db.commit()
    provider = AsyncMock(side_effect=AssertionError("held custom rule must not generate"))
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    result = submit(client, multi=multi, prompt="custom-needle exact unique prompt")
    assert result["decision"] == "HUMAN_REVIEW"
    with factory() as db:
        row = db.scalar(select(Content))
        assert secure.decrypt_prompt(row, db.get(Review, result["review_id"]).execution_id) == "custom-needle exact unique prompt"
        view = reporting_v2.execution(db, Identity("admin", "one", "Admin"), result["request_id"])
        assert "custom-needle" not in json.dumps(view)
        assert "original_prompt" not in json.dumps(view)
    provider.assert_not_awaited()


def test_cleanup_is_bounded_and_backlog_disables_capture(protected):
    _, engine, factory = protected
    install(factory)
    with factory() as db:
        policy = db.scalar(select(Policy))
        created = secure.clock(db) - secure.RETENTION - 1
        for _ in range(205):
            execution = Execution(tenant="one", actor="admin", policy_id=policy.id, version=1, model="fixture", decision="HUMAN_REVIEW", metadata_json="{}")
            db.add(execution)
            db.flush()
            review = Review(tenant="one", execution_id=execution.id)
            db.add(review)
            db.flush()
            db.add(secure.encrypt_prompt("synthetic expired prompt", "one", review.id, execution.id, created))
        db.commit()
    first = secure.cleanup_once(engine, factory)
    assert first["removed"] <= 200 and not first["healthy"]
    assert not secure.health.healthy(engine)
    for _ in range(10):
        if secure.cleanup_once(engine, factory)["healthy"]:
            break
    assert secure.health.healthy(engine)
    with factory() as db:
        assert db.scalar(select(Content)) is None


def test_feature_disabled_keeps_cleanup_but_never_reveals(protected, monkeypatch):
    client, engine, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    login(client)
    monkeypatch.setattr(settings, "review_capture_enabled", False)
    assert secure.cleanup_once(engine, factory)["healthy"]
    assert reveal(client, rid, version).status_code == 503
    metadata = client.get(f"/api/reviews/{rid}").json()["protected_content"]
    assert metadata["availability"] == "UNAVAILABLE" and not metadata["can_reveal"]


def test_historical_metadata_only_review_and_unassigned_reviewer(protected, monkeypatch):
    client, _, factory = protected
    install(factory)
    monkeypatch.setattr(settings, "review_capture_enabled", False)
    rid = submit(client)["review_id"]
    detail = client.get(f"/api/reviews/{rid}").json()
    assert detail["protected_content"]["availability"] == "NEVER_RETAINED"
    monkeypatch.setattr(settings, "review_capture_enabled", True)
    login(client)
    assert reveal(client, rid).status_code == 403


def test_wrong_key_bytes_fail_without_plaintext(protected, monkeypatch):
    row = secure.encrypt_prompt("DoNotLeak", "one", "r", "e", 100)
    monkeypatch.setattr(settings, "review_content_keys_json", json.dumps({"synthetic-v1": base64.b64encode(b"z" * 32).decode()}))
    with pytest.raises(HTTPException) as caught:
        secure.decrypt_prompt(row, "e")
    assert caught.value.status_code == 503 and "DoNotLeak" not in str(caught.value.detail)


def test_approval_never_generates_and_resubmission_reinspects(protected, monkeypatch, caplog):
    client, _, factory = protected
    install(factory)
    provider = AsyncMock(side_effect=AssertionError("held content must never generate"))
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    original = "internal-only sensitive original DoNotLog"
    rid = submit(client, prompt=original)["review_id"]
    assign(factory, rid)
    login(client)
    response = client.post(f"/api/reviews/{rid}/approve", json={"reason": "Resubmission required"})
    assert response.status_code == 200
    client.headers["Authorization"] = "Bearer admin"
    response = client.post("/api/governance/generate", json={"text": original, "source_review_id": rid})
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == "HUMAN_REVIEW" and response.json()["review_id"] != rid
    provider.assert_not_awaited()
    assert "DoNotLog" not in caplog.text


def test_access_audit_commit_failure_prevents_release(protected, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
    client, _, factory = protected
    install(factory)
    rid = submit(client)["review_id"]
    version = assign(factory, rid)
    login(client)
    original = Session.commit
    def commit(db):
        if getattr(db, "reveal_commit_test", False):
            raise OperationalError("synthetic", {}, RuntimeError("audit commit failure"))
        return original(db)
    audit = secure.record_audit_event
    def mark(db, user, action, resource):
        audit(db, user, action, resource)
        if action == "review.content.viewed":
            db.reveal_commit_test = True
    monkeypatch.setattr(secure, "record_audit_event", mark)
    monkeypatch.setattr(Session, "commit", commit)
    response = reveal(client, rid, version)
    assert response.status_code == 503 and "Please share" not in response.text
    with factory() as db:
        assert not list(db.scalars(select(Audit).where(Audit.action == "review.content.viewed")))


def test_provider_credentials_cannot_be_used_as_encryption_keys(protected, monkeypatch):
    monkeypatch.setattr(settings, "azure_openai_api_key", json.loads(settings.review_content_keys_json)["synthetic-v1"])
    with pytest.raises(HTTPException) as caught:
        secure.keyring()
    assert caught.value.status_code == 503
