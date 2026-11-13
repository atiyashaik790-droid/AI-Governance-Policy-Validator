# Stage B compatibility deployment approval — 4 November 2026

Status: PREPARED; NOT APPROVED OR EXECUTED.

## Evidence and scope

The existing working tree contains prior modified and untracked implementation, tests and evidence. All are preserved. No code was rewritten, hosted checks or test suites rerun, or Azure operations performed during this preparation. Local candidate and rollback SHA-256 confirmation only was performed.

Latest user-reported runtime verification (this continuation's evidence; not an independent agent observation) supersedes the older runtime UNKNOWN notes in the deployment documents:

```json
{
  "status": "PASS",
  "category": "RUNTIME_004_CONTRACT_VERIFIED",
  "permission_subject": "actual_app_service_managed_identity",
  "hosted_runtime_identity_verified": true,
  "schema_metadata_and_effective_permissions": "PASS",
  "runtime_role_member": true,
  "revision": "004",
  "database_mutated": false
}
```

The user also confirms the existing app is running, SQL connected at 004, backup retention seven days and corrected package verified. Earlier evidence records principal object ID `600447fe-5fea-4801-9033-ab4aafc474cc`. Preserve all historical evidence as historical; do not rerun passed verification to satisfy obsolete UNKNOWN statements. This is not migration 005 or full SSO readiness certification.

## Frozen artifacts

| Purpose | Artifact | Release | SHA-256 |
|---|---|---|---|
| Deploy | `/tmp/governance-sso-compatibility-fixed-004-20261104.zip` | `1.2-6749226f1af65b63` | `9d81fa9b7700557eac2cb41edd5ab861d19a6b8c4f9052e55068e5eab784df80` |
| Rollback while SQL remains 004 | `artifacts/restricted-demo-20261101/governance-workspace-policy-delete.zip` | `1.2-5e8064f901573795` | `b44afedb721ae8ed5b4d48c9ea50fe3aab6a586ed8325af7c08ca93969abf776` |

Both files exist and match these hashes. Candidate manifest: `docs/evidence/sso-compatibility/package-fixed004.json`; original manifest: `docs/evidence/workspace-delete-package.json`. Candidate supports 004/005, minimum 004; SSO requires 005. Superseded candidate `1.2-7105751bb3be1300` must not be used. Deploy the frozen ZIP, not a rebuild of the dirty tree. Keep the `/tmp` artifact available through acceptance/rollback.

## Remaining Stage B prerequisites

1. Bind the existing app's resource group/ARM ID using the non-secret exact-name lookup below. The supplied latest evidence does not contain its group, and historical runbook placeholders are not authoritative.
2. Confirm saved effective SSO disabled/demo enabled flags through an existing authorized safe boolean-only view. Preserve database selection, account hashes, managed identity and all other settings. If incompatible, STOP: this approval contains no settings-save authorization and the pending Entra secret must remain unsaved. Missing flags may use application defaults only if their effective behavior is confirmed.
3. Approval names the existing authorized release/rollback operator and execution window; accepts a possible service interruption and bounded demo session/audit/rate-limit writes. Proposed operator: this agent using the existing project CLI context; proposed window: immediately after explicit approval, if that context has existing deployment access. No login, identity switch or new permissions.

A fresh restore drill is not a Stage B requirement in the reviewed documents. Restore authority, current exact PITR point, recovery ownership/RTO/RPO/cutover and the atomic 005 visibility/grant boundary remain separate migration approval prerequisites. No database restore is included here.

## Exact prepared deployment commands — execute only after explicit approval

Run from repository root. This resolves the missing group without guessing or changing Azure. If lookup is unavailable/ambiguous, stop; do not retry deployment or change access settings.

```bash
export AZURE_CONFIG_DIR="$PWD/.azure-sql-cli"
STAGE_B_GROUP="$(az webapp list \
  --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 \
  --query "[?name=='app-governance-validator-atiya-1026'].resourceGroup" \
  --output tsv --only-show-errors)" || exit 1
[[ -n "$STAGE_B_GROUP" && "$STAGE_B_GROUP" != *$'\n'* ]] || exit 1
az webapp show \
  --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 \
  --resource-group "$STAGE_B_GROUP" --name app-governance-validator-atiya-1026 \
  --query '{id:id,name:name,resourceGroup:resourceGroup,state:state}' \
  --output json --only-show-errors
# STOP unless this resolves the intended existing Running app and flag prerequisite is satisfied.
az webapp deploy \
  --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 \
  --resource-group "$STAGE_B_GROUP" --name app-governance-validator-atiya-1026 \
  --type zip --src-path /tmp/governance-sso-compatibility-fixed-004-20261104.zip \
  --async true --output none --only-show-errors
```

This uses the repository's established ZIP/Oryx deployment path and existing build/startup configuration. Approval includes the deployment-induced application restart/interruption, not a separate settings update/restart command. Submit once; an asynchronous return is not acceptance. Observe the existing deployment status until terminal outcome before proceeding. On submission timeout/unknown state, reconcile deployment status before any further submission; never blindly retry or race rollback against an active deployment. Preserve sanitized deployment ID/status and acceptance results, never raw secrets or CLI debug output.

## Acceptance after deployment

At `https://app-governance-validator-atiya-1026.azurewebsites.net`:

- `/health` and `/ready` return success; readiness reports actual revision 004 and release `1.2-6749226f1af65b63`, minimum 004/supported 004 and 005. Confirm served frontend reflects this release using the existing public release metadata.
- In a fresh browser context, approved existing demo login succeeds; refresh/session restoration, tenant-scoped policy GET and logout work.
- Existing approved role/tenant negative checks deny unauthorized access; SSO stays unavailable. No new accounts or memberships are created for acceptance.
- Bound activity to those checks and their normal session/audit/rate-limit writes. No policy mutations, provider generation/moderation, exports or ADLS operations.

These are acceptance checks of the newly hosted release, not repetition of completed predeployment tests. Fail acceptance on wrong release, unready app, failed demo/session/logout or any tenant/role isolation failure. Do not bypass guards.

## Rollback included in proposed Stage B approval

After reconciling any active deployment, on failed acceptance redeploy the pinned original ZIP to the same confirmed app, leaving configuration and SQL 004 unchanged:

```bash
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az webapp deploy \
  --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 \
  --resource-group "${STAGE_B_GROUP:?confirmed Stage B resource group required}" \
  --name app-governance-validator-atiya-1026 --type zip \
  --src-path "$PWD/artifacts/restricted-demo-20261101/governance-workspace-policy-delete.zip" \
  --async true --output none --only-show-errors
```

Observe terminal deployment outcome, then verify original release `1.2-5e8064f901573795`, health/readiness at 004 and the same bounded demo acceptance. If rollback fails or data integrity is in doubt, stop and report; no database repair/restore or configuration change is authorized. This original ZIP is forbidden against 005. After any separately approved migration, the corrected 004/005 bridge is the application fallback with separately approved flags; no downgrade or dropping tables.

## Single approval request

Approve Stage B only: deploy corrected release `1.2-6749226f1af65b63` with the pinned hash to existing `app-governance-validator-atiya-1026` in subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, using the exact group resolved above, conditional on saved SSO-off/demo-on flags; authorize this agent through the existing CLI context immediately after approval, deployment interruption, bounded demo acceptance writes and the pinned original-004 ZIP rollback on failed acceptance. No migration 005, SQL permissions/membership changes, Azure configuration changes, SSO activation or database restore is included.
