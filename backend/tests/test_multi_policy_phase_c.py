"""Local v2 HTTP contracts; fixture providers and disposable 005/006 only."""

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_database
from app.main import app
from app.models import Audit, Policy, SsoMembership, Version
from app.models_multi_policy import WorkspacePolicyAssignmentEvent as Event, WorkspacePolicyState as State
from app.services import policy_sets as domain
import test_multi_policy_bridge as phase_b_bridge
import test_multi_policy_phase_b as phase_b
from test_multi_policy_phase_b import fixture_engine, legacy, policy, ADMIN

# Reuse the disposable Phase B fixtures without changing their setup contracts.
bridge = phase_b_bridge.bridge
templates = phase_b.templates
template010 = phase_b.template010
engine006 = phase_b.engine010

BASE = "/api/v2/workspace"


def state(client):
    response = client.get(BASE + "/policy-state")
    assert response.status_code == 200, response.text
    return response


def mode(client, value="MULTI", **fields):
    return client.put(BASE + "/policy-mode", json={"mode": value, **fields}, headers={"If-Match": state(client).headers["etag"]})


def assign(client, pid, active=True, version=None, tag=None):
    body = {"active": active}
    if version is not None:
        body["version_id"] = version
    return client.put(BASE + f"/policy-assignments/{pid}", json=body,
                      headers={"If-Match": tag or state(client).headers["etag"]})


def records(engine, count=2):
    with Session(engine, expire_on_commit=False) as db:
        return [(p.id, v.id) for p, v in [policy(db, name=f"Policy {i}") for i in range(count)]]


def test_independent_assignments_counts_noops_and_history(bridge, engine006):
    pins = records(engine006)
    initial = state(bridge)
    assert initial.json() == {"mode": "LEGACY", "multi_policy_available": True, "set_revision": 1, "active_policy_count": 0}
    with Session(engine006) as db:
        assert db.scalar(select(func.count()).select_from(State)) == 0  # GET has no initialization side effects.
    assert assign(bridge, pins[0][0], version=pins[0][1]).status_code == 409
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    for pid, vid in pins:
        assert assign(bridge, pid, version=vid).status_code == 200
    assert state(bridge).json()["active_policy_count"] == 2
    page = bridge.get(BASE + "/policy-assignments?limit=1&offset=1")
    assert page.status_code == 200 and len(page.json()["items"]) == 1
    assert page.json()["total"] == page.json()["active_policy_count"] == 2
    assert "tenant" not in page.json()["items"][0]
    tag = state(bridge).headers["etag"]
    with Session(engine006) as db:
        before = db.scalar(select(func.count()).select_from(Event))
        audits = db.scalar(select(func.count()).select_from(Audit))
    noop = assign(bridge, pins[0][0], version=pins[0][1], tag=tag)
    assert noop.status_code == 200 and noop.headers["etag"] == tag
    assert mode(bridge, seed_legacy_assignment=False).headers["etag"] == tag
    with Session(engine006) as db:
        assert db.scalar(select(func.count()).select_from(Event)) == before
        assert db.scalar(select(func.count()).select_from(Audit)) == audits
    assert assign(bridge, pins[0][0], active=False).status_code == 200
    assert state(bridge).json()["active_policy_count"] == 1
    tag = state(bridge).headers["etag"]
    assert assign(bridge, pins[0][0], active=False).headers["etag"] == tag
    events = bridge.get(BASE + "/policy-assignment-events?limit=2").json()
    assert len(events["items"]) == 2 and events["total"] == before + 1
    assert events["items"][0]["event_type"] == "DEACTIVATE"
    assert events["items"][0]["actor"] == "admin"
    with Session(engine006) as db:
        actions = list(db.scalars(select(Audit.action)))
        assert actions.count("policy.assignment.activate") == 2
        assert actions.count("policy.assignment.deactivate") == 1


def test_explicit_pinning_and_no_automatic_upgrade(bridge, engine006):
    (pid, vid), = records(engine006, 1)
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    assert assign(bridge, pid).status_code == 422
    assert assign(bridge, pid, version=vid).status_code == 200
    with Session(engine006, expire_on_commit=False) as db:
        p = db.get(Policy, pid)
        v2 = Version(tenant="one", policy_id=pid, number=2, document=p.draft)
        db.add(v2)
        db.commit()
        newer = v2.id
    assert bridge.get(BASE + "/policy-assignments").json()["items"][0]["version_id"] == vid
    assert assign(bridge, pid, version=newer).status_code == 200
    latest = bridge.get(BASE + "/policy-assignment-events").json()["items"][0]
    assert (latest["event_type"], latest["old_version_id"], latest["new_version_id"]) == ("REPIN", vid, newer)
    assert assign(bridge, pid, active=False, version=newer).status_code == 422


@pytest.mark.parametrize("ineligible", ["disabled", "ARCHIVED", "DELETED", "unpublished"])
def test_ineligible_policy_cannot_activate(bridge, engine006, ineligible):
    (pid, vid), = records(engine006, 1)
    with Session(engine006) as db:
        p = db.get(Policy, pid)
        if ineligible == "disabled":
            p.enabled = 0
        elif ineligible != "unpublished":
            p.status = ineligible
        db.commit()
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    result = assign(bridge, pid, version="not-a-published-version" if ineligible == "unpublished" else vid)
    assert result.status_code == (404 if ineligible == "unpublished" else 409)
    assert state(bridge).json()["active_policy_count"] == 0


def test_v2_mode_keeps_v1_guards_and_requires_one_legacy_survivor(bridge, engine006, monkeypatch):
    from app import providers
    pins = records(engine006)
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    for pid, vid in pins:
        assert assign(bridge, pid, version=vid).status_code == 200
    assert mode(bridge, "LEGACY", legacy_version_id=pins[0][1]).status_code == 409
    provider = AsyncMock(side_effect=AssertionError("No provider permitted"))
    monkeypatch.setattr(providers, "generate_ai_response", provider)
    assert bridge.post("/api/governance/generate", json={"text": "Withhold"}).status_code == 409
    pid = pins[0][0]
    for operation in ["activate", "disable", "archive"]:
        assert bridge.post(f"/api/policies/{pid}/{operation}").status_code == 409
    provider.assert_not_awaited()


def test_browser_can_read_etag_header(bridge):
    response = bridge.get(BASE + "/policy-state", headers={"Origin": settings.cors_origin})
    assert response.status_code == 200
    assert "etag" in response.headers["access-control-expose-headers"].lower()


def test_listing_counts_are_not_limited_to_first_hundred(bridge, engine006):
    pins = records(engine006, 105)
    with Session(engine006) as db:
        revision = domain.change_mode(db, ADMIN, "MULTI", expected_revision=1, seed_legacy_assignment=False)
        for pid, vid in pins:
            revision = domain.change_assignment(db, ADMIN, pid, active=True, version_id=vid, expected_revision=revision)
    first = bridge.get(BASE + "/policy-assignments?limit=100").json()
    last = bridge.get(BASE + "/policy-assignments?limit=100&offset=100").json()
    assert len(first["items"]) == 100 and len(last["items"]) == 5
    assert first["total"] == last["total"] == first["active_policy_count"] == 105
    assert len({item["policy_id"] for item in first["items"] + last["items"]}) == 105
    events = bridge.get(BASE + "/policy-assignment-events?limit=100&offset=100").json()
    assert events["total"] == 107 and len(events["items"]) == 7


@pytest.mark.parametrize("header,expected", [(None, 428), ('W/"1"', 412), ("*", 412), ("1", 412), ('"1", "2"', 412), ('"999"', 412)])
def test_precondition_validation(bridge, header, expected):
    response = bridge.put(BASE + "/policy-mode", json={"mode": "MULTI", "seed_legacy_assignment": False},
                          headers={"If-Match": header} if header is not None else {})
    assert response.status_code == expected
    assert state(bridge).json()["set_revision"] == 1


def test_same_etag_parallel_requests_have_one_winner(bridge, engine006):
    pins = records(engine006)
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    tag = state(bridge).headers["etag"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pin: assign(bridge, pin[0], version=pin[1], tag=tag), pins))
    assert sorted(r.status_code for r in results) == [200, 412]
    assert state(bridge).json()["active_policy_count"] == 1


def test_mode_transitions_reservations_and_explicit_survivor(bridge, engine006):
    (pid, vid), = records(engine006, 1)
    assert mode(bridge).status_code == 422
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    assert assign(bridge, pid, version=vid).status_code == 200
    with Session(engine006) as db:
        reservation = domain.admit(db, ADMIN)
    assert mode(bridge, "LEGACY", legacy_version_id=vid).status_code == 409
    with Session(engine006) as db:
        assert domain.finish_admission(db, ADMIN, reservation, "FAILED")
    assert mode(bridge, "LEGACY").status_code == 422
    assert mode(bridge, "LEGACY", legacy_version_id=vid).status_code == 200
    assert state(bridge).json()["active_policy_count"] == 1
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    assert state(bridge).json()["active_policy_count"] == 0


def test_tenant_isolation_and_rejected_client_tenant(bridge, engine006):
    (pid, vid), (other, wrong_version) = records(engine006)
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    assert assign(bridge, pid, version=wrong_version).status_code == 404
    assert assign(bridge, pid, version=vid).status_code == 200
    bridge.headers["Authorization"] = "Bearer foreign"
    assert state(bridge).json()["set_revision"] == 1
    assert bridge.get(BASE + "/policy-assignments?tenant=one").json()["total"] == 0
    assert bridge.get(BASE + "/policy-assignment-events?tenant=one").json()["total"] == 0
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    assert assign(bridge, pid, version=vid).status_code == 404
    assert assign(bridge, pid, active=False).status_code == 404
    assert mode(bridge, "LEGACY", legacy_version_id=vid).status_code == 404
    response = bridge.put(BASE + "/policy-mode", headers={"If-Match": state(bridge).headers["etag"]},
                          json={"mode": "MULTI", "tenant": "one"})
    assert response.status_code == 422


@pytest.mark.parametrize("role", ["developer", "auditor", "reviewer"])
def test_roles_can_read_but_cannot_mutate(bridge, role):
    bridge.headers["Authorization"] = "Bearer " + role
    assert state(bridge).status_code == 200
    for path, body in [("/policy-mode", {"mode": "MULTI", "seed_legacy_assignment": False}),
                       ("/policy-assignments/unknown", {"active": False})]:
        assert bridge.put(BASE + path, json=body, headers={"If-Match": '"1"'}).status_code == 403
    bridge.headers.pop("Authorization")
    assert bridge.get(BASE + "/policy-state").status_code == 401


@pytest.mark.parametrize("payload", [{"mode": "multi"}, {"mode": "MULTI", "seed_legacy_assignment": "false"}, {"mode": "MULTI", "tenant": "two"}])
def test_strict_mode_payload(bridge, payload):
    assert bridge.put(BASE + "/policy-mode", json=payload, headers={"If-Match": '"1"'}).status_code == 422


@pytest.mark.parametrize("suffix", ["?limit=0", "?limit=101", "?offset=-1"])
def test_pagination_bounds(bridge, suffix):
    for path in ["/policy-assignments", "/policy-assignment-events"]:
        assert bridge.get(BASE + path + suffix).status_code == 422


def test_schema_005_fallback_never_queries_006_tables(client, templates, tmp_path):
    import shutil
    path = tmp_path / "legacy005.db"
    shutil.copyfile(templates["005"], path)
    engine = fixture_engine(path)
    statements = []
    @event.listens_for(engine, "before_cursor_execute")
    def capture(_connection, _cursor, statement, *_args):
        statements.append(statement.lower())
    def dependency():
        with Session(engine, expire_on_commit=False) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_database] = dependency
    with Session(engine) as db:
        legacy(db)
    response = state(client)
    assert response.json() == {"mode": "LEGACY", "multi_policy_available": False, "set_revision": None, "active_policy_count": 1}
    assert "etag" not in response.headers
    for path in ["/policy-assignments", "/policy-assignment-events"]:
        assert client.get(BASE + path).status_code == 503
    assert client.put(BASE + "/policy-mode", json={"mode": "MULTI", "seed_legacy_assignment": False}, headers={"If-Match": '"1"'}).status_code == 503
    assert assign(client, "missing", active=False, tag='"1"').status_code == 503
    assert client.get("/api/policies").status_code == 200
    assert client.post("/api/policies", json={"name": "Legacy still works"}).status_code == 201
    assert not any(any(name in sql for name in ["workspace_policy_states", "workspace_policy_assignments", "workspace_policy_assignment_events", "execution_policy_evidence"]) for sql in statements)
    engine.dispose()


def test_audit_failure_rolls_back_entire_mutation(bridge, engine006, monkeypatch):
    (pid, vid), = records(engine006, 1)
    assert mode(bridge, seed_legacy_assignment=False).status_code == 200
    tag = state(bridge).headers["etag"]
    before = bridge.get(BASE + "/policy-assignment-events").json()["total"]
    def fail(*_args):
        raise RuntimeError("synthetic audit persistence failure")
    monkeypatch.setattr(domain, "record_audit_event", fail)
    assert assign(bridge, pid, version=vid, tag=tag).status_code == 500
    assert state(bridge).headers["etag"] == tag
    assert bridge.get(BASE + "/policy-assignments").json()["total"] == 0
    assert bridge.get(BASE + "/policy-assignment-events").json()["total"] == before


@pytest.mark.parametrize("role,expected", [("Admin", 200), ("Reviewer", 403)])
def test_existing_sso_csrf_applies_to_v2(bridge, engine006, monkeypatch, role, expected):
    from app import sso
    directory = "11111111-1111-4111-8111-111111111111"
    oid = "33333333-3333-4333-8333-333333333333"
    for key, value in {"sso_enabled": True, "demo_browser_login_enabled": False, "entra_tenant_id": directory,
                       "entra_client_id": "22222222-2222-4222-8222-222222222222", "entra_client_secret": "synthetic-only",
                       "sso_public_origin": "https://testserver"}.items():
        monkeypatch.setattr(settings, key, value)
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
    assert state(bridge).status_code == 200
    body = {"mode": "MULTI", "seed_legacy_assignment": False}
    assert bridge.put(BASE + "/policy-mode", json=body, headers={"If-Match": '"1"'}).status_code == 403
    assert bridge.put(BASE + "/policy-mode", json=body, headers={"If-Match": '"1"', "Origin": "https://evil.invalid", "X-CSRF-Token": csrf}).status_code == 403
    headers = {"If-Match": '"1"', "Origin": "https://testserver", "X-CSRF-Token": csrf}
    assert bridge.put(BASE + "/policy-mode", json=body, headers=headers).status_code == expected
    assert bridge.post("/api/sso/logout", headers=headers).status_code == 200
    assert bridge.get(BASE + "/policy-state").status_code == 401
