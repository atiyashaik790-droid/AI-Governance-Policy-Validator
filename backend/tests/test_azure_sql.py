"""Synthetic token/transport contracts and real local pooling; no Azure calls or writes."""

import base64
import json
import runpy
import struct
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from azure.core.credentials import AccessToken
from azure.identity import CredentialUnavailableError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import QueuePool

from app import azure_sql, database
from app.config import Settings
from app.azure_sql import (
    DatabaseAuthenticationError,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    ODBC_DRIVER,
    SQL_COPT_SS_ACCESS_TOKEN,
    SQL_SCOPE,
    build_azure_sql_url,
    create_azure_sql_engine,
    install_token_provider,
)

TENANT = "11111111-1111-1111-1111-111111111111"
USER = "22222222-2222-2222-2222-222222222222"
OTHER = "33333333-3333-3333-3333-333333333333"
SQL_URL = "mssql+pyodbc://@example.database.windows.net/example-db?driver=ODBC+Driver+18+for+SQL+Server"


# Create unsigned synthetic SDK token fixtures, never real organizational credentials.
def fake_token(tenant=TENANT, user=USER, nonce="one", lifetime=3600):
    payload = base64.urlsafe_b64encode(json.dumps({"tid": tenant, "oid": user, "nonce": nonce}).encode()).decode().rstrip("=")
    return AccessToken(f"fixture.{payload}.not-a-real-signature", int(time.time()) + lifetime)


# Build independent in-memory engines while simulating the ODBC handshake boundary.
def pooled_token_engine(monkeypatch, credential):
    engine = create_engine("sqlite://", poolclass=QueuePool, pool_size=1, max_overflow=0, pool_pre_ping=True, pool_recycle=2700)
    original_connect = engine.dialect.connect
    handshakes = []

    # Record only fixture connection attributes and use SQLite for real pool behavior.
    def local_transport(*args, **kwargs):
        handshakes.append(kwargs.pop("attrs_before"))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(engine.dialect, "connect", local_transport)
    install_token_provider(engine, credential, TENANT, USER)
    return engine, handshakes


# SQLite keeps working without importing the absent native ODBC runtime.
def test_sqlite_backward_compatibility(monkeypatch):
    monkeypatch.setattr(azure_sql.importlib, "import_module", Mock(side_effect=AssertionError("ODBC must not load for SQLite")))
    configuration = Settings(_env_file=None, database_url="sqlite://")
    engine = database.create_database_engine(configuration)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    engine.dispose()


# The canonical SQL URL forces TLS and has no conflicting authentication parameters.
def test_tls_and_authentication_string():
    url = build_azure_sql_url(make_url(SQL_URL))
    parameters = url.query["odbc_connect"]
    assert "Encrypt=yes" in parameters and "TrustServerCertificate=no" in parameters
    assert "Connection Timeout=10" in parameters and "LongAsMax=Yes" in parameters
    for forbidden in ("UID=", "PWD=", "Authentication=", "Trusted_Connection="):
        assert forbidden not in parameters


# Unsafe settings fail before an ODBC connection or authentication attempt.
@pytest.mark.parametrize(
    "url",
    [
        "mssql+pyodbc://name:password@example.database.windows.net/example-db",
        SQL_URL + "&Encrypt=no",
        SQL_URL + "&TrustServerCertificate=yes",
        SQL_URL + "&Authentication=ActiveDirectoryDefault",
        SQL_URL + "&Trusted_Connection=yes",
        SQL_URL + "&odbc_connect=untrusted",
        SQL_URL + "&UID=someone",
        SQL_URL + "&PWD=secret",
        "mssql+pyodbc://@attacker.example/example-db",
        "mssql+pyodbc://@example.database.windows.net:1444/example-db",
        "mssql+pyodbc://@example.database.windows.net/db%3BUID%3Dsomeone",
        SQL_URL.replace("18+for", "17+for"),
        SQL_URL + "&encrypt=yes&Encrypt=no",
    ],
)
def test_reject_unsafe_database_urls(url):
    with pytest.raises(DatabaseConfigurationError):
        build_azure_sql_url(make_url(url))


# SQL selection fails explicitly when the organizational identity is not configured.
@pytest.mark.parametrize("tenant,user", [("", ""), (TENANT, ""), ("organizations", USER), (TENANT, "not-a-guid")])
def test_missing_identity_configuration(tenant, user):
    with pytest.raises(DatabaseConfigurationError):
        create_azure_sql_engine(make_url(SQL_URL), tenant, user)


# Native import failures are sanitized and cannot create a fallback SQLite engine.
def test_driver_missing_no_fallback(monkeypatch):
    monkeypatch.setattr(azure_sql.importlib, "import_module", Mock(side_effect=ImportError("private-native-loader-detail")))
    configuration = Settings(_env_file=None, database_url=SQL_URL, azure_sql_tenant_id=TENANT, azure_sql_user_object_id=USER)
    with pytest.raises(DatabaseConfigurationError) as captured:
        database.create_database_engine(configuration)
    assert "private-native-loader-detail" not in str(captured.value)


# A Python pyodbc wheel without the registered Microsoft driver is insufficient.
def test_unregistered_driver(monkeypatch):
    monkeypatch.setattr(azure_sql.importlib, "import_module", lambda name: SimpleNamespace(drivers=lambda: [], pooling=True))
    with pytest.raises(DatabaseConfigurationError):
        create_azure_sql_engine(make_url(SQL_URL), TENANT, USER)


# SQL engine creation configures one pool owner and the pinned CLI identity without connecting.
def test_engine_configuration_and_explicit_cli_identity(monkeypatch):
    native = SimpleNamespace(drivers=lambda: [ODBC_DRIVER], pooling=True)
    monkeypatch.setattr(azure_sql.importlib, "import_module", lambda name: native)
    created_engine = create_engine("sqlite://")
    factory = Mock(return_value=created_engine)
    credential = Mock()
    credential_factory = Mock(return_value=credential)
    monkeypatch.setattr(azure_sql, "create_engine", factory)
    monkeypatch.setattr(azure_sql, "AzureCliCredential", credential_factory)
    result = create_azure_sql_engine(make_url(SQL_URL), TENANT, USER)
    assert result is created_engine and native.pooling is False
    credential_factory.assert_called_once_with(tenant_id=TENANT, process_timeout=15)
    credential.get_token.assert_not_called()
    options = factory.call_args.kwargs
    assert options["pool_pre_ping"] is True and options["pool_recycle"] == 2700
    assert options["pool_size"] == 5 and options["max_overflow"] == 5 and options["pool_timeout"] == 10
    assert options["hide_parameters"] is True
    created_engine.dispose()


# Injection uses documented UTF-16-LE bytes and a four-byte little-endian length prefix.
def test_access_token_injection_and_trusted_connection_removal():
    engine = create_engine("sqlite://")
    token = fake_token()
    credential = Mock()
    credential.get_token.return_value = token
    dialect = Mock()
    hook = install_token_provider(engine, credential, TENANT, USER)
    hook(dialect, None, ["Driver={ODBC Driver 18 for SQL Server};Trusted_Connection=Yes"], {})
    credential.get_token.assert_called_once_with(SQL_SCOPE)
    assert "Trusted_Connection" not in dialect.connect.call_args.args[0]
    packed = dialect.connect.call_args.kwargs["attrs_before"][SQL_COPT_SS_ACCESS_TOKEN]
    size = struct.unpack("<I", packed[:4])[0]
    assert size == len(packed[4:]) and packed[4:].decode("utf-16-le") == token.token
    engine.dispose()


# An unexpected conflicting authentication parameter is rejected at the final handshake too.
def test_connection_event_rejects_conflicting_authentication():
    engine = create_engine("sqlite://")
    credential = Mock()
    hook = install_token_provider(engine, credential, TENANT, USER)
    with pytest.raises(DatabaseConfigurationError):
        hook(Mock(), None, ["Driver={ODBC Driver 18 for SQL Server};Authentication=SqlPassword"], {})
    credential.get_token.assert_not_called()
    engine.dispose()


# Missing login, denied authentication and invalid tokens remain sanitized failures.
@pytest.mark.parametrize("failure", [CredentialUnavailableError("sensitive-auth-detail"), RuntimeError("sensitive-auth-detail")])
def test_authentication_failure_is_sanitized(failure):
    engine = create_engine("sqlite://")
    credential = Mock()
    credential.get_token.side_effect = failure
    hook = install_token_provider(engine, credential, TENANT, USER)
    dialect = Mock()
    with pytest.raises(DatabaseAuthenticationError) as captured:
        hook(dialect, None, ["safe-connection"], {})
    assert "sensitive-auth-detail" not in str(captured.value)
    dialect.connect.assert_not_called()
    engine.dispose()


# Wrong tenant, wrong cached account, expiration and malformed identity claims fail closed.
@pytest.mark.parametrize(
    "token", [fake_token(tenant=OTHER), fake_token(user=OTHER), fake_token(lifetime=-1), AccessToken("malformed", int(time.time()) + 3600)]
)
def test_token_account_binding(token):
    engine = create_engine("sqlite://")
    credential = Mock()
    credential.get_token.return_value = token
    hook = install_token_provider(engine, credential, TENANT, USER)
    dialect = Mock()
    with pytest.raises(DatabaseAuthenticationError):
        hook(dialect, None, ["safe-connection"], {})
    dialect.connect.assert_not_called()
    engine.dispose()


# Reusing a valid pooled connection does not authenticate every query; new connections do.
def test_pool_reuse_and_token_renewal_after_dispose(monkeypatch):
    credential = Mock()
    credential.get_token.side_effect = [fake_token(nonce="first"), fake_token(nonce="renewed")]
    engine, handshakes = pooled_token_engine(monkeypatch, credential)
    for _ in range(2):
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    assert credential.get_token.call_count == 1
    engine.dispose()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
    assert credential.get_token.call_count == 2 and handshakes[0] != handshakes[1]
    engine.dispose()


# A failed pre-ping creates a new physical connection and asks the credential for a valid token.
def test_pre_ping_reconnects_with_fresh_token(monkeypatch):
    credential = Mock()
    credential.get_token.side_effect = [fake_token(nonce="first"), fake_token(nonce="second")]
    engine, handshakes = pooled_token_engine(monkeypatch, credential)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    monkeypatch.setattr(engine.dialect, "do_ping", Mock(return_value=False))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
    assert credential.get_token.call_count == 2 and handshakes[0] != handshakes[1]
    engine.dispose()


# Recycled pool entries renew their authentication at the next physical connection.
def test_pool_recycling_renews_token(monkeypatch):
    credential = Mock()
    credential.get_token.side_effect = [fake_token(nonce="first"), fake_token(nonce="second")]
    engine, handshakes = pooled_token_engine(monkeypatch, credential)
    with engine.connect():
        pass
    engine.pool._recycle = 0
    with engine.connect():
        pass
    assert credential.get_token.call_count == 2 and len(handshakes) == 2
    engine.dispose()


# Driver transport failures never expose the native error or create an alternate database.
def test_connection_failure_is_sanitized(monkeypatch):
    credential = Mock()
    credential.get_token.return_value = fake_token()
    engine, handshakes = pooled_token_engine(monkeypatch, credential)
    monkeypatch.setattr(engine.dialect, "connect", Mock(side_effect=RuntimeError("sensitive-driver-detail")))
    with pytest.raises(DatabaseConnectionError) as captured:
        engine.connect()
    assert "sensitive-driver-detail" not in str(captured.value)
    assert engine.url.drivername == "sqlite"  # Explicit local transport harness; no fallback factory exists.
    engine.dispose()


# Alembic executes its connection through the same token-enabled engine without running DDL.
def test_alembic_uses_shared_token_engine(monkeypatch):
    from alembic import context
    from contextlib import nullcontext

    credential = Mock()
    credential.get_token.return_value = fake_token()
    engine, handshakes = pooled_token_engine(monkeypatch, credential)
    configure = Mock()
    run_migrations = Mock()
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(context, "configure", configure)
    monkeypatch.setattr(context, "begin_transaction", lambda: nullcontext())
    monkeypatch.setattr(context, "run_migrations", run_migrations)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "migrations" / "env.py"))
    assert configure.call_args.kwargs["connection"].engine is engine
    assert len(handshakes) == 1
    run_migrations.assert_called_once_with()  # Mocked; no real migration runs here.
    engine.dispose()


# The API returns its existing sanitized 503 when SQL authentication or transport fails.
@pytest.mark.parametrize(
    "error", [DatabaseAuthenticationError("Safe authentication failure"), DatabaseConnectionError("Safe connection failure")]
)
def test_api_connection_failures_are_non_releasing(client, monkeypatch, error):
    from app.main import app
    from app.database import get_database

    previous = app.dependency_overrides[get_database]

    # Replace only the test session dependency with a failing selected-database boundary.
    def failing_database():
        raise error
        yield

    app.dependency_overrides[get_database] = failing_database
    try:
        response = client.get("/ready")
        assert response.status_code == 503 and response.json()["detail"] == "Database operation unavailable; nothing released"
    finally:
        app.dependency_overrides[get_database] = previous


# The selector delegates SQL explicitly instead of treating another dialect as SQLite.
def test_explicit_sql_selection_and_unsupported_dialect(monkeypatch):
    selected = Mock()
    factory = Mock(return_value=selected)
    monkeypatch.setattr(database, "create_azure_sql_engine", factory)
    configuration = Settings(_env_file=None, database_url=SQL_URL, azure_sql_tenant_id=TENANT, azure_sql_user_object_id=USER)
    assert database.create_database_engine(configuration) is selected
    assert factory.call_args.args[1:] == (TENANT, USER)
    with pytest.raises(DatabaseConfigurationError):
        database.create_database_engine(Settings(_env_file=None, database_url="postgresql://localhost/db"))
    with pytest.raises(DatabaseConfigurationError):
        database.create_database_engine(Settings(_env_file=None, database_url="invalid-url"))


# Import the operator's probe as a module without invoking its explicit network entry point.
@pytest.fixture
def probe_module():
    from importlib.util import module_from_spec, spec_from_file_location

    path = Path(__file__).resolve().parents[2] / "scripts" / "check_azure_sql.py"
    specification = spec_from_file_location("check_azure_sql_test", path)
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


# The probe cannot contact Azure unless the operator explicitly supplies --connect.
def test_probe_requires_explicit_connection_flag(probe_module, monkeypatch):
    factory = Mock()
    monkeypatch.setattr(probe_module, "create_azure_sql_engine", factory)
    monkeypatch.setattr("sys.argv", ["check_azure_sql.py", "--server", "example.database.windows.net", "--database", "db"])
    with pytest.raises(SystemExit) as error:
        probe_module.main()
    assert error.value.code == 2
    factory.assert_not_called()


# A successful operator probe issues only SELECTs and does not change active configuration.
def test_read_only_probe_success(probe_module, monkeypatch):
    from unittest.mock import MagicMock

    previous_url = probe_module.settings.database_url
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.side_effect = lambda query, parameters=None: "example-db" if str(query) == "SELECT DB_NAME()" else 1
    monkeypatch.setattr(probe_module, "create_azure_sql_engine", Mock(return_value=engine))
    result, status = probe_module.verify_read_only_connection("example.database.windows.net", "example-db")
    assert status == 0 and result["connection_status"] == "CONNECTED" and result["runtime_permissions_ready"]
    assert result["migrations_executed"] is False and result["active_application_database_changed"] is False
    assert all(str(call.args[0]).startswith("SELECT ") for call in connection.scalar.call_args_list)
    assert probe_module.settings.database_url == previous_url
    engine.dispose.assert_called_once_with()


# A connection can succeed while permissions/schema are not ready; never call this integration-ready.
def test_read_only_probe_missing_runtime_permissions(probe_module, monkeypatch):
    from unittest.mock import MagicMock

    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.side_effect = lambda query, parameters=None: "example-db" if str(query) == "SELECT DB_NAME()" else None
    monkeypatch.setattr(probe_module, "create_azure_sql_engine", Mock(return_value=engine))
    result, status = probe_module.verify_read_only_connection("example.database.windows.net", "example-db")
    assert status == 3 and result["connection_status"] == "CONNECTED" and not result["runtime_permissions_ready"]


# SQL diagnostics do not echo native errors, connection strings or private parameters.
def test_read_only_probe_sanitizes_unexpected_sql_errors(probe_module, monkeypatch):
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(
        probe_module,
        "create_azure_sql_engine",
        Mock(side_effect=OperationalError("private-sql", {"private": "value"}, Exception("private-error"))),
    )
    result, status = probe_module.verify_read_only_connection("example.database.windows.net", "example-db")
    assert status == 2 and result["connection_status"] == "NOT_CONNECTED"
    assert "private" not in json.dumps(result)
