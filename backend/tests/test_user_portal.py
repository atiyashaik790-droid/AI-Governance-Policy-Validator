"""Least-privileged synthetic accounts, durable snapshots and read-only audit views."""
import hashlib
import json
import shutil
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import providers, sso
from app.config import settings
from app.models import Audit, Execution, SsoMembership
from app.models_multi_policy import Execution006
from app.chat_models import ChatConversation, ChatMessage
from app.chat_history import record_turn
from app.security import Identity
from app.services.audit_attribution import execution_attribution
import test_multi_policy_bridge as phase_bridge
import test_multi_policy_phase_b as phase_b
import test_multi_policy_phase_d as phase_d
import test_document_uploads as uploads

templates = phase_b.templates
bridge = phase_bridge.bridge


@pytest.fixture
def engine006(templates, tmp_path, monkeypatch):
    """Exercise current portal behavior on a disposable current-schema database."""
    path = tmp_path / "portal.db"
    shutil.copyfile(templates["006"], path)
    phase_b.migrate(path, "011")
    monkeypatch.setattr(settings, "inference_daily_quota", 100000)
    monkeypatch.setattr(settings, "inference_tenant_per_minute", 100000)
    monkeypatch.setattr(settings, "inference_user_per_minute", 100000)
    engine = phase_b.fixture_engine(path)
    yield engine
    engine.dispose()


def user_account(client, monkeypatch, role="User", tenant="one"):
    accounts = json.loads(settings.demo_accounts_json)
    accounts.append({"user": "actual.user@example.test", "tenant": tenant, "role": role,
                     "token_hash": hashlib.sha256(b"synthetic-user").hexdigest()})
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    client.headers["Authorization"] = "Bearer synthetic-user"


def workspace(bridge, db, mode, decision):
    doc = uploads.policy("BLOCK" if decision == "ALLOW" else decision)
    doc.name = "Retained Finance Policy"
    if mode == "MULTI":
        phase_d.setup_workspace(db, [doc, phase_d.document(name="Second pinned policy")])
        return "/api/v2", {"If-Match": bridge.get("/api/v2/workspace/policy-state").headers["etag"]}
    row = bridge.post("/api/policies", json=doc.model_dump()).json()
    for operation in ["submit", "approve", "publish", "activate"]:
        assert bridge.post(f"/api/policies/{row['id']}/{operation}").status_code == 200
    return "/api", {}


@pytest.mark.parametrize("mode", ["LEGACY", "MULTI"])
@pytest.mark.parametrize("attachment", [False, True])
@pytest.mark.parametrize("decision,calls", [("ALLOW", 1), ("BLOCK", 0), ("HUMAN_REVIEW", 0), ("REDACT", 1)])
def test_user_requests_are_governed_and_history_has_durable_server_identity(bridge, engine006, monkeypatch, mode, attachment, decision, calls):
    with Session(engine006, expire_on_commit=False) as db:
        prefix, headers = workspace(bridge, db, mode, decision)
    user_account(bridge, monkeypatch)
    generate = AsyncMock(return_value="public reply")
    monkeypatch.setattr(providers, "generate_ai_response", generate)
    text = "public" if decision == "ALLOW" else "private finance"
    response = bridge.post(prefix + "/governance/" + ("generate-document" if attachment else "generate"),
                           json=uploads.payload(text=text) if attachment else {"text": text}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"] == decision and generate.await_count == calls
    assert bool(body["safe_response"]) == bool(calls)
    assert all(name not in body for name in ["policy_id", "policy_name", "provider_diagnostics", "execution_identity"])
    assert "Retained Finance Policy" not in response.text and "custom:private" not in response.text
    assert "findings" not in response.text and "document_sha256" not in response.text
    assert "safe_text" not in response.text and "private finance" not in response.text
    model = Execution006 if mode == "MULTI" else Execution
    with Session(engine006) as db:
        row = db.get(model, body["request_id"])
        metadata = json.loads(row.metadata_json)
        assert metadata["execution_identity"]["actor"] == row.actor == "actual.user@example.test"
        assert metadata["execution_identity"]["role"] == "User"
        assert metadata["execution_identity"]["tenant"] == "one"
        assert "private finance" not in row.metadata_json
    # A later membership role change cannot rewrite the historical role.
    accounts = json.loads(settings.demo_accounts_json)
    accounts[-1]["role"] = "Developer"
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    bridge.headers["Authorization"] = "Bearer admin"
    history = bridge.get("/api/v2/audit/executions").json()
    assert history["total"] == 1
    item = history["items"][0]
    assert item["actor"] == "actual.user@example.test" and item["actor_role"] == "User"
    assert "Retained Finance Policy" in item["policy_names"]
    detail = bridge.get("/api/v2/audit/executions/" + body["request_id"]).json()
    assert all(p["version"] == 1 for p in detail["policies"])
    if mode == "MULTI":
        assert len(detail["policies"]) == 2 and len(detail["policy_evidence"]) == 2
    bridge.headers["Authorization"] = "Bearer foreign"
    assert bridge.get("/api/v2/audit/executions/" + body["request_id"]).status_code == 404
    assert bridge.get("/api/v2/audit/executions").json()["total"] == 0


@pytest.mark.parametrize("decision", ["ALLOW", "REDACT", "BLOCK", "HUMAN_REVIEW"])
def test_user_chat_history_retains_only_safe_display_content(bridge, engine006, monkeypatch, decision):
    with Session(engine006, expire_on_commit=False) as db:
        prefix, headers = workspace(bridge, db, "MULTI", decision)
    user_account(bridge, monkeypatch)
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(return_value="public reply"))
    created = bridge.post("/api/chat/conversations")
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    prompt = "public" if decision == "ALLOW" else "private finance"
    response = bridge.post(prefix + "/governance/generate", json={"text": prompt, "conversation_id": conversation_id}, headers=headers)
    assert response.status_code == 200, response.text
    detail = bridge.get("/api/chat/conversations/" + conversation_id)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert response.json()["request_id"] not in detail.text
    assert "private finance" not in detail.text
    if decision == "ALLOW":
        assert messages[0]["content"] == "public" and messages[1]["content"] == "public reply"
    elif decision == "REDACT":
        assert messages[0]["content"] != prompt and messages[1]["content"] == "public reply"
    elif decision == "BLOCK":
        assert messages[0]["content"] == "Request submitted"
        assert "restricted information" in messages[1]["content"]
    else:
        assert messages[0]["content"] == "Request submitted"
        assert "requires review" in messages[1]["content"]
    with Session(engine006) as db:
        assert db.query(ChatConversation).count() == 1
        assert db.query(ChatMessage).count() == 2
        assert db.query(Audit).count() >= 1


def test_chat_history_survives_relogin_and_enforces_user_and_workspace(bridge, engine006, monkeypatch):
    user_account(bridge, monkeypatch)
    first = bridge.post("/api/chat/conversations").json()["id"]
    second = bridge.post("/api/chat/conversations").json()["id"]
    assert [row["id"] for row in bridge.get("/api/chat/conversations").json()] == [second, first]
    first_session = bridge.post("/api/auth/session").json()["access_token"]
    bridge.headers["Authorization"] = "Bearer " + first_session
    assert bridge.get("/api/chat/conversations/" + first).status_code == 200
    assert bridge.post("/api/auth/logout").status_code == 200
    bridge.headers["Authorization"] = "Bearer synthetic-user"
    second_session = bridge.post("/api/auth/session").json()["access_token"]
    bridge.headers["Authorization"] = "Bearer " + second_session
    assert bridge.get("/api/chat/conversations/" + first).status_code == 200
    accounts = json.loads(settings.demo_accounts_json)
    accounts.append({"user": "other.user@example.test", "tenant": "one", "role": "User",
                     "token_hash": hashlib.sha256(b"another-user").hexdigest()})
    accounts.append({"user": "actual.user@example.test", "tenant": "two", "role": "User",
                     "token_hash": hashlib.sha256(b"other-workspace").hexdigest()})
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    for token in ("another-user", "other-workspace"):
        bridge.headers["Authorization"] = "Bearer " + token
        assert bridge.get("/api/chat/conversations").json() == []
        assert bridge.get("/api/chat/conversations/" + first).status_code == 404


def test_output_block_never_retains_input_or_model_text(engine006):
    user = Identity("chat.user@example.test", "one", "User")
    with Session(engine006, expire_on_commit=False) as db:
        conversation = ChatConversation(tenant=user.tenant, actor=user.user)
        db.add(conversation)
        db.flush()
        record_turn(db, user, conversation.id, {
            "decision": "BLOCK", "generation_status": "SUCCEEDED",
            "input": {"decision": "ALLOW", "safe_text": "Original prompt that must not be retained"},
            "output": {"decision": "BLOCK", "safe_text": None},
            "safe_response": "Unapproved model text", "model_invoked": True,
        })
        db.commit()
        contents = [row.content for row in db.query(ChatMessage).all()]
    assert contents[0] == "Request submitted"
    assert "restricted information" in contents[1]
    assert "Original prompt" not in " ".join(contents)
    assert "Unapproved model text" not in " ".join(contents)


@pytest.mark.parametrize("path,method", [
    ("/api/policies", "GET"), ("/api/policies", "POST"), ("/api/policies/missing", "GET"),
    ("/api/policies/missing/versions", "GET"), ("/api/policies/missing/simulate", "POST"),
    ("/api/settings", "GET"), ("/api/capabilities", "GET"), ("/api/audit/events", "GET"),
    ("/api/audit/executions", "GET"), ("/api/v2/audit/events", "GET"), ("/api/v2/audit/executions", "GET"),
    ("/api/v2/audit/executions/missing", "GET"), ("/api/v2/analytics/overview", "GET"),
    ("/api/v2/workspace/policy-assignments", "GET"), ("/api/v2/workspace/policy-mode", "PUT"),
    ("/api/v2/reviews", "GET"), ("/api/reviews", "GET"), ("/api/feedback/summary", "GET"),
    ("/api/auth/sessions", "GET"), ("/api/v2/reports/export", "POST"),
    ("/api/governance/validate-input", "POST"), ("/api/v2/governance/validate-output", "POST"),
])
def test_user_cannot_access_privileged_apis(client, monkeypatch, path, method):
    user_account(client, monkeypatch)
    assert client.request(method, path, json={}).status_code == 403


def test_unknown_roles_and_client_identity_fail_closed(client, monkeypatch):
    user_account(client, monkeypatch, role="Unknown")
    assert client.get("/api/policies").status_code == 403
    accounts = json.loads(settings.demo_accounts_json)
    accounts[-1]["role"] = "User"
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    assert client.post("/api/governance/generate", json={"text": "public", "actor": "admin", "role": "Admin"}).status_code == 422


@pytest.mark.parametrize("role", ["Admin", "Policy Owner", "Reviewer", "Auditor", "Developer"])
def test_existing_roles_retain_policy_read_access(client, monkeypatch, role):
    user_account(client, monkeypatch, role=role)
    assert client.get("/api/policies").status_code == 200


@pytest.mark.parametrize("mode", ["LEGACY", "MULTI"])
def test_execution_snapshots_are_append_only_and_old_records_do_not_infer_role(bridge, engine006, mode):
    with Session(engine006, expire_on_commit=False) as db:
        prefix, headers = workspace(bridge, db, mode, "ALLOW")
    response = bridge.post(prefix + "/governance/generate", json={"text": "public"}, headers=headers)
    assert response.status_code == 200
    model = Execution006 if mode == "MULTI" else Execution
    with Session(engine006) as db:
        row = db.get(model, response.json()["request_id"])
        row.metadata_json = "{}"
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
        db.rollback()
        db.delete(db.get(model, response.json()["request_id"]))
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
    with Session(engine006) as db:
        p, v = phase_b.policy(db)
        old = Execution(tenant="one", actor="old.actor", policy_id=p.id, version=v.number, model="fixture", decision="ALLOW", metadata_json="{}")
        db.add(old)
        db.commit()
        from app.security import Identity
        value = execution_attribution(db, Identity("admin", "one", "Admin"), old)
        assert value["actor_role"] == "Historical role unavailable" and value["execution_identity"] is None


def test_policy_and_administrative_history_are_named_without_role_backfill(bridge, engine006):
    with Session(engine006, expire_on_commit=False) as db:
        workspace(bridge, db, "LEGACY", "ALLOW")
    events = bridge.get("/api/v2/audit/events?category=policy&limit=1&offset=0").json()
    assert events["total"] >= 4 and len(events["items"]) == 1
    item = events["items"][0]
    assert item["policy_name"] == "Retained Finance Policy" and item["actor"] == "admin"
    assert item["actor_role"] == "Admin"
    with Session(engine006) as db:
        db.add(Audit(tenant="one", actor="actual.user@example.test", action="sso.session.created", resource="synthetic"))
        db.commit()
    admin = bridge.get("/api/v2/audit/events?category=administration").json()["items"][0]
    assert admin["actor"] == "actual.user@example.test" and admin["policy_name"] == "Not applicable"
    assert admin["actor_role"] == "Historical role unavailable"


@pytest.mark.parametrize("role", ["User", "Admin"])
def test_sso_role_routing_identity_snapshot_csrf_and_login_logout_audit(bridge, engine006, monkeypatch, role):
    with Session(engine006, expire_on_commit=False) as db:
        workspace(bridge, db, "LEGACY", "ALLOW")
    directory = "11111111-1111-4111-8111-111111111111"
    oid = "33333333-3333-4333-8333-333333333333"
    for key, value in {"sso_enabled": True, "demo_browser_login_enabled": False, "entra_tenant_id": directory,
        "entra_client_id": "22222222-2222-4222-8222-222222222222", "entra_client_secret": "synthetic-only", "sso_public_origin": "https://testserver"}.items():
        monkeypatch.setattr(settings, key, value)
    with Session(engine006) as db:
        db.add(SsoMembership(directory_tenant=directory, object_id=oid, tenant="one", actor="actual.account@example.test", role=role))
        db.commit()
    monkeypatch.setattr(sso, "metadata", AsyncMock(return_value={"authorization_endpoint": f"https://login.microsoftonline.com/{directory}/oauth2/v2.0/authorize"}))
    monkeypatch.setattr(sso, "exchange_code", AsyncMock(return_value={"tid": directory, "oid": oid}))
    bridge.headers.pop("Authorization")
    bridge.base_url = httpx.URL("https://testserver")
    login = bridge.get("/api/sso/login", follow_redirects=False)
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    assert bridge.get("/api/sso/callback", params={"state": state, "code": "fixture"}, follow_redirects=False).status_code == 303
    me = bridge.get("/api/sso/me").json()
    assert me["role"] == role and me["user"] == "actual.account@example.test"
    assert bridge.get("/api/sso/sessions").status_code == (403 if role == "User" else 200)
    headers = {"X-CSRF-Token": me["csrf_token"], "Origin": "https://testserver"}
    assert bridge.post("/api/governance/generate", json={"text": "public"}).status_code == 403
    assert bridge.post("/api/governance/generate", json={"text": "public"}, headers={**headers, "Origin": "https://foreign.invalid"}).status_code == 403
    response = bridge.post("/api/governance/generate", json={"text": "public"}, headers=headers)
    assert response.status_code == 200, response.text
    with Session(engine006) as db:
        metadata = json.loads(db.get(Execution, response.json()["request_id"]).metadata_json)
        assert metadata["execution_identity"]["object_id"] == oid
        assert metadata["execution_identity"]["directory_tenant"] == directory
        assert metadata["execution_identity"]["role"] == role
    assert bridge.post("/api/sso/logout", headers=headers).status_code == 200
    assert bridge.get("/api/sso/me").status_code == 401
    with Session(engine006) as db:
        assert {(e.action, e.actor) for e in db.scalars(select(Audit).where(Audit.action.like("sso.%")))} == {
            ("sso.session.created", "actual.account@example.test"), ("sso.session.revoked", "actual.account@example.test")}


@pytest.mark.parametrize("mode", ["LEGACY", "MULTI"])
@pytest.mark.parametrize("kind", ["pdf", "docx"])
def test_user_pdf_and_docx_use_existing_governance(bridge, engine006, monkeypatch, mode, kind):
    with Session(engine006, expire_on_commit=False) as db:
        prefix, headers = workspace(bridge, db, mode, "BLOCK")
    user_account(bridge, monkeypatch)
    provider = AsyncMock(side_effect=AssertionError("Held document must not generate"))
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    response = bridge.post(prefix + "/governance/generate-document", json=uploads.payload(kind, text="private finance"), headers=headers)
    assert response.status_code == 200 and response.json()["decision"] == "BLOCK"
    assert response.json()["attachment"]["type"] == kind
    assert "private finance" not in response.text and "Retained Finance Policy" not in response.text
    provider.assert_not_awaited()


def test_identity_snapshot_rejects_unknown_extra_and_cross_tenant_data():
    from types import SimpleNamespace
    from app.execution_identity import recorded_identity
    row = SimpleNamespace(actor="actor", tenant="one")
    for value in [{"actor": "actor", "tenant": "two", "role": "Admin"},
                  {"actor": "actor", "tenant": "one", "role": "Unknown"},
                  {"actor": "actor", "tenant": "one", "role": "User", "secret": "MustNotEscape"}]:
        assert recorded_identity(row, {"execution_identity": value}) is None


@pytest.mark.parametrize("decision", ["ALLOW", "REDACT", "BLOCK"])
def test_document_turn_keeps_only_governed_question_and_attachment_type(bridge, engine006, monkeypatch, decision):
    with Session(engine006, expire_on_commit=False) as db:
        prefix, headers = workspace(bridge, db, "MULTI", decision)
    user_account(bridge, monkeypatch)
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(return_value="public reply"))
    conversation_id = bridge.post("/api/chat/conversations").json()["id"]
    prompt = "Summarize this resume" if decision == "ALLOW" else "Summarize this private finance resume"
    body = uploads.payload("pdf", text="public document body", prompt=prompt) | {"conversation_id": conversation_id}
    assert bridge.post(prefix + "/governance/generate-document", json=body, headers=headers).status_code == 200
    detail = bridge.get("/api/chat/conversations/" + conversation_id).json()
    shown = detail["messages"][0]["content"]
    serialized = json.dumps(detail)
    # Extracted document text and the client filename are never retained.
    assert "public document body" not in serialized and "synthetic.pdf" not in serialized
    assert "private finance" not in serialized
    if decision == "ALLOW":
        assert shown == "Summarize this resume\n\nAttachment: PDF document"
        assert detail["title"] == "Resume Summary"
    elif decision == "REDACT":
        assert shown.startswith("Summarize this ") and shown.endswith("\n\nAttachment: PDF document")
        assert detail["title"] == "Resume Summary"
    else:
        assert shown == "Request submitted" and detail["title"] == "Document conversation"


def test_established_title_is_not_rewritten_by_later_turns(bridge, engine006, monkeypatch):
    with Session(engine006, expire_on_commit=False) as db:
        prefix, headers = workspace(bridge, db, "MULTI", "ALLOW")
    user_account(bridge, monkeypatch)
    monkeypatch.setattr(providers, "generate_ai_response", AsyncMock(return_value="public reply"))
    conversation_id = bridge.post("/api/chat/conversations").json()["id"]
    for text in ("What is AI governance?", "Explain Python decorators."):
        assert bridge.post(prefix + "/governance/generate", json={"text": text, "conversation_id": conversation_id},
                           headers=headers).status_code == 200
    detail = bridge.get("/api/chat/conversations/" + conversation_id).json()
    assert detail["title"] == "Understanding AI Governance"
    assert [m["content"] for m in detail["messages"] if m["role"] == "user"] == [
        "What is AI governance?", "Explain Python decorators."]
    assert bridge.get("/api/chat/conversations").json()[0]["title"] == "Understanding AI Governance"


@pytest.mark.parametrize("prompt,attachment,title", [
    ("What is AI governance?", None, "Understanding AI Governance"),
    ("Explain Python decorators.", None, "Python Decorators"),
    ("Summarize the uploaded resume", "pdf", "Resume Summary"),
    ("Tell me about Azure SQL connections", None, "Azure SQL Connections"),
    ("Explain what a data retention policy is", None, "Understanding Data Retention Policy"),
    ("", "docx", "DOCX Document"),
    ("[REDACTED]", None, "New conversation"),
])
def test_conversation_title_is_short_and_deterministic(prompt, attachment, title):
    from app.chat_history import conversation_title
    assert conversation_title(prompt, attachment) == title


@pytest.mark.parametrize("prompt", [
    "My email is jane.doe@example.com, summarise GDPR",
    "Use api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWX to call the service",
    "Call me on 9876543210 about payroll",
    "Reset password Hunter2Hunter2Hunter2Hunter2 for https://intranet.example.test/login",
    "Contact [REDACTED] at [REDACTED] about onboarding",
])
def test_conversation_title_excludes_sensitive_tokens(prompt):
    from app.chat_history import conversation_title
    title = conversation_title(prompt)
    assert 1 <= len(title.split()) <= 7
    for fragment in ("@", "jane", "sk-test", "9876543210", "Hunter2", "http", "intranet", "REDACTED", "="):
        assert fragment.lower() not in title.lower()


def test_document_question_requires_the_request_boundary():
    from app.chat_history import document_question
    marker = "a" * 32
    combined = f"USER PROMPT:\nSummarize it\n\nUNTRUSTED DOCUMENT DATA {marker} BEGIN\nsecret body\nUNTRUSTED DOCUMENT DATA {marker} END"
    assert document_question(combined) == "Summarize it"
    assert document_question(combined.replace(f"{marker} END", f"{'b' * 32} END")) is None
    assert document_question("Summarize it") is None


def test_event_role_is_an_immutable_snapshot_and_system_actors_have_none(bridge, engine006, monkeypatch):
    with Session(engine006, expire_on_commit=False) as db:
        workspace(bridge, db, "LEGACY", "ALLOW")
    before = {item["id"]: item["actor_role"] for item in
              bridge.get("/api/v2/audit/events?category=policy&limit=100&offset=0").json()["items"]}
    assert before and set(before.values()) == {"Admin"}
    # Later demotion of the same account must not rewrite event-time roles.
    accounts = json.loads(settings.demo_accounts_json)
    for account in accounts:
        if account["user"] == "admin":
            account["role"] = "Auditor"
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    after = {item["id"]: item["actor_role"] for item in
             bridge.get("/api/v2/audit/events?category=policy&limit=100&offset=0").json()["items"]}
    assert after == before
    with Session(engine006) as db:
        db.add(Audit(tenant="one", actor="system:review-cleanup", action="review.content.expired", resource="synthetic"))
        db.commit()
    system = [item for item in bridge.get("/api/v2/audit/events?category=administration&limit=100&offset=0").json()["items"]
              if item["actor"] == "system:review-cleanup"]
    assert system and system[0]["actor_role"] == "Not applicable"
    bridge.headers["Authorization"] = "Bearer foreign"
    assert bridge.get("/api/v2/audit/events?category=policy&limit=100&offset=0").json()["items"] == []
