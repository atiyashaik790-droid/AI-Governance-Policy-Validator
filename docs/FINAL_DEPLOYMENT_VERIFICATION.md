> Historical release report. For the current implementation and deployment boundary, see [CURRENT_STATUS.md](CURRENT_STATUS.md).

# Final deployment preparation and verification

Updated 31 October 2026, Asia/Kolkata. **CONDITIONAL DEMO READINESS; NOT PRODUCTION READY.**

## Exact candidate — NOT DEPLOYED
- Target: existing `app-governance-validator-atiya-1026`, resource group `REPLACE_WITH_AZURE_RESOURCE_GROUP`, subscription `REPLACE_WITH_AZURE_SUBSCRIPTION_ID`.
- Artifact: `artifacts/final-implementation-20261031/governance-reliability-final.zip`.
- ZIP SHA-256: `3d81bdfca85f4df3b4786562283bce4d599d34662993f2c21623eeb6d3286992`; 240,732 bytes.
- Release: `1.1-544cbf32d11a251a`; API contract 1.1; backend API version 1.1.0.
- Commit baseline: `8d12cc4caf78ad2b38c0d81fa297d27ace7aca9a` plus preserved uncommitted changes. Member hashes and frontend/backend fingerprints are in [package manifest](evidence/final-implementation-2026-10-31/package-manifest.json).
- Build time: 2026-10-31T14:14:32.149755+00:00 (UTC). This is package build time, not a deployment timestamp.
- Required migration: **004**; fresh Azure actual migration: **003**. Do not deploy this ZIP first.
- Current hosted deployment: `8c2639f4-41d7-4787-bce4-e7253ecbb4b2`, active/complete/status 4, completed 31 October 2026 at 19:18:36 IST. New session endpoint absent. This task deployed nothing.

## Approval-required order
1. Review [004 SQL](evidence/final-implementation-2026-10-31/migration-004.REVIEW_ONLY.sql), source migration, permissions and downtime. Confirm a recoverable Azure SQL backup/PITR window and responsible operator. Do not claim the local SQLite restore drill proves Azure restore.
2. With explicit approval, apply only 003→004 to the existing database, using the approved migration identity; preserve all rows. It creates six tables, a tenant/date index and three history triggers. No existing table is dropped or recreated. Verify revision, tables, indexes, triggers, counts and least privilege before proceeding.
3. Review `deployment/runtime_004_permissions.REVIEW_ONLY.sql`. It grants only required operations on new tables and SELECT on alembic_version to the existing approved runtime role. The exact actual role and inherited privileges must be inspected before execution. No new principal or database-wide grant is proposed. This script is not executed.
4. Reconfirm artifact checksum, then use the existing ZIP deployment method once. The single worker can be interrupted for several minutes; no zero-downtime claim. Startup never applies migrations.
5. Verify actual server-side deployment completion, release metadata, exact HTML/asset bytes, API schema, health/readiness (which checks SQL head 004), protected routes, expiring demo session, RBAC, SPA deep links and security headers.
6. Stop before any inference/moderation/export or other hosted data mutation not explicitly approved. A session/login itself now persists SQL session/audit rows and must be included in the approved acceptance scope.

Reviewed command, **NOT EXECUTED**:
```bash
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az webapp deploy \
  --subscription REPLACE_WITH_AZURE_SUBSCRIPTION_ID \
  --resource-group REPLACE_WITH_AZURE_RESOURCE_GROUP \
  --name app-governance-validator-atiya-1026 \
  --type zip --src-path artifacts/final-implementation-20261031/governance-reliability-final.zip \
  --async true --track-status false
```

## Rollback limitations
Preserve the currently serving 31 October package `artifacts/live-stabilization-20261031/governance-live-stabilized.zip` (historical recorded SHA-256 `5f22b7d829e79251f58f4b216bcc18d92f500220e28381eee18ad6f251e1d697`) and verify it against the actual serving assets before rollout approval. Restoring an older ZIP does not undo SQL 004 or remove durable export/session evidence. Migration downgrade deliberately refuses destructive rollback. Old browser sessions using new session tokens are not understood by old code; require sign-in using the restricted legacy demo flow after rollback. Existing core schema is unchanged, but validate old runtime compatibility in a safe rehearsal. A restored old application does not retain the new quota/recovery controls. Never roll back or retry while inference/export is in flight without first inspecting its durable state.

No local package approval from the earlier 31 October generation-only task is treated as authorization for this larger schema-dependent release.

Final rollback review: the preserved 5f22b7d8 package checksum matches its historical fingerprint, and its static HTML SHA-256 matches the freshly observed hosted shell. Backend worker archive bytes were not freshly downloaded here. Existing serving evidence must be checked before an actual rollback. See rollback-review.json.
