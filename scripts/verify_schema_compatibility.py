"""Explicit SELECT-only compatibility assessment with sanitized failure categories."""

import argparse
import json
import logging
import re
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
# Native/SDK errors may contain sensitive diagnostics. Print only allowlisted labels.
for logger_name in ("azure", "msal", "sqlalchemy.engine"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

from sql_diagnostics import classify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--connect", action="store_true")
    parser.add_argument("--require-sso", action="store_true")
    args = parser.parse_args()
    if not args.connect:
        parser.error("Explicit --connect required; no network operation performed")
    engine = None
    checks = {}
    stage = "driver"
    try:
        import pyodbc

        if "ODBC Driver 18 for SQL Server" not in pyodbc.drivers():
            print(
                json.dumps(
                    {
                        "status": "BLOCKED",
                        "category": "ODBC_DRIVER_UNAVAILABLE",
                        "stage": stage,
                        "permission_subject": "executing_cli_identity",
                        "hosted_runtime_identity_verified": False,
                        "database_mutated": False,
                    }
                )
            )
            return 1
        checks["odbc_driver18"] = "PASS"
        from sqlalchemy.engine import URL
        from sqlalchemy.orm import Session
        from sqlalchemy import text
        from app.config import settings
        from app.azure_sql import create_azure_sql_engine
        from app.schema_compatibility import inspect_schema

        stage = "configuration"
        engine = create_azure_sql_engine(
            URL.create("mssql+pyodbc", host=args.server, database=args.database),
            settings.azure_sql_tenant_id,
            settings.azure_sql_user_object_id,
            auth_mode="cli",
        )
        checks["configuration"] = "PASS"
        stage = "dns"
        socket.getaddrinfo(args.server, 1433, type=socket.SOCK_STREAM)
        checks["dns"] = "PASS"
        stage = "tcp"
        with socket.create_connection((args.server, 1433), timeout=10):
            pass
        checks["tcp1433"] = "PASS"
        stage = "sql_connect"
        with Session(engine) as db:
            db.connection()
            checks["sql_connection"] = "PASS"
            stage = "target_identity"
            if db.scalar(text("SELECT DB_NAME()")) != args.database:
                print(
                    json.dumps(
                        {
                            "status": "BLOCKED",
                            "category": "DATABASE_TARGET_MISMATCH",
                            "checks": checks,
                            "permission_subject": "executing_cli_identity",
                            "hosted_runtime_identity_verified": False,
                            "database_mutated": False,
                        }
                    )
                )
                return 1
            checks["database_identity"] = "PASS"
            stage = "revision"
            revisions = list(
                db.execute(
                    text("SELECT version_num FROM dbo.alembic_version")
                ).scalars()
            )
            checks["observed_revision"] = (
                revisions[0]
                if len(revisions) == 1
                and isinstance(revisions[0], str)
                and re.fullmatch(r"[0-9]{3}", revisions[0])
                else "UNKNOWN_OR_AMBIGUOUS"
            )
            stage = "schema"
            # Exactly the reviewed revision/object/permission SELECT contract.
            result = inspect_schema(db, require_sso=args.require_sso)
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "database": args.database,
                        **result,
                        "checks": checks,
                        "permission_subject": "executing_cli_identity",
                        "hosted_runtime_identity_verified": False,
                        "database_mutated": False,
                    }
                )
            )
    except Exception as error:
        if stage in {"dns", "tcp", "driver"}:
            diagnostic = {
                "category": {
                    "dns": "DNS_RESOLUTION_UNAVAILABLE",
                    "tcp": "SQL_TCP_UNAVAILABLE",
                    "driver": "ODBC_DRIVER_UNAVAILABLE",
                }[stage],
                "stage": stage,
            }
        else:
            diagnostic = classify(error, stage)
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    **diagnostic,
                    "checks": checks,
                    "permission_subject": "executing_cli_identity",
                    "hosted_runtime_identity_verified": False,
                    "database_mutated": False,
                }
            )
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
