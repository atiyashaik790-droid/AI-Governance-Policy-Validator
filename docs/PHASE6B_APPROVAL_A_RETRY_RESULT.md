# Phase 6B Approval A retry result — 6 November 2026

**PARTIAL — stopped on unexpected revision-006 schema-contract failure. Cleanup independently confirmed. No retry or second incarnation was used. Approval A only.**

## Results

| Gate | Result |
|---|---|
| Target, budget, pins, exclusions | PASS: exact approved subscription/server/database; absent before creation; seven wrong-target dry cases; original approval token rejected for retry window; package/migration pins verified |
| Resource shape | PASS: westus2, Standard S0 / 10 DTUs, 250 GiB ceiling, source collation, Local backup redundancy; owner/purpose/expiry tags |
| Actual frozen migrations 001–005 | PASS: initialized empty temporary database to 005; synthetic fixtures and temporary runtime mapping/role/grants only |
| Revision-005 physical schema | PASS under operator context |
| Extracted candidate revision 005 | PASS: readiness, release contract, SPA/auth boundary, mocked SSO, policy lifecycle and LEGACY ALLOW/HUMAN_REVIEW |
| Corrected 120-minute session assertion | PASS on actual Azure SQL transport under SQL EXECUTE AS runtime context; exact issuance/DB/API/cookie alignment, absolute expiry boundary and revoked-session rejection |
| 005 → 006 migration | PASS: actual upgrade completed; marker advanced to 006; all frozen pre-migration row/column hashes retained |
| Temporary 006 grants | Applied only inside approved temporary database; application/schema qualification did not complete |
| Revision-006 schema-contract gate | **FAILED**: HTTP 503, `Reviewed schema objects and runtime permissions are required`, during `catalog(e, "006")` → `inspect_schema(db, require_sso=True)` under operator context |
| Revision-006 application/readiness, tenant/RBAC/SQL negatives | NOT RUN after failed gate |
| 006 → 007 and encrypted Human Review | NOT RUN |
| Same-code fallback ciphertext test | NOT RUN; not independent fallback qualification |
| Planned second-incarnation 006 rejection / 007 THROW rollback | NOT RUN |
| Cleanup | PASS: exact-target deletion; independent ARM GET 404 / ResourceNotFound and inventory absence; no unexpected test database names |

## Session evidence

The session issued at approximately `2026-11-06T13:32:30.1297Z`, with persisted expiry `2026-11-06T15:32:30.129742Z`. Cookie Max-Age was 7200; second-precision Expires was `15:32:30Z`. Observed issuance-duration bounds were 7199.999970–7200.000056 seconds. `/me` reported 7090.036060 seconds remaining after request latency. This would fail the original age-sensitive 7100-second lower bound, while the corrected duration/consistency contract passed. A virtual UTC clock tested validity one microsecond before expiry and rejection exactly at expiry, against the real SQL session row. The unchanged expiry and explicit SQL-backed revocation rejection also passed. This qualifies the 005 session gate, not session compatibility at 006/007.

## Stop and diagnostic limit

The harness stopped immediately after the unexpected 006 contract exception, attempted cleanup in `finally`, and did not proceed to 007, a deliberate failure cycle, another incarnation, or Approvals B–F. The schema verifier catches the underlying exception and replaces it with this generic HTTP 503 (`raise ... from None`). The underlying constraint/type/permission/driver mismatch was **not captured**, so no more specific root cause is established. The failed scan did not save a completed 006 catalog. Do not interpret successful DDL/retained-row checks as complete SQL Server compatibility or weaken the verifier to pass it.

A future local diagnostic task should preserve a sanitized underlying diagnostic and review the operator/runtime contract before requesting another separately authorized Azure window. This consumed retry is not reusable authorization.

## Resources, cleanup and cost

Only one incarnation of:

`/subscriptions/25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6/resourceGroups/rg_techdemo_Atiya_Tabsum_Shaik/providers/Microsoft.Sql/servers/sql-governance-validator-dev-atiya/databases/sqldb-gpv-mig-20261106-a1`

was created, seeded, mapped/granted and migrated through 006, then deleted. Those temporary objects/grants/fixtures disappeared with deletion. The total harness execution was **1403.25 seconds (23 minutes 23.25 seconds)**. Deletion was confirmed by the harness at **19:15:33.812 IST** and independently by ARM GET **404 / ResourceNotFound** at **19:15:50.442 IST**. Inventory contained only `sqldb-governance-validator-dev` and `master`; cleanup watchdog process was confirmed gone. No cleanup failure or residual active temporary resource was identified. Resource deletion does not promise immediate service-managed backup erasure; no backup purge was attempted.

Refreshed retail meter: USD 0.4839/day (USD 0.0201625/hour). Allowing two billed compute hours conservatively for this single under-24-minute execution gives **USD 0.040325**, below USD 1. This is an estimate, not an invoice or hard billing cap.

## Preservation and files

Independent final SELECT-only production metadata matched the pre-run baseline: revision **005**, all five new 006/007 tables absent, same runtime mapping/membership and 51 recorded direct permission rows across the selected user/role. No production SQL writes, production grants/settings/secrets changes, application deployment, restore, actual managed identity authentication, real SSO login, real generation/moderation/ADLS calls, customer data or production encryption keys were used.

Local SQLite remains byte-identical at revision 003: SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. All 71 execution-pinned source hashes match. No migration/application sources were edited. Existing working-tree changes and original Approval A evidence were preserved; no Git commit/reset/clean/stash/discard occurred.

Harness-only changes for this approved run: `scripts/phase6b_approval_a.py` selects the separate retry window/token and uses bounded 1800-second package probes; `scripts/tests/phase6b_sql_package_probe.py` adds actual SQL-backed expiry/revocation checks, fail-closed provider/storage guards and suppression of dotenv secrets (only public operator identifiers read). Reviewed exact copies were frozen before execution. Added report and evidence/scripts under the retry evidence directory. No completed local suites were repeated.

Evidence: [retry directory](evidence/phase6b-approval-a-retry1-2026-11-06/), especially `execution.json`, `run.log`, `independent-deletion.json`, `production-final-readonly.json`, `temporary-resource-snapshot.json`, `catalog-1-005.json`, approval/dry-run/pins and frozen approved source files.

## Remaining blockers and next approval

Azure SQL 006 contract qualification remains blocked by the unexplained 503; 006 application/security/tenant negatives, all 007 encryption/schema/security checks, fallback retained-ciphertext behavior and deliberate failure/rollback cycles remain unqualified. Recovery/PITR, synthetic-007 recovery, independent fallback or explicitly accepted forward-fix strategy, and separately scoped production approvals remain outstanding. **NO-GO for production migration/deployment.**

Next: local-only diagnosis and review of the 006 failure. Any further Azure create/rehearsal requires a **new explicit Approval A window** after that review. Approval B–F is not granted or exercised. STOP after Approval A.
