"""Read live settings, simulate cutover and rollback in memory; never writes Azure."""

import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "deployment/cutover-rollback-fields.REVIEW_ONLY.json"
NEW = "mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-gpv-demo-v008-20261108"


def main():
    plan = json.loads(PLAN.read_text())
    cmd = [
        "az", "webapp", "config", "appsettings", "list",
        "--subscription", plan["subscription"], "--resource-group", plan["resource_group"],
        "--name", plan["webapp"], "--output", "json", "--only-show-errors",
    ]
    raw = subprocess.run(
        cmd, cwd=ROOT, env={**os.environ, "AZURE_CONFIG_DIR": str(ROOT / ".azure-sql-cli")},
        capture_output=True, text=True, timeout=40, check=True,
    ).stdout
    current = {entry["name"]: entry["value"] for entry in json.loads(raw)}
    expected = plan["original_changed_fields"]
    for key, value in expected.items():
        if current.get(key) != value or (value is None) != (key not in current):
            raise RuntimeError("ORIGINAL_FIELD_DRIFT")
    if not current.get("REVIEW_CONTENT_ACTIVE_KEY_ID") or not current.get("REVIEW_CONTENT_KEYS_JSON"):
        raise RuntimeError("REVIEW_KEY_SETTINGS_MISSING")
    proposed = {**current, "DATABASE_URL": NEW, "REVIEW_CAPTURE_ENABLED": "false", "REVIEW_CLEANUP_ENABLED": "true"}
    if len(proposed) != len(current) + 2:
        raise RuntimeError("PROPOSED_DELTA_MISMATCH")
    restored = dict(proposed)
    for key, value in expected.items():
        if value is None:
            restored.pop(key, None)
        else:
            restored[key] = value
    if restored != current:
        raise RuntimeError("SIMULATED_ROLLBACK_MISMATCH")
    drift = dict(proposed)
    drift["UNRELATED_CONCURRENT_CHANGE"] = "synthetic"
    if drift == proposed:
        raise RuntimeError("DRIFT_TEST_INVALID")
    report = {
        "status": "PASS_LOCAL_SIMULATION_ONLY", "azure_settings_written": False,
        "original_changed_fields_matched": True, "original_setting_count": len(current),
        "rollback_restored_all_original_values_in_memory": True,
        "secret_values_logged_or_saved": False,
        "actual_azure_conditional_write_verified": False,
        "exclusive_writer_boundary_verified": False,
    }
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
