"""No network, credentials, migrations or database writes; sanitized error contracts."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from sql_diagnostics import classify
from app.azure_sql import DatabaseConnectionError, DatabaseAuthenticationError
from app import schema_compatibility


@pytest.mark.parametrize(
    "state,code,expected",
    [
        ("42000", 40615, "SQL_FIREWALL_DENIED"),
        ("28000", 18456, "SQL_LOGIN_DENIED"),
        ("42000", 4060, "SQL_DATABASE_ACCESS_DENIED"),
        ("42000", 916, "SQL_DATABASE_ACCESS_DENIED"),
        ("42000", 229, "SQL_PERMISSION_DENIED"),
        ("42S02", 208, "SQL_OBJECT_MISSING_OR_NOT_VISIBLE"),
        ("IM002", None, "ODBC_DRIVER_UNAVAILABLE"),
        ("HYT00", None, "SQL_CONNECTION_TIMEOUT"),
        ("08001", None, "SQL_TRANSPORT_FAILURE"),
    ],
)
def test_native_errors_survive_sanitizing_wrappers_without_leaks(state, code, expected):
    native = Exception(state, f"[driver] synthetic-private-content ({code})" if code else "[driver] synthetic-private-content")
    hidden = DatabaseConnectionError("Sanitized SQL connection failed")
    hidden.__context__ = native
    hidden.__suppress_context__ = True
    result = classify(hidden, "sql_connect")
    assert result["category"] == expected
    assert "synthetic-private-content" not in json.dumps(result)
    if code:
        assert result["native_code"] == code


@pytest.mark.parametrize(
    "message,category",
    [
        ("Azure SQL authentication unavailable; sign in to the approved organizational tenant", "TOKEN_ACQUISITION_UNAVAILABLE"),
        ("Azure SQL requires an unexpired token for the configured organizational tenant and user", "IDENTITY_PIN_OR_EXPIRY_MISMATCH"),
    ],
)
def test_identity_failure_categories(message, category):
    assert classify(DatabaseAuthenticationError(message), "sql_connect")["category"] == category


def test_tls_error_contains_no_certificate_or_server_details():
    result = classify(Exception("08001", "SSL Provider: certificate synthetic-private-server"), "sql_connect")
    assert result["category"] == "TLS_VALIDATION_FAILED"
    assert "synthetic-private-server" not in json.dumps(result)


def test_hidden_schema_failure_is_identified_without_changing_http_contract(monkeypatch):
    # MSSQL now reads batched key catalogs before checking table visibility.
    # An empty catalog must be represented by an empty result, not a missing
    # connection.execute method (which correctly signals implementation failure).
    connection = SimpleNamespace(
        dialect=SimpleNamespace(name="mssql"),
        execute=lambda _: SimpleNamespace(mappings=lambda: []),
    )
    inspector = SimpleNamespace(get_table_names=lambda **kwargs: [])
    monkeypatch.setattr(schema_compatibility, "inspect", lambda _: inspector)
    with pytest.raises(Exception) as captured:
        schema_compatibility.inspect_schema(SimpleNamespace(connection=lambda: connection))
    error = captured.value
    assert error.status_code == 503
    assert error.detail == "Reviewed schema objects and runtime permissions are required"
    result = classify(error, "schema")
    assert result["category"] == "ALEMBIC_HISTORY_MISSING_OR_NOT_VISIBLE"
    assert result["schema_object"] == "alembic_version"


def test_schema_implementation_errors_are_not_mislabeled_as_permission_denials(monkeypatch):
    def broken(_):
        raise AttributeError("synthetic-private-field")

    monkeypatch.setattr(schema_compatibility, "inspect", broken)
    with pytest.raises(Exception) as captured:
        schema_compatibility.inspect_schema(SimpleNamespace(connection=lambda: None))
    result = classify(captured.value, "schema")
    assert result["category"] == "SCHEMA_QUERY_OR_IMPLEMENTATION_FAILURE"
    assert "synthetic-private-field" not in json.dumps(result)


def test_exception_chain_cycles_are_bounded():
    error = Exception("synthetic-private-content")
    error.__context__ = error
    assert classify(error, "schema")["category"] == "SCHEMA_QUERY_OR_IMPLEMENTATION_FAILURE"


def test_real_adapter_preserves_firewall_category_without_exposing_driver_details(monkeypatch):
    from sqlalchemy import create_engine
    from app.azure_sql import install_token_provider
    from test_azure_sql import fake_token, TENANT, USER

    engine = create_engine("sqlite://")
    credential = SimpleNamespace(get_token=lambda scope: fake_token())

    def denied(*args, **kwargs):
        assert kwargs["attrs_before"]  # Synthetic token reached the real adapter boundary.
        raise RuntimeError("42000", "[ODBC Driver 18] Client with IP address '192.0.2.10' is not allowed to access server private-host; password=private-secret (40615)")

    monkeypatch.setattr(engine.dialect, "connect", denied)
    install_token_provider(engine, credential, TENANT, USER)
    try:
        with pytest.raises(DatabaseConnectionError) as captured:
            engine.connect()
        result = classify(captured.value, "sql_connect")
        assert result["category"] == "SQL_FIREWALL_DENIED"
        assert result["sqlstates"] == ["42000"] and result["native_code"] == 40615
        encoded = json.dumps(result)
        assert all(secret not in encoded for secret in ("192.0.2.10", "private-host", "private-secret", "password", "fixture."))
    finally:
        engine.dispose()
