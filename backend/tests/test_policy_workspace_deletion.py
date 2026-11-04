"""Workspace deletion preserves published evidence and rejects stale or active deletes."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from app.main import delete_draft_policy, transition_policy
from app.models import Base, Policy, Version, Assignment
from app.schemas import PolicyDocument
from app.security import Identity
from test_governance import activate


def etag(client, policy_id):
    return {"If-Match": str(client.get(f"/api/policies/{policy_id}").json()["row_version"])}


def test_published_policy_removed_from_workspace_but_history_remains(client):
    policy_id, _ = activate(client)
    result = client.post("/api/governance/generate", json={"text": "Safe fixture request"}).json()
    versions = client.get(f"/api/policies/{policy_id}/versions").json()
    activate(client)  # Move the tenant assignment to another enabled policy.
    assert client.delete(f"/api/policies/{policy_id}", headers=etag(client, policy_id)).status_code == 409
    client.post(f"/api/policies/{policy_id}/disable")
    assert client.delete(f"/api/policies/{policy_id}").status_code == 428
    assert client.delete(f"/api/policies/{policy_id}", headers={"If-Match": "0"}).status_code == 412
    response = client.delete(f"/api/policies/{policy_id}", headers=etag(client, policy_id))
    assert response.status_code == 200 and response.json()["history_retained"]
    for query in ("", "?search=Test", "?enabled=false", "?status=ARCHIVED"):
        assert all(row["id"] != policy_id for row in client.get("/api/policies" + query).json())
    assert client.get(f"/api/policies/{policy_id}").json()["status"] == "DELETED"
    assert client.get(f"/api/policies/{policy_id}/versions").json() == versions
    assert any(row["id"] == result["request_id"] for row in client.get("/api/audit/executions").json())
    assert any(
        row["action"] == "policy.removed" and row["resource"] == policy_id for row in client.get("/api/audit/events?category=policy").json()
    )
    assert client.get("/api/analytics/overview").json()["total_policies"] == 1
    assert client.put(f"/api/policies/{policy_id}", json={"name": "Revive"}, headers=etag(client, policy_id)).status_code == 404
    for operation in ("enable", "disable", "activate", "submit", "approve", "publish", "archive"):
        assert client.post(f"/api/policies/{policy_id}/{operation}").status_code == 404
    assert client.post(f"/api/policies/{policy_id}/rollback", json={"version": 1}).status_code == 404
    assert client.post(f"/api/policies/{policy_id}/simulate", json={"text": "safe"}).status_code == 404
    assert client.delete(f"/api/policies/{policy_id}", headers=etag(client, policy_id)).status_code == 404
    client.headers["Authorization"] = "Bearer foreign"
    assert client.get(f"/api/policies/{policy_id}").status_code == 404
    assert client.get(f"/api/policies/{policy_id}/versions").status_code == 404


def test_disabled_active_policy_and_read_only_roles_cannot_delete(client):
    policy_id, _ = activate(client)
    client.post(f"/api/policies/{policy_id}/disable")
    headers = etag(client, policy_id)
    response = client.delete(f"/api/policies/{policy_id}", headers=headers)
    assert response.status_code == 409 and "Activate another policy" in response.text
    for role in ("developer", "auditor", "reviewer"):
        client.headers["Authorization"] = "Bearer " + role
        assert client.delete(f"/api/policies/{policy_id}", headers=headers).status_code == 403


def test_stale_activation_cannot_reassign_deleted_policy(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "activation.db"))
    Base.metadata.create_all(engine)
    user = Identity("admin", "one", "Admin")
    with Session(engine) as setup:
        policy = Policy(tenant="one", name="Retained", draft=PolicyDocument(name="Retained").model_dump_json(), status="PUBLISHED")
        setup.add(policy)
        setup.flush()
        identifier = policy.id
        setup.add(Version(tenant="one", policy_id=identifier, number=1, document=policy.draft))
        setup.commit()
    with Session(engine, expire_on_commit=False) as stale:
        original = stale.scalar(select(Policy).where(Policy.id == identifier))
        assert original.enabled == 1
        with Session(engine) as current:
            transition_policy(identifier, "disable", current, user)
            current.commit()
            version = current.get(Policy, identifier).row_version
            delete_draft_policy(identifier, current, user, str(version))
            current.commit()
        with pytest.raises(StaleDataError):
            transition_policy(identifier, "activate", stale, user)
        stale.rollback()
    with Session(engine) as check:
        assert check.get(Policy, identifier).status == "DELETED"
        assert check.get(Assignment, "one") is None
    engine.dispose()
