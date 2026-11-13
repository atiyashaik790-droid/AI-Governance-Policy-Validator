"""Small local-only performance samples: synthetic SSO, disposable DB, no cloud."""

import json
import os
from pathlib import Path
from time import perf_counter
from statistics import median
from unittest.mock import patch

from sqlalchemy import event
from app import schema_compatibility
from app.database import get_database
from app.main import app
from test_entra_sso import browser, sign_in  # noqa: F401


def test_local_loading_profile(browser):  # noqa: F811
    assert sign_in(browser).status_code == 303
    session_cookie = dict(browser.cookies)
    rows = []
    dependency = app.dependency_overrides[get_database]()
    db = next(dependency)
    engine = db.get_bind()
    for name, path, authenticated in [
        ("session_anonymous", "/api/sso/me", False),
        ("session_authenticated", "/api/sso/me", True),
        ("overview", "/api/analytics/overview", True),
        ("policies", "/api/policies?limit=20", True),
        ("history", "/api/audit/executions?limit=20", True),
    ]:
        browser.cookies.clear()
        if authenticated:
            browser.cookies.update(session_cookie)
        samples = []
        for _ in range(3):
            statements = []

            def count(conn, cursor, statement, parameters, context, executemany):
                statements.append(1)

            event.listen(engine, "before_cursor_execute", count)
            try:
                with patch.object(schema_compatibility, "inspect_schema", wraps=schema_compatibility.inspect_schema) as inspector:
                    start = perf_counter()
                    response = browser.get(path)
                    elapsed = (perf_counter() - start) * 1000
                    assert response.status_code == (200 if authenticated else 401)
                    samples.append(
                        {"elapsed_ms": round(elapsed, 3), "sql_statements": len(statements), "schema_inspections": inspector.call_count}
                    )
            finally:
                event.remove(engine, "before_cursor_execute", count)
        rows.append({"name": name, "path": path, "samples": samples, "median_ms": median(s["elapsed_ms"] for s in samples)})
    dependency.close()
    output = os.getenv("LOCAL_LOADING_PROFILE")
    if output:
        Path(output).write_text(json.dumps({"environment": "disposable SQLite and synthetic SSO", "rows": rows}, indent=2) + "\n")
