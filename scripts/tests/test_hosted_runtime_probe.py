"""Focused read-only runtime-channel regressions; no live Azure or database access."""

import ast
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_hosted_runtime as runtime


def success():
    return {
        "status": "PASS",
        "category": "RUNTIME_004_CONTRACT_VERIFIED",
        "principal_id": runtime.PRINCIPAL,
        "tenant_id": runtime.TENANT,
        "database": runtime.DATABASE,
        "revision": "004",
        "database_mutated": False,
        "permission_subject": "actual_app_service_managed_identity",
        "hosted_runtime_identity_verified": True,
        "schema_metadata_and_effective_permissions": "PASS",
        "runtime_role_member": True,
    }


def test_complete_results_only_and_no_raw_output():
    raw = (
        b"banner=password=SENSITIVE\n"
        + b"MARK:"
        + json.dumps({**success(), "secret": "SENSITIVE"}).encode()
    )
    assert runtime.safe_result(raw, "MARK:") is None
    result = runtime.safe_result(raw + b"\r\n", "MARK:")
    assert result == success()
    assert "SENSITIVE" not in json.dumps(result)


@pytest.mark.parametrize(
    "field",
    [
        "principal_id",
        "tenant_id",
        "database",
        "permission_subject",
        "hosted_runtime_identity_verified",
    ],
)
def test_incomplete_or_wrong_identity_never_passes(field):
    value = success()
    value.pop(field)
    with pytest.raises(runtime.Stop):
        runtime.safe_result(b"MARK:" + json.dumps(value).encode() + b"\n", "MARK:")


def test_payload_is_pinned_in_memory_and_uses_read_only_session():
    source = runtime.payload("MARK:")
    ast.parse(source)
    assert "SessionLocal()" in source and "ManagedIdentityCredential(" not in source
    assert "SELECT USER_NAME()" in source and "SELECT DB_NAME()" in source
    assert 'settings.azure_sql_auth_mode == "managed_identity"' in source
    assert runtime.PRINCIPAL in source
    assert "db.commit(" not in source and "SessionLocal.begin(" not in source
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(ast.parse(source)))
    command = runtime.remote_input("MARK:").decode()
    assert max(map(len, command.splitlines())) < 1024
    assert "PYTHONDONTWRITEBYTECODE=1" in command and "unset HISTFILE" in command
    assert "> /" not in command and "pip install" not in command


def test_notactions_and_wildcards_are_allow_metadata_only():
    assert runtime.allowed_action(
        [{"actions": ["*"], "notActions": []}], "Microsoft.Sql/servers/databases/write"
    )
    assert not runtime.allowed_action(
        [{"actions": ["*"], "notActions": ["Microsoft.Sql/*/write"]}],
        "Microsoft.Sql/servers/databases/write",
    )
    assert runtime.allowed_action(
        [{"actions": ["Microsoft.Sql/servers/*"], "notActions": []}],
        "Microsoft.Sql/servers/databases/read",
    )


@pytest.fixture
def cloud(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    (tmp_path / ".azure-sql-cli").mkdir()
    group = "existing-group"
    prefix = f"/subscriptions/{runtime.SUB}/resourceGroups/{group}/providers"
    responses = [
        {"id": runtime.SUB, "tenantId": runtime.TENANT, "state": "Enabled"},
        [
            {
                "name": runtime.APP,
                "resourceGroup": group,
                "id": f"{prefix}/Microsoft.Web/sites/{runtime.APP}",
                "state": "Running",
                "identity": {
                    "type": "SystemAssigned",
                    "principalId": runtime.PRINCIPAL,
                    "tenantId": runtime.TENANT,
                },
            }
        ],
        [
            {
                "name": runtime.SERVER,
                "resourceGroup": group,
                "id": f"{prefix}/Microsoft.Sql/servers/{runtime.SERVER}",
            }
        ],
        [{"actions": ["*"], "notActions": []}],
    ]
    return Mock(side_effect=responses), responses


def test_existing_main_app_channel_only_and_no_restore_claim(cloud):
    call, _ = cloud
    probe = Mock(return_value=success())
    result = runtime.verify(call=call, probe=probe)
    command = probe.call_args.args[0]
    assert command[:3] == ["az", "webapp", "exec"]
    assert command[command.index("--mode") + 1] == "shell"
    assert command[command.index("--target") + 1] == "app"
    assert not result["hosted_files_written"]
    assert not result["recovery_review"]["restore_authority_verified"]
    assert result["recovery_review"]["database_write_action_in_allow_metadata"]
    assert "NOT_A_STAGE_B_PREREQUISITE" in result["recovery_review"]["recovery_drill"]
    assert all(
        "list-publishing-credentials" not in args.args for args in call.call_args_list
    )


def test_identity_drift_stops_before_channel_or_recovery(cloud):
    call, responses = cloud
    responses[1][0]["identity"]["principalId"] = "wrong"
    probe = Mock()
    with pytest.raises(runtime.Stop):
        runtime.verify(call=call, probe=probe)
    probe.assert_not_called()
    assert call.call_count == 2


def test_channel_unavailable_preserves_permission_metadata(cloud):
    call, _ = cloud
    result = runtime.verify(
        call=call,
        probe=Mock(
            side_effect=runtime.Stop(
                "UNKNOWN", "MAIN_APP_SHELL_OR_COMPLETE_PROBE_RESULT_UNAVAILABLE"
            )
        ),
    )
    assert result["status"] == "UNKNOWN"
    assert not result["hosted_runtime_identity_verified"]
    assert result["recovery_review"]["permission_metadata_readable"]


def test_pty_probe_collects_only_completed_sanitized_result():
    # A local fake CLI shell exercises PTY input/output; it never executes payload SQL.
    source = """
import ast, base64, json, re, sys
print("banner password=SENSITIVE", flush=True)
print("$ ", end="", flush=True)
body = []
collect = False
for line in sys.stdin:
    if line.strip() == "import base64":
        collect = True
    if collect:
        if line.strip() == "SSO_READ_ONLY_PROBE":
            break
        body.append(line)
node = ast.parse("".join(body)).body[1].value.args[0].args[0]
payload = base64.b64decode(ast.literal_eval(node)).decode()
marker = re.search(r"SSO_PROBE_[0-9a-f]+:", payload).group()
print(marker + json.dumps(RESULT), flush=True)
""".replace("RESULT", repr(success()))
    result = runtime.shell_probe([sys.executable, "-c", source], timeout=5)
    assert result == success()
    assert "SENSITIVE" not in json.dumps(result)


def test_pty_no_prompt_times_out_without_printing_banner():
    with pytest.raises(runtime.Stop) as error:
        runtime.shell_probe(
            [
                sys.executable,
                "-c",
                "import time; print('password=SENSITIVE', flush=True); time.sleep(5)",
            ],
            timeout=0.2,
        )
    assert error.value.category == "SHELL_PROMPT_NOT_RECOGNIZED_TIMEOUT"
    assert "SENSITIVE" not in str(error.value)


def test_existing_wrapper_dispatch_skips_already_passing_checks(monkeypatch):
    import sso_deployment_readiness as readiness

    runner = Mock(return_value=2)
    monkeypatch.setattr(runtime, "main", runner)
    old_verify = Mock(side_effect=AssertionError("Full A must not repeat"))
    monkeypatch.setattr(readiness, "verify", old_verify)
    monkeypatch.setattr(sys, "argv", ["preflight", "--remaining-only"])
    assert readiness.main() == 2
    runner.assert_called_once_with([])
    old_verify.assert_not_called()


def test_stage_b_keeps_runtime_and_rollback_gate_without_database_restore_drill():
    import prepare_sso_rollout as rollout

    requirements = " ".join(rollout.plan("B")["prerequisites"])
    assert "actual runtime identity/permissions" in requirements
    assert "reviewed 004 application rollback and owner" in requirements
    assert "database restore drill not required for B" in requirements
    assert not rollout.plan("B")["approval_required"]["authorizes_later_stages"]


@pytest.mark.parametrize(
    "text,category",
    [
        (
            "ERROR AuthorizationFailed 403 password=SENSITIVE",
            "MAIN_APP_SHELL_AUTHORIZATION_DENIED",
        ),
        ("ERROR 'exec' is misspelled token=SENSITIVE", "AZURE_CLI_EXEC_UNSUPPORTED"),
        (
            "Could not connect websocket password=SENSITIVE",
            "MAIN_APP_SHELL_CONNECTION_FAILED",
        ),
    ],
)
def test_cli_shell_failures_are_precise_and_sanitized(text, category):
    source = "import sys; print(" + repr(text) + "); sys.exit(1)"
    with pytest.raises(runtime.ProbeStop) as error:
        runtime.shell_probe([sys.executable, "-c", source], timeout=2)
    assert error.value.category == category
    assert error.value.diagnostics["stage"] == "shell_connect"
    assert not error.value.diagnostics["payload_sent"]
    assert "SENSITIVE" not in json.dumps(error.value.diagnostics)


def test_colored_prompt_and_final_queued_output_are_handled():
    source = """
import ast, base64, json, re, sys
print("\\x1b[32mroot@host:# \\x1b[0m", end="", flush=True)
body = []
for line in sys.stdin:
    if line.strip() == "import base64" or body:
        if line.strip() == "SSO_READ_ONLY_PROBE": break
        body.append(line)
node = ast.parse("".join(body)).body[1].value.args[0].args[0]
marker = re.search(r"SSO_PROBE_[0-9a-f]+:", base64.b64decode(ast.literal_eval(node)).decode()).group()
print(marker + "STAGE:sql_connect", flush=True)
print("noise" * 10000, flush=True)
print(marker + json.dumps(RESULT), flush=True)
""".replace("RESULT", repr(success()))
    assert runtime.shell_probe([sys.executable, "-c", source], timeout=5) == success()


def test_incomplete_and_malformed_json_are_distinct():
    assert runtime.safe_result(b'MARK:{"status":"PA', "MARK:") is None
    error = runtime.channel_failure(
        b'MARK:{"status":"PA', "MARK:", "sql_connect", True, False, 1
    )
    assert error.category == "PROBE_RESULT_INCOMPLETE_JSON"
    with pytest.raises(runtime.ProbeStop) as error:
        runtime.safe_result(b"MARK:{broken}\n", "MARK:")
    assert error.value.category == "PROBE_RESULT_JSON_INVALID"


def test_runtime_timeout_reports_last_safe_stage():
    error = runtime.channel_failure(
        b"MARK:STAGE:sql_connect\n", "MARK:", "sql_connect", True, True, None
    )
    assert error.category == "RUNTIME_STAGE_TIMEOUT"
    assert error.diagnostics["stage"] == "sql_connect"
    assert (
        runtime.last_stage(b"MARK:STAGE:sql_connect\n", "MARK:", "shell_ready")
        == "sql_connect"
    )


@pytest.mark.parametrize(
    "fault,category,stage",
    [
        ("permission", "SQL_PERMISSION_DENIED", "schema_permissions"),
        ("identity", "RUNTIME_IDENTITY_CONFIGURATION_MISMATCH", "configuration"),
        ("imports", "RUNTIME_IMPORT_UNAVAILABLE", "runtime_imports"),
        ("connection", "SQL_CONNECTION_TIMEOUT", "sql_connect"),
        (None, "RUNTIME_004_CONTRACT_VERIFIED", "complete"),
    ],
)
def test_real_payload_error_handling_no_sql_writes(monkeypatch, fault, category, stage):
    import io
    import types

    code = runtime.payload("MARK:")
    settings = types.SimpleNamespace(
        azure_sql_auth_mode="managed_identity",
        azure_sql_tenant_id=runtime.TENANT,
        azure_sql_user_object_id=runtime.PRINCIPAL,
        database_url=f"mssql+pyodbc://{runtime.SERVER}.database.windows.net/{runtime.DATABASE}",
    )
    if fault == "identity":
        settings.azure_sql_user_object_id = "wrong"
    calls = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def connection(self):
            if fault == "connection":
                raise Exception("HYT00", "timeout password=SENSITIVE")

        def scalar(self, statement):
            calls.append(str(statement))
            return {
                "SELECT DB_NAME()": runtime.DATABASE,
                "SELECT USER_NAME()": runtime.APP,
                "SELECT IS_ROLEMEMBER('governance_validator_web_runtime')": 1,
            }[str(statement)]

        def execute(self, statement):
            calls.append(str(statement))
            return types.SimpleNamespace(scalars=lambda: ["004"])

    app = types.ModuleType("app")
    app.__path__ = []
    config = types.ModuleType("app.config")
    config.settings = settings
    database = types.ModuleType("app.database")
    database.SessionLocal = Session
    monkeypatch.setitem(sys.modules, "app", app)
    monkeypatch.setitem(
        sys.modules, "app.config", None if fault == "imports" else config
    )
    monkeypatch.setitem(sys.modules, "app.database", database)

    # Substitute the schema implementation only; exercise the actual payload
    # identity/session/stage/classifier/output code, with no network or SQL writes.
    def compile_stub(source, filename, mode):
        if filename == "<reviewed-read-only-contract>":
            if fault == "permission":
                source = 'def inspect_schema(db, **kwargs):\n raise Exception("42000", "denied password=SENSITIVE (229)")'
            else:
                source = 'def inspect_schema(db, **kwargs):\n return {"revision":"004","versioned":True,"sso_schema":False}'
        return compile(source, filename, mode)

    output = io.StringIO()
    monkeypatch.setattr(sys, "__stdout__", output)
    exec(code, {"compile": compile_stub})
    rendered = output.getvalue()
    assert "SENSITIVE" not in rendered
    value = runtime.safe_result(rendered.encode(), "MARK:")
    assert value["category"] == category and value["stage"] == stage
    assert all(statement.startswith("SELECT ") for statement in calls)
    assert not value["database_mutated"]
    assert value["hosted_runtime_identity_verified"] is (fault is None)


def test_manual_fallback_is_self_contained_read_only_command():
    command = runtime.remote_input("SSO_MANUAL:", close_shell=False).decode()
    assert not command.endswith("exit\n")
    assert "SSO_READ_ONLY_PROBE" in command
    assert "LAYOUT:" in runtime.layout_bootstrap("MARK:")
    assert "pip install" not in command and "az webapp" not in command


@pytest.mark.parametrize(
    "fault,category",
    [
        ("directory", "APP_WORKING_DIRECTORY_UNAVAILABLE"),
        ("package", "RUNTIME_APP_PACKAGE_UNAVAILABLE"),
        ("python", "RUNTIME_PYTHON_EXECUTABLE_UNAVAILABLE"),
    ],
)
def test_shell_pre_python_failures_are_reported(monkeypatch, tmp_path, fault, category):
    import os
    import subprocess

    path = tmp_path / "app-root"
    if fault != "directory":
        path.mkdir()
    if fault == "python":
        (path / "app").mkdir()
        (path / "app/database.py").touch()
    env = {
        **os.environ,
        "APP_PATH": str(path),
        "VIRTUAL_ENV": "",
        "PATH": str(tmp_path / "empty"),
    }
    output = subprocess.run(
        ["/bin/sh"], input=runtime.remote_input("MARK:"), env=env, capture_output=True
    )
    value = runtime.safe_result(output.stdout, "MARK:")
    assert value["category"] == "RUNTIME_PYTHON_EXECUTABLE_UNAVAILABLE"
    assert value["status"] == "UNKNOWN" and not value["database_mutated"]


def test_arm_failure_names_external_stage(cloud):
    call, _ = cloud
    call.side_effect = [
        {"id": runtime.SUB, "tenantId": runtime.TENANT, "state": "Enabled"},
        runtime.Stop("UNKNOWN", "AZURE_NETWORK_OR_DNS_UNAVAILABLE"),
    ]
    with pytest.raises(runtime.ProbeStop) as error:
        runtime.verify(call=call, probe=Mock())
    assert error.value.diagnostics["stage"] == "app_discovery"
    assert error.value.category == "AZURE_NETWORK_OR_DNS_UNAVAILABLE"


@pytest.mark.parametrize("suffix", ["\n# synthetic changed contract\n", "\n"])
def test_frozen_contract_fingerprint_rejects_changes(monkeypatch, tmp_path, suffix):
    reference = runtime.ROOT / "scripts/contracts/schema_compatibility_004_005.py"
    frozen = tmp_path / "scripts/contracts/schema_compatibility_004_005.py"
    frozen.parent.mkdir(parents=True)
    frozen.write_text(reference.read_text() + suffix)
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    with pytest.raises(runtime.Stop) as error:
        runtime.payload("LOCAL_ONLY:")
    assert error.value.category == "REVIEWED_SCHEMA_CONTRACT_CHANGED"


def test_probe_uses_only_hash_approved_legacy_contract():
    source = runtime.payload("LOCAL_ONLY:")
    assert 'SUPPORTED_REVISIONS = ("004", "005")' in source
    assert "from .models import Base" in source
    assert "schema_manifests" not in source
    assert "schema_006_verification" not in source
    assert "review_protected_content" not in source


def test_application_helper_changes_do_not_redefine_probe(monkeypatch, tmp_path):
    import shutil

    for name in ("scripts/contracts/schema_compatibility_004_005.py", "scripts/sql_diagnostics.py"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(runtime.ROOT / name, target)
    application = tmp_path / "backend/app/schema_compatibility.py"
    application.parent.mkdir(parents=True)
    application.write_text("raise RuntimeError('must never be loaded by legacy probe')")
    expected = runtime.payload("LOCAL_ONLY:")
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    assert runtime.payload("LOCAL_ONLY:") == expected
