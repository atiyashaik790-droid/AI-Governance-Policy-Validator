# Phase 6B — Approval A result (6 November 2026)

**STOPPED / NOT QUALIFIED. Cleanup confirmed. Approval A only was exercised.** The candidate's revision-005 application probe failed a session-lifetime assertion. The rehearsal stopped immediately, deleted its single temporary database, and did not attempt 006, 007, a retry, incarnation 2, or Approvals B–F.

## Authorized target and actual resource changes

Subscription: `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`  
Resource group: `rg_techdemo_Atiya_Tabsum_Shaik`  
Existing server: `sql-governance-validator-dev-atiya`  
Temporary database: `sqldb-gpv-mig-20261106-a1`

Exact resource ID:

```text
/subscriptions/25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6/resourceGroups/rg_techdemo_Atiya_Tabsum_Shaik/providers/Microsoft.Sql/servers/sql-governance-validator-dev-atiya/databases/sqldb-gpv-mig-20261106-a1
```

One incarnation was created and deleted. Confirmed shape: westus2, Standard S0, 10 DTUs, 268,435,456,000-byte maximum, `SQL_Latin1_General_CP1_CI_AS`, Local backup redundancy. Owner, purpose and expiry tags were applied. The resource's creation timestamp was **16:23:37.897 IST**; deletion was confirmed by **16:35:05.376 IST**. The entire execution, including prerequisite guards and cleanup, lasted **740.09 seconds (12 minutes 20 seconds)**.

Inside that database only:

- Frozen migrations 001–005 were applied using Alembic MigrationContext/Operations and their actual upgrade functions. The marker reached 005; no startup migration or stamping command ran.
- Synthetic policy, published version, legacy assignment, execution, review, feedback, audit and persisted demo-session fixtures were seeded. Their canonical row hashes and column selections were recorded.
- The existing runtime identity's reconfirmed SID was mapped as contained external user `app-governance-validator-atiya-1026`, default schema dbo. A temporary `governance_validator_web_runtime` role and one membership were created. The actual snapshot records **64 object grants**, including required object metadata visibility. No broad runtime database/DDL role was assigned.
- The extracted candidate used real Azure SQL transport under **SQL EXECUTE AS runtime permission context**. Its synthetic mocked-SSO flow wrote membership, transaction, session and audit fixtures. This was not actual managed identity authentication or a real Entra login.
- Deleting the database removed its tables, fixtures, user, role, membership and grants together.

There was no production database mutation, production-data copy, server/network/firewall/Entra/Azure-role change, application deployment, hosted settings change, production-key operation, real generation/moderation/SSO, ADLS acceptance, restore, or backup-policy change. No second database incarnation was created.

## Checks and outcomes

| Gate | Actual result |
|---|---|
| Exact subscription/server and name collision | PASS: live approved IDs/FQDN; temporary name absent before creation |
| Restrictions | No locks/deny assignments returned at subscription, group or server scope; creation/deletion succeeded under existing authority |
| Harness wrong-target guards | PASS: seven negative dry cases; production, master, another name, subscription, server, resource ID and approval token rejected |
| Source/package integrity | PASS: candidate/fallback ZIP hashes and 005/006/007 migration hashes matched preflight; dependency manifest captured |
| SQL target/default schema | PASS: DB_NAME(), logical SERVERPROPERTY ServerName and dbo checked on new connections; DB_NAME()/server checked before each SQL statement through the locked endpoint |
| Empty database through 005 | PASS: actual SQL Server execution of frozen 001–005 upgrades; synthetic seed committed |
| Physical 005 schema | PASS: application's SQL Server schema/permission contract under operator; catalog columns/defaults/indexes/checks/FKs/triggers saved |
| Retained-row baseline | CAPTURED: canonical hashes for every 005 table; no subsequent preservation-across-006/007 claim |
| Candidate under runtime context: `/ready` | HTTP 200, revision 005; release contract assertion passed |
| Candidate SPA/auth boundary | `/chat` 200; unauthenticated `/api/policies` 401 |
| Mocked SSO | Login 302, callback 303, `/api/sso/me` 200; authenticated session returned |
| 120-minute session assertion | **FAILED**: `7100 < lifetime <= 7200`, where lifetime is returned expires_at minus returned server_now |
| 006 and 007 migrations/catalog/preservation | NOT RUN |
| Explicit SQL denial probes / 006–007 temporary grant proposals | NOT RUN |
| Lifecycle, LEGACY/MULTI decisions, portal/RBAC/tenant negatives | NOT RUN beyond the boundaries listed above |
| Encrypted capture/reveal/audit/disposition/expiry/cleanup | NOT RUN |
| Fallback retained-ciphertext behavior | NOT RUN |
| Deliberate 006 rejection / 007 transactional THROW rollback cycle | NOT RUN; incarnation 2 was not used |
| Cleanup | PASS: independent final ARM GET HTTP 404 and inventory absence |

The probe failed an assertion, **not** its ten-minute timeout. Its HTTP log records `/ready` at 109,026.9 ms, mocked login at 106,738.21 ms, callback at 107,369.4 ms and `/me` at 107,207.94 ms. The copied local probe allows less than 100 seconds of elapsed session age. The approximately 107-second `/me` request therefore makes that assertion latency-sensitive. This is a plausible explanation, not an independently established TTL defect: the exact returned expiry/server-now values were not captured before deletion. Neither a full 120-minute qualification nor a production performance diagnosis is claimed. The target guard adds a SQL round trip to every statement; the logs cannot isolate its contribution from remote latency, schema reflection or S0 performance. A sampled metadata check observed no blocked request.

The operator schema result does not replace runtime evidence. The successful runtime-context readiness check is useful, but explicit least-privilege denial tests and actual managed identity authentication remain unverified.

## Cost and cleanup evidence

The live retail query returned the exact **S0 / S0 DTUs** USD meter at **0.4839/day**, approximately **0.0201625/hour**. The meter's `isPrimaryMeterRegion=false` field is retained in the response; it is not a secondary SKU. The earlier broad filter requiring that field to be true returned no rows, so it was replaced with the exact SKU/meter query before creation.

The pre-create envelope conservatively allowed ten billed compute hours across the two planned incarnations: USD 0.201625, below the USD 1 limit with headroom for the small synthetic workload. Actual usage was one incarnation for under 13 minutes including the create/delete window. Even allowing **two full compute hours**, estimated compute is **USD 0.040325 (under USD 0.05)**. This is a retail estimate, not an actual invoice or a hard Azure billing cap; finalized billed spend was not available. No evidence supports continued active database compute charges after deletion.

A separate cleanup watchdog was started before creation with a three-hour deletion deadline, reserving an hour within the approved window for cleanup. It was verified alive, then terminated after confirmed early cleanup; final process inspection found it gone.

Final verification recorded:

- Exact target ARM GET: **HTTP 404 / ResourceNotFound**.
- Server inventory: only `sqldb-governance-validator-dev` and `master`; neither A nor B present.
- No matching temporary deleted-database backup record returned by the service's deleted-database listing. This is the observed metadata result, not proof of immediate erasure from all service-managed backup media.
- **No residual active temporary database or cleanup failure identified.** No backup purging was attempted.
- Production revision remains **005**; all five new 006/007 tables absent; existing runtime object grants equal the preflight snapshot.
- Public production `/ready` remains HTTP 200 at **1.2-ca5df7c1dc19e525**, revision 005.
- Existing application/migration source hashes unchanged. Local SQLite remains byte-identical: `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`.

## Evidence and source provenance

Evidence directory: [phase6b-approval-a-2026-11-06](evidence/phase6b-approval-a-2026-11-06/).

- [execution.json](evidence/phase6b-approval-a-2026-11-06/execution.json): ordered mutation/test/stop/cleanup events, hashes, elapsed time and incarnation count.
- [live-preflight.json](evidence/phase6b-approval-a-2026-11-06/live-preflight.json), [retail-live.json](evidence/phase6b-approval-a-2026-11-06/retail-live.json): live scope, restrictions, original SQL revision/mapping and exact pricing response.
- [harness-dry-run.json](evidence/phase6b-approval-a-2026-11-06/harness-dry-run.json): original guard/dependency/SQLite baselines.
- [temporary-resource-snapshot.json](evidence/phase6b-approval-a-2026-11-06/temporary-resource-snapshot.json), [catalog-1-005.json](evidence/phase6b-approval-a-2026-11-06/catalog-1-005.json): actual resource, tags, user/role membership, grants and physical catalog.
- [package-candidate-005-failure.txt](evidence/phase6b-approval-a-2026-11-06/package-candidate-005-failure.txt): HTTP results/timings and failed assertion. No SQL credential, token, cookie or production key is included.
- [final-verification.json](evidence/phase6b-approval-a-2026-11-06/final-verification.json): independent actual 404, inventory, backup listing result, production grants/revision/readiness and preservation checks.
- [harness.executed.py](evidence/phase6b-approval-a-2026-11-06/harness.executed.py), [package-probe-005.executed.py](evidence/phase6b-approval-a-2026-11-06/package-probe-005.executed.py): exact executed sources. The package transport/configuration adaptation was reviewed before that probe. Additional 007 checks were prepared while 005 was in flight; they were not executed and are not pass evidence. The executing child's traceback displayed a stale source line after that edit; the preserved executed file resolves the discrepancy and matches its recorded SHA-256.
- [package-probe-pretest-review.json](evidence/phase6b-approval-a-2026-11-06/package-probe-pretest-review.json): those source versions and their distinction.

Only new Approval A harness/evidence/report files were added. Existing repository changes were preserved; no Git reset/clean/stash/commit occurred. The prepared harness was formatted after saving executed sources, and now refuses to reuse an execution evidence directory. Its final lint, compilation, seven dry guard cases and zero-network repeat-execution rejection passed. These local checks are separate from the stopped SQL rehearsal. The original execution evidence was preserved.

## Remaining blockers and stop boundary

Approval A is incomplete. A future separately approved window needs a reviewed session-lifetime measurement based on session issuance/expiry (with sanitized timestamps and elapsed latency recorded), investigation of the slow guarded SQL probe, and completion of every NOT RUN gate above. The current assertion alone does not justify changing application session settings or security checks. No retry or second incarnation was used after the unexpected failure.

Recovery/PITR, synthetic 007 ciphertext recovery, an independent qualified 007 fallback or explicit strategy decision, and all production migrations/grants/deployment/settings/live acceptance remain outside this execution and unqualified. The same-code fallback limitation from preflight remains. **Approval B and Approvals C–F were not exercised. STOP after Approval A.**
