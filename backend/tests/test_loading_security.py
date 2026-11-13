"""Performance changes retain fail-closed checks and safe public-asset behavior."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from app import schema_compatibility as schema
from app.web_assets import mount_frontend
from test_entra_sso import browser, sign_in  # noqa: F401

GRANTS = [("dbo." + table, permission) for table, permissions in schema.RUNTIME_PERMISSIONS.items() for permission in permissions]


@pytest.mark.parametrize("missing", GRANTS)
@pytest.mark.parametrize("denied_value", [0, None])
def test_batched_permission_sql_denies_every_missing_or_unknown_grant(missing, denied_value):
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.connection.driver_connection.create_function(
            "HAS_PERMS_BY_NAME", 3, lambda name, kind, permission: denied_value if (name, permission) == missing else 1
        )
        statements = []
        event.listen(connection, "before_cursor_execute", lambda *args: statements.append(1))
        with pytest.raises(schema.SchemaCheckError):
            schema.verify_runtime_permissions(connection, require_sso=True)
        assert len(statements) == 1
    engine.dispose()


def test_batched_permissions_rechecked_without_cache():
    engine = create_engine("sqlite://")
    enabled = [True]
    with engine.connect() as connection:
        connection.connection.driver_connection.create_function("HAS_PERMS_BY_NAME", 3, lambda *args: int(enabled[0]))
        schema.verify_runtime_permissions(connection, require_sso=True)
        enabled[0] = False
        with pytest.raises(schema.SchemaCheckError):
            schema.verify_runtime_permissions(connection, require_sso=True)
    engine.dispose()


def test_authentication_inspects_once_and_anonymous_requests_do_no_sql(browser):  # noqa: F811
    browser.cookies.clear()
    with patch.object(schema, "inspect_schema", side_effect=AssertionError("Anonymous request must not reflect schema")):
        assert browser.get("/api/sso/me").status_code == 401
    assert sign_in(browser).status_code == 303
    with patch.object(schema, "inspect_schema", wraps=schema.inspect_schema) as inspector:
        assert browser.get("/api/sso/me").status_code == 200
        assert inspector.call_count == 1
    with patch.object(schema, "inspect_schema", side_effect=HTTPException(503, "Schema unavailable")):
        assert browser.get("/api/sso/me").status_code == 503
        assert browser.get("/api/policies").status_code == 503


def test_public_assets_compress_and_cache_but_html_and_apis_do_not(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    content = ("const publicExample = 'synthetic static content';\n" * 100).encode()
    (assets / "index-abcdefgh.js").write_bytes(content)
    (assets / "plain.js").write_bytes(content)
    (tmp_path / "index.html").write_text('<script src="/assets/index-abcdefgh.js"></script>')
    app = FastAPI()

    @app.get("/api/synthetic")
    def synthetic():
        from fastapi.responses import JSONResponse

        return JSONResponse({"value": "synthetic" * 500}, headers={"Cache-Control": "no-store"})

    mount_frontend(app, Path(tmp_path))
    with TestClient(app) as client:
        compressed = client.get("/assets/index-abcdefgh.js", headers={"Accept-Encoding": "gzip"})
        assert compressed.headers["content-encoding"] == "gzip"
        assert compressed.content == content
        assert "Accept-Encoding" in compressed.headers["vary"]
        assert int(compressed.headers["content-length"]) < len(content)
        assert compressed.headers["cache-control"] == "public, max-age=31536000, immutable"
        plain = client.get("/assets/index-abcdefgh.js", headers={"Accept-Encoding": "identity"})
        assert "content-encoding" not in plain.headers
        assert len(compressed.content) == len(plain.content)
        assert "immutable" not in client.get("/assets/plain.js").headers.get("cache-control", "")
        assert client.get("/").headers["cache-control"] == "no-cache"
        response = client.get("/api/synthetic", headers={"Accept-Encoding": "gzip"})
        assert response.headers["cache-control"] == "no-store" and "content-encoding" not in response.headers
