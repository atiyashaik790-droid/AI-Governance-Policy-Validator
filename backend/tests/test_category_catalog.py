"""Standalone category CRUD and policy associations."""

from app.models import GovernanceCategory
from app.main import app


def payload(name="Sensitive finance"):
    return {
        "name": name,
        "description": "Synthetic finance terms",
        "enabled": True,
        "action": "BLOCK",
        "detection": "keyword",
        "values": ["private finance"],
    }


def test_category_lifecycle_and_draft_enforcement(client):
    created = client.post("/api/categories", json=payload())
    assert created.status_code == 201
    category = created.json()
    assert category["policy_ids"] == [] and not category["builtin"]
    category_id = category["id"]
    assert client.put(f"/api/categories/{category_id}", json=payload("Finance"), headers={"If-Match": '"0"'}).status_code == 412
    updated = client.put(f"/api/categories/{category_id}", json=payload("Finance"), headers={"If-Match": '"1"'})
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    policy = client.post("/api/policies", json={"name": "Finance policy"}).json()
    policy_id = policy["id"]
    assigned = client.put(f"/api/categories/{category_id}/policies/{policy_id}")
    assert assigned.status_code == 200 and assigned.json()["policy_ids"] == [policy_id]
    draft = client.get(f"/api/policies/{policy_id}").json()["draft"]
    assert category_id in draft
    assert client.delete(f"/api/categories/{category_id}", headers={"If-Match": '"2"'}).status_code == 409
    assert client.put(f"/api/categories/{category_id}", json=payload(), headers={"If-Match": '"2"'}).status_code == 409
    assert client.delete(f"/api/categories/{category_id}/policies/{policy_id}").status_code == 200
    assert client.delete(f"/api/categories/{category_id}", headers={"If-Match": '"2"'}).status_code == 200
    assert client.get(f"/api/categories/{category_id}").status_code == 404


def test_category_permissions_tenant_isolation_and_twenty_policies(client):
    category_id = client.post("/api/categories", json=payload()).json()["id"]
    policy_ids = []
    for number in range(20):
        created = client.post("/api/policies", json={"name": f"Policy {number:02}"})
        assert created.status_code == 201
        policy_ids.append(created.json()["id"])
        assert client.put(f"/api/categories/{category_id}/policies/{policy_ids[-1]}").status_code == 200
    listed = client.get(f"/api/categories/{category_id}").json()
    assert len(listed["policy_ids"]) == 20
    client.headers["Authorization"] = "Bearer foreign"
    assert client.get(f"/api/categories/{category_id}").status_code == 404
    assert client.put(f"/api/categories/{category_id}/policies/{policy_ids[0]}").status_code == 404
    client.headers["Authorization"] = "Bearer reviewer"
    assert client.get("/api/categories").status_code == 200
    assert client.post("/api/categories", json=payload("Other")).status_code == 403
    client.headers["Authorization"] = "Bearer admin"
    result = client.get("/api/categories?search=finance&enabled=true&limit=10")
    assert result.status_code == 200 and result.json()["total"] == 1


def test_builtin_category_is_protected(client):
    from app.database import get_database

    fixture_database = app.dependency_overrides[get_database]()
    db = next(fixture_database)
    db.add(
        GovernanceCategory(
            id="pii",
            tenant="*",
            name="PII",
            description="Personal information",
            builtin=1,
            enabled=1,
            detector="builtin",
            action="BLOCK",
            values_json="[]",
        )
    )
    db.commit()
    fixture_database.close()
    assert client.delete("/api/categories/pii", headers={"If-Match": '"1"'}).status_code == 403
    assert client.put("/api/categories/pii", json=payload("Changed"), headers={"If-Match": '"1"'}).status_code == 403


def test_inline_policy_category_is_registered_and_kept_in_sync(client):
    document = {
        "name": "Inline policy",
        "custom_categories": [
            {
                "id": "inline-finance",
                "name": "Inline finance",
                "action": "BLOCK",
                "detection": "keyword",
                "values": ["private finance"],
            }
        ],
    }
    created = client.post("/api/policies", json=document)
    assert created.status_code == 201, created.text
    policy_id = created.json()["id"]
    assert client.get("/api/categories/inline-finance").json()["policy_ids"] == [policy_id]
    document["custom_categories"][0]["description"] = "Reviewed draft rule"
    changed = client.put(f"/api/policies/{policy_id}", json=document, headers={"If-Match": str(created.json()["row_version"])})
    assert changed.status_code == 200, changed.text
    assert client.get("/api/categories/inline-finance").json()["description"] == "Reviewed draft rule"
    document["custom_categories"] = []
    removed = client.put(f"/api/policies/{policy_id}", json=document, headers={"If-Match": str(changed.json()["row_version"])})
    assert removed.status_code == 200, removed.text
    assert client.get("/api/categories/inline-finance").json()["policy_ids"] == []
