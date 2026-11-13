# Master repair result — PARTIAL; local preparation complete

7 November 2026, Asia/Kolkata. No Azure or real-provider calls, Azure resources, deployment or production changes occurred during this repair; database tests used disposable local fixtures. Frozen migrations 001–008, local SQLite and prior evidence/artifacts are preserved. **Stop at fresh Approval A retry-9.**

## Cleanup root cause and evidence

The confirmed application defect is **starvation before the first DELETE**. Frozen retry-8 `cleanup_once` starts a two-second monotonic budget before connection/schema verification, database clock and eligibility SQL. Inside the first eligible-row loop it immediately exits when that budget has elapsed. It then commits no deletion, sees the expired backlog and returns exactly `removed: 0, healthy: false`. Retry-8's empty startup pass already took **7.695 seconds**; its per-statement target guards add SQL round trips. Raising a timeout would conceal this progress defect.

[The regression](../backend/tests/test_cleanup_sql_semantics.py) extracts the actual function from the immutable retry-8 ZIP and runs it against real disposable revision-008 data with deterministic 0.8-second SQL-round-trip accounting. The original returns **0/false without issuing a DELETE**. The corrected worker commits one expired row/audit, reports **1/false while backlog remains**, then **1/true when cleared**; the unexpired row survives. [Reproduction output](evidence/master-repair-2026-11-07/cleanup-reproduction.log).

Historical-evidence limit: retry-8 suppressed exception details and did not record cleanup cutoff/selection/delete stages, so its old return alone cannot conclusively exclude an additional SQL exception. The starvation mechanism is proven and reproduces the observed failure; it is not a measured Azure server root-cause claim. New sanitized stage/reason/count telemetry removes that ambiguity at the pending Azure confirmation.

The complete flow was checked:

| Stage | Finding / verification |
| --- | --- |
| Synthetic record | Retry-8 committed a new encrypted expired fixture after a second HUMAN_REVIEW 200. New short probe creates an explicit LEGACY execution/review plus ciphertext and retained audit, without an engine/provider call. |
| Stored expiry | `created_at` / `expires_at` are **BIGINT Unix seconds**, not SQL datetime columns. Encryptor binds expiry to AES-GCM AAD; exactly 604800 seconds retained. Frozen retention CHECK remains. |
| Current UTC | MSSQL `SYSUTCDATETIME()` is assigned UTC and converted to integer epoch seconds. Fractional precision truncation cannot turn a fixture aged RETENTION+1 into unexpired data. Local MSSQL clock-contract and equality-boundary tests pass. Original concrete timestamps were not retained; no invented historical values. |
| Eligibility | Tenant/review keys plus `expires_at <= cutoff`; local tests remove overdue and exact-boundary records and preserve future expiry. New Azure fixture explicitly asserts stored eligibility and logs only timestamps/booleans. |
| Worker/budget | Original stops before first DELETE after slow setup. Correction retains two-second scheduling budget and max 200 deletes, but permits a first conditional deletion so slow guarded SQL cannot permanently starve work. Driver statement timeouts and 90-second inference deadline unchanged. This is a scheduling budget, not a promise of a two-second SQL transaction. |
| Permissions | Existing grant/readiness contracts already require protected-table SELECT/INSERT/DELETE and audit INSERT; no new grants. Permission-denial tests fail closed. Actual runtime permissions under Azure must still be confirmed; no local test proves managed-identity authentication. |
| Transaction | Conditional deletion and matching expiry audit commit together. Injected eligibility/delete/audit/commit failures preserve the row and report failure. Removed count advances only **after** successful commit. |
| Row count | Confirm deletion through returned review identities, not DBAPI `rowcount` (unknown may be -1). MSSQL compiles to `OUTPUT deleted.review_id`; no nonce/ciphertext is returned. The frozen trigger covers UPDATE, not DELETE. Unknown-rowcount and empty-result contracts pass locally. |
| Health | Healthy only after the real pass succeeds and the cutoff backlog query is empty. Backlog, failure, stale heartbeat, foreign engine and stopped worker remain unhealthy. Diagnostic messages expose fixed stage/reason/count fields, never raw exceptions/content/keys. |

SQL semantics references: [SQLAlchemy rowcount limitations](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.CursorResult.rowcount), [Microsoft OUTPUT clause and rollback/trigger restrictions](https://learn.microsoft.com/en-us/sql/t-sql/queries/output-clause-transact-sql?view=sql-server-ver17). Returned rows are not treated as committed success until the enclosing transaction commits.

## Corrections and remaining-assertion audit

[Application](../backend/app/protected_reviews.py): starvation correction; deleted-identity confirmation for expiry cleanup and resolution purge; committed-only counting; sanitized `cleanup.pass` diagnostics. Keyring, AES-GCM/AAD, expiry, readiness, reveal/authorization, session and inference semantics are unchanged. Only this application module differs from retry-8; 63 other packaged modules and all frontend bytes match. Sixteen pre-existing protected-review functions/classes match structurally; only cleanup/purge changed and one deletion helper was added.

[Short remaining probe](../scripts/tests/phase6b_remaining_probe.py) exercises corrected cleanup plus affected purge/security assertions. [Main probe](../scripts/tests/phase6b_sql_package_probe.py) uses it for retry-9 and retains strict assertions. [Orchestrator](../scripts/phase6b_approval_a.py) adds a distinct consumed-once approval window, source/artifact/evidence pins and expanded catalog preservation.

The full audit found and corrected additional preparation defects:

- Preservation previously accepted any truthy plaintext. It now requires the exact synthetic original, and compares both retained rows and expanded catalog hashes.
- The old rollback catalog check used sys.objects names/types, which cannot detect a leaked unique index. New fingerprint includes indexes/memberships, columns, constraints/definitions and triggers; a leaked-index regression proves it detects drift.
- Local backup/restore migrated to head 008 but expected 007. The fixture now expects 008; the actual restore/integrity/immutable-history checks pass.
- Cross-release tests depended on a historical `/tmp` extraction. They now verify immutable ZIP checksums and extract fresh copies before the separate-process check.
- The preserved independent rollback package shares the proven cleanup defect. Its original bytes remain intact; a **distinct repaired rollback** derives from that older release with only this cleanup module correction. It retains the older Settings/frontend/source behavior and is not a candidate copy. Shared cleanup/core defects remain a recovery limitation.
- Local extracted-package verification now binds the package before pytest adds source paths and asserts actual import origins, so source-tree imports cannot silently substitute for the packaged candidate.

## Focused local verification

All completed verification batches run with clean fixture settings, repository dotenv blocked and inherited kernel IPv4/IPv6 socket denial. TestClient thread wakeup hung in the restricted sandbox; the same socket-denied launcher ran outside that sandbox. No real provider call was possible. Batches overlap; counts are not summed as unique tests.

| Batch | Result / evidence |
| --- | --- |
| Frozen failure reproduction / SQL semantics | **8 passed**, 0.88s; [log](evidence/master-repair-2026-11-07/cleanup-reproduction.log). |
| Sanitized failure visibility | **1 passed**; [log](evidence/master-repair-2026-11-07/cleanup-diagnostics.log). |
| Backend cleanup, protected review, startup health, 008, Settings and migration/domain checks | **170 passed**, 26.22s; [log](evidence/master-repair-2026-11-07/backend-focused.log). |
| Remaining workflow, catalog, restore, migration preflight, session and audit checks | **112 passed**, 7.76s; [log](evidence/master-repair-2026-11-07/remaining-assertions.log). |
| Release transitions, local failure cycles, preservation and schema/grant contracts | **50 passed**, 37.47s; [log](evidence/master-repair-2026-11-07/release-transition.log). |
| Exact extracted candidate, including origin assertions | **36 passed**, 8.32s; [log](evidence/master-repair-2026-11-07/extracted-candidate.log). |
| Corrected independent rollback, slow cleanup and review compatibility | **19 passed**, 3.60s; [log](evidence/master-repair-2026-11-07/independent-rollback.log). |
| Candidate ciphertext → original and corrected rollback processes | **2 passed**, 1.93s; exact plaintext, unchanged database hash; [log](evidence/master-repair-2026-11-07/cross-release-ciphertext.log). |
| Lint / offline approval guards | Ruff PASS; seven wrong-target/token guard denials PASS, 82 dependency hashes; [lint](evidence/master-repair-2026-11-07/ruff.log), [dry run](evidence/phase6b-approval-a-retry9-2026-11-07/harness-dry-run.json). |
| Frontend | Unaffected; packaged frontend bytes match retry-8 exactly. Prior qualified frontend results reused; no unrelated rerun. |

These cover locally executable expiry eligibility, actual deletion/audit transactions, unexpired preservation, concurrent cleanup, role/tenant/session/CSRF/version denial, assignment/resolution/resubmission, failure health, stable-key decryptability, audit rollback, migration denials, Settings unverified/VERIFIED-with-mocks/FAILED/STALE and disabled real verification. SQL Server compilation/clock/rowcount contracts and deterministic latency are local simulations, not Azure SQL execution evidence. Local SQLite DDL failure behavior does not prove transactional SQL Server THROW rollback.

## Packaged artifacts

[Candidate](../artifacts/master-repair-2026-11-07/candidate.zip): **1.2-240cc70e239a595f**, SHA-256 **274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22**.

[Independent repaired rollback](../artifacts/master-repair-2026-11-07/rollback-cleanup-fixed.zip): **1.2-230d63e0c546e0ba**, SHA-256 **b52287bbf048a66a9f7233753a3fb95730397016f03074d4deb399c1e74c0d29**. Derived from preserved `1.2-677a11e4b649fa7d`; only cleanup module corrected. Original rollback checksum remains `be1ab97768954fecb5cf26b255bfcecf2a22811848ca910536846b3784174ee9`.

[Package manifest](evidence/master-repair-2026-11-07/package-manifest.json), [artifact/provenance record](evidence/master-repair-2026-11-07/candidate.json), [frozen comparisons and reuse pins](evidence/master-repair-2026-11-07/qualification-pins.json). Deployment is false. Local SQLite remains SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`; all frozen migration hashes match before repair.

## Azure-only checks, recovery and next approval

The shortest prepared confirmation is [Approval A retry-9](FINAL_DEMO_SQL_QUALIFICATION_PLAN.md): fresh exact-target/preflight, minimal migrations/grants through008, corrected SQL cleanup and affected review regression using direct synthetic setup, byte-identical compatible-copy exact decryption plus row/catalog preservation, then the two planned 006 preflight denials and transactional007 THROW on incarnation two. Keep S0/10 DTUs, four hours, USD1 estimate, two sequential incarnations, synthetic data/mocked providers and independent ARM404/inventory cleanup. Prior passed governed engine/session/MULTI/tenant/immutability checks are reused only under pins. No new Azure resource exists from this preparation; actual target absence and price must be freshly rechecked after approval.

[Deployment readiness](MASTER_REPAIR_DEPLOYMENT_READINESS.md) prepares recovery/rollback, frozen006–008/runtime grants, Entra SSO, Admin/User portals, providers/ADLS, truthful Settings and hosted acceptance. Recovery B still needs an approved actual Azure restore/PITR/access/data-preservation drill and refreshed exact timestamp/destination/budget. Production C–F, stable production key provisioning, actual managed-identity authentication, fresh hosted Admin/User SSO/portal acceptance and bounded real-provider/ADLS checksum/read-back/cleanup remain unapproved and unexecuted.

**Verdict: PARTIAL.** Safe local repairs, remaining-assertion audit, packaging and deployment preparation are complete. Azure SQL confirmation and later recovery/production/hosted acceptance remain mandatory. Approve only the exact new retry-9 scope in the linked plan to continue. No later approval is inferred; stop here.
