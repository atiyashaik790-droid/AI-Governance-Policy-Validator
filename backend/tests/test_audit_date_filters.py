"""Tenant-scoped UTC history filtering on disposable schemas; no providers."""
from datetime import datetime, timedelta, timezone
import shutil

import pytest
from sqlalchemy.orm import Session

from app.models import Audit, Execution
from app.exports import date_bounds
import test_multi_policy_phase_b as phase_b
import test_multi_policy_bridge as phase_bridge

templates = phase_b.templates
bridge = phase_bridge.bridge
PATHS = ["/api/audit/events", "/api/audit/executions", "/api/v2/audit/events", "/api/v2/audit/executions"]


@pytest.fixture
def engine006(templates, tmp_path, monkeypatch):
    """Filter current audit records on a disposable current-schema database."""
    path = tmp_path / "audit-filters.db"
    shutil.copyfile(templates["006"], path)
    phase_b.migrate(path, "010")
    monkeypatch.setattr(phase_b.settings, "inference_daily_quota", 100000)
    monkeypatch.setattr(phase_b.settings, "inference_tenant_per_minute", 100000)
    monkeypatch.setattr(phase_b.settings, "inference_user_per_minute", 100000)
    engine = phase_b.fixture_engine(path)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded(bridge, engine006):
    day = datetime.now(timezone.utc).date() - timedelta(days=1)
    midnight = datetime.combine(day, datetime.min.time(), timezone.utc)
    moments = [midnight - timedelta(days=100), midnight - timedelta(microseconds=1), midnight,
               midnight + timedelta(days=1) - timedelta(microseconds=1), midnight + timedelta(days=1)]
    with Session(engine006, expire_on_commit=False) as db:
        policy, _ = phase_b.legacy(db)
        for tenant in ["one", "two"]:
            for index, moment in enumerate(moments):
                for category in ["policy.published", "governance.generate.ALLOW", "sso.session.created"]:
                    db.add(Audit(id=f"{tenant}-{index}-{category}", tenant=tenant, actor="synthetic", action=category,
                                 resource="synthetic", created=moment.isoformat()))
                db.add(Execution(id=f"{tenant}-exec-{index}", tenant=tenant, actor="synthetic", policy_id=policy.id,
                                 version=1, model="fixture", decision="ALLOW", metadata_json="{}", created=moment.isoformat()))
        db.commit()
    return bridge, day, moments


def items(response):
    value = response.json()
    return value["items"] if isinstance(value, dict) else value


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("selection", ["none", "start", "end", "both", "same"])
def test_date_modes_boundaries_pagination_totals_and_tenant(seeded, path, selection):
    client, day, moments = seeded
    params = {"limit": 100}
    if selection in {"start", "both", "same"}:
        params["start_date"] = day.isoformat()
    if selection in {"end", "both", "same"}:
        params["end_date"] = day.isoformat()
    first, last = date_bounds(params.get("start_date"), params.get("end_date"))
    filtered = selection != "none" or path == "/api/v2/audit/executions"
    expected = [moment.isoformat() for moment in moments if not filtered or first <= moment.isoformat() < last]
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    rows = items(response)
    field = "timestamp" if path == "/api/v2/audit/executions" else "created"
    multiple = 3 if path.endswith("events") else 1
    assert len(rows) == len(expected) * multiple
    assert all(row[field] in expected for row in rows)
    assert all(not str(row.get("id", row.get("request_id"))).startswith("two-") for row in rows)
    if selection in {"both", "same", "end"}:
        assert moments[2].isoformat() in [row[field] for row in rows]  # inclusive UTC midnight
        assert moments[3].isoformat() in [row[field] for row in rows]  # last instant of end day
        assert moments[4].isoformat() not in [row[field] for row in rows]  # exclusive next day
    if path.startswith("/api/v2"):
        assert response.json()["total"] == len(rows)
    page = client.get(path, params={**params, "limit": 1, "offset": 1})
    assert items(page) == rows[1:2]
    if path.startswith("/api/v2"):
        assert page.json()["total"] == len(rows)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("params", [{"start_date": "2026-11-03", "end_date": "2026-11-02"},
    {"start_date": "bad-date"}, {"end_date": "2026-02-30"}, {"start_date": "2020-01-01", "end_date": "2026-01-01"}])
def test_invalid_ranges_are_safe_validation_errors(bridge, path, params):
    result = bridge.get(path, params=params)
    assert result.status_code == 422, result.text
    assert "Traceback" not in result.text


@pytest.mark.parametrize("path", PATHS)
def test_authentication_and_user_role_restrictions(bridge, path, monkeypatch):
    import json
    from app.config import settings
    bridge.headers.pop("Authorization")
    assert bridge.get(path).status_code == 401
    accounts = json.loads(settings.demo_accounts_json)
    accounts[0]["role"] = "User"
    monkeypatch.setattr(settings, "demo_accounts_json", json.dumps(accounts))
    bridge.headers["Authorization"] = "Bearer admin"
    assert bridge.get(path, params={"start_date": "2026-11-01", "end_date": "2026-11-01"}).status_code == 403


@pytest.mark.parametrize("path", ["/api/audit/events", "/api/v2/audit/events"])
@pytest.mark.parametrize("category,action", [("policy", "policy.published"), ("governance", "governance.generate.ALLOW"), ("administration", "sso.session.created")])
def test_all_audit_categories_keep_date_conditions(seeded, path, category, action):
    client, day, _ = seeded
    response = client.get(path, params={"category": category, "start_date": day.isoformat(), "end_date": day.isoformat()})
    assert len(items(response)) == 2
    assert all(row["action"] == action for row in items(response))
    if path.startswith("/api/v2"):
        assert response.json()["total"] == 2
