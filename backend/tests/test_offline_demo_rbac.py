"""Exercise actual offline provisioning against policy creation on isolated SQLite."""

import importlib.util
import json
from pathlib import Path

import pytest

from app.config import settings
from app.schemas import PolicyDocument


@pytest.mark.parametrize(
    "role,expected",
    [("Admin", 201), ("Policy Owner", 201), ("Developer", 403), ("Reviewer", 403), ("Auditor", 403)],
)
def test_provisioned_offline_roles_enforce_draft_creation(client, tmp_path, monkeypatch, role, expected):
    path = Path(__file__).resolve().parents[2] / "scripts/run_offline_demo.py"
    spec = importlib.util.spec_from_file_location("offline_rbac_fixture", path)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    environment = launcher.offline_environment(tmp_path, "http://localhost:5174")
    credential_file = tmp_path / ".demo-tokens.json"
    assert credential_file.stat().st_mode & 0o777 == 0o600
    tokens = json.loads(credential_file.read_text())
    monkeypatch.setattr(settings, "demo_accounts_json", environment["DEMO_ACCOUNTS_JSON"])
    client.headers["Authorization"] = "Bearer " + tokens[role]
    diagnostics = client.get("/api/settings")
    assert diagnostics.status_code == 200
    assert diagnostics.json()["role"] == role
    if role == "User":
        session = client.post("/api/auth/session")
        assert session.status_code == 201
        client.headers["Authorization"] = "Bearer " + session.json()["access_token"]
        assert client.get("/api/auth/me").json()["role"] == "User"
        assert client.get("/api/policies").status_code == 403
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/auth/me").status_code == 401
        client.headers["Authorization"] = "Bearer " + tokens[role]
    response = client.post("/api/policies", json=PolicyDocument(name="Synthetic RBAC policy").model_dump())
    assert response.status_code == expected
    policies = client.get("/api/policies").json()
    if expected == 201:
        assert response.json()["status"] == "DRAFT"
        assert len(policies) == 1
        assert policies[0]["id"] == response.json()["id"]
    else:
        assert response.json()["detail"] == "Role does not permit this operation"
        assert policies == []
        client.headers["Authorization"] = "Bearer " + tokens["Admin"]
        assert client.get("/api/audit/events").json() == []
