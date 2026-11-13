"""Bounded main-app-container SELECT probe; no uploads, settings, writes or secrets."""

import argparse
import base64
import fnmatch
import hashlib
from datetime import datetime, timezone
import json
import os
import pty
import re
import select
import signal
import subprocess
import time

from sso_deployment_readiness import (
    APP,
    DATABASE,
    ROOT,
    SERVER,
    SUB,
    TENANT,
    Stop,
    az,
    require,
    resource,
    unique,
)

PRINCIPAL = "600447fe-5fea-4801-9033-ab4aafc474cc"
STAGES = {
    "shell_connect",
    "shell_ready",
    "working_directory",
    "python_executable",
    "python_started",
    "runtime_imports",
    "configuration",
    "database_engine",
    "sql_connect",
    "sql_identity",
    "revision",
    "schema_permissions",
    "role",
    "complete",
}


class ProbeStop(Stop):
    def __init__(self, category, stage, **diagnostics):
        super().__init__("UNKNOWN", category)
        self.diagnostics = {"stage": stage, **diagnostics}


def payload(marker):
    # Stream the frozen, hash-approved 004/005 probe contract in memory. The
    # application helper evolves independently for 006/007; those contracts are
    # not approved by this 004-only probe. No hosted file is made.
    contract = (ROOT / "scripts/contracts/schema_compatibility_004_005.py").read_text()
    require(
        hashlib.sha256(contract.encode()).hexdigest()
        == "e3530bb5af9199ee850f54f71984da4643dbd458c791dcd5b2c9a5b4e7612497",
        "REVIEWED_SCHEMA_CONTRACT_CHANGED",
    )
    diagnostics = (ROOT / "scripts/sql_diagnostics.py").read_text()
    return f"""
import contextlib, io, json, logging, sys, types
for name in ("azure", "msal", "sqlalchemy.engine"):
    logging.getLogger(name).setLevel(logging.CRITICAL)
result = {{"status":"UNKNOWN", "category":"RUNTIME_PROBE_UNAVAILABLE",
          "permission_subject":"actual_app_service_managed_identity",
          "hosted_runtime_identity_verified":False, "database_mutated":False}}
stage = "python_started"
def progress(value):
    global stage
    stage = value
    print({marker!r} + "STAGE:" + stage, file=sys.__stdout__, flush=True)
def ensure(condition):
    if not condition:
        raise AssertionError
progress(stage)
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        progress("runtime_imports")
        from sqlalchemy import text
        from sqlalchemy.engine import make_url
        from app.config import settings
        progress("configuration")
        ensure(settings.azure_sql_auth_mode == "managed_identity")
        ensure(settings.azure_sql_tenant_id.lower() == {TENANT!r})
        ensure(settings.azure_sql_user_object_id.lower() == {PRINCIPAL!r})
        url = make_url(settings.database_url)
        ensure(url.drivername == "mssql+pyodbc" and url.host == {SERVER + ".database.windows.net"!r} and url.database == {DATABASE!r})
        progress("database_engine")
        from app.database import SessionLocal
        module = types.ModuleType("app._readiness_contract")
        module.__package__ = "app"
        exec(compile({contract!r}, "<reviewed-read-only-contract>", "exec"), module.__dict__)
        progress("sql_connect")
        with SessionLocal() as db:
            db.connection()
            progress("sql_identity")
            ensure(db.scalar(text("SELECT DB_NAME()")) == {DATABASE!r})
            ensure(db.scalar(text("SELECT USER_NAME()")) == {APP!r})
            progress("revision")
            ensure(list(db.execute(text("SELECT version_num FROM dbo.alembic_version")).scalars()) == ["004"])
            progress("schema_permissions")
            checked = module.inspect_schema(db, require_sso=False)
            ensure(checked["revision"] == "004" and checked["versioned"] is True and checked["sso_schema"] is False)
            progress("role")
            role = db.scalar(text("SELECT IS_ROLEMEMBER('governance_validator_web_runtime')"))
            ensure(role == 1)
        progress("complete")
        result.update(status="PASS", category="RUNTIME_004_CONTRACT_VERIFIED",
                      hosted_runtime_identity_verified=True, principal_id={PRINCIPAL!r},
                      tenant_id={TENANT!r}, database={DATABASE!r}, revision="004",
                      schema_metadata_and_effective_permissions="PASS", runtime_role_member=True)
except AssertionError:
    result.update(status="FAIL", category={{
        "configuration":"RUNTIME_IDENTITY_CONFIGURATION_MISMATCH",
        "sql_identity":"RUNTIME_SQL_TARGET_OR_USER_MISMATCH",
        "revision":"RUNTIME_REVISION_MISMATCH", "role":"RUNTIME_ROLE_MEMBERSHIP_MISSING",
    }}.get(stage, "RUNTIME_IDENTITY_TARGET_OR_004_CONTRACT_MISMATCH"))
except Exception as error:
    if stage in ("runtime_imports", "python_started"):
        result.update(category="RUNTIME_IMPORT_UNAVAILABLE")
    else:
        diagnostic = types.ModuleType("_safe_sql_diagnostics")
        exec(compile({diagnostics!r}, "<safe-sql-diagnostics>", "exec"), diagnostic.__dict__)
        classified = diagnostic.classify(error, "schema" if stage == "schema_permissions" else stage)
        category = classified["category"]
        result.update(category=category)
        if stage == "schema_permissions" or category in ("SQL_PERMISSION_DENIED", "SQL_LOGIN_DENIED", "SQL_DATABASE_ACCESS_DENIED", "IDENTITY_PIN_OR_EXPIRY_MISMATCH"):
            result.update(status="FAIL")
result["stage"] = stage
print({marker!r} + json.dumps(result), file=sys.__stdout__, flush=True)
"""


def shell_event(marker, stage):
    return "printf '\\n%s\\n' " + repr(marker + "STAGE:" + stage) + "\n"


def shell_failure(marker, category, stage):
    value = {
        "status": "UNKNOWN",
        "category": category,
        "stage": stage,
        "hosted_runtime_identity_verified": False,
        "database_mutated": False,
    }
    # JSON contains only fixed labels and no credentials/paths.
    return (
        "printf '\\n%s%s\\n' " + repr(marker) + " '" + json.dumps(value) + "'; exit 1; "
    )


def layout_bootstrap(marker, *, layout_only=False):
    source = (ROOT / "scripts/runtime_layout.py").read_text()
    runtime = "" if layout_only else payload(marker)
    return f"""
import json, os, sys, types
module = types.ModuleType("_read_only_runtime_layout")
exec(compile({source!r}, "<read-only-layout-discovery>", "exec"), module.__dict__)
try:
    layout = module.discover_layout()
except module.LayoutError as error:
    print({marker!r} + json.dumps({{"status":"UNKNOWN", "category":str(error), "stage":"working_directory", "database_mutated":False, "hosted_runtime_identity_verified":False}}), flush=True)
    sys.exit(0)
print({marker!r} + "LAYOUT:" + json.dumps(layout), flush=True)
if not {layout_only!r}:
    os.chdir(layout["working_directory"])
    code = "import sys; sys.path.insert(0, " + repr(layout["application_import_path"]) + ");\\n" + {runtime!r}
    os.execve(layout["python_executable"], [layout["python_executable"], "-c", code], {{**os.environ, "PYTHONDONTWRITEBYTECODE":"1"}})
"""


def remote_input(marker, *, close_shell=True, layout_only=False):
    encoded = base64.b64encode(
        layout_bootstrap(marker, layout_only=layout_only).encode()
    ).decode()
    chunks = "\n".join(repr(encoded[i : i + 160]) for i in range(0, len(encoded), 160))
    return (
        "set +x; unset HISTFILE\n"
        + shell_event(marker, "working_directory")
        + "if command -v python >/dev/null 2>&1; then probe_python=python; "
        + "elif command -v python3 >/dev/null 2>&1; then probe_python=python3; "
        + 'elif [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then probe_python="$VIRTUAL_ENV/bin/python"; '
        + 'elif [ -n "$APP_PATH" ] && [ -x "$APP_PATH/antenv/bin/python" ]; then probe_python="$APP_PATH/antenv/bin/python"; '
        + "else "
        + shell_failure(
            marker, "RUNTIME_PYTHON_EXECUTABLE_UNAVAILABLE", "python_executable"
        )
        + "fi\n"
        + "PYTHONDONTWRITEBYTECODE=1 \"$probe_python\" - <<'SSO_READ_ONLY_PROBE'\n"
        + "import base64\nexec(base64.b64decode(\n"
        + chunks
        + "\n))\n"
        + "SSO_READ_ONLY_PROBE\n"
        + 'probe_status=$?; if [ "$probe_status" -ne 0 ]; then '
        + shell_failure(marker, "RUNTIME_PYTHON_PROCESS_FAILED", "python_executable")
        + "fi\n"
        + ("exit\n" if close_shell else "")
    ).encode()


def terminal_text(raw):
    # Remove ANSI CSI/OSC controls, including colored prompts and bracketed paste.
    value = raw.decode(errors="replace")
    value = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", value)
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)


def last_stage(raw, marker, default):
    stages = re.findall(
        re.escape(marker) + r"STAGE:([a-z_]+)(?:\r?\n)", terminal_text(raw)
    )
    return next((value for value in reversed(stages) if value in STAGES), default)


def safe_layout(raw, marker):
    for line in terminal_text(raw).splitlines(keepends=True):
        if line.startswith(marker + "LAYOUT:") and line.endswith("\n"):
            value = json.loads(line[len(marker + "LAYOUT:") :])
            keys = {
                "working_directory",
                "package_location",
                "python_executable",
                "application_import_path",
                "process_working_directory",
            }
            clean = {
                k: v
                for k, v in value.items()
                if k in keys
                and isinstance(v, str)
                and v.startswith("/")
                and len(v) < 1024
                and not any(ord(c) < 32 for c in v)
            }
            for key, values in {
                "evidence": {"running_app_process", "verified_bounded_root"},
                "startup_module": {
                    "app.hosting:app",
                    "app.main:app",
                    "backend.app.hosting:app",
                    "backend.app.main:app",
                    "NOT_OBSERVED",
                },
            }.items():
                if value.get(key) in values:
                    clean[key] = value[key]
            return clean
    return None


def safe_result(raw, marker):
    for line in terminal_text(raw).splitlines(keepends=True):
        if line.startswith(marker) and line.endswith("\n"):
            content = line[len(marker) :]
            if content.startswith(("STAGE:", "LAYOUT:")):
                continue
            try:
                value = json.loads(content)
            except ValueError:
                raise ProbeStop("PROBE_RESULT_JSON_INVALID", "complete") from None
            if not isinstance(value, dict):
                raise ProbeStop("PROBE_RESULT_JSON_INVALID", "complete")
            # Only fixed enumerated labels and known identifiers can leave the probe.
            allowed = {
                "status": {"PASS", "FAIL", "UNKNOWN"},
                "category": {
                    "RUNTIME_PROBE_UNAVAILABLE",
                    "RUNTIME_004_CONTRACT_VERIFIED",
                    "RUNTIME_SCHEMA_OR_EFFECTIVE_PERMISSION_NOT_VERIFIED",
                    "RUNTIME_IDENTITY_TARGET_OR_004_CONTRACT_MISMATCH",
                },
                "permission_subject": {"actual_app_service_managed_identity"},
                "hosted_runtime_identity_verified": {True, False},
                "database_mutated": {False},
                "principal_id": {PRINCIPAL},
                "tenant_id": {TENANT},
                "database": {DATABASE},
                "revision": {"004"},
                "schema_metadata_and_effective_permissions": {"PASS"},
                "runtime_role_member": {True},
            }
            from sql_diagnostics import DESCRIPTIONS

            contract = (ROOT / "backend/app/schema_compatibility.py").read_text()
            allowed["category"].update(DESCRIPTIONS)
            allowed["category"].update(
                re.findall(r'SchemaCheckError\("([A-Z_]+)"', contract)
            )
            allowed["category"].update(
                {
                    "RUNTIME_IDENTITY_CONFIGURATION_MISMATCH",
                    "RUNTIME_SQL_TARGET_OR_USER_MISMATCH",
                    "RUNTIME_REVISION_MISMATCH",
                    "RUNTIME_ROLE_MEMBERSHIP_MISSING",
                    "RUNTIME_IMPORT_UNAVAILABLE",
                    "SQL_CONFIGURATION_INVALID",
                    "SQL_CONNECTION_UNCLASSIFIED",
                    "APP_WORKING_DIRECTORY_UNAVAILABLE",
                    "RUNTIME_PYTHON_EXECUTABLE_UNAVAILABLE",
                    "RUNTIME_APP_PACKAGE_UNAVAILABLE",
                    "RUNTIME_APP_PACKAGE_NOT_FOUND_IN_BOUNDED_ROOTS",
                    "RUNTIME_APP_PACKAGE_LOCATION_AMBIGUOUS",
                    "RUNTIME_PYTHON_PROCESS_FAILED",
                }
            )
            allowed["stage"] = STAGES
            output = {
                k: v
                for k, v in value.items()
                if k in allowed and type(v) in (str, bool) and v in allowed[k]
            }
            require(
                output.get("status") in {"PASS", "FAIL", "UNKNOWN"}
                and "category" in output,
                "RUNTIME_RESPONSE_INVALID",
            )
            if output["status"] == "PASS":
                require(
                    all(
                        output.get(k) == v
                        for k, v in {
                            "category": "RUNTIME_004_CONTRACT_VERIFIED",
                            "principal_id": PRINCIPAL,
                            "tenant_id": TENANT,
                            "database": DATABASE,
                            "revision": "004",
                            "database_mutated": False,
                            "hosted_runtime_identity_verified": True,
                            "permission_subject": "actual_app_service_managed_identity",
                            "schema_metadata_and_effective_permissions": "PASS",
                            "runtime_role_member": True,
                        }.items()
                    ),
                    "RUNTIME_RESPONSE_INVALID",
                )
            return output
    return None


def channel_failure(raw, marker, stage, sent, timed_out, exit_code):
    text = terminal_text(raw).lower()
    category = None
    for words, label in (
        (
            (
                "unrecognized arguments",
                "not in the 'az webapp' command group",
                "'exec' is misspelled",
            ),
            "AZURE_CLI_EXEC_UNSUPPORTED",
        ),
        (
            (
                "authorizationfailed",
                "forbidden",
                "status code: 403",
                "401 unauthorized",
                "not authorized",
            ),
            "MAIN_APP_SHELL_AUTHORIZATION_DENIED",
        ),
        (
            ("az login", "aadsts", "authenticationfailed"),
            "EXISTING_CLI_AUTHENTICATION_UNAVAILABLE",
        ),
        (
            ("name resolution", "failed to resolve", "nameresolutionerror"),
            "MAIN_APP_SHELL_NETWORK_OR_DNS_UNAVAILABLE",
        ),
        (
            (
                "could not connect",
                "connection refused",
                "websocketbadstatus",
                "bad handshake",
            ),
            "MAIN_APP_SHELL_CONNECTION_FAILED",
        ),
    ):
        if any(word in text for word in words):
            category = label
            break
    if category is None:
        if not sent:
            category = (
                "SHELL_PROMPT_NOT_RECOGNIZED_TIMEOUT"
                if timed_out
                else "MAIN_APP_CLI_EXITED_BEFORE_SHELL_PROMPT"
            )
        elif stage in {"shell_ready", "working_directory", "python_executable"}:
            category = (
                "PYTHON_START_NOT_OBSERVED_TIMEOUT"
                if timed_out
                else "SHELL_EXITED_BEFORE_PYTHON_STARTED"
            )
        elif re.search(re.escape(marker) + r"[\{]", terminal_text(raw)):
            category = "PROBE_RESULT_INCOMPLETE_JSON"
        else:
            category = (
                "RUNTIME_STAGE_TIMEOUT"
                if timed_out
                else "RUNTIME_EXITED_WITHOUT_FINAL_RESULT"
            )
    return ProbeStop(
        category,
        stage,
        payload_sent=sent,
        timed_out=timed_out,
        cli_exit_code=exit_code if isinstance(exit_code, int) else None,
    )


def shell_probe(command, timeout=55, *, layout_only=False):
    marker = "SSO_PROBE_" + os.urandom(12).hex() + ":"
    master, slave = pty.openpty()
    os.set_blocking(master, False)
    process = None
    buffer = b""
    sent = False
    pending = b""
    stage = "shell_connect"
    timed_out = True
    try:
        process = subprocess.Popen(
            command,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env={**os.environ, "AZURE_CONFIG_DIR": str(ROOT / ".azure-sql-cli")},
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave)
        slave = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            readable, writable, _ = select.select(
                [master], [master] if pending else [], [], 0.2
            )
            if writable:
                try:
                    count = os.write(master, pending[:2048])
                    pending = pending[count:]
                except BlockingIOError:
                    pass
            if readable:
                try:
                    chunk = os.read(master, 16384)
                except OSError:
                    timed_out = False
                    break
                if not chunk:
                    timed_out = False
                    break
                buffer = (buffer + chunk)[-262144:]
                if not sent and re.search(
                    r"(?:^|[\r\n])[^\r\n]{0,180}[#$] *$", terminal_text(buffer)
                ):
                    pending = remote_input(marker, layout_only=layout_only)
                    sent = True
                    stage = "shell_ready"
                stage = last_stage(buffer, marker, stage)
                if layout_only:
                    layout = safe_layout(buffer, marker)
                    if layout:
                        return {
                            "status": "UNKNOWN",
                            "category": "LAYOUT_DISCOVERED_RUNTIME_SQL_NOT_TESTED",
                            "stage": "working_directory",
                            "layout_status": "PASS",
                            "layout": layout,
                            "database_mutated": False,
                            "hosted_runtime_identity_verified": False,
                        }
                result = safe_result(buffer, marker)
                if result is not None:
                    layout = safe_layout(buffer, marker)
                    return {**result, **({"layout": layout} if layout else {})}
            # Drain the PTY through EOF even if the CLI has already exited.
            # Polling and breaking here used to discard queued final output.
        raise channel_failure(buffer, marker, stage, sent, timed_out, process.poll())
    finally:
        if slave is not None:
            os.close(slave)
        os.close(master)
        if process is not None:
            # Stop only this local CLI session, never the Web App or its workers.
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def scoped_call(call, stage, *args):
    try:
        return call(*args)
    except Stop as error:
        raise ProbeStop(error.category, stage) from None


def verify(call=az, probe=shell_probe, *, layout_only=False):
    require((ROOT / ".azure-sql-cli").is_dir(), "PROJECT_CLI_CONTEXT_MISSING")
    account = scoped_call(
        call,
        "account_context",
        "account",
        "show",
        "--query",
        "{id:id,tenantId:tenantId,state:state}",
    )
    require(
        account.get("id") == SUB
        and account.get("tenantId") == TENANT
        and account.get("state") == "Enabled",
        "APPROVED_ACCOUNT_MISMATCH",
    )
    app = unique(
        scoped_call(
            call,
            "app_discovery",
            "webapp",
            "list",
            "--subscription",
            SUB,
            "--query",
            f"[?name=='{APP}'].{{name:name,resourceGroup:resourceGroup,id:id,state:state,identity:identity}}",
        )
    )
    group, app_id = resource(app, "Microsoft.Web", "sites", APP)
    identity = app.get("identity") or {}
    require(
        app.get("state") == "Running"
        and identity.get("principalId") == PRINCIPAL
        and identity.get("tenantId") == TENANT
        and "SystemAssigned" in str(identity.get("type", "")),
        "APP_OR_CONFIRMED_MANAGED_IDENTITY_DRIFT",
    )
    # Current CLI operator's existing management grants, not SQL permissions.
    recovery = (
        {"status": "NOT_ATTEMPTED_LAYOUT_ONLY"}
        if layout_only
        else recovery_review(call)
    )
    try:
        result = probe(
            [
                "az",
                "webapp",
                "exec",
                "--subscription",
                SUB,
                "--resource-group",
                group,
                "--name",
                APP,
                "--mode",
                "shell",
                "--target",
                "app",
                "--shell",
                "/bin/sh",
                "--only-show-errors",
            ]
        )
    except Stop as error:
        result = {
            "status": error.status,
            "category": error.category,
            "database_mutated": False,
            "hosted_runtime_identity_verified": False,
            **getattr(error, "diagnostics", {}),
        }
    return {
        **result,
        "app_resource_id": app_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "channel": "existing_main_app_container_shell",
        "status_scope": "hosted_runtime004_only_not_deployment_authorization",
        "recovery_review": recovery,
        "hosted_files_written": False,
    }


def allowed_action(entries, action):
    return any(
        any(
            fnmatch.fnmatchcase(action.lower(), value.lower())
            for value in entry.get("actions", [])
            if isinstance(value, str)
        )
        and not any(
            fnmatch.fnmatchcase(action.lower(), value.lower())
            for value in entry.get("notActions", [])
            if isinstance(value, str)
        )
        for entry in entries
        if isinstance(entry, dict)
    )


def recovery_review(call):
    server = unique(
        scoped_call(
            call,
            "recovery_server_discovery",
            "sql",
            "server",
            "list",
            "--subscription",
            SUB,
            "--query",
            f"[?name=='{SERVER}'].{{name:name,resourceGroup:resourceGroup,id:id}}",
        )
    )
    _, server_id = resource(server, "Microsoft.Sql", "servers", SERVER)
    entries = scoped_call(
        call,
        "recovery_permission_metadata",
        "rest",
        "--method",
        "get",
        "--url",
        f"https://management.azure.com{server_id}/providers/Microsoft.Authorization/permissions?api-version=2022-04-01",
        "--query",
        "value[].{actions:actions,notActions:notActions}",
    )
    require(isinstance(entries, list), "RECOVERY_PERMISSION_RESPONSE_INVALID")
    return {
        "permission_subject": "executing_cli_identity",
        "permission_metadata_readable": True,
        "database_read_action_in_allow_metadata": allowed_action(
            entries, "Microsoft.Sql/servers/databases/read"
        ),
        "database_write_action_in_allow_metadata": allowed_action(
            entries, "Microsoft.Sql/servers/databases/write"
        ),
        "restore_authority_verified": False,
        "designated_recovery_operator": "UNKNOWN_OPERATOR_CONFIRMATION_REQUIRED",
        "deny_assignments_locks_target_capacity_cutover": "UNKNOWN_REVIEW_REQUIRED",
        "recovery_drill": "NOT_PERFORMED_NOT_A_STAGE_B_PREREQUISITE",
        "migration005_recovery_readiness": "UNKNOWN_SEPARATE_REVIEW_REQUIRED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manual-console",
        action="store_true",
        help="Print reviewed read-only command for the existing main App Service console; no network",
    )
    parser.add_argument(
        "--layout-only",
        action="store_true",
        help="Discover paths only; no SQL/recovery checks. With --manual-console print the command",
    )
    args = parser.parse_args(argv)
    try:
        if args.manual_console:
            print(
                remote_input(
                    "SSO_MANUAL:", close_shell=False, layout_only=args.layout_only
                ).decode()
            )
            return 0
        result = (
            verify(
                probe=lambda command: shell_probe(command, layout_only=True),
                layout_only=True,
            )
            if args.layout_only
            else verify()
        )
    except Stop as error:
        result = {
            "status": error.status,
            "category": error.category,
            "database_mutated": False,
            "hosted_runtime_identity_verified": False,
            **getattr(error, "diagnostics", {}),
        }
    except Exception as error:
        # Unknown implementation failures are explicit; never echo error text.
        kind = type(error).__name__
        result = {
            "status": "FAIL",
            "category": "LOCAL_PROBE_IMPLEMENTATION_OR_INPUT_FAILURE",
            "stage": "local_probe",
            "error_kind": kind
            if kind
            in {
                "OSError",
                "FileNotFoundError",
                "ValueError",
                "TypeError",
                "KeyError",
                "ImportError",
                "ModuleNotFoundError",
            }
            else "UNCLASSIFIED",
            "database_mutated": False,
            "hosted_runtime_identity_verified": False,
        }
    print(json.dumps(result, indent=2))
    return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
