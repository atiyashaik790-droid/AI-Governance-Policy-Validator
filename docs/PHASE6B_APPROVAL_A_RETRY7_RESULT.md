# Approval A retry-7 — PARTIAL / HUMAN_REVIEW deadline passed; assignment fixture stopped

Candidate **1.2-677a11e4b649fa7d**, SHA-256 `be1ab97768954fecb5cf26b255bfcecf2a22811848ca910536846b3784174ee9`, ran only against temporary database `sqldb-gpv-mig-20261106-a1`, server `sql-governance-validator-dev-atiya`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`. **The targeted HUMAN_REVIEW deadline correction passed on Azure SQL.** Overall Approval A remains incomplete because the next review-assignment assertion failed. The run stopped and cleanup was independently verified.

## Results and reused evidence

- Preflight PASS: exact subscription/server/FQDN, temporary absence, candidate/migration/evidence integrity, current SQL connectivity, existing single-IP firewall match, S0 availability/restrictions and live pricing. Seven negative target guards, third-incarnation denial, testing-deadline denial and probe-order/health/deadline assertions passed offline; 79 source dependencies pinned. Candidate/application bytes remained unchanged during execution.
- Recreated **005→006→007→008** with synthetic seeding and minimum temporary runtime grants. Retained hashes matched at every boundary. The **new batched verifier passed actual Azure SQL contracts at 006, 007 and runtime 008**. Final 008 catalog/runtime checks include enabled execution immutability protection and absence of execution UPDATE/DELETE permission.
- Reused pinned prior 006 MULTI/tenant and SQL security evidence, including execution UPDATE/DELETE error 51000. Reused retry-6 secure 120-minute issuance/cookie/absolute-expiry/revocation evidence with unchanged session/configuration bytes and recorded authentication logic equivalence. These are historical passes, not fresh full session or security-suite runs.
- Fresh cleanup first pass PASS: **8.838 seconds**, completed and healthy. Extracted `/ready` and release checks passed before the governance probe.
- **HUMAN_REVIEW PASS:** HTTP **200**, decision **HUMAN_REVIEW**, `model_invoked=false`. Governed execution **66,079.636 ms**, below the unchanged **90,000 ms** deadline. Remaining budget before commit **29,038.186 ms**; remaining at execution completion **23,920.318 ms**. The HUMAN_REVIEW request ran before ALLOW; no failed assertion or deadline was bypassed.
- Subsequent LEGACY ALLOW request passed HTTP 200. Encrypted-capture checks passed: protected-content row exists, synthetic original prompt bytes are not present in its ciphertext, retention is exactly **604800 seconds**, and the audit-row presence assertion passed. This does not establish successful decryption/reveal, access-audit behavior, or all plaintext-metadata assertions.
- Authorization denials reached and passed: User policy access **403**, foreign-tenant policy access **404**, and unassigned Admin protected-content reveal **403**.

## Sanitized HUMAN_REVIEW stage timings

Correlation ID `66c8fc68-4bef-4cfe-9a71-22acceaa7b1a`. Durations are inclusive; nested stages overlap and must not be summed as independent work.

| Stage | Duration | SQL count | Relevant budget |
| --- | ---: | ---: | --- |
| Authentication | 0.822 s | Not instrumented | Before governance execution budget |
| Review schema, preflight | 53.118 s | 80 | Before execution budget |
| Entire governance preflight | 54.210 s | 82 | Before execution budget |
| Policy admission | 17.362 s | 29 | Before execution budget |
| Policy selection | 0.000413 s | 0 | Inside execution budget |
| Inspection | 0.007018 s | 0 | Inside execution budget |
| Execution persistence | 0.619 s | 1 | Inside execution budget |
| Review persistence | 1.229 s | 2 | Inside execution budget |
| Review schema, capture | 52.706 s | 80 | Inside execution budget |
| Entire protected capture | 55.638 s | 85 | 29.039 s left afterwards |
| Pre-commit checkpoint | 0.000233 s | 0 | **29.038 s left** |
| Commit stage | 0.356 s | 0 cursor executions | Transaction commit is not a cursor execution |
| Entire governed execution | **66.080 s** | 101 | **23.920 s left** |

Governed execution cursor time was 44.921 s; connection acquisition/reuse at its entry was 202.646 ms. The capture schema check had 76 catalog statements out of 80 counted SQL statements. These measurements show metadata verification remains the dominant capture cost under this transport, while the corrected request fits its existing budget. They do not isolate SQL Server lock waits, network latency, raw DBAPI guard-query time or retries. Whole HTTP wall time includes authentication/preflight/admission and is **not** claimed below 90 seconds. Earlier retry-6's exact internal wait remains unknown; this run establishes the correction's successful governed execution.

## Exact stop and unreached checks

`scripts/tests/phase6b_sql_package_probe.py:396` required `assigned.status_code == 200`. The request was `PUT /api/reviews/{review_id}/assignment`, with synthetic reviewer `probe` and reason **`Synthetic test`**. Actual: **HTTP 422**, `Select a structured review reason; free-form sensitive commentary is not accepted` (3,534.58 ms). The fixture supplied a reason outside the application's accepted structured reasons. The rejection preserves that requirement; it is not evidence of an authorization bypass.

No fixture/candidate/security changes or failure retry were made during the run. Successful assignment/reveal/access-audit, remaining authorization/tampering/expiry-cleanup assertions, remaining 008 MULTI application checks, compatible-copy ciphertext preservation and second-incarnation 006 preflight/007 rollback cycles were **NOT REACHED**. No second incarnation was created. Overall package probe did not pass.

Remaining blocker: correct the invalid synthetic assignment reason locally while retaining the structured-reason requirement, then separately qualify the remaining checks under a fresh approval. No such correction or additional rehearsal is included in this execution result.

## Cleanup, resource bounds and preservation

One Standard **S0 / 10-DTU** database, Local backup, maximum size 250 GiB. Cleanup watchdog started before creation. Harness start **7 November 2026, 14:15:42 IST**; finally cleanup finished **14:31:14 IST**. Elapsed **932.05 seconds (15m 32s)**, within the three-hour testing/four-hour total bounds.

Independent verification at **14:31:31 IST** returned **ARM GET 404 / ResourceNotFound**; separate inventory contains only production and master, no unexpected test databases. Final SELECT-only production comparison confirms revision 005, schema metadata, runtime mapping, roles and baseline grants unchanged. Launch-pinned sources match. Candidate and frozen migrations unchanged. Local SQLite remains SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`.

Refreshed S0 price **USD 0.4839/day**. Conservative rounded compute estimate **USD 0.040325**, below USD 1; this is an estimate rather than a final invoice. No deployment, production writes/migrations/permission/configuration changes, firewall changes, new Azure services, real provider/storage calls or customer data were used. SQL runtime impersonation does not qualify actual managed-identity authentication.

Local preparation added retry-7 target/token/artifact/evidence handling, hash-verified historical evidence reuse and reordered the existing probe to test HUMAN_REVIEW first. It added strict model-not-invoked and positive pre-commit/execution-budget assertions without changing candidate bytes or weakening existing gates. Existing source changes and historical artifacts were preserved. No Git reset/clean/stash/discard/commit occurred.

## Evidence

[Summary](evidence/phase6b-approval-a-retry7-2026-11-07/result-summary.json), [execution](evidence/phase6b-approval-a-retry7-2026-11-07/execution.json), [full sanitized stage timings](evidence/phase6b-approval-a-retry7-2026-11-07/package-candidate-008-timings.json), [health/HUMAN_REVIEW confirmation and failure trace](evidence/phase6b-approval-a-retry7-2026-11-07/package-candidate-008-failure.txt), [008 catalog](evidence/phase6b-approval-a-retry7-2026-11-07/catalog-1-008.json), [independent deletion/cost/preservation](evidence/phase6b-approval-a-retry7-2026-11-07/independent-deletion.json), [production comparison](evidence/phase6b-approval-a-retry7-2026-11-07/production-final-readonly.json), [preflight](evidence/phase6b-approval-a-retry7-2026-11-07/live-preflight.json), [approval](evidence/phase6b-approval-a-retry7-2026-11-07/approval-record.json).

**STOPPED after Approval A retry-7.** Recovery drill B and production Approvals C–F were not executed.
