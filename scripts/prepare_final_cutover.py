"""Print a local cutover command review. Never invokes Azure or executes commands."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def review():
    manifest = json.loads(
        (ROOT / "deployment/final-cutover.REVIEW_ONLY.json").read_text()
    )
    evidence = json.loads(
        (
            ROOT / "docs/evidence/runtime-user-bootstrap-2026-11-09/summary.json"
        ).read_text()
    )
    seed = json.loads(
        (ROOT / "docs/evidence/policy-seeding-retry-2026-11-09/result.json").read_text()
    )
    sql_seed = seed.get("sql_result", {})
    hosted_mi = json.loads(
        (ROOT / "docs/evidence/policy-seeding-retry-2026-11-09/hosted-mi-new008.json").read_text()
    )
    if (
        seed.get("status") != "PASS"
        or seed.get("firewall_cleanup") != "PASS"
        or not seed.get("original_rules_unchanged")
        or sql_seed.get("status") != "PASS"
        or not sql_seed.get("transaction_committed")
        or sql_seed.get("policy_count") != 8
        or sql_seed.get("active_policy_count") != 8
        or sql_seed.get("revision") != "008"
    ):
        raise ValueError("Committed eight-policy seed evidence missing")
    if (
        hosted_mi.get("status") != "PASS"
        or hosted_mi.get("channel") != "existing_main_app_container_shell"
        or hosted_mi.get("database") != manifest["target_database"]["name"]
        or hosted_mi.get("revision") != "008"
        or hosted_mi.get("policies") != 8
        or hosted_mi.get("active_assignments") != 8
        or hosted_mi.get("database_mutated") is not False
    ):
        raise ValueError("Hosted new008 managed-identity evidence missing")
    artifacts = {}
    for key in ("candidate", "paired_rollback"):
        entry = manifest[key]
        path = (ROOT / entry["path"]).resolve()
        if not path.is_relative_to(ROOT / "artifacts"):
            raise ValueError("Artifact path outside reviewed artifact directory")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError("Pinned artifact checksum mismatch")
        artifacts[key] = {
            "path": str(path),
            "release": entry["release"],
            "sha256": actual,
        }
    if evidence["bootstrap"] != "PASS" or evidence["revision"] != "008":
        raise ValueError("Expected completed008 bootstrap evidence missing")
    common = [
        "--subscription",
        manifest["subscription"],
        "--resource-group",
        manifest["resource_group"],
        "--name",
        manifest["webapp"],
    ]

    def deploy(path):
        return [
            "az",
            "webapp",
            "deploy",
            *common,
            "--src-path",
            path,
            "--type",
            "zip",
            "--clean",
            "true",
            "--restart",
            "false",
            "--async",
            "false",
            "--track-status",
            "false",
            "--enable-kudu-warmup",
            "false",
            "--timeout",
            "600000",
            "--only-show-errors",
            "--output",
            "none",
        ]

    def setting(*values):
        return [
            "az",
            "webapp",
            "config",
            "appsettings",
            "set",
            *common,
            "--settings",
            *values,
            "--only-show-errors",
            "--output",
            "none",
        ]

    start = ["az", "webapp", "start", *common, "--only-show-errors", "--output", "none"]
    stop = ["az", "webapp", "stop", *common, "--only-show-errors", "--output", "none"]
    new_url = "mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-gpv-demo-v008-20261108"
    old_url = "mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-governance-validator-dev"
    return {
        "mode": "REVIEW_ONLY_NO_EXECUTOR_NO_CLOUD_ACCESS",
        "decision": "NO_GO",
        "artifacts": artifacts,
        "verified_bootstrap": evidence,
        "policy_latest_verified_count": sql_seed["policy_count"],
        "policy_current_hosted_count": "OLD005_SITE_NOT_NEW008",
        "hosted_new008_managed_identity": hosted_mi,
        "gates_still_required": [
            "Mandatory actual recovery/controlled-failure qualification evidence",
            "Approved exclusive config-writer boundary, drift protection, encrypted original-settings snapshot and available recovery operator",
            "Reconfirmed key recovery custody and exact absent/present original settings before restoration",
            "Fresh pre-deployment health/target checks plus explicit pinned cutover approval",
        ],
        "execution_order_after_approval_only": [
            {"stage": "stop_main_site_after_all_gates", "command": stop},
            {
                "stage": "deploy_pinned_candidate_main_site_must_stay_stopped",
                "command": deploy(artifacts["candidate"]["path"]),
            },
            {
                "stage": "verify_deployment_success_and_main_site_still_stopped",
                "command": None,
                "required": True,
            },
            {
                "stage": "apply_only_reviewed_setting_changes_under_exclusive_writer_guard",
                "command": setting(
                    "DATABASE_URL=" + new_url,
                    "REVIEW_CLEANUP_ENABLED=true",
                    "REVIEW_CAPTURE_ENABLED=false",
                ),
            },
            {"stage": "start_exact_candidate_with_new008_connection", "command": start},
            {
                "stage": "warmup_then_three_health_ready_pairs_plus_successful_cleanup_worker_pass",
                "command": None,
                "required": True,
            },
            {
                "stage": "only_after_worker_pass_enable_capture_if_explicitly_approved",
                "command": setting("REVIEW_CAPTURE_ENABLED=true"),
            },
            {
                "stage": "repeat_readiness_after_recycle_and_begin_only_approved_acceptance",
                "command": None,
                "required": True,
            },
        ],
        "paired_rollback_review_only": [
            {"stage": "stop_writers_and_main_site", "command": stop},
            {
                "stage": "restore_exact_original005_artifact",
                "command": deploy(artifacts["paired_rollback"]["path"]),
            },
            {
                "stage": "restore_original005_connection_under_exclusive_writer_guard",
                "command": setting("DATABASE_URL=" + old_url),
            },
            {
                "stage": "remove_only_two_flags_if_original_absence_is_freshly_confirmed",
                "command": [
                    "az",
                    "webapp",
                    "config",
                    "appsettings",
                    "delete",
                    *common,
                    "--setting-names",
                    "REVIEW_CAPTURE_ENABLED",
                    "REVIEW_CLEANUP_ENABLED",
                    "--only-show-errors",
                    "--output",
                    "none",
                ],
            },
            {
                "stage": "verify_old_pair_before_start",
                "command": None,
                "required": True,
            },
            {"stage": "start_restored005_pair", "command": start},
            {
                "stage": "verify005_release_and_readiness_keep_new008_db_and_keys",
                "command": None,
                "required": True,
            },
        ],
        "critical_command_limits": [
            "This tool has no execute/apply switch and does not authorize printed commands.",
            "App settings CLI merges into a whole-map update without verified CAS; never execute without the approved writer/restore guards.",
            "Clean deployment replaces deployed release files; confirm no unrelated persistent business files in webroot before approval.",
            "Linux deployment may have platform side effects despite restart=false; verify Stopped after deployment before connection change, abort/recover if it did not remain stopped.",
            "Disable Kudu warmup fallback to avoid the installed CLI's exception-driven deployment POST replay; ambiguous outcomes still require read-only reconciliation, no blind retry.",
            "A command timeout is not evidence that deployment stopped remotely; reconcile before retry or rollback.",
            "Original full settings must be backed up encrypted outside the repository; do not print, export plaintext, or reset encryption keys.",
            "No old005 application may start against008; rollback new008-only writes stay in the preserved new DB and are absent from005.",
            "Missing command=None checkpoints are mandatory gates, not instructions to skip checks.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(review(), indent=2))
