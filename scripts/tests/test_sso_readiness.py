"""No network or hosted changes: exercise the complete orchestrated read-only path."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_sso_rollout as rollout
import sso_deployment_readiness as readiness


@pytest.fixture
def fixtures(monkeypatch, tmp_path):
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    (tmp_path / ".azure-sql-cli").mkdir()
    monkeypatch.setattr(
        readiness, "artifacts", lambda path: {"release": readiness.RELEASE}
    )
    group = "existing-group"
    base = f"/subscriptions/{readiness.SUB}/resourceGroups/{group}/providers"
    app = {
        "name": readiness.APP,
        "id": f"{base}/Microsoft.Web/sites/{readiness.APP}",
        "resourceGroup": group,
        "state": "Running",
        "identity": {
            "type": "SystemAssigned",
            "principalId": "11111111-2222-3333-4444-555555555555",
            "tenantId": readiness.TENANT,
        },
    }
    server = {
        "name": readiness.SERVER,
        "id": f"{base}/Microsoft.Sql/servers/{readiness.SERVER}",
        "resourceGroup": group,
    }
    db = {
        "id": f"{server['id']}/databases/{readiness.DATABASE}",
        "name": readiness.DATABASE,
        "status": "Online",
        "earliestRestoreDate": (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat(),
    }
    responses = [
        {"id": readiness.SUB, "tenantId": readiness.TENANT, "state": "Enabled"},
        [app],
        [server],
        db,
        {"retentionDays": 7},
        [{"actions": ["*"], "notActions": []}],
    ]
    cli = Mock(side_effect=responses)
    sql = Mock(
        return_value={
            "status": "PASS",
            "database": readiness.DATABASE,
            "revision": "004",
            "versioned": True,
            "sso_schema": False,
            "database_mutated": False,
            "permission_subject": "executing_cli_identity",
            "hosted_runtime_identity_verified": False,
        }
    )
    return cli, sql, responses


def test_successful_cli_checks_never_prove_runtime_or_recovery(fixtures):
    cli, sql, _ = fixtures
    report = readiness.verify(call=cli, sql_call=sql)
    assert report["status"] == "UNKNOWN"
    assert report["checks"]["cli_sql_schema004"]["status"] == "PASS"
    assert report["checks"]["backup_metadata"]["status"] == "PASS"
    assert report["checks"]["hosted_runtime"]["status"] == "UNKNOWN"
    assert report["checks"]["recovery_permissions"]["status"] == "UNKNOWN"
    assert not report["hosted_runtime_identity_verified"]
    assert not report["hosted_mutations_attempted"]
    assert sql.call_count == 1
    for call in cli.call_args_list:
        words = call.args
        assert words[:2] in {
            ("account", "show"),
            ("webapp", "list"),
            ("sql", "server"),
            ("sql", "db"),
            ("rest", "--method"),
        }
        assert not set(words) & {
            "login",
            "set",
            "deploy",
            "update",
            "create",
            "delete",
            "restart",
            "grant",
        }
        if words[0] == "rest":
            assert words[2] == "get"


@pytest.mark.parametrize(
    "fault", ["subscription", "tenant", "stopped", "ambiguous", "identity", "database"]
)
def test_fail_closed_and_stop(fixtures, fault):
    cli, sql, responses = fixtures
    if fault == "subscription":
        responses[0]["id"] = "wrong"
    elif fault == "tenant":
        responses[0]["tenantId"] = "wrong"
    elif fault == "stopped":
        responses[1][0]["state"] = "Stopped"
    elif fault == "ambiguous":
        responses[1].append(dict(responses[1][0]))
    elif fault == "identity":
        responses[1][0]["identity"]["principalId"] = None
    else:
        responses[3]["id"] = "wrong"
    report = readiness.verify(call=cli, sql_call=sql)
    assert report["status"] == "FAIL"
    sql.assert_not_called()
    assert cli.call_count < 6


@pytest.mark.parametrize(
    "field,value",
    [
        ("revision", "005"),
        ("sso_schema", True),
        ("versioned", False),
        ("database_mutated", True),
        ("permission_subject", "runtime"),
    ],
)
def test_sql_contract_stops_before_backup(fixtures, field, value):
    cli, sql, _ = fixtures
    sql.return_value[field] = value
    report = readiness.verify(call=cli, sql_call=sql)
    assert report["status"] == "FAIL"
    assert report["category"] == "CLI_SQL_004_CONTRACT_NOT_VERIFIED"
    assert cli.call_count == 4


def test_raw_errors_and_extra_response_fields_are_not_reported(fixtures):
    cli, sql, responses = fixtures
    secret = "SENSITIVE_TEST_SENTINEL"
    responses[0]["password"] = secret
    sql.side_effect = RuntimeError(f"password={secret} token={secret}")
    report = readiness.verify(call=cli, sql_call=sql)
    assert secret not in json.dumps(report)
    assert report["status"] == "UNKNOWN"
    assert cli.call_count == 4


def test_subprocess_failure_and_timeout_sanitized(monkeypatch):
    secret = "SENSITIVE_TEST_SENTINEL"
    runner = Mock(return_value=subprocess.CompletedProcess([], 1, secret, secret))
    monkeypatch.setattr(readiness.subprocess, "run", runner)
    with pytest.raises(readiness.Stop) as error:
        readiness.run_json(["az", "account", "show"])
    assert secret not in str(error.value)
    assert runner.call_args.kwargs["capture_output"] is True
    assert runner.call_args.kwargs["env"]["AZURE_CONFIG_DIR"] == str(
        readiness.ROOT / ".azure-sql-cli"
    )
    runner.side_effect = subprocess.TimeoutExpired(
        "az", 60, output=secret, stderr=secret
    )
    with pytest.raises(readiness.Stop):
        readiness.run_json(["az", "account", "show"])


def test_missing_context_stops_before_cloud(fixtures):
    cli, sql, _ = fixtures
    (readiness.ROOT / ".azure-sql-cli").rmdir()
    report = readiness.verify(call=cli, sql_call=sql)
    assert report["category"] == "PROJECT_CLI_CONTEXT_MISSING"
    cli.assert_not_called()


def test_artifact_tamper_and_missing_stop_before_cloud(fixtures, monkeypatch, tmp_path):
    cli, sql, _ = fixtures
    monkeypatch.undo()
    artifact = tmp_path / "fake.zip"
    artifact.write_bytes(b"tampered")
    report = readiness.verify(package=artifact, call=cli, sql_call=sql)
    assert report["status"] == "FAIL"
    cli.assert_not_called()
    artifact.unlink()
    assert (
        readiness.verify(package=artifact, call=cli, sql_call=sql)["category"]
        == "ARTIFACT_MISSING"
    )


@pytest.mark.parametrize("stage", list("BCDEFG"))
def test_later_stages_cannot_execute_or_cascade(stage, monkeypatch, capsys):
    runner = Mock(side_effect=AssertionError("No hosted executor allowed"))
    monkeypatch.setattr(rollout.subprocess, "run", runner)
    assert rollout.main(["--stage", stage]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"
    assert rollout.main(["--stage", stage, "--plan"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["approval_required"]["stage_only"] == stage
    assert plan["approval_required"]["authorizes_later_stages"] is False
    assert not plan["hosted_mutations_attempted"]
    runner.assert_not_called()


def test_default_is_a_only(monkeypatch):
    runner = Mock(return_value=subprocess.CompletedProcess([], 2))
    monkeypatch.setattr(rollout.subprocess, "run", runner)
    assert rollout.main([]) == 2
    assert runner.call_count == 1
    assert runner.call_args.args[0] == [
        "bash",
        str(rollout.ROOT / "scripts/verify_sso_deployment_readiness.sh"),
    ]


@pytest.mark.parametrize("fault", ["retention", "future", "missing"])
def test_backup_metadata_failure_stops_permissions_check(fixtures, fault):
    cli, sql, responses = fixtures
    if fault == "retention":
        responses[4]["retentionDays"] = 0
    elif fault == "future":
        responses[3]["earliestRestoreDate"] = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat()
    else:
        responses[3]["earliestRestoreDate"] = None
    report = readiness.verify(call=cli, sql_call=sql)
    assert report["status"] in {"FAIL", "UNKNOWN"}
    assert report["checks"]["backup_metadata"]["status"] != "PASS"
    assert cli.call_count == 5


@pytest.mark.parametrize(
    "diagnostic,category",
    [
        ("Temporary failure in name resolution", "AZURE_NETWORK_OR_DNS_UNAVAILABLE"),
        ("Please run az login", "EXISTING_CLI_AUTHENTICATION_UNAVAILABLE"),
        ("AuthorizationFailed", "EXISTING_READ_PERMISSION_UNAVAILABLE"),
    ],
)
def test_read_only_errors_categorized_without_disclosure(
    monkeypatch, diagnostic, category
):
    monkeypatch.setattr(
        readiness.subprocess,
        "run",
        Mock(
            return_value=subprocess.CompletedProcess(
                [], 1, "", diagnostic + " password=SENSITIVE_TEST_SENTINEL"
            )
        ),
    )
    with pytest.raises(readiness.Stop) as error:
        readiness.run_json(["az", "account", "show"])
    assert error.value.category == category
    assert "SENSITIVE_TEST_SENTINEL" not in str(error.value)
