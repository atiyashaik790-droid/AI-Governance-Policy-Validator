# Approval A retry-8 result — PARTIAL / STOPPED

7 November 2026. Explicitly approved candidate **1.2-597d9528f2d018aa**, SHA-256 `b2166855d3bfddf879e1a7fc5af35d70538f6a7bdf96125c4ca3f05ed99b3c6f`. Retry-8 is consumed. Execution stopped at the first critical failure; no retry, fix, second incarnation, Recovery B or production C–F was performed.

The exact authorized target was subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, server `sql-governance-validator-dev-atiya`, temporary database `sqldb-gpv-mig-20261106-a1`. Fresh account/server, target absence, firewall IP, SQL connectivity, S0 capability, restrictions, live pricing and candidate/source/prior-evidence integrity gates passed. Initial sandbox network denial was resolved with network-enabled execution before any creation.

## Results

- One S0 / 10-DTU incarnation with Local backup; independent exact-target watchdog started before creation. Minimum migrations 005→006→007→008, synthetic seed, minimum runtime grants, schema contracts and retained hashes passed. Qualified prior migration/MULTI/tenant/session/immutability/security evidence was reused under pinned comparisons.
- Candidate startup cleanup completed healthy in **7.695 seconds**. Settings configured-but-unverified/null timestamp/disabled verification assertions passed, including verification rejection. Real providers were blocked.
- HUMAN_REVIEW returned **200**, no model invocation, **67.182 seconds** governed execution, **27.777 seconds** positive pre-commit budget; the unchanged 90-second assertion passed.
- Sequential assertions before the failure passed: encrypted capture (prompt bytes absent from ciphertext), seven-day expiry, role/tenant denials, unassigned reveal 403, corrected `Assigned for review` assignment 200, stale version 412, authorized exact reveal 200 with `no-store`, committed access audit, disposition 200 and ciphertext purge, renewed HUMAN_REVIEW ciphertext creation.
- **Critical blocker:** actual SQL expired-row cleanup returned `{'removed': 0, 'healthy': False}` and failed `cleaned["healthy"] and cleaned["removed"] >= 1` at probe line 455. Expired-row deletion and expiration audit were therefore not confirmed. The sanitized return does not distinguish a backlog from an exception; root cause is unestablished. No deadline/assertion/validation changes or failure skips were made.
- Not reached: compatible-copy decryptability/preservation probe, final retained-row/catalog comparison after that probe, and incarnation-two synthetic 006 preflight denials / transactional 007 THROW rollback. Approval A remains incomplete.

## Cleanup, preservation and cost

Creation intent **14:56:57 IST**, Online verified **14:58:07 IST**, deletion initiated **15:14:00 IST**, absence confirmed **15:14:20 IST**. Harness duration **1046.15 seconds (17m26s)**; confirmed Online-to-absence **972.944 seconds (16m13s)**. One of two permitted incarnations used.

Independent ARM GET returned **404 / ResourceNotFound**; independent inventory contained only `sqldb-governance-validator-dev` and `master`, with no unexpected test database. Production SELECT-only metadata/grants match the baseline at revision 005. All 81 pinned source/operator dependencies, frozen migrations, candidate and local SQLite checks passed; SQLite SHA-256 remains `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`.

Live S0 price **USD 0.4839/day**. Conservative compute estimate, allowing two billed hours for this one incarnation: **USD 0.040325**, below USD 1. This is an estimate, not an Azure billing cap or invoice. No deployment, production SQL writes, real OpenAI/Moderation/ADLS calls, additional Azure services or prohibited Git operations were performed.

Evidence: [approval](evidence/phase6b-approval-a-retry8-2026-11-07/approval-record.json), [preflight](evidence/phase6b-approval-a-retry8-2026-11-07/live-preflight.json), [execution](evidence/phase6b-approval-a-retry8-2026-11-07/execution.json), [failure](evidence/phase6b-approval-a-retry8-2026-11-07/package-candidate-008-failure.txt), [stage timings](evidence/phase6b-approval-a-retry8-2026-11-07/package-candidate-008-timings.json), [independent deletion](evidence/phase6b-approval-a-retry8-2026-11-07/independent-deletion.json), [production preservation](evidence/phase6b-approval-a-retry8-2026-11-07/production-final-readonly.json), [summary](evidence/phase6b-approval-a-retry8-2026-11-07/result-summary.json).

**STOPPED after Approval A retry-8.** Recovery B and production C–F remain unauthorized.
