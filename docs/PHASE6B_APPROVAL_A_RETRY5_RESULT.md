# Approval A retry-5 — PARTIAL / stopped at candidate health gate

Executed only the approved temporary target `sqldb-gpv-mig-20261106-a1` on server `sql-governance-validator-dev-atiya`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, with candidate **1.2-0b51806b794e3d00** (SHA-256 `e6e8531e0c28a8fca921e56a38014c9b369b5e9b170c36055f08f7ca5c14eb23`). No deployment, production writes, permission/configuration changes, real provider calls, or new services were performed. Approval A is incomplete.

## Results

- Preflight recorded the exact subscription/server/FQDN, temporary absence, SQL/firewall connectivity, S0 availability and restrictions, live retail price, candidate/migration pins and seven negative guards. All 77 pinned source dependencies and local SQLite match after execution.
- Migrations **005 → 006 → 007 → 008 passed**. Retained row hashes matched at each boundary. Revision-005 evidence was reused under the existing guards; this was not a fresh candidate-005 application qualification.
- Revision-006 schema contract, extracted candidate readiness/MULTI behavior, authentication boundary, database integrity and separate tenant-isolation gate passed. Historical session evidence was reused only under the existing unchanged-code guards.
- Revision-007 schema contract passed. Revision-008 schema/readiness contract passed under temporary runtime `EXECUTE AS` context, including required permissions and absence of execution UPDATE/DELETE permissions. Actual managed-identity authentication was not tested.
- The **unchanged security gate passed**. The saved 008 catalog contains enabled trigger `immutable_validation_executions`, implementing `INSTEAD OF UPDATE, DELETE` with THROW 51000. UPDATE and DELETE against `validation_executions` both raised expected SQL error **51000**, as did the other append-only-table assertions. Protected-content SQL constraints, nonce uniqueness, runtime permission negatives and denied DDL passed.
- The extracted candidate-008 probe then **failed** at `scripts/tests/phase6b_sql_package_probe.py:127`: `assert secure.health.healthy(engine)`. The probe waits up to 100 iterations with 0.02-second sleeps for the cleanup health signal. The evidence establishes an unhealthy/not-yet-healthy signal at this assertion, not its root cause. No assertion was changed or bypassed, and no unexplained-failure retry was attempted.
- Fresh 008 session issuance/expiry/cookie/revocation tests, full Human Review encrypted capture/reveal/audit/RBAC/tampering/expiry checks, final 008 MULTI application checks, compatible-copy ciphertext preservation and second-incarnation synthetic failure cycles were **not reached**. Passing SQL constraints does not qualify those application behaviors.

## Cleanup, limits and preservation

One Standard S0 / 10-DTU incarnation, Local backup, maximum size 250 GiB. Harness started **7 November 2026, 00:36:56 IST** and finished after finally cleanup at **00:55:33 IST**, elapsed **1,117.18 seconds (18m 37s)**. The cleanup watchdog started before creation and was terminated by the harness after confirmed deletion. No second incarnation was created.

Independent verification at approximately **00:56 IST** returned ARM GET **404 / ResourceNotFound**; separate server inventory contained only `sqldb-governance-validator-dev` and `master`, with no unexpected test databases. The independent final SELECT-only comparison confirmed production revision 005, schema metadata, runtime mapping, roles and grants unchanged. Local SQLite SHA-256 remains `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. All pinned source hashes remain unchanged; existing source changes were preserved.

Refreshed S0 price: **USD 0.4839/day**. Conservative rounded compute estimate: **USD 0.040325**, below the USD 1 limit; this is an estimate rather than a final invoice. The preflight ten-billed-hour estimate was USD 0.201625.

## Evidence and remaining blocker

[Execution](evidence/phase6b-approval-a-retry5-2026-11-07/execution.json), [candidate failure](evidence/phase6b-approval-a-retry5-2026-11-07/package-candidate-008-failure.txt), [008 catalog](evidence/phase6b-approval-a-retry5-2026-11-07/catalog-1-008.json), [independent deletion/cost/preservation](evidence/phase6b-approval-a-retry5-2026-11-07/independent-deletion.json), [production comparison](evidence/phase6b-approval-a-retry5-2026-11-07/production-final-readonly.json), [preflight](evidence/phase6b-approval-a-retry5-2026-11-07/live-preflight.json), [launch trace](evidence/phase6b-approval-a-retry5-2026-11-07/launch.log).

Remaining blocker: investigate the extracted candidate's protected-review cleanup health failure locally before proposing another Azure qualification. This run does not establish whether the cause is worker failure, startup timing, or another issue. Any further Azure rehearsal requires a fresh approval window. **STOPPED after Approval A retry-5.** Recovery drill B and production Approvals C–F were not executed.
