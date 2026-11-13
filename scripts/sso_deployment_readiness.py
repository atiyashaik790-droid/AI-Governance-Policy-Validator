"""Pinned, read-only SSO preflight. Never forwards Azure/SQL stderr or raw JSON."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SUB = "25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6"
TENANT = "4ac50105-0c66-404e-a107-7cbd8a9a6442"
APP = "app-governance-validator-atiya-1026"
SERVER = "sql-governance-validator-dev-atiya"
DATABASE = "sqldb-governance-validator-dev"
RELEASE = "1.2-6749226f1af65b63"
PACKAGE = Path("/tmp/governance-sso-compatibility-fixed-004-20261104.zip")
PACKAGE_HASH = "9d81fa9b7700557eac2cb41edd5ab861d19a6b8c4f9052e55068e5eab784df80"
ROLLBACK = (
    ROOT / "artifacts/restricted-demo-20261101/governance-workspace-policy-delete.zip"
)
ROLLBACK_HASH = "b44afedb721ae8ed5b4d48c9ea50fe3aab6a586ed8325af7c08ca93969abf776"
CHECKS = (
    "artifacts",
    "cli_context",
    "subscription",
    "app_service",
    "managed_identity",
    "sql_target",
    "cli_sql_schema004",
    "backup_metadata",
    "recovery_permissions",
    "hosted_runtime",
    "recovery_drill",
)


class Stop(Exception):
    def __init__(self, status, category):
        self.status, self.category = status, category


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run_json(command, timeout=60):
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env={**os.environ, "AZURE_CONFIG_DIR": str(ROOT / ".azure-sql-cli")},
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        # Error output can include credentials or SQL content; never forward it.
        if result.returncode:
            # Classify internally; never include any fragment of stderr in output.
            diagnostic = result.stderr.lower()
            category = "READ_ONLY_COMMAND_UNAVAILABLE"
            if any(
                word in diagnostic
                for word in (
                    "name resolution",
                    "failed to resolve",
                    "nameresolutionerror",
                    "temporary failure in name",
                    "getaddrinfo failed",
                )
            ):
                category = "AZURE_NETWORK_OR_DNS_UNAVAILABLE"
            elif any(
                word in diagnostic
                for word in (
                    "az login",
                    "authenticationfailed",
                    "aadsts",
                    "expired",
                )
            ):
                category = "EXISTING_CLI_AUTHENTICATION_UNAVAILABLE"
            elif any(
                word in diagnostic
                for word in (
                    "authorizationfailed",
                    "forbidden",
                    "does not have authorization",
                )
            ):
                category = "EXISTING_READ_PERMISSION_UNAVAILABLE"
            raise Stop("UNKNOWN", category)
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise Stop("UNKNOWN", "READ_ONLY_COMMAND_UNAVAILABLE") from None


def az(*args):
    # All call sites are fixed show/list operations. No arbitrary CLI passthrough.
    return run_json(["az", *args, "--output", "json", "--only-show-errors"])


def require(condition, category):
    if not condition:
        raise Stop("FAIL", category)


def resource(value, provider, kind, name):
    require(isinstance(value, dict), "RESOURCE_RESPONSE_INVALID")
    group = value.get("resourceGroup")
    require(
        isinstance(group, str) and re.fullmatch(r"[\w.()\-]{1,90}", group),
        "RESOURCE_GROUP_INVALID",
    )
    expected = f"/subscriptions/{SUB}/resourceGroups/{group}/providers/{provider}/{kind}/{name}"
    require(
        str(value.get("id", "")).lower() == expected.lower(), "RESOURCE_TARGET_MISMATCH"
    )
    require(value.get("name") == name, "RESOURCE_TARGET_MISMATCH")
    return group, expected


def unique(values):
    require(
        isinstance(values, list) and len(values) == 1, "RESOURCE_MISSING_OR_AMBIGUOUS"
    )
    return values[0]


def uuid(value):
    return isinstance(value, str) and bool(
        re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value)
    )


def artifacts(package):
    require(package.is_file() and ROLLBACK.is_file(), "ARTIFACT_MISSING")
    require(sha256(package) == PACKAGE_HASH, "COMPATIBILITY_CHECKSUM_MISMATCH")
    require(sha256(ROLLBACK) == ROLLBACK_HASH, "ROLLBACK_CHECKSUM_MISMATCH")
    # ZIP hash pins every byte, including manifest and members; never extract it.
    with zipfile.ZipFile(package) as archive:
        release = json.loads(archive.read("release.json"))
    require(release.get("build_version") == RELEASE, "PACKAGE_RELEASE_MISMATCH")
    require(
        release.get("supported_migrations") == ["004", "005"],
        "PACKAGE_SCHEMA_CONTRACT_MISMATCH",
    )
    return {
        "release": RELEASE,
        "sha256": PACKAGE_HASH,
        "rollback_sha256": ROLLBACK_HASH,
        "rollback_before005_only": True,
        "after005_rollback": RELEASE,
    }


def verify(package=PACKAGE, call=az, sql_call=run_json):
    report = {
        "status": "UNKNOWN",
        "stage": "A",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "subscription": SUB,
        "database": DATABASE,
        "database_mutated": False,
        "hosted_mutations_attempted": False,
        "hosted_runtime_identity_verified": False,
        "checks": {
            name: {"status": "UNKNOWN", "category": "NOT_ATTEMPTED"} for name in CHECKS
        },
    }
    current = "artifacts"

    def passed(data=None):
        report["checks"][current] = {"status": "PASS", **(data or {})}

    try:
        passed(artifacts(package))
        current = "cli_context"
        require((ROOT / ".azure-sql-cli").is_dir(), "PROJECT_CLI_CONTEXT_MISSING")
        passed()
        current = "subscription"
        account = call(
            "account", "show", "--query", "{id:id,tenantId:tenantId,state:state}"
        )
        require(
            account.get("id") == SUB and account.get("tenantId") == TENANT,
            "APPROVED_ACCOUNT_MISMATCH",
        )
        require(account.get("state") == "Enabled", "SUBSCRIPTION_NOT_ENABLED")
        passed({"tenant_id": TENANT})
        current = "app_service"
        app = unique(
            call(
                "webapp",
                "list",
                "--subscription",
                SUB,
                "--query",
                f"[?name=='{APP}'].{{name:name,resourceGroup:resourceGroup,id:id,state:state,identity:identity}}",
            )
        )
        app_group, app_id = resource(app, "Microsoft.Web", "sites", APP)
        require(app.get("state") == "Running", "APP_SERVICE_NOT_RUNNING")
        passed({"resource_group": app_group, "resource_id": app_id, "state": "Running"})
        current = "managed_identity"
        identity = app.get("identity") or {}
        require(
            "SystemAssigned" in str(identity.get("type", "")),
            "EXISTING_SYSTEM_IDENTITY_UNAVAILABLE",
        )
        principal = identity.get("principalId")
        require(
            uuid(principal) and identity.get("tenantId") == TENANT,
            "MANAGED_IDENTITY_INVALID",
        )
        passed({"principal_id": principal, "tenant_id": TENANT})
        current = "sql_target"
        server = unique(
            call(
                "sql",
                "server",
                "list",
                "--subscription",
                SUB,
                "--query",
                f"[?name=='{SERVER}'].{{name:name,resourceGroup:resourceGroup,id:id}}",
            )
        )
        sql_group, server_id = resource(server, "Microsoft.Sql", "servers", SERVER)
        db = call(
            "sql",
            "db",
            "show",
            "--subscription",
            SUB,
            "--resource-group",
            sql_group,
            "--server",
            SERVER,
            "--name",
            DATABASE,
            "--query",
            "{id:id,name:name,status:status,earliestRestoreDate:earliestRestoreDate}",
        )
        require(
            str(db.get("id", "")).lower()
            == f"{server_id}/databases/{DATABASE}".lower(),
            "DATABASE_TARGET_MISMATCH",
        )
        require(
            db.get("name") == DATABASE and db.get("status") == "Online",
            "DATABASE_NOT_ONLINE",
        )
        passed(
            {
                "resource_group": sql_group,
                "resource_id": f"{server_id}/databases/{DATABASE}",
            }
        )
        current = "cli_sql_schema004"
        sql = sql_call(
            [
                sys.executable,
                str(ROOT / "scripts/verify_schema_compatibility.py"),
                "--server",
                f"{SERVER}.database.windows.net",
                "--database",
                DATABASE,
                "--connect",
            ],
            timeout=90,
        )
        require(
            sql.get("status") == "PASS"
            and sql.get("database") == DATABASE
            and sql.get("revision") == "004"
            and sql.get("versioned") is True
            and sql.get("sso_schema") is False
            and sql.get("database_mutated") is False
            and sql.get("permission_subject") == "executing_cli_identity"
            and sql.get("hosted_runtime_identity_verified") is False,
            "CLI_SQL_004_CONTRACT_NOT_VERIFIED",
        )
        passed(
            {
                "revision": "004",
                "partial005": False,
                "permission_subject": "executing_cli_identity",
            }
        )
        current = "backup_metadata"
        policy = call(
            "sql",
            "db",
            "str-policy",
            "show",
            "--subscription",
            SUB,
            "--resource-group",
            sql_group,
            "--server",
            SERVER,
            "--name",
            DATABASE,
            "--query",
            "{retentionDays:retentionDays,diffBackupIntervalInHours:diffBackupIntervalInHours}",
        )
        days = policy.get("retentionDays")
        earliest = datetime.fromisoformat(
            db.get("earliestRestoreDate", "").replace("Z", "+00:00")
        )
        require(type(days) is int and 1 <= days <= 35, "BACKUP_RETENTION_INVALID")
        require(
            earliest.tzinfo is not None and earliest < datetime.now(timezone.utc),
            "PITR_WINDOW_INVALID",
        )
        passed(
            {
                "retention_days": days,
                "earliest_restore_utc": earliest.isoformat(),
                "latest_restore_point_verified": False,
                "restore_performed": False,
            }
        )
        current = "recovery_permissions"
        # Read existing management permissions only. Do not infer complete restore authority.
        permissions = call(
            "rest",
            "--method",
            "get",
            "--url",
            f"https://management.azure.com{server_id}/providers/Microsoft.Authorization/permissions?api-version=2022-04-01",
            "--query",
            "value[].{actions:actions,notActions:notActions}",
        )
        require(isinstance(permissions, list), "PERMISSIONS_RESPONSE_INVALID")
        # Do not copy policy text/identities or claim deny/lock/target checks passed.
        report["checks"][current] = {
            "status": "UNKNOWN",
            "category": "RECOVERY_OPERATOR_AND_TARGET_REVIEW_REQUIRED",
            "permission_metadata_readable": True,
            "permission_subject": "executing_cli_identity",
        }
        current = "hosted_runtime"
        report["checks"][current] = {
            "status": "UNKNOWN",
            "category": "ACTUAL_RUNTIME_PROBE_NOT_RUN",
            "next_command": "bash scripts/verify_sso_deployment_readiness.sh --remaining-only",
            "principal_id": principal,
            "cli_permissions_are_runtime_proof": False,
        }
        report["checks"]["recovery_drill"] = {
            "status": "UNKNOWN",
            "category": "RESTORE_AND_CUTOVER_NOT_AUTHORIZED",
        }
        report["category"] = "RUNTIME_AND_RECOVERY_EVIDENCE_REQUIRED"
    except Stop as error:
        report["status"] = error.status
        report["category"] = error.category
        report["checks"][current] = {"status": error.status, "category": error.category}
    except Exception:
        # Never stringify unknown exception objects, raw response data or paths.
        report["category"] = "READ_ONLY_RESPONSE_OR_LOCAL_PREREQUISITE_INVALID"
        report["checks"][current] = {
            "status": "UNKNOWN",
            "category": report["category"],
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package",
        type=Path,
        default=PACKAGE,
        help="Existing candidate ZIP; the pinned SHA-256 is mandatory",
    )
    parser.add_argument(
        "--remaining-only",
        action="store_true",
        help="Check only actual runtime and recovery permissions; skip passing schema/backup/artifact checks",
    )
    args = parser.parse_args()
    if args.remaining_only:
        from verify_hosted_runtime import main as remaining_main

        return remaining_main([])
    report = verify(args.package)
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
