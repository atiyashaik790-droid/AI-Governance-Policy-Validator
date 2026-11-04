"""Offline deployment contracts: mock identity, in-memory DB and temporary static assets only."""

import importlib.util
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app import azure_sql, database
from app.config import Settings
from app.web_assets import mount_frontend, validate_hosting_settings

TENANT = "11111111-1111-1111-1111-111111111111"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"
SQL_URL = "mssql+pyodbc://@example.database.windows.net/synthetic-db"


def hosted_settings(**changes):
    configuration = dict(
        database_url=SQL_URL,
        azure_sql_auth_mode="managed_identity",
        azure_sql_tenant_id=TENANT,
        azure_sql_user_object_id=PRINCIPAL,
        provider_mode="live",
        pii_mode="presidio",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_deployment="fixture",
        openai_api_key="fixture-key",
        adls_account_url="https://example.dfs.core.windows.net",
        adls_file_system="reports",
        cors_origin="https://example.azurewebsites.net",
        demo_accounts_json=json.dumps([{"user": "fixture", "tenant": "fixture", "role": "Admin", "token_hash": "a" * 64}]),
    )
    configuration.update(changes)
    return Settings(_env_file=None, **configuration)


@pytest.mark.parametrize("mode", ["cli", "managed_identity"])
def test_explicit_sql_identity_selection_without_network(monkeypatch, mode):
    credential = Mock()
    cli, managed = Mock(return_value=credential), Mock(return_value=credential)
    monkeypatch.setattr(azure_sql, "AzureCliCredential", cli)
    monkeypatch.setattr(azure_sql, "ManagedIdentityCredential", managed)
    monkeypatch.setattr(azure_sql.importlib, "import_module", lambda _: SimpleNamespace(drivers=lambda: [azure_sql.ODBC_DRIVER]))
    engine = create_engine("sqlite://")
    monkeypatch.setattr(azure_sql, "create_engine", Mock(return_value=engine))
    install = Mock()
    monkeypatch.setattr(azure_sql, "install_token_provider", install)
    assert azure_sql.create_azure_sql_engine(make_url(SQL_URL), TENANT, PRINCIPAL, auth_mode=mode) is engine
    install.assert_called_once_with(engine, credential, TENANT, PRINCIPAL)
    if mode == "managed_identity":
        managed.assert_called_once_with()
        cli.assert_not_called()
    else:
        cli.assert_called_once_with(tenant_id=TENANT, process_timeout=15)
        managed.assert_not_called()
    engine.dispose()


def test_managed_identity_factory_failure_cannot_use_cli(monkeypatch):
    monkeypatch.setattr(azure_sql.importlib, "import_module", lambda _: SimpleNamespace(drivers=lambda: [azure_sql.ODBC_DRIVER]))
    monkeypatch.setattr(azure_sql, "ManagedIdentityCredential", Mock(side_effect=azure_sql.DatabaseAuthenticationError("unavailable")))
    cli = Mock(side_effect=AssertionError("CLI fallback forbidden"))
    monkeypatch.setattr(azure_sql, "AzureCliCredential", cli)
    with pytest.raises(azure_sql.DatabaseAuthenticationError):
        azure_sql.create_azure_sql_engine(make_url(SQL_URL), TENANT, PRINCIPAL, auth_mode="managed_identity")
    cli.assert_not_called()


def test_database_routes_managed_identity_explicitly(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(database, "create_azure_sql_engine", factory)
    configuration = hosted_settings()
    assert database.create_database_engine(configuration) is factory.return_value
    assert factory.call_args.kwargs == {"auth_mode": "managed_identity", "query_timeout": 15}
    assert Settings(_env_file=None).azure_sql_auth_mode == "cli"
    with pytest.raises(azure_sql.DatabaseConfigurationError):
        azure_sql.create_azure_sql_engine(make_url(SQL_URL), TENANT, PRINCIPAL, auth_mode="default")


@pytest.mark.parametrize(
    "changes",
    [
        {"database_url": "sqlite://"},
        {"azure_sql_auth_mode": "cli"},
        {"provider_mode": "fixture"},
        {"pii_mode": "regex"},
        {"openai_api_key": ""},
        {"adls_file_system": ""},
        {"cors_origin": "http://localhost:5173"},
        {"demo_accounts_json": "[]"},
        {"demo_accounts_json": "invalid-private-data"},
        {"azure_sql_user_object_id": ""},
    ],
)
def test_hosting_rejects_incomplete_or_local_configuration(changes):
    with pytest.raises(RuntimeError) as error:
        validate_hosting_settings(hosted_settings(**changes))
    assert "invalid-private-data" not in str(error.value)


def test_valid_hosting_configuration_does_not_connect():
    validate_hosting_settings(hosted_settings())


def test_static_spa_does_not_capture_api_or_private_paths(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>React shell</html>")
    (tmp_path / "assets" / "fixture.js").write_text("export default 'fixture';")
    (tmp_path / ".env").write_text("PRIVATE_FIXTURE")
    application = FastAPI()

    @application.get("/health")
    def health():
        return {"status": "ok"}

    mount_frontend(application, tmp_path)
    with TestClient(application) as client:
        assert client.get("/").status_code == 200
        assert "React shell" in client.get("/policies/synthetic-id").text
        assert client.get("/assets/fixture.js").status_code == 200
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/api/missing").status_code == 404
        assert client.get("/.env").status_code == 404
        assert client.get("/assets/%2e%2e/.env").status_code == 404
        assert client.get("/health").json() == {"status": "ok"}


def test_hosting_preserves_existing_api_auth(client, tmp_path):
    from app.main import app

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>React shell</html>")
    original_routes = list(app.router.routes)
    try:
        mount_frontend(app, tmp_path)
        assert client.get("/policies").status_code == 200
        assert client.get("/api/policies", headers={"Authorization": ""}).status_code == 401
        assert client.get("/api/missing").status_code == 404
    finally:
        app.router.routes[:] = original_routes


def test_missing_assets_fail_before_serving(tmp_path):
    with pytest.raises(RuntimeError):
        mount_frontend(FastAPI(), tmp_path)


def test_package_allowlist_excludes_secrets_data_and_migrations(tmp_path):
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("app_service_package", root / "scripts/prepare_app_service.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<html><script src="/assets/index-fixture.js"></script></html>')
    (dist / "assets/index-fixture.js").write_text("fetch('/api/settings');")
    (dist / ".env").write_text("PRIVATE_FIXTURE")
    (dist / "private.db").write_text("PRIVATE_FIXTURE")
    archive = tmp_path / "application.zip"
    result = module.package(root, dist, archive)
    assert result["deployed"] is False
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        assert {"app/hosting.py", "static/index.html", "startup.sh", "requirements.txt"} <= names
        assert not any(".env" in name or name.endswith(".db") or "migrations" in name or "tests" in name for name in names)
        assert "alembic" not in package.read("startup.sh").decode()
    with pytest.raises(FileExistsError):
        module.package(root, dist, archive)
    (dist / "assets/index-fixture.js").write_text("fetch('http://localhost:8000/api/settings');")
    with pytest.raises(ValueError):
        module.package(root, dist, tmp_path / "wrong-origin.zip")


def test_adls_new_date_directories_are_conditional_and_not_overwritten(monkeypatch):
    from unittest.mock import MagicMock
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceExistsError
    from app import providers
    from app.config import settings

    monkeypatch.setattr(settings, "adls_account_url", "https://example.dfs.core.windows.net")
    monkeypatch.setattr(settings, "adls_file_system", "reports")
    service, credential = MagicMock(), MagicMock()
    filesystem = service.__enter__.return_value.get_file_system_client.return_value
    directory = filesystem.get_directory_client.return_value
    directory.create_directory.side_effect = [None, ResourceExistsError("existing"), None, None]
    directory.get_directory_properties.return_value = SimpleNamespace(metadata={"hdi_isfolder": "true"})
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: credential)
    monkeypatch.setattr("azure.storage.filedatalake.DataLakeServiceClient", lambda *_, **__: service)
    providers.upload_report("governance-reports/2026/10/29/fixture.json", "[]")
    assert [call.args[0] for call in filesystem.get_directory_client.call_args_list] == [
        "governance-reports",
        "governance-reports/2026",
        "governance-reports/2026/10",
        "governance-reports/2026/10/29",
    ]
    assert all(call.kwargs == {"match_condition": MatchConditions.IfMissing} for call in directory.create_directory.call_args_list)
    filesystem.get_file_client.return_value.upload_data.assert_called_once_with(
        b"[]", overwrite=True, match_condition=MatchConditions.IfMissing
    )


@pytest.mark.parametrize("path", ["../fixture.json", "/fixture.json", "reports//fixture.json", "reports/./fixture.json"])
def test_adls_invalid_path_does_not_authenticate(monkeypatch, path):
    from app import providers
    from app.config import settings

    monkeypatch.setattr(settings, "adls_account_url", "https://example.dfs.core.windows.net")
    monkeypatch.setattr(settings, "adls_file_system", "reports")
    factory = Mock(side_effect=AssertionError("No credential acquisition"))
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", factory)
    with pytest.raises(providers.ProviderUnavailable):
        providers.upload_report(path, "[]")
    factory.assert_not_called()


def test_adls_parent_file_conflict_cannot_upload(monkeypatch):
    from unittest.mock import MagicMock
    from azure.core.exceptions import ResourceExistsError
    from app import providers
    from app.config import settings

    monkeypatch.setattr(settings, "adls_account_url", "https://example.dfs.core.windows.net")
    monkeypatch.setattr(settings, "adls_file_system", "reports")
    service = MagicMock()
    filesystem = service.__enter__.return_value.get_file_system_client.return_value
    filesystem.get_directory_client.return_value.create_directory.side_effect = ResourceExistsError("conflict")
    filesystem.get_directory_client.return_value.get_directory_properties.return_value = SimpleNamespace(metadata={"hdi_isfolder": "false"})
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", MagicMock())
    monkeypatch.setattr("azure.storage.filedatalake.DataLakeServiceClient", lambda *_, **__: service)
    with pytest.raises(providers.ProviderUnavailable):
        providers.upload_report("reports/fixture.json", "[]")
    filesystem.get_file_client.assert_not_called()
