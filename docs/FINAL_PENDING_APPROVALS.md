> Historical release report. For the current implementation and deployment boundary, see [CURRENT_STATUS.md](CURRENT_STATUS.md).

# Final pending approvals

Updated 31 October 2026, Asia/Kolkata. **CONDITIONAL DEMO READINESS; NOT PRODUCTION READY.**

All safe local implementation and listed tests are complete. No approval-required operation below has been executed.

| Approval | Concrete scope | Why required / expected effect |
|---|---|---|
| SQL migration | Review and apply only 003→004 on existing sqldb-governance-validator-dev; six tables, one index and three append-only triggers; preserve all rows | User's sections 18/20 require hosted-schema approval. Index/DDL may lock tables; rollback is not destructive downgrade. Confirm backup/PITR and operator first. |
| Runtime permissions | Inspect actual existing runtime role; review deployment/runtime_004_permissions.REVIEW_ONLY.sql for new-table operations plus alembic SELECT | Permission change; no database-wide grants/new principals. Do not execute against an assumed role. |
| Deployment | Existing App Service; exact ZIP SHA-256 `3d81bdfca85f4df3b4786562283bce4d599d34662993f2c21623eeb6d3286992`, release `1.1-544cbf32d11a251a`; existing ZIP method; approved known-good package recovery if necessary | User's sections 4/20 prohibit silent deployment. Single-worker restart may cause several minutes' interruption. SQL must be ready first. |
| Hosted auth/read-only acceptance | Create bounded demo sessions and their audit rows; verify tenant/RBAC/revocation using existing provisioned accounts | New login/logout write session/audit rows; user requires approval for hosted data modifications. Ordinary public health/schema reads were already safe. |
| Paid generation/moderation | Proposed upper bounds: two generation calls and eight moderation calls; one harmless and one synthetic PII workflow; no automatic retries; zero exports | Paid usage and SQL execution/audit/usage writes. Must agree tenant, existing active version, exact policy behavior and retained record scope. Stop on error and retain sanitized diagnostics. |
| Fresh ADLS acceptance | One bounded metadata-only JSON export with a fixed idempotency key, one new deterministic object; exact read-back/hash; SQL job/export/audit writes | Storage mutation/live acceptance; no overwrite/deletion or repeated uncertain export. Confirm existing data-plane read/write access first; do not add roles silently. |
| Enterprise identity | User identifies approved provider and supplies issuer/audience/tenant/role mapping via secure configuration | No provider/configuration supplied; do not invent credentials, new services or custom MFA. |
| Commit | Review source/tests/docs and preexisting changes, then authorize one commit | User section 21 says do not commit/push without approval. Nothing staged or committed by this task; push needs separate authorization. |

Recommended order: approve/review SQL migration and runtime access → deploy exact ZIP → verify hosted release/auth → approve bounded provider/storage acceptance → assess final demo readiness. All actions preserve existing policies, audits, failed exports and evidence.

The previously accepted generation-only package is a different artifact; its historical approval is not reused for this larger release. The exact package/deployment/rollback plan is in FINAL_DEPLOYMENT_VERIFICATION.md. No auto-review rejection blocked this work; the remaining boundary comes directly from the user's supplied instructions.
