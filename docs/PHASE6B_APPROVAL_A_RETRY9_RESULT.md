# Approval A retry-9 result — PARTIAL / STOPPED

7 November 2026, Asia/Kolkata. Candidate **1.2-240cc70e239a595f**, SHA-256 **274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22**. Explicit user approval was limited to retry-9. The window is consumed; no automatic retry, second incarnation, Recovery B or production C–F was performed.

**The corrected expiry cleanup passed on real Azure SQL. Overall qualification is incomplete, and the approved four-hour lifetime limit was exceeded.**

## Target and gates

Subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`; resource group `rg_techdemo_Atiya_Tabsum_Shaik`; server `sql-governance-validator-dev-atiya`; temporary database only `sqldb-gpv-mig-20261106-a1`. Candidate SHA-256, all source/artifact/migration/reused-evidence pins and SQLite matched. Fresh account/server/absence/firewall-IP/SQL-connectivity/S0-capability/restriction gates passed. Live price remained USD 0.4839/day, with preflight conservative ten-billed-hour estimate USD 0.201625.

One tagged Standard S0  / 10-DTU database was created with Local backup and 250 GiB maximum size. Independent exact-target watchdog was started before creation. Migrations 005→006→007→008, minimum grants, migration-boundary retained hashes and final 008 schema/runtime readiness passed. Prior qualified MULTI/tenant/session/immutability/governed-execution evidence was reused under pins.

## Exact reached results

The extracted candidate probe **passed** at 10:21:14 UTC (15:51:14 IST):

- Startup cleanup completed healthy in 8.070 seconds; normal readiness and release/SPA/auth boundaries passed.
- Settings reported configured-but-unverified evidence, null verification timestamps and disabled real verification; the verification request was rejected. Real providers remained blocked.
- Synthetic encrypted content had exactly 604800-second retention, no original plaintext bytes in ciphertext and exact successful decryption.
- Unassigned reveal 403, valid `Assigned for review` assignment 200, stale-version 412, authorized exact reveal 200/no-store and committed access audit passed.
- Disposition 200, physical ciphertext purge and committed purge audit passed.
- SQL-clock fixture explicitly confirmed expired-row eligibility: created 1793442059, expires 1794046859, cutoff 1794046864; retained expiry 1794651660 was in the future.
- Actual expiry cleanup returned **removed 1 / healthy true** in 4.925286 seconds; the expired row was absent and its expiry audit committed. The unexpired retained row remained exactly decryptable. This is fresh Azure SQL evidence of the correction, not a SQLite claim.

## Stop and unreached checks

The byte-identical compatible-copy process completed healthy startup but its `/ready` returned **503**, category `DATABASE_OPERATION_FAILED`, SQLSTATE **08S01**. It stopped before its preservation/decryptability assertions. A watchdog deadline/deletion was also recorded during the multi-hour log gap. The evidence does not establish whether connection loss preceded deletion or resulted from it; no separate application-schema root cause is claimed.

The parent stopped on this readiness failure and confirmed cleanup. Compatible-copy exact decryption and the final retained-row/catalog comparisons were **not completed**. Incarnation two was **not started**, so synthetic 006 RESERVED/invalid-LEGACY preflight denials and controlled transactional 007 THROW rollback remain unexecuted in Azure.

## Timing limit breach and corrected cost

Azure activity, independently read for the exact resource, records creation started **2026-11-07T10:11:24.610911+00:00** and deletion succeeded **2026-11-07T16:24:14.639641+00:00**: **22370.029 seconds, approximately 6h13m**. This exceeds the approved four-hour maximum. The database was already Online by 10:12:31 UTC and still required deletion at 16:23:58 UTC. Resource deletion is confirmed, but the watchdog did not enforce the authorized wall-clock deadline.

The local harness reports only **674.44 seconds** monotonic elapsed, despite the UTC gap. That value cannot establish lifetime compliance. Suspension/clock behavior is a possible explanation, not a demonstrated root cause. No elapsed-time or deadline assertion was changed. The control must be reviewed before another Azure execution; this report does not implement or authorize another rehearsal.

The existing pinned independent-deletion helper calculated USD 0.040325 from the undercounted monotonic duration. **That estimate is superseded** by [independent lifetime/cost reconciliation](evidence/phase6b-approval-a-retry9-2026-11-07/lifetime-and-cost.json): ceil(control-plane lifetime hours)+one incarnation = **8 conservative billed hours**, at USD 0.4839/day, estimated compute **USD 0.161300**. This remains below USD 1; it is not an invoice or billing cap. No claim is made that all approval limits were met.

## Independent cleanup and preservation

Independent exact-target ARM GET at 16:26:16 UTC returned **404 / ResourceNotFound**. Independent inventory contains only production `sqldb-governance-validator-dev` and `master`, with no unexpected test names. Azure activity also records successful deletion. One incarnation used; no temporary resource remains in that inventory.

Production SELECT-only metadata/grants match the preflight baseline at revision 005, with 51 grant records. All 82 dry-run source/operator dependency hashes, qualification artifact/source/migration/reused-evidence pins and local SQLite are unchanged. SQLite SHA-256 remains `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`.

The first independent-deletion tool request encountered an automatic permission-review timeout; its single permitted retry succeeded. Production comparison also succeeded. No cleanup action remains blocked by approval review.

No production SQL/permission/configuration changes, deployment, real OpenAI/Moderation/ADLS calls, additional Azure services or prohibited Git operations were performed.

## Evidence and verdict

[Approval](evidence/phase6b-approval-a-retry9-2026-11-07/approval-record.json), [live preflight](evidence/phase6b-approval-a-retry9-2026-11-07/live-preflight.json), [execution](evidence/phase6b-approval-a-retry9-2026-11-07/execution.json), [candidate cleanup evidence](evidence/phase6b-approval-a-retry9-2026-11-07/package-candidate-008-cleanup.json), [compatible-copy failure](evidence/phase6b-approval-a-retry9-2026-11-07/package-fallback-008-failure.txt), [watchdog](evidence/phase6b-approval-a-retry9-2026-11-07/watchdog.log), [ARM activity](evidence/phase6b-approval-a-retry9-2026-11-07/resource-activity-readonly.json), [independent deletion](evidence/phase6b-approval-a-retry9-2026-11-07/independent-deletion.json), [production preservation](evidence/phase6b-approval-a-retry9-2026-11-07/production-final-readonly.json), [adjusted lifetime/cost](evidence/phase6b-approval-a-retry9-2026-11-07/lifetime-and-cost.json), [machine-readable result](evidence/phase6b-approval-a-retry9-2026-11-07/result-summary.json).

**PARTIAL / STOPPED after retry-9.** Cleanup is independently verified. Remaining gates: compatible-copy preservation, controlled failure cycles, and a trustworthy wall-clock cleanup bound before another rehearsal. No next approval is inferred. Recovery B and production C–F remain unauthorized.
