"""Application transaction integration: temporary SQLite transport, mocked Azure selection/providers."""

from unittest.mock import Mock

import pytest
from sqlalchemy import Float, cast, func, select
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from app import database, main
from app.config import Settings
from app.models import Base, Feedback
from app.providers import ProviderUnavailable
from app.schemas import PolicyDocument

SQL_URL = "mssql+pyodbc://@example.database.windows.net/synthetic-db"


@pytest.fixture(params=["sqlite", "mocked_azure_selection"])
def selected_application(client, tmp_path, monkeypatch, request):
    # Each parameter has its own disposable DB; root SQLite and Azure are never opened.
    configuration = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'application.db'}")
    local_engine = database.create_database_engine(configuration)
    Base.metadata.create_all(local_engine)
    if request.param == "mocked_azure_selection":
        factory = Mock(return_value=local_engine)
        monkeypatch.setattr(database, "create_azure_sql_engine", factory)
        configuration = Settings(
            _env_file=None,
            database_url=SQL_URL,
            azure_sql_tenant_id="11111111-1111-1111-1111-111111111111",
            azure_sql_user_object_id="22222222-2222-2222-2222-222222222222",
        )
        assert database.create_database_engine(configuration) is local_engine
        factory.assert_called_once()
    # Exercise the REAL production dependency, not conftest's duplicated session lifecycle.
    original = main.app.dependency_overrides.pop(database.get_database)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(local_engine, expire_on_commit=False))
    monkeypatch.setattr(main.providers, "upload_report", Mock(side_effect=ProviderUnavailable("synthetic unavailable")))
    try:
        yield client, local_engine
    finally:
        main.app.dependency_overrides[database.get_database] = original
        local_engine.dispose()


def publish(client, document=None):
    document = document or PolicyDocument(name="Synthetic integration").model_dump()
    created = client.post("/api/policies", json=document)
    assert created.status_code == 201
    policy = created.json()
    for action in ("submit", "approve", "publish", "activate"):
        response = client.post(f"/api/policies/{policy['id']}/{action}")
        assert response.status_code == 200
        assert response.json()["row_version"] == client.get(f"/api/policies/{policy['id']}").json()["row_version"]
    return policy["id"], document


def test_workflows_persist_across_independent_http_requests(selected_application):
    client, _ = selected_application
    policy_id, document = publish(client)
    assert client.get("/ready").status_code == 200
    assert client.get("/api/settings").json()["database"] == "sqlite"  # Local transport, including mocked Azure selection.
    assert client.post(f"/api/policies/{policy_id}/simulate", json={"text": "Synthetic safe text"}).status_code == 200
    assert client.get(f"/api/policies/{policy_id}/versions").json()[0]["number"] == 1
    for endpoint in ("validate-input", "validate-output", "generate"):
        response = client.post(f"/api/governance/{endpoint}", json={"text": "Synthetic safe text"})
        assert response.status_code == 200
        assert response.json()["decision"] == "ALLOW"
    execution = client.get("/api/audit/executions").json()[0]
    for rating in (2, 3):
        assert client.post("/api/feedback", json={"execution_id": execution["id"], "rating": rating}).status_code == 201
    assert client.get("/api/feedback/summary").json() == {"count": 2, "average": 2.5}
    for endpoint in ("audit/summary", "analytics/overview", "analytics/violations", "analytics/compliance"):
        assert client.get(f"/api/{endpoint}").json()["total_validations"] == 3
    for format in ("json", "csv"):
        response = client.post("/api/reports/export", json={"format": format})
        assert response.status_code == 201 and response.json()["status"] == "FAILED"
    assert len(client.get("/api/reports/exports").json()) == 2
    assert client.get("/api/audit/events").json()
    # Publishing a second version and replacing activation uses the same database.
    document["name"] = "Synthetic second version"
    edited = client.put(f"/api/policies/{policy_id}", json=document)
    assert edited.json()["row_version"] == client.get(f"/api/policies/{policy_id}").json()["row_version"]
    for action in ("submit", "approve", "publish", "activate", "disable", "enable"):
        assert client.post(f"/api/policies/{policy_id}/{action}").status_code == 200
    assert len(client.get(f"/api/policies/{policy_id}/versions").json()) == 2
    draft = client.post("/api/policies", json=PolicyDocument(name="Disposable draft").model_dump()).json()
    assert client.delete(f"/api/policies/{draft['id']}").status_code == 200
    inactive = client.post("/api/policies", json=PolicyDocument(name="Unactivated archival test").model_dump()).json()
    for action in ("submit", "approve", "publish", "archive"):
        assert client.post(f"/api/policies/{inactive['id']}/{action}").status_code == 200
    assert client.get(f"/api/policies/{inactive['id']}").json()["status"] == "ARCHIVED"
    client.headers["Authorization"] = "Bearer foreign"
    assert client.get("/api/policies").json() == []
    assert client.get(f"/api/policies/{policy_id}").status_code == 404


def test_review_persistence_and_response_counter(selected_application):
    client, _ = selected_application
    document = PolicyDocument(name="Synthetic held policy").model_dump()
    document["rules"]["blocked_keywords"]["action"] = "HUMAN_REVIEW"
    publish(client, document)
    held = client.post("/api/governance/generate", json={"text": "internal-only"}).json()
    assert held["decision"] == "HUMAN_REVIEW" and held["safe_response"] is None
    review_id = held["review_id"]
    assert client.get("/api/reviews").json()[0]["id"] == review_id
    response = client.post(f"/api/reviews/{review_id}/approve")
    assert response.status_code == 200 and response.json()["row_version"] == 2
    assert client.get(f"/api/reviews/{review_id}").json()["row_version"] == 2
    assert client.post(f"/api/reviews/{review_id}/reject").status_code == 409


@pytest.mark.parametrize(
    "error,status",
    [(OperationalError("private-query", {}, Exception("private-driver")), 503), (StaleDataError("private-concurrency"), 409)],
)
def test_dependency_commit_failure_prevents_success_response(selected_application, monkeypatch, error, status):
    client, engine = selected_application

    class FailingSession(Session):
        def commit(self):
            raise error

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(engine, class_=FailingSession, expire_on_commit=False))
    response = client.post("/api/policies", json=PolicyDocument(name="Must rollback").model_dump())
    assert response.status_code == status
    assert "private" not in response.text and "Must rollback" not in response.text
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    assert client.get("/api/policies").json() == []
    assert client.get("/api/audit/events").json() == []


def test_process_environment_overrides_file_without_mutating_it(tmp_path, monkeypatch):
    environment_file = tmp_path / "synthetic.env"
    content = "DATABASE_URL=sqlite:///synthetic.db\n"
    environment_file.write_text(content)
    monkeypatch.setenv("DATABASE_URL", SQL_URL)
    assert Settings(_env_file=environment_file).database_url == SQL_URL
    monkeypatch.delenv("DATABASE_URL")
    assert Settings(_env_file=environment_file).database_url == "sqlite:///synthetic.db"
    assert environment_file.read_text() == content


def test_feedback_average_compiles_as_float_on_sql_server():
    compiled = str(select(func.avg(cast(Feedback.rating, Float))).compile(dialect=mssql.dialect()))
    assert "CAST(feedback_records.rating AS FLOAT)" in compiled
