"""Completion regressions using only disposable SQLite and mocked cloud transports."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from azure.core import MatchConditions
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app import database, main, providers
from app.config import Settings, settings
from app.models import Base, Execution, Export
from app.schemas import PolicyDocument


@pytest.fixture
def integrated_app(client, tmp_path, monkeypatch):
    engine = database.create_database_engine(Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'integration.db'}"))
    Base.metadata.create_all(engine)
    old = main.app.dependency_overrides.pop(database.get_database)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    requests, uploads = [], []

    def transport(request):
        payload = json.loads(request.content)
        requests.append((request.url.host, payload))
        if request.url.host == "api.openai.com":
            if "[OUTAGE]" in payload["input"]:
                return httpx.Response(503, json={})
            if "[EMPTY_MODERATION]" in payload["input"]:
                return httpx.Response(200, json={"results": [{"flagged": False, "categories": {}}]})
            flagged = "[FLAG]" in payload["input"]
            return httpx.Response(200, json={"results": [{"flagged": flagged, "categories": {"violence": flagged}}]})
        assert request.url.host == "example.openai.azure.com"
        prompt = payload["messages"][0]["content"]
        content = "api_key=sk-test-" + "A" * 30 if "[OUTPUT_SECRET]" in prompt else "Synthetic inspected answer."
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": content}}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs))
    for key, value in {
        "provider_mode": "live",
        "pii_mode": "regex",
        "azure_openai_endpoint": "https://example.openai.azure.com",
        "azure_openai_deployment": "test-deployment",
        "azure_openai_api_key": "fixture-key",
        "azure_openai_api_version": "v1",
        "openai_api_key": "fixture-key",
        "adls_account_url": "https://example.dfs.core.windows.net",
        "adls_file_system": "fixture-reports",
    }.items():
        monkeypatch.setattr(settings, key, value)
    service = MagicMock()
    file = service.__enter__.return_value.get_file_system_client.return_value.get_file_client.return_value
    file.upload_data.side_effect = lambda content, **kwargs: uploads.append((content, kwargs))
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", MagicMock())
    monkeypatch.setattr("azure.storage.filedatalake.DataLakeServiceClient", lambda *_, **__: service)
    try:
        yield client, engine, requests, uploads, file
    finally:
        main.app.dependency_overrides[database.get_database] = old
        engine.dispose()


def publish(client, document):
    created = client.post("/api/policies", json=document)
    assert created.status_code == 201
    identifier = created.json()["id"]
    for operation in ("submit", "approve", "publish", "activate", "enable"):
        assert client.post(f"/api/policies/{identifier}/{operation}").status_code == 200
    return identifier


def test_complete_workflow_with_real_provider_adapters_and_mock_transports(integrated_app):
    client, engine, requests, uploads, _ = integrated_app
    document = PolicyDocument(name="Integrated demo protection").model_dump()
    assert client.post("/api/policies", json={**document, "unexpected": True}).status_code == 422
    identifier = publish(client, document)
    assert client.post(f"/api/policies/{identifier}/simulate", json={"text": "Safe synthetic text"}).json()["decision"] == "ALLOW"
    results = []
    for text, decision in (
        ("Safe synthetic text", "ALLOW"),
        ("api_key=sk-test-" + "A" * 30, "BLOCK"),
        ("Contact person@example.com", "REDACT"),
        ("[OUTPUT_SECRET]", "BLOCK"),
        ("[FLAG]", "BLOCK"),
        ("[OUTAGE]", "BLOCK"),
    ):
        before = sum(host == "example.openai.azure.com" for host, _ in requests)
        response = client.post("/api/governance/generate", json={"text": text})
        assert response.status_code == 200
        result = response.json()
        assert result["decision"] == decision
        if decision == "BLOCK":
            assert result["safe_response"] is None
        if text == "Safe synthetic text":
            assert result["safe_response"] == "Synthetic inspected answer."
        if "person@example.com" in text:
            assert result["input"]["revalidated"]
            assert "person@example.com" not in json.dumps(requests)
        if text in ("[FLAG]", "[OUTAGE]") or text.startswith("api_key"):
            assert sum(host == "example.openai.azure.com" for host, _ in requests) == before
        results.append(result)
    # Editing and republishing leaves the first immutable snapshot intact.
    first = client.get(f"/api/policies/{identifier}/versions").json()[0]
    document["rules"]["blocked_keywords"]["action"] = "HUMAN_REVIEW"
    assert (
        client.put(
            f"/api/policies/{identifier}",
            json=document,
            headers={"If-Match": str(client.get(f"/api/policies/{identifier}").json()["row_version"])},
        ).status_code
        == 200
    )
    for operation in ("submit", "approve", "publish", "activate"):
        assert client.post(f"/api/policies/{identifier}/{operation}").status_code == 200
    assert client.get(f"/api/policies/{identifier}/versions").json()[1] == first
    for action, expected in (("approve", "APPROVED_RESUBMIT_REQUIRED"), ("reject", "REJECTED")):
        held = client.post("/api/governance/generate", json={"text": "internal-only"}).json()
        assert held["decision"] == "HUMAN_REVIEW" and not held["model_invoked"] and held["safe_response"] is None
        result = client.post(f"/api/reviews/{held['review_id']}/{action}")
        assert result.status_code == 200 and result.json()["status"] == expected
        assert result.json()["row_version"] == 2
    revised = client.post("/api/governance/generate", json={"text": "Revised safe synthetic text"}).json()
    assert revised["decision"] == "ALLOW"
    for rating in (2, 3):
        client.headers["Authorization"] = "Bearer admin" if rating == 2 else "Bearer developer"
        assert client.post("/api/feedback", json={"execution_id": revised["request_id"], "rating": rating}).status_code == 201
    client.headers["Authorization"] = "Bearer admin"
    assert client.get("/api/feedback/summary").json() == {"count": 2, "average": 2.5}
    summary = client.get("/api/analytics/overview").json()
    assert summary["total_validations"] == 9 and summary["pending_reviews"] == 0
    assert summary["active_policy"] == {"id": identifier, "version": 2}
    assert client.get("/api/audit/events").json()
    for format in ("json", "csv"):
        response = client.post("/api/reports/export", json={"format": format})
        assert response.status_code == 201 and response.json()["status"] == "SUCCEEDED"
        assert response.json()["path"].endswith("." + format)
    assert len(uploads) == 2 and all(options == {"overwrite": True, "match_condition": MatchConditions.IfMissing} for _, options in uploads)
    assert all(set(row) == {"request_id", "timestamp", "decision", "policy_id", "version"} for row in json.loads(uploads[0][0]))
    assert b"metadata_json" not in uploads[1][0] and b"person@example.com" not in uploads[1][0]
    assert len(client.get("/api/reports/exports").json()) == 2
    with engine.connect() as connection:
        assert len(connection.execute(select(Execution.id)).all()) == 9
        assert set(connection.scalars(select(Export.status))) == {"SUCCEEDED"}
        metadata = " ".join(connection.scalars(select(Execution.metadata_json)))
        assert "safe_response" not in metadata and "safe_text" not in metadata and "person@example.com" not in metadata
    assert client.post(f"/api/policies/{identifier}/disable").status_code == 200
    assert client.post("/api/governance/generate", json={"text": "Safe"}).status_code == 409
    assert client.post(f"/api/policies/{identifier}/enable").status_code == 200
    client.headers["Authorization"] = "Bearer foreign"
    assert client.get(f"/api/policies/{identifier}").status_code == 404
    assert client.post("/api/feedback", json={"execution_id": revised["request_id"], "rating": 5}).status_code == 404


def test_malformed_empty_moderation_fails_closed(integrated_app):
    client, _, requests, _, _ = integrated_app
    publish(client, PolicyDocument(name="Fail closed").model_dump())
    result = client.post("/api/governance/generate", json={"text": "[EMPTY_MODERATION]"}).json()
    assert result["decision"] == "BLOCK" and result["safe_response"] is None
    assert result["input"]["breakdown"]["moderation"] == "UNKNOWN"
    assert not any(host == "example.openai.azure.com" for host, _ in requests)


def test_adls_failure_and_no_overwrite(integrated_app):
    client, _, _, uploads, file = integrated_app
    file.upload_data.side_effect = RuntimeError("fixture upload failed")
    result = client.post("/api/reports/export", json={"format": "json"})
    assert result.status_code == 201 and result.json()["status"] == "FAILED"
    assert not uploads
    file.upload_data.assert_called_once_with(b"[]", overwrite=True, match_condition=MatchConditions.IfMissing)
    assert client.get("/api/reports/exports").json()[0]["status"] == "FAILED"


def test_trends_are_chronological_and_recent(client):
    from datetime import datetime, timedelta, timezone
    from unittest.mock import Mock
    from sqlalchemy.dialects import mssql
    from app.security import Identity

    dependency = main.app.dependency_overrides[database.get_database]()
    session = next(dependency)
    ordered = []
    try:
        for number in reversed(range(102)):
            created = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=number)).isoformat()
            # Duplicate the first retained timestamp to exercise deterministic ID tie-breaking.
            if number == 3:
                created = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=2)).isoformat()
            identifier = f"00000000-0000-0000-0000-{number:012d}"
            ordered.append((created, identifier, number))
            session.add(
                Execution(
                    id=identifier,
                    tenant="one",
                    actor="fixture",
                    policy_id="fixture",
                    version=1,
                    model="fixture",
                    decision="ALLOW",
                    metadata_json=json.dumps({"input": {"score": number, "breakdown": {}, "contributions": {}}}),
                    created=created,
                )
            )
        session.commit()
    finally:
        dependency.close()
    expected = [{"date": created[:10], "score": number} for created, _, number in sorted(ordered)][-100:]
    result = client.get("/api/analytics/overview?start_date=2026-01-01&end_date=2026-04-30").json()
    assert result["total_validations"] == 102 and result["trends"] == expected
    db = Mock()
    db.scalars.return_value = []
    db.execute.return_value.all.return_value = []
    db.execute.return_value.one.return_value = (0, 0)
    db.bind.dialect.name = "mssql"
    db.get.return_value = None
    main.analytics(db, Identity("fixture", "one", "Admin"))
    sql = str(db.scalars.call_args.args[0].compile(dialect=mssql.dialect()))
    assert "ORDER BY validation_executions.created DESC, validation_executions.id DESC" in sql


def test_offline_launcher_isolates_configuration(tmp_path):
    spec = importlib.util.spec_from_file_location("offline_launcher", Path(__file__).resolve().parents[2] / "scripts/run_offline_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    environment = module.offline_environment(tmp_path, "http://localhost:5174")
    assert environment["PROVIDER_MODE"] == "fixture" and environment["PII_MODE"] == "regex"
    assert str(tmp_path) in environment["DATABASE_URL"]
    assert not any(
        environment[key]
        for key in ("AZURE_OPENAI_API_KEY", "OPENAI_API_KEY", "ADLS_ACCOUNT_URL", "ADLS_FILE_SYSTEM", "AZURE_SQL_TENANT_ID")
    )
    token_file = tmp_path / ".demo-tokens.json"
    assert token_file.stat().st_mode & 0o777 == 0o600
    tokens = json.loads(token_file.read_text())
    assert set(tokens) == {"Admin", "Policy Owner", "Developer", "Reviewer", "Auditor"}
    assert all(token not in environment["DEMO_ACCOUNTS_JSON"] for token in tokens.values())
    assert Settings(_env_file=None, **{key.lower(): value for key, value in environment.items()}).provider_mode == "fixture"
    with pytest.raises(ValueError):
        module.offline_environment(tmp_path, "https://external.example")


@pytest.mark.asyncio
@pytest.mark.parametrize("version,use_key", [("synthetic-version", True), ("v1", False)])
async def test_generation_versioned_route_and_entra_auth(monkeypatch, version, use_key):
    from unittest.mock import AsyncMock, Mock

    http = AsyncMock()
    http.__aenter__.return_value = http
    http.post.return_value = httpx.Response(
        200,
        json={"choices": [{"finish_reason": "stop", "message": {"content": "Inspected synthetic answer"}}]},
        request=httpx.Request("POST", "https://example.openai.azure.com"),
    )
    client_factory = Mock(return_value=http)
    monkeypatch.setattr(providers.httpx, "AsyncClient", client_factory)
    for key, value in {
        "provider_mode": "live",
        "azure_openai_endpoint": "https://example.openai.azure.com",
        "azure_openai_deployment": "deployment with space",
        "azure_openai_api_version": version,
        "azure_openai_api_key": "fixture-key" if use_key else "",
        "provider_timeout": 7,
    }.items():
        monkeypatch.setattr(settings, key, value)
    credential = Mock()
    credential.__enter__ = Mock(return_value=credential)
    credential.__exit__ = Mock(return_value=False)
    credential.get_token.return_value.token = "fixture-access-token"
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: credential)
    assert await providers.generate_ai_response("Safe synthetic prompt") == "Inspected synthetic answer"
    client_factory.assert_called_once_with(timeout=7)
    arguments = http.post.call_args
    assert arguments.kwargs["json"]["model"] == "deployment with space"
    if use_key:
        assert arguments.args[0].endswith("/deployments/deployment%20with%20space/chat/completions")
        assert arguments.kwargs["params"] == {"api-version": version}
        assert arguments.kwargs["headers"] == {"api-key": "fixture-key"}
        credential.get_token.assert_not_called()
    else:
        assert arguments.args[0].endswith("/openai/v1/chat/completions")
        assert arguments.kwargs["headers"] == {"Authorization": "Bearer fixture-access-token"}
        credential.get_token.assert_called_once_with("https://cognitiveservices.azure.com/.default")


@pytest.mark.asyncio
async def test_generation_timeout_is_sanitized(monkeypatch):
    from unittest.mock import AsyncMock

    http = AsyncMock()
    http.__aenter__.return_value = http
    http.post.side_effect = httpx.ReadTimeout("fixture-private-detail")
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: http)
    for key, value in {
        "provider_mode": "live",
        "azure_openai_endpoint": "https://example.openai.azure.com",
        "azure_openai_deployment": "fixture",
        "azure_openai_api_key": "fixture-key",
    }.items():
        monkeypatch.setattr(settings, key, value)
    with pytest.raises(providers.ProviderUnavailable, match="Azure generation unavailable") as captured:
        await providers.generate_ai_response("Safe synthetic prompt")
    assert "fixture-private-detail" not in str(captured.value)
