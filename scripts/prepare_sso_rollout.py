"""Read-only stage controller. A runs checks; B-G produce separate approval plans."""

import argparse
import json
from pathlib import Path
import subprocess

from sso_deployment_readiness import APP, DATABASE, PACKAGE_HASH, RELEASE, SUB

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    "B": {
        "name": "Compatibility deployment",
        "prerequisites": [
            "Current A evidence including actual runtime identity/permissions; reviewed 004 application rollback and owner (database restore drill not required for B)",
            "Confirmed target resource group and saved SSO=false/demo=true flags without secret disclosure",
            "Pinned candidate and original rollback ZIP available; accepted service interruption window",
        ],
        "approval_scope": [
            "Deploy only the pinned compatibility ZIP to the confirmed existing App Service",
            "Explicitly enumerate any setting changes/restart and bounded demo session/audit acceptance writes",
        ],
        "verification": "At 004: serving release, health/readiness, demo login/refresh/policy reads/RBAC/logout; no provider calls",
        "rollback": "Original checksum-verified 004 ZIP before migration only; no database changes",
    },
    "C": {
        "name": "Migration 005",
        "prerequisites": [
            "B accepted at 004; fresh exact database revision/schema and backup/PITR evidence",
            "Frozen reviewed 005 SQL/source; approved quiet window and recovery owner/RTO/RPO",
            "D minimum visibility/grants transaction boundary reviewed to avoid 005 readiness gap",
        ],
        "approval_scope": [
            "Apply only reviewed 004-to-005 migration to the confirmed database; no downgrade or retries on partial state"
        ],
        "verification": "Single 005 revision, three SSO tables/constraints/indexes, history protections, runtime metadata and working demo",
        "rollback": "Preserve 005 data; compatible bridge with SSO off/demo on; restore requires separate approval",
    },
    "D": {
        "name": "Minimum runtime grants",
        "prerequisites": [
            "Independently confirmed existing MI object/client IDs, contained user and custom role membership",
            "Review deployment/sso-runtime-permissions.REVIEW_ONLY.sql identity placeholder and exact 005 target",
            "Separate C and D approvals before any combined atomic transaction; neither authorizes the other",
        ],
        "approval_scope": [
            "Only SELECT sso_memberships and SELECT/INSERT/UPDATE sso_transactions and sso_sessions to existing runtime role",
            "No new roles/users/memberships, broad grants or membership writes",
        ],
        "verification": "Actual runtime effective grants and complete 005 metadata visibility; demo works",
        "rollback": "Stop and review drift; no automatic revocation or schema downgrade",
    },
    "E": {
        "name": "Approved SSO memberships",
        "prerequisites": [
            "C/D verified",
            "Exact tenant/object/workspace/actor/role/enabled values and existing authorized operator approved per member",
        ],
        "approval_scope": [
            "Provision only enumerated memberships through the reviewed operator tool; Admin requires explicit approval"
        ],
        "verification": "Exact intended membership/role and audit; unknown identities stay denied",
        "rollback": "Separate reviewed membership disable/correction; no bulk deletion",
    },
    "F": {
        "name": "SSO configuration and release",
        "prerequisites": [
            "B-E accepted; complete tenant/client/origin/CORS/callback review",
            "Existing secret supplied server-side by authorized operator without script/log/report access",
            "Review all pending portal changes; demo browser login stays enabled",
        ],
        "approval_scope": [
            "Save only enumerated SSO settings and explicitly approved restart window",
            "No second deployment needed for unchanged bridge; changed package requires separately reviewed checksum/deployment scope",
        ],
        "verification": "005 readiness and demo continue; login redirect has intended issuer/callback",
        "rollback": "Explicitly approved SSO=false/demo=true with compatible bridge; retain 005 data",
    },
    "G": {
        "name": "Real Microsoft login acceptance",
        "prerequisites": [
            "F verified",
            "Approved organizational test account/MFA and exact intended membership/role/workspace",
        ],
        "approval_scope": [
            "Real browser login/callback, bounded SQL session/audit writes, policy GET/refresh, CSRF/logout/denial tests; no paid AI/storage"
        ],
        "verification": "Correct role/tenant isolation, denied unknown user, logout/re-login, demo recovery; record sanitized evidence",
        "rollback": "Use separately approved F rollback if needed; demo retirement needs another explicit approval",
    },
}


def plan(stage):
    return {
        "stage": stage,
        **STAGES[stage],
        "status": "AWAITING_SEPARATE_APPROVAL",
        "subscription": SUB,
        "app": APP,
        "database": DATABASE,
        "release": RELEASE,
        "package_sha256": PACKAGE_HASH,
        "hosted_mutations_attempted": False,
        "approval_required": {
            "stage_only": stage,
            "exact_target_and_artifact": True,
            "fresh_prerequisite_evidence": True,
            "operator_and_approval_reference": True,
            "approved_window_and_rollback": True,
            "authorizes_later_stages": False,
        },
        "execution": "Preparation only. No hosted mutation executor is implemented or enabled. Separate review/approval is required before executing this plan.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=list("ABCDEFG"), default="A")
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print a later stage's approval checklist only",
    )
    args = parser.parse_args(argv)
    if args.stage == "A":
        if args.plan:
            parser.error("Stage A runs verification; omit --plan")
        return subprocess.run(
            ["bash", str(ROOT / "scripts/verify_sso_deployment_readiness.sh")],
            check=False,
        ).returncode
    if not args.plan:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "stage": args.stage,
                    "category": "PREPARATION_ONLY_USE_PLAN_AND_REQUEST_STAGE_SPECIFIC_APPROVAL",
                    "hosted_mutations_attempted": False,
                }
            )
        )
        return 2
    print(json.dumps(plan(args.stage), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
