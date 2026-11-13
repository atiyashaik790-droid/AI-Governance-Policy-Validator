"""Read-only new008 SQL probe through the existing main App Service container shell."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_hosted_runtime as channel

SUB = "25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6"
GROUP = "rg_techdemo_Atiya_Tabsum_Shaik"
APP = "app-governance-validator-atiya-1026"
DB = "sqldb-gpv-demo-v008-20261108"
TENANT = "4ac50105-0c66-404e-a107-7cbd8a9a6442"
PRINCIPAL = "600447fe-5fea-4801-9033-ab4aafc474cc"


def payload(marker):
    return f'''
import json,sys
from sqlalchemy import text
from sqlalchemy.engine import URL
from app.azure_sql import create_azure_sql_engine
result={{"status":"BLOCKED","stage":"connect","hosted_mi_verified":False,"database_mutated":False}}
engine=None
try:
    engine=create_azure_sql_engine(URL.create("mssql+pyodbc",host="sql-governance-validator-dev-atiya.database.windows.net",database={DB!r}),{TENANT!r},{PRINCIPAL!r},auth_mode="managed_identity",query_timeout=15)
    with engine.connect() as conn:
        row=conn.execute(text("SELECT DB_NAME(), USER_NAME(), (SELECT version_num FROM dbo.alembic_version), (SELECT COUNT_BIG(*) FROM dbo.policies), (SELECT COUNT_BIG(*) FROM dbo.workspace_policy_assignments WHERE active=1)")).one()
        role=conn.scalar(text("SELECT IS_ROLEMEMBER('governance_validator_web_runtime')"))
    if tuple(row)!=({DB!r},{APP!r},"008",8,8) or role!=1:
        result.update(status="FAIL",stage="contract")
    else:
        result.update(status="PASS",stage="complete",hosted_mi_verified=True,database={DB!r},revision="008",policies=8,active_assignments=8,role_member=True)
except Exception:
    result.update(status="BLOCKED",stage="connect")
finally:
    if engine is not None: engine.dispose()
print({marker!r}+json.dumps(result),file=sys.__stdout__,flush=True)
'''


def safe_result(raw, marker):
    for line in channel.terminal_text(raw).splitlines():
        if not line.startswith(marker + "{"):
            continue
        try:
            value = json.loads(line[len(marker):])
        except ValueError:
            return None
        allowed = {"status", "stage", "hosted_mi_verified", "database_mutated", "database", "revision", "policies", "active_assignments", "role_member"}
        if set(value) - allowed or value.get("status") not in {"PASS", "FAIL", "BLOCKED"} or value.get("database_mutated") is not False:
            raise ValueError("Unexpected probe response")
        if value.get("status") == "PASS" and value != {"status":"PASS","stage":"complete","hosted_mi_verified":True,"database_mutated":False,"database":DB,"revision":"008","policies":8,"active_assignments":8,"role_member":True}:
            raise ValueError("Hosted SQL contract mismatch")
        return value
    return None


def main():
    channel.payload = payload
    channel.safe_result = safe_result
    command = ["az", "webapp", "exec", "--subscription", SUB, "--resource-group", GROUP, "--name", APP, "--mode", "shell", "--target", "app", "--shell", "/bin/sh", "--only-show-errors"]
    try:
        result = channel.shell_probe(command, timeout=70)
    except Exception as exc:
        result = {"status":"BLOCKED","category":getattr(exc,"category",type(exc).__name__),"hosted_mi_verified":False,"database_mutated":False}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
