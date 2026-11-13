# Approval A retry-2 result — 6 November 2026

**PARTIAL — corrected 006 schema verification passed; stopped on a distinct MULTI-mode workflow failure. Cleanup independently confirmed.**

| Check | Result |
|---|---|
| Preflight | PASS: approved subscription/server/name absence, S0 capability, restrictions and cost; candidate **1.2-29ce93fc10de32b3**, package CRC/verifier/source/migration pins |
| Temporary resource | One incarnation, exact approved name, westus2 Standard S0 / 10 DTUs, 250 GiB, matching collation, Local redundancy and ownership/expiry tags |
| Essential 005 prerequisites | Actual frozen chain through 005 and synthetic seeding passed. Prior successful Azure 005 application/session evidence explicitly reused; its full probe was not repeated |
| 005 → 006 | PASS: real migration completed; prior selected row/column hashes retained |
| Corrected 006 schema contract | **PASS on Azure SQL**, operator context; complete catalog saved. DATETIME2 precision and CHECK catalog correction are now Azure-tested |
| 006 runtime readiness | **PASS**: extracted candidate `/ready` HTTP 200 under SQL EXECUTE AS temporary runtime identity; required effective permissions/objects verified |
| 006 session security | PASS: mocked SSO login/callback/me; issued duration/database/API/cookie alignment; validity one microsecond before expiry, rejection at expiry and after revocation; no activity renewal |
| 006 tenant isolation | PASS in an isolated supplemental gate before any 007 attempt: authenticated same-tenant read 200, foreign-tenant read 404, cross-tenant assignment FK rejected with native code 547, zero failed-insert rows retained |
| Legacy application behavior | PASS before failure: demo-session exchange, policy create/submit/approve/publish/activate and LEGACY ALLOW/HUMAN_REVIEW assertions |
| MULTI transition | **FAILED**: `PUT /api/v2/workspace/policy-mode` returned HTTP 503, `Database operation unavailable; nothing released`; expected 200 |
| MULTI execution / 006 final package result | NOT QUALIFIED: main probe stopped at the transition assertion |
| 006 → 007; 007 readiness/encryption/security | NOT RUN, as required by the 006 gate |
| Same-code fallback and planned second-incarnation failures | NOT RUN; no second incarnation or unexplained-failure retry |
| Cleanup | PASS: exact-target delete, independent ARM GET 404/ResourceNotFound, inventory absence and terminated watchdog |

## Failure boundary

This is **not a recurrence of the corrected schema-verifier failure**. The operator schema scan and runtime `/ready` passed. The package later failed at its MULTI-mode transition assertion (`scripts/tests/phase6b_sql_package_probe.py`, `assert switched.status_code == 200`). The application database-error handler exposed only its fail-closed public message; no underlying SQLSTATE/native error was captured for this workflow failure. The saved schema diagnostic on the parent wrapper is generic and does not establish a more specific SQL cause. Do not infer a missing grant, migration defect or safe workaround from HTTP 503 alone.

The main package was bounded at 1800 seconds and stopped on an assertion, not that timeout. Its readiness request took 147.77 seconds; SSO requests took approximately 142–144 seconds. The passing session observation had 120 configured minutes, cookie Max-Age 7200, issuance bounds 7199.999962–7200.000077 seconds, persisted/API expiry `2026-11-06T16:22:43.994036+00:00`, and 7054.206917 seconds remaining after latency. No provider latency or production performance claim is made.

The supplemental 006 gate used the unchanged approved bootstrap/pinned candidate and temporary runtime identity, separate synthetic tenant accounts/data, no new resource or production access, and an eight-minute bound. It completed successfully before the main failure. Its cross-tenant failed transaction was rolled back. It was configured to signal the main harness to stop/cleanup on any failed assertion. It did not alter any execution-pinned source file.

## Resources, cleanup, cost and preservation

Only this resource was created, seeded, granted/mapped and migrated through 006, then deleted:

`/subscriptions/25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6/resourceGroups/rg_techdemo_Atiya_Tabsum_Shaik/providers/Microsoft.Sql/servers/sql-governance-validator-dev-atiya/databases/sqldb-gpv-mig-20261106-a1`

Total harness duration: **1592.56 seconds (26 minutes 32.56 seconds)**. Service creation timestamp: **19:40:00.220 IST**. Harness deletion confirmed **20:05:32.142 IST**; independent ARM verification **20:05:47.114 IST**, HTTP **404 / ResourceNotFound**. Independent server inventory: only `sqldb-governance-validator-dev` and `master`; no unexpected test names. Watchdog confirmed gone. No cleanup failure or residual active test resource was identified. No service-managed backup purge was attempted or immediate backup erasure claimed.

Refreshed retail meter: USD 0.4839/day (USD 0.0201625/hour). A conservative **two billed compute hours** gives **USD 0.040325**, below the approved USD 1 estimate. This is not a final invoice or enforceable billing cap. Both duration and incarnation limits were respected.

Independent final SELECT-only production metadata exactly matched the initial baseline: revision **005**, all five new 006/007 tables absent, same runtime SID/role membership and 51 selected direct permission rows. Local SQLite remains byte-identical at revision 003, SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. All 71 execution-pinned source hashes match. No application, migration, production SQL, production settings/grants/secrets, hosting/deployment, real SSO, generation/moderation/ADLS, production keys, customer data, restore or B–F operation occurred. Existing working-tree changes and older evidence were preserved; no Git commit/reset/clean/stash/discard.

Only retry-2 approval/evidence, frozen source snapshots, supplemental synthetic tenant gate and this result report were added/refreshed during this execution. Existing corrected application/harness sources were not edited.

Evidence: [retry-2 directory](evidence/phase6b-approval-a-retry2-2026-11-06/): `execution.json`, `catalog-1-006.json`, `package-candidate-006-failure.txt`, `tenant-006-result.json`/`tenant-006.log`, `temporary-resource-snapshot.json`, `independent-deletion.json`, `production-final-readonly.json`, `watchdog-final.json`, pins and frozen executed sources.

## Remaining blockers / next boundary

006 MULTI-mode SQL workflow remains unqualified and requires local diagnosis with sanitized database error evidence. 007 migration, Azure encryption/security, retained-ciphertext fallback and failure/rollback cycles remain untested. Recovery/PITR, independent fallback or approved forward-fix strategy, and all production approvals remain outstanding. **NO-GO for production deployment or migration.**

No further Azure work is authorized by this consumed window. Next step is local-only diagnosis/review of the MULTI-mode failure. Any subsequent rehearsal requires a **new explicit Approval A window** after that review. No Approval B–F was exercised. **STOP after Approval A retry-2.**
