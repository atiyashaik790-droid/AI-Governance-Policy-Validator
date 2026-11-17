"""Approval A ONLY: exact disposable Azure SQL target. No application deployment.

No default execution. --dry-run validates guards/hashes without network or SQL.
--execute requires the exact approval token. Unexpected failures stop and cleanup.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
WINDOW = os.environ.get("PHASE6B_APPROVAL_A_WINDOW", "original")
if WINDOW not in {"original", "retry-1"}:
    raise ValueError("Unknown Approval A window")
EVIDENCE = ROOT / (
    "docs/evidence/phase6b-approval-a-2026-11-06"
    if WINDOW == "original"
    else "docs/evidence/phase6b-approval-a-retry1-2026-11-06"
)
SUB = "25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6"
GROUP = "rg_techdemo_Atiya_Tabsum_Shaik"
SERVER = "sql-governance-validator-dev-atiya"
DB = "sqldb-gpv-mig-20261106-a1"
SOURCE = "sqldb-governance-validator-dev"
SERVER_ID = f"/subscriptions/{SUB}/resourceGroups/{GROUP}/providers/Microsoft.Sql/servers/{SERVER}"
TARGET_ID = SERVER_ID + "/databases/" + DB
TOKEN = (
    "PHASE6B-APPROVAL-A-20261106"
    if WINDOW == "original"
    else "PHASE6B-APPROVAL-A-RETRY1-20261106"
)
RUNTIME = "app-governance-validator-atiya-1026"
ROLE = "governance_validator_web_runtime"
PIN = json.loads(
    (
        ROOT / "docs/evidence/phase6b-readonly-2026-11-06/local-artifacts.json"
    ).read_text()
)
STATE = {"scope": "Approval A ONLY", "events": [], "incarnations": 0, "created": False}
START = None
ENGINES = []
SQL_FACTORY = None


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(kind, **data):
    STATE["events"].append(
        {"utc": datetime.now(timezone.utc).isoformat(), "kind": kind, **data}
    )
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "execution.json").write_text(
        json.dumps(STATE, indent=2, default=str) + "\n"
    )
    print(json.dumps({"kind": kind, **data}, default=str), flush=True)


def guard(sub=SUB, server=SERVER, database=DB, resource_id=TARGET_ID, token=TOKEN):
    if (sub, server, database, resource_id, token) != (
        SUB,
        SERVER,
        DB,
        TARGET_ID,
        TOKEN,
    ):
        raise ValueError("Exact Approval A target required")
    if database in (SOURCE, "master"):
        raise ValueError("Forbidden database")


def pin_sources():
    for path, expected in PIN["migration_hashes"].items():
        if digest(ROOT / path) != expected:
            raise ValueError("Migration hash mismatch: " + path)
    for path in [
        "artifacts/phase6a-2026-11-06/candidate.zip",
        "artifacts/phase6a-2026-11-06/fallback007.zip",
    ]:
        if digest(ROOT / path) != PIN[path]["sha256"]:
            raise ValueError("Artifact hash mismatch")
    paths = (
        sorted((ROOT / "backend/app").rglob("*.py"))
        + sorted((ROOT / "backend/migrations").rglob("*.py"))
        + [
            ROOT / "scripts/phase6b_approval_a.py",
            ROOT / "scripts/tests/phase6b_sql_package_probe.py",
            ROOT / "scripts/tests/session_contract.py",
        ]
    )
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def az(*args, absent_ok=False):
    p = subprocess.run(
        ["az", *args, "-o", "json"], capture_output=True, text=True, timeout=120
    )
    if p.returncode:
        if absent_ok and (
            "ResourceNotFound" in p.stderr or "DatabaseDoesNotExist" in p.stderr
        ):
            return None
        # Never print CLI credentials or complete unreviewed diagnostics.
        raise RuntimeError(
            "Azure command failed: " + " ".join(args[:3]) + "; " + p.stderr[:250]
        )
    return json.loads(p.stdout) if p.stdout.strip() else None


def account_guard():
    guard()
    if az("account", "show", "--query", "id") != SUB:
        raise ValueError("Subscription mismatch")
    s = az(
        "sql",
        "server",
        "show",
        "--subscription",
        SUB,
        "-g",
        GROUP,
        "-n",
        SERVER,
        "--query",
        "{id:id,fqdn:fullyQualifiedDomainName,location:location}",
    )
    if (
        s["id"].lower() != SERVER_ID.lower()
        or s["fqdn"] != SERVER + ".database.windows.net"
        or s["location"] != "westus2"
    ):
        raise ValueError("Server mismatch")


def target_metadata():
    return az(
        "sql",
        "db",
        "show",
        "--subscription",
        SUB,
        "-g",
        GROUP,
        "-s",
        SERVER,
        "-n",
        DB,
        absent_ok=True,
    )


def check_time():
    if START and time.monotonic() - START > 3 * 3600:
        raise TimeoutError("Testing deadline: reserve one hour for cleanup")


def resource_guard():
    check_time()
    account_guard()
    pin_sources()
    d = target_metadata()
    if not d or d["id"].lower() != TARGET_ID.lower():
        raise ValueError("Target missing or wrong ID")
    if (
        d["sku"]["capacity"] != 10
        or d["sku"]["tier"] != "Standard"
        or d["currentServiceObjectiveName"] != "S0"
    ):
        raise ValueError("Wrong tier")
    if d["tags"].get("purpose") != "phase6b-approval-a-synthetic":
        raise ValueError("Ownership tag mismatch")
    return d


def create():
    account_guard()
    pin_sources()
    check_time()
    if target_metadata() is not None:
        raise ValueError("Name collision; do not adopt")
    if STATE["incarnations"] >= 2:
        raise ValueError("Incarnation limit")
    STATE["incarnations"] += 1
    # Persist intent before the request, so uncertain outcomes are cleanup obligations.
    STATE["created"] = True
    emit("create_intent", resource_id=TARGET_ID, incarnation=STATE["incarnations"])
    expiry = datetime.fromtimestamp(time.time() + 4 * 3600, timezone.utc).isoformat()
    az(
        "sql",
        "db",
        "create",
        "--subscription",
        SUB,
        "-g",
        GROUP,
        "-s",
        SERVER,
        "-n",
        DB,
        "--service-objective",
        "S0",
        "--max-size",
        "250GB",
        "--collation",
        "SQL_Latin1_General_CP1_CI_AS",
        "--backup-storage-redundancy",
        "Local",
        "--tags",
        "purpose=phase6b-approval-a-synthetic",
        "owner=approved-operator",
        f"expiresUtc={expiry}",
    )
    d = resource_guard()
    if (
        d["maxSizeBytes"] != 268435456000
        or d["collation"] != "SQL_Latin1_General_CP1_CI_AS"
        or d["currentBackupStorageRedundancy"] != "Local"
    ):
        raise ValueError("Wrong database shape")
    emit(
        "created",
        resource_id=d["id"],
        sku=d["sku"],
        objective=d["currentServiceObjectiveName"],
        max_size=d["maxSizeBytes"],
        backup=d["currentBackupStorageRedundancy"],
    )


def cleanup():
    for e in ENGINES:
        e.dispose()
    account_guard()
    d = target_metadata()
    if d is not None:
        if (
            d["id"].lower() != TARGET_ID.lower()
            or d.get("tags", {}).get("purpose") != "phase6b-approval-a-synthetic"
        ):
            raise ValueError("Cleanup ownership/target mismatch")
        emit("delete_intent", resource_id=TARGET_ID)
        az(
            "sql",
            "db",
            "delete",
            "--subscription",
            SUB,
            "-g",
            GROUP,
            "-s",
            SERVER,
            "-n",
            DB,
            "--yes",
        )
    for _ in range(30):
        if target_metadata() is None:
            break
        time.sleep(2)
    else:
        raise RuntimeError("Cleanup deletion not confirmed")
    names = az(
        "sql",
        "db",
        "list",
        "--subscription",
        SUB,
        "-g",
        GROUP,
        "-s",
        SERVER,
        "--query",
        "[].name",
    )
    if DB in names:
        raise RuntimeError("Deleted database remains in inventory")
    STATE["created"] = False
    emit(
        "cleanup_confirmed",
        arm_get="ResourceNotFound",
        inventory=names,
        resource_id=TARGET_ID,
    )


def engine(runtime=False):
    global SQL_FACTORY
    from sqlalchemy import event
    from sqlalchemy.engine import URL
    from app.config import settings
    from app.azure_sql import create_azure_sql_engine

    resource_guard()
    if SQL_FACTORY is None:
        SQL_FACTORY = create_azure_sql_engine
    e = SQL_FACTORY(
        URL.create("mssql+pyodbc", host=SERVER + ".database.windows.net", database=DB),
        settings.azure_sql_tenant_id,
        settings.azure_sql_user_object_id,
    )

    @event.listens_for(e, "connect")
    def connect_guard(dbapi, record):
        c = dbapi.cursor()
        c.execute(
            "SELECT DB_NAME(), CAST(SERVERPROPERTY('ServerName') AS varchar(128)), SCHEMA_NAME()"
        )
        row = c.fetchone()
        if row[0] != DB or row[1].lower() != SERVER.lower() or row[2] != "dbo":
            raise ValueError("SQL target/default schema mismatch")
        if runtime:
            c.execute(f"EXECUTE AS USER = '{RUNTIME}'")
            c.execute("SELECT USER_NAME()")
            if c.fetchone()[0] != RUNTIME:
                raise ValueError("Impersonation failed")
        c.close()

    @event.listens_for(e, "before_cursor_execute")
    def before(conn, cursor, statement, parameters, context, executemany):
        check_time()
        guard()
        # Validate on every SQL statement including ORM flushes and migration DDL.
        c = conn.connection.cursor()
        c.execute(
            "SELECT DB_NAME(), CAST(SERVERPROPERTY('ServerName') AS varchar(128))"
        )
        row = c.fetchone()
        c.close()
        if row[0] != DB or row[1].lower() != SERVER.lower():
            raise ValueError("SQL target changed")

    ENGINES.append(e)
    return e


def migrate(e, revision, fail007=False):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text, event

    resource_guard()
    pin_sources()
    files = {
        p.name[:3]: p
        for p in sorted((ROOT / "backend/migrations/versions").glob("*.py"))
    }
    injected = []

    def injection(conn, cursor, statement, parameters, context, executemany):
        if "CREATE UNIQUE INDEX ux_review_cases_tenant_id" in statement:
            injected.append(True)
            conn.exec_driver_sql(
                "THROW 51000, 'Approval A deliberate 007 rollback probe', 1;"
            )

    if fail007:
        event.listen(e, "after_cursor_execute", injection)
    try:
        with e.begin() as c:
            if c.scalar(text("SELECT SCHEMA_NAME()")) != "dbo":
                raise ValueError("dbo required")
            c.exec_driver_sql("SET LOCK_TIMEOUT 10000")
            ctx = MigrationContext.configure(c, opts={"transactional_ddl": True})
            ctx._ensure_version_table()
            current = c.scalar(text("SELECT version_num FROM dbo.alembic_version"))
            for number in range(int(current or 0) + 1, int(revision) + 1):
                rev = f"{number:03}"
                spec = importlib.util.spec_from_file_location(
                    "approved_migration_" + rev, files[rev]
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with Operations.context(ctx):
                    module.upgrade()
                if current:
                    c.execute(
                        text("UPDATE dbo.alembic_version SET version_num=:v"),
                        {"v": rev},
                    )
                else:
                    c.execute(
                        text(
                            "INSERT INTO dbo.alembic_version(version_num) VALUES (:v)"
                        ),
                        {"v": rev},
                    )
                current = rev
        emit("migration_pass", revision=revision)
    finally:
        if fail007:
            event.remove(e, "after_cursor_execute", injection)


def snapshot(e, columns=None):
    from sqlalchemy import inspect, text

    result = {}
    selected = {}
    with e.connect() as c:
        for table in sorted(inspect(c).get_table_names(schema="dbo")):
            if table == "alembic_version":
                continue
            if columns and table not in columns:
                continue
            names = (
                columns[table]
                if columns
                else [x["name"] for x in inspect(c).get_columns(table, schema="dbo")]
            )
            rows = c.execute(
                text(
                    "SELECT "
                    + ",".join("[" + n + "]" for n in names)
                    + " FROM dbo.["
                    + table
                    + "]"
                )
            ).all()
            canonical = sorted(
                json.dumps(
                    list(row),
                    default=lambda x: x.hex() if isinstance(x, bytes) else str(x),
                    sort_keys=True,
                )
                for row in rows
            )
            result[table] = {
                "count": len(rows),
                "sha256": hashlib.sha256(json.dumps(canonical).encode()).hexdigest(),
            }
            selected[table] = names
    return result, selected


def seed(e):
    from sqlalchemy.orm import Session
    from app.models import (
        Policy,
        Version,
        Assignment,
        Execution,
        Review,
        Feedback,
        Audit,
        DemoSession,
    )

    with Session(e) as db:
        p = Policy(
            id="synthetic-policy",
            tenant="retained",
            name="Synthetic fixture",
            draft="{}",
            status="PUBLISHED",
        )
        db.add(p)
        db.flush()
        v = Version(
            id="synthetic-version",
            tenant="retained",
            policy_id=p.id,
            number=1,
            document="{}",
        )
        db.add(v)
        db.flush()
        db.add(Assignment(tenant="retained", version_id=v.id))
        x = Execution(
            id="synthetic-execution",
            tenant="retained",
            actor="fixture",
            policy_id=p.id,
            version=1,
            model="fixture",
            decision="HUMAN_REVIEW",
            metadata_json="{}",
        )
        db.add(x)
        db.flush()
        db.add(Review(id="synthetic-review", tenant="retained", execution_id=x.id))
        db.add(Feedback(tenant="retained", execution_id=x.id, rating=1))
        db.add(
            Audit(
                tenant="retained",
                actor="fixture",
                action="synthetic.seed",
                resource=p.id,
            )
        )
        # Persisted sessions are seeded using reflected columns below if defaults differ.
        db.add(
            DemoSession(
                id="synthetic-persisted-session",
                tenant="retained",
                actor="fixture",
                role="Admin",
                credential_hash="0" * 64,
                expires="2026-11-07T00:00:00+00:00",
            )
        )
        db.commit()
    emit("synthetic_seed_pass")


def catalog(e, revision):
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from app.schema_compatibility import inspect_schema

    with Session(e) as db:
        result = inspect_schema(db, require_sso=True)
        emit("schema_contract_pass", revision=revision, result=result)
    queries = {
        "columns": "SELECT t.name table_name,c.name column_name,ty.name type_name,c.max_length,c.precision,c.scale,c.is_nullable,d.definition default_definition FROM sys.tables t JOIN sys.columns c ON t.object_id=c.object_id JOIN sys.types ty ON ty.user_type_id=c.user_type_id LEFT JOIN sys.default_constraints d ON d.object_id=c.default_object_id ORDER BY t.name,c.column_id",
        "checks": "SELECT name,is_disabled,is_not_trusted,definition FROM sys.check_constraints",
        "foreign_keys": "SELECT name,is_disabled,is_not_trusted FROM sys.foreign_keys",
        "triggers": "SELECT name,is_disabled,OBJECT_DEFINITION(object_id) definition FROM sys.triggers",
        "indexes": "SELECT t.name table_name,i.name index_name,c.name column_name,ic.key_ordinal,ic.is_included_column,i.is_unique,i.is_disabled FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id ORDER BY t.name,i.name,ic.index_column_id",
    }
    with e.connect() as c:
        out = {
            k: [dict(r) for r in c.execute(text(q)).mappings()]
            for k, q in queries.items()
        }
        assert all(
            not r["is_disabled"] and not r["is_not_trusted"]
            for k in ["checks", "foreign_keys"]
            for r in out[k]
        )
        assert all(not r["is_disabled"] for r in out["triggers"])
        if revision in ("006", "007"):
            assert (
                c.scalar(
                    text(
                        "SELECT mode FROM workspace_policy_states WHERE tenant='retained'"
                    )
                )
                == "LEGACY"
            )
            includes = {
                r["column_name"]
                for r in out["indexes"]
                if r["index_name"] == "ix_wpa_tenant_active_policy"
                and r["is_included_column"]
            }
            assert includes == {"version_id", "changed_revision"}
    (EVIDENCE / f"catalog-{STATE['incarnations']}-{revision}.json").write_text(
        json.dumps(out, indent=2, default=str)
    )


def grants(e, revision):
    from app.schema_compatibility import RUNTIME_PERMISSIONS

    resource_guard()
    pre = json.loads((EVIDENCE / "live-preflight.json").read_text())
    mapping = pre["source_sql"]["runtime_mapping"][0]
    if mapping["type"] != "E" or len(mapping["sid"]) != 34:
        raise ValueError("Runtime mapping not verified")
    if revision == "005":
        with e.begin() as c:
            c.exec_driver_sql(
                f"CREATE USER [{RUNTIME}] WITH SID={mapping['sid']}, TYPE=E, DEFAULT_SCHEMA=[dbo]"
            )
            c.exec_driver_sql(f"CREATE ROLE [{ROLE}]")
            c.exec_driver_sql(f"ALTER ROLE [{ROLE}] ADD MEMBER [{RUNTIME}]")
            for table, permissions in RUNTIME_PERMISSIONS.items():
                c.exec_driver_sql(
                    f"GRANT {', '.join(permissions)}, VIEW DEFINITION ON OBJECT::dbo.[{table}] TO [{ROLE}]"
                )
    else:
        source = (
            ROOT / f"deployment/phase6a-runtime-{revision}-grants.REVIEW_ONLY.sql"
        ).read_text()
        adapted = (
            source.replace("@explicit_approval bit = 0", "@explicit_approval bit = 1")
            .replace(SOURCE, DB)
            .replace(
                "REPLACE_WITH_RECONFIRMED_CONTAINED_MI_CLIENT_ID", mapping["client_id"]
            )
        )
        (EVIDENCE / f"temporary-{revision}-grants.sql").write_text(adapted)
        with e.begin() as c:
            c.exec_driver_sql(adapted)
    emit(
        "temporary_grants_pass",
        revision=revision,
        identity=RUNTIME,
        authentication="SQL EXECUTE AS context only; no managed identity authentication claim",
    )


def negative(e, statement, expected, params=None):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    try:
        with e.begin() as c:
            c.execute(text(statement), params or {})
    except DBAPIError as ex:
        message = str(ex.orig)
        if expected not in message:
            raise
        emit(
            "expected_sql_denial",
            statement=statement,
            expected=expected,
            sqlstate=ex.orig.args[0],
        )
        return
    raise AssertionError("Expected SQL denial did not happen")


def security(e):
    from sqlalchemy import text

    for table in [
        "audit_events",
        "policy_versions",
        "review_notes",
        "validation_executions",
        "execution_policy_evidence",
        "workspace_policy_assignment_events",
    ]:
        negative(e, f"UPDATE dbo.{table} SET tenant=tenant", "51000")
        negative(e, f"DELETE FROM dbo.{table}", "51000")
    negative(
        e,
        "INSERT INTO workspace_policy_states(tenant,mode,set_revision,updated_by) VALUES ('bad','BAD',1,'fixture')",
        "547",
    )
    negative(
        e,
        "INSERT INTO workspace_policy_assignments(tenant,policy_id,version_id,active,changed_revision,updated_by) VALUES ('retained','missing','missing',1,1,'fixture')",
        "547",
    )
    base = "INSERT INTO review_protected_content(tenant,review_id,content_kind,format_version,key_id,nonce,ciphertext,created_at,expires_at) VALUES (:tenant,:review_id,:kind,:format,:key,:nonce,:ciphertext,:created,:expires)"
    valid = {
        "tenant": "retained",
        "review_id": "synthetic-review",
        "kind": "original_prompt",
        "format": 1,
        "key": "synthetic-constraint",
        "nonce": b"n" * 12,
        "ciphertext": b"c" * 16,
        "created": 100,
        "expires": 604900,
    }
    for changed, code in [
        ({"kind": "wrong"}, "547"),
        ({"format": 2}, "547"),
        ({"nonce": b"n" * 11}, "547"),
        ({"ciphertext": b"c" * 15}, "547"),
        ({"expires": 604901}, "547"),
        ({"expires": 100}, "547"),
        ({"tenant": "foreign"}, "547"),
    ]:
        negative(e, base, code, {**valid, **changed})
    with e.begin() as c:
        c.execute(text(base), valid)
    negative(e, "UPDATE review_protected_content SET expires_at=expires_at", "51000")
    # Duplicate nonce with a different review must be rejected independently of PK.
    with e.begin() as c:
        c.exec_driver_sql(
            "INSERT INTO human_review_cases(id,tenant,execution_id,status,created,row_version) VALUES ('nonce-probe','retained','synthetic-execution','PENDING','2026-11-06',1)"
        )
    negative(e, base, "2601", {**valid, "review_id": "nonce-probe"})
    with e.begin() as c:
        c.exec_driver_sql(
            "DELETE FROM review_protected_content WHERE key_id='synthetic-constraint'"
        )
    emit("protected_content_sql_constraints_pass")
    runtime = engine(runtime=True)
    with runtime.connect() as c:
        assert c.scalar(text("SELECT USER_NAME()")) == RUNTIME
        for table in [
            "audit_events",
            "policy_versions",
            "review_notes",
            "execution_policy_evidence",
            "workspace_policy_assignment_events",
            "review_protected_content",
        ]:
            for op in (
                ["UPDATE"]
                if table == "review_protected_content"
                else ["UPDATE", "DELETE"]
            ):
                assert (
                    c.scalar(
                        text("SELECT HAS_PERMS_BY_NAME(:o,'OBJECT',:p)"),
                        {"o": "dbo." + table, "p": op},
                    )
                    == 0
                )
        assert (
            c.scalar(text("SELECT HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL')"))
            == 0
        )
        assert (
            c.scalar(
                text("SELECT HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CREATE TABLE')")
            )
            == 0
        )
    negative(runtime, "UPDATE dbo.audit_events SET actor=actor", "229")
    negative(runtime, "UPDATE dbo.review_protected_content SET key_id=key_id", "229")
    negative(runtime, "CREATE TABLE dbo.must_be_denied(id int)", "262")
    emit("runtime_permission_negatives_pass")


def dry():
    guard()
    for kw in [
        {"database": SOURCE},
        {"database": "master"},
        {"database": DB + "-other"},
        {"sub": "wrong"},
        {"server": "wrong"},
        {"resource_id": TARGET_ID + "x"},
        {"token": "wrong"},
    ]:
        try:
            guard(**kw)
        except ValueError:
            pass
        else:
            raise AssertionError("Deny guard failed")
    hashes = pin_sources()
    sqlite = ROOT / "backend/governance.db"
    out = {
        "scope": "Approval A only",
        "guard_negatives": 7,
        "source_hashes": hashes,
        "sqlite_sha256": digest(sqlite),
        "status": "PASS",
        "cloud_mutations": 0,
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = (
        "harness-prepared-dry-run.json"
        if (EVIDENCE / "execution.json").exists()
        else "harness-dry-run.json"
    )
    (EVIDENCE / destination).write_text(json.dumps(out, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "PASS",
                "guard_negatives": 7,
                "operator_dependencies_hashed": len(hashes),
            }
        )
    )


def package_probe(name, revision, *options):
    import tempfile
    import zipfile

    resource_guard()
    path = ROOT / (
        "artifacts/phase6a-2026-11-06/"
        + ("candidate.zip" if name == "candidate" else "fallback007.zip")
    )
    with tempfile.TemporaryDirectory(prefix="phase6b-package-") as tmp:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            for member in z.namelist():
                if Path(member).is_absolute() or ".." in Path(member).parts:
                    raise ValueError("Unsafe package path")
            z.extractall(tmp)
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/tests/phase6b_sql_package_probe.py"),
                "--directory",
                tmp,
                "--database",
                DB,
                "--revision",
                revision,
                *options,
            ],
            cwd=tmp,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            # Schema reflection plus the per-statement target guard was measured
            # at ~107 seconds per SSO request. Keep a finite probe bound without
            # imposing the old ten-minute limit on the expanded session checks.
            timeout=1800,
        )
        if completed.returncode:
            # Sanitize SQL parameter dumps; full local diagnostics are intentionally not published.
            session_diagnostics = []
            for line in completed.stdout.splitlines():
                try:
                    record = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if record.get("event") in {"session.observation", "session.contract"}:
                    session_diagnostics.append(json.dumps(record, sort_keys=True))
            lines = session_diagnostics + completed.stderr.splitlines()
            safe = [
                line
                for line in lines
                if not any(
                    t in line
                    for t in [
                        "parameters:",
                        "ciphertext",
                        "access_token",
                        "nonce",
                        "credential_hash",
                    ]
                )
            ]
            (EVIDENCE / f"package-{name}-{revision}-failure.txt").write_text(
                "\n".join(session_diagnostics + safe[-35:]) + "\n"
            )
            raise RuntimeError(
                "Extracted package probe failed: " + name + "/" + revision
            )
        result = json.loads(completed.stdout.splitlines()[-1])
        assert result["passed"]
        emit("package_probe_pass", artifact=name, **result)


def rollback007(e):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    before, cols = snapshot(e)
    with e.connect() as c:
        before_catalog = c.execute(
            text(
                "SELECT name,type FROM sys.objects WHERE is_ms_shipped=0 ORDER BY name,type"
            )
        ).all()
    try:
        migrate(e, "007", fail007=True)
    except DBAPIError as ex:
        if "Approval A deliberate 007 rollback probe" not in str(ex.orig):
            raise
        emit("planned_007_throw_observed", sqlstate=ex.orig.args[0])
    else:
        raise AssertionError("007 injection did not throw")
    with e.connect() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == "006"
        assert (
            c.execute(
                text(
                    "SELECT name,type FROM sys.objects WHERE is_ms_shipped=0 ORDER BY name,type"
                )
            ).all()
            == before_catalog
        )
    assert snapshot(e, cols)[0] == before
    emit(
        "planned_007_transactional_rollback_pass",
        marker="006",
        catalog_unchanged=True,
        retained_rows_unchanged=True,
    )


def execute():
    # This approval window was consumed by a stopped run. Never silently retry it.
    if (EVIDENCE / "execution.json").exists():
        raise RuntimeError(
            "Existing Approval A execution evidence; a reviewed new approval window and evidence directory are required before another execution"
        )
    global START
    START = time.monotonic()
    dry_evidence = json.loads((EVIDENCE / "harness-dry-run.json").read_text())
    assert pin_sources() == dry_evidence["source_hashes"]
    assert digest(ROOT / "backend/governance.db") == dry_evidence["sqlite_sha256"]
    prices = json.loads((EVIDENCE / "retail-live.json").read_text())["Items"]
    price = [
        x
        for x in prices
        if x["skuName"] == "S0"
        and x["meterName"] == "S0 DTUs"
        and x["currencyCode"] == "USD"
        and x["unitOfMeasure"] == "1/Day"
    ]
    assert len(price) == 1 and price[0]["retailPrice"] * 10 / 24 < 0.5
    emit(
        "budget_gate_pass",
        daily_usd=price[0]["retailPrice"],
        conservative_compute_10_billed_hours_usd=price[0]["retailPrice"] * 10 / 24,
        total_budget_usd=1,
        testing_stop_hours=3,
        cleanup_deadline_hours=4,
        notes="Bounded tiny synthetic data; local backups; estimate monitored from actual lifetime, not delayed Azure billing",
    )
    # Independent timed process starts BEFORE creation; cleanup can survive the harness.
    watchlog = open(EVIDENCE / "watchdog.log", "a")
    watchdog = subprocess.Popen(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "--watchdog",
            "--deadline",
            str(time.time() + 3 * 3600),
        ],
        cwd=ROOT,
        env=os.environ.copy(),
        stdout=watchlog,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    emit("cleanup_watchdog_started", pid=watchdog.pid, delete_after_hours=3)
    try:
        create()
        e = engine()
        migrate(e, "005")
        seed(e)
        grants(e, "005")
        catalog(e, "005")
        baseline, cols = snapshot(e)
        emit("retained_baseline", revision="005", tables=baseline)
        package_probe("candidate", "005")
        # Package fixtures are synthetic too; freeze all 005 rows after fixture run.
        baseline, cols = snapshot(e)
        migrate(e, "006")
        assert snapshot(e, cols)[0] == baseline
        emit("retained_005_to_006_pass", tables=baseline)
        grants(e, "006")
        catalog(e, "006")
        package_probe("candidate", "006")
        baseline, cols = snapshot(e)
        migrate(e, "007")
        assert snapshot(e, cols)[0] == baseline
        emit("retained_006_to_007_pass", tables=baseline)
        grants(e, "007")
        catalog(e, "007")
        security(e)
        package_probe("candidate", "007")
        before, cols = snapshot(e)
        package_probe("fallback", "007", "--recovery", "--preserve-only")
        assert snapshot(e, cols)[0] == before
        emit(
            "fallback_retained_hashes_pass",
            tables=before,
            independent_code_fallback=False,
        )
        cleanup()
        create()
        e = engine()
        migrate(e, "005")
        seed(e)
        # Deliberate 006 denials and 007 THROW are transaction-isolated on incarnation 2.
        deliberate_cycle(e)
        emit("rehearsal_pass")
        STATE["status"] = "PASS"
    except BaseException as ex:
        STATE["status"] = "STOPPED"
        emit(
            "unexpected_stop",
            failure_type=type(ex).__name__,
            detail=str(ex)[:400]
            if not hasattr(ex, "statement")
            else "SQL operation failed; sanitized diagnostics required",
        )
        raise
    finally:
        try:
            if STATE["created"]:
                cleanup()
        except BaseException as ex:
            emit(
                "CLEANUP_FAILURE", resource_id=TARGET_ID, failure_type=type(ex).__name__
            )
            raise
        finally:
            STATE["elapsed_seconds"] = round(time.monotonic() - START, 2)
            STATE["sqlite_unchanged"] = (
                digest(ROOT / "backend/governance.db") == dry_evidence["sqlite_sha256"]
            )
            emit(
                "execution_finished",
                status=STATE.get("status"),
                elapsed_seconds=STATE["elapsed_seconds"],
                sqlite_unchanged=STATE["sqlite_unchanged"],
            )
            if not STATE["created"]:
                watchdog.terminate()


def deliberate_cycle(e):
    from sqlalchemy import text

    # Run 006 preflight against uncommitted synthetic negatives, then rollback each
    # fixture transaction. No immutable trigger or migration source is disabled.
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = ROOT / "backend/migrations/versions/006_multi_policy.py"
    spec = importlib.util.spec_from_file_location("failure006", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baseline, cols = snapshot(e)
    for label, stmt, expected in [
        (
            "RESERVED",
            "INSERT INTO inference_usage(id,tenant,actor,status,expires,created) VALUES ('reserved-probe','retained','fixture','RESERVED','2026-11-07','2026-11-06')",
            "006 requires drained and reconciled inference reservations",
        ),
        (
            "invalid_legacy",
            "INSERT INTO validation_executions(id,tenant,actor,policy_id,version,model,decision,metadata_json,created) VALUES ('invalid-probe','retained','fixture','synthetic-policy',0,'fixture','ALLOW','{}','2026-11-06')",
            "006 requires valid existing LEGACY execution identities",
        ),
    ]:
        resource_guard()
        with e.connect() as c:
            tx = c.begin()
            try:
                c.exec_driver_sql(stmt)
                ctx = MigrationContext.configure(c, opts={"transactional_ddl": True})
                try:
                    with Operations.context(ctx):
                        module.upgrade()
                except RuntimeError as ex:
                    assert str(ex) == expected
                else:
                    raise AssertionError("006 preflight accepted " + label)
                assert (
                    c.scalar(text("SELECT version_num FROM alembic_version")) == "005"
                )
                assert (
                    c.scalar(
                        text(
                            "SELECT COUNT(*) FROM sys.tables WHERE name='workspace_policy_states'"
                        )
                    )
                    == 0
                )
            finally:
                tx.rollback()
        assert snapshot(e, cols)[0] == baseline
        emit(
            "planned_006_preflight_denial_pass",
            fixture=label,
            marker="005",
            no_ddl=True,
            retained_hashes_unchanged=True,
        )
    migrate(e, "006")
    rollback007(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--watchdog", action="store_true")
    parser.add_argument("--deadline", type=float)
    args = parser.parse_args()
    os.environ["AZURE_CONFIG_DIR"] = str(ROOT / ".azure-sql-cli")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.path.insert(0, str(ROOT / "backend"))
    if args.dry_run:
        dry()
    elif args.watchdog:
        if not args.deadline:
            parser.error("deadline required")
        while time.time() < args.deadline:
            time.sleep(min(20, args.deadline - time.time()))
        current = json.loads((EVIDENCE / "execution.json").read_text())
        if current.get("created"):
            STATE.update(current)
            emit("WATCHDOG_DEADLINE")
            cleanup()
    elif args.execute:
        guard(token=args.approval_token)
        execute()
    else:
        parser.error("Explicit --dry-run or --execute required")
