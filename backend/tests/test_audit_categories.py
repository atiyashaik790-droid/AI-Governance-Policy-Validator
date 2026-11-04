"""Audit histories remain separate before pagination and cannot cross tenant boundaries."""

from app.main import app, get_database
from app.models import Audit


def test_audit_categories_filter_before_pagination(client):
    dependency = app.dependency_overrides[get_database]()
    db = next(dependency)
    for index, action in enumerate(
        [
            "policy.created",
            "governance.generate.ALLOW",
            "session.created",
            "policy.publish",
            "governance.generate.BLOCK",
            "policy.simulated",
        ]
    ):
        db.add(Audit(tenant="one", actor="admin", action=action, resource="fixture", created=f"2026-11-01T00:00:0{index}"))
    db.add(Audit(tenant="two", actor="foreign", action="policy.created", resource="private"))
    try:
        next(dependency)
    except StopIteration:
        pass
    assert [r["action"] for r in client.get("/api/audit/events?category=policy&limit=1&offset=1").json()] == ["policy.publish"]
    assert [r["action"] for r in client.get("/api/audit/events?category=governance").json()] == [
        "governance.generate.BLOCK",
        "governance.generate.ALLOW",
    ]
    assert [r["action"] for r in client.get("/api/audit/events?category=administration").json()] == ["session.created"]
    rows = client.get("/api/audit/events").json()
    assert len(rows) == 6 and all(r["tenant"] == "one" for r in rows)
    assert client.get("/api/audit/events?category=invalid").status_code == 422
