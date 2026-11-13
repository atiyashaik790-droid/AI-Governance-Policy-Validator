# Approval A retry-6 — PARTIAL / stopped at HUMAN_REVIEW deadline

Approved candidate **1.2-cf0a97a4daffd3e7**, SHA-256 `dbb916e5f2679e482d603e52f349b4de7f85e7d820142ac98ce23999a3d3918d`, ran only against temporary database `sqldb-gpv-mig-20261106-a1` on `sql-governance-validator-dev-atiya`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`. The corrected cleanup assertion passed. The run stopped at the next failed application assertion and cleaned up. Approval A remains incomplete.

## Confirmed results

- Exact-target/candidate/migration/evidence pins, temporary absence, SQL connectivity, existing single-IP firewall match, S0 availability/restrictions and live retail price passed. Seven negative target guards, third-incarnation denial and testing-deadline denial passed offline before execution. The fresh retry-6 window preserved all historical evidence.
- Recreated **005→006→007→008** with unchanged migrations, synthetic seeding and minimum temporary runtime grants. Retained row hashes matched at all boundaries; schema contracts passed at 006, 007 and 008. Final 008 readiness used SQL runtime `EXECUTE AS`, including absence of execution UPDATE/DELETE permissions. The enabled `immutable_validation_executions` trigger is present in the new 008 catalog.
- Reused hash-pinned retry-5 revision-006 MULTI/tenant and SQL security evidence, including the exact execution UPDATE/DELETE rejections with SQL error 51000. These full acceptance suites were not repeated. No application bytes except the already approved cleanup completion signal differ from retry-5; candidate bytes were unchanged during this execution.
- **Corrected protected-review cleanup startup PASS:** first pass completed and health was true after **8.087 seconds**, within the 120-second bound. This is a real background pass under guarded Azure SQL runtime impersonation, not a forced heartbeat/manual cleanup. Its measured duration exceeds the old roughly two-second polling window. Saved output contains `cleanup.startup` with `completed=true`, `healthy=true`.
- Extracted `/ready` returned **200** with the expected 008 release contract; SPA returned 200; unauthenticated policies returned 401.
- **Fresh 008 session checks PASS:** mocked SSO login/callback, secure 120-minute cookie, persisted absolute expiry and issuance duration aligned. Cookie Max-Age was **7200**; issuance-duration bounds were approximately **7199.999972–7200.000062 seconds**. Session reads returned **200, 200, 401, 401**, including active immediately before expiry, denial exactly at expiry and denial after revocation. Persisted expiry remained unchanged. Expiry boundaries used the existing controlled clock rather than waiting two real hours.
- Synthetic demo session creation, policy create/submit/approve/publish/activate and LEGACY **ALLOW** generation passed.

## Stop and unreached gates

The assertion at `scripts/tests/phase6b_sql_package_probe.py:306` required `held.status_code == 200` and decision `HUMAN_REVIEW`. Actual response: **HTTP 504**, `{"detail":"Governance deadline exceeded; response withheld"}`. Recorded request duration: **274,791.87 ms**. The preceding ALLOW request returned 200 in 154,616.16 ms; `/ready` took 243,707.4 ms and SSO calls approximately 123–129 seconds under guarded SQL transport. These timings establish significant latency, but do not isolate its bottleneck or justify changing the application deadline/security checks.

The deadline response withheld content; it is not a passing HUMAN_REVIEW result. No assertion, deadline, runtime grant or candidate code was changed to continue. The harness stopped immediately when the probe returned failure. No unexplained-failure retry and no second incarnation occurred.

Full encrypted capture/reveal/access-audit/RBAC/assignment/tampering/expiry-cleanup assertions, remaining 008 MULTI application checks, same-code ciphertext-preservation checks and the second-incarnation synthetic 006 denials/007 transactional rollback were **NOT REACHED**. Passing startup health and historical SQL constraints do not qualify these application behaviors. The overall package probe did not pass.

## Cleanup, bounds and preservation

One Standard **S0 / 10-DTU** database, Local backup, maximum size 250 GiB. Watchdog started before creation. Harness start **7 November 2026, 01:10:05 IST**; finally cleanup complete **01:46:41 IST**. Elapsed **2,196.70 seconds (36m 37s)**. Testing remained below the three-hour stop/four-hour total bounds.

Independent verification at **01:46:58 IST** returned **ARM GET 404 / ResourceNotFound**; separate inventory contained only production and master, with no unexpected test databases. The final SELECT-only production comparison confirmed revision 005, schema metadata, runtime identity mapping, roles and all baseline grants unchanged. Pinned sources match their launch baseline. Candidate, frozen migrations and local SQLite remain unchanged; SQLite SHA-256 is `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`.

Refreshed S0 price **USD 0.4839/day**; conservative rounded compute estimate **USD 0.040325**, below USD 1. This is an estimate, not the final Azure invoice. No firewall changes, production writes/configuration/permission changes, deployment, new services, customer data or real AI/moderation/ADLS calls were performed. SQL `EXECUTE AS` does not establish actual managed-identity authentication.

## Preparation and evidence

Only local orchestration was adapted for the new authorized window: retry-6 token/evidence/artifact pins, validated historical-evidence reuse, omission of previously passed full 006/security acceptance suites, and existing 008 candidate probe plus conditional second-incarnation cycle. Target/time/cost/cleanup guards remained in place. Same-code `fallback007.zip` is byte-identical to the approved corrected candidate; its preservation probe was not reached. Application/probe security assertions were unchanged during execution. Existing source changes and historical artifacts were preserved; no Git reset/clean/stash/discard/commit occurred.

[Summary](evidence/phase6b-approval-a-retry6-2026-11-07/result-summary.json), [execution](evidence/phase6b-approval-a-retry6-2026-11-07/execution.json), [startup/session results and failure trace](evidence/phase6b-approval-a-retry6-2026-11-07/package-candidate-008-failure.txt), [008 catalog](evidence/phase6b-approval-a-retry6-2026-11-07/catalog-1-008.json), [independent deletion/cost/preservation](evidence/phase6b-approval-a-retry6-2026-11-07/independent-deletion.json), [production comparison](evidence/phase6b-approval-a-retry6-2026-11-07/production-final-readonly.json), [preflight](evidence/phase6b-approval-a-retry6-2026-11-07/live-preflight.json), [approval](evidence/phase6b-approval-a-retry6-2026-11-07/approval-record.json), [launch log](evidence/phase6b-approval-a-retry6-2026-11-07/launch.log).

Remaining blocker: investigate the HUMAN_REVIEW deadline failure locally before proposing any further Azure qualification. No repair or further rehearsal is included in this result. **STOPPED after Approval A retry-6.** Recovery drill B and production Approvals C–F were not executed.
