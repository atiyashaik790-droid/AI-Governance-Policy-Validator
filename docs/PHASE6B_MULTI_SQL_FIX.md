# MULTI transition SQL fix — local continuation, 6 November 2026

**PASS locally — 287 tests passed, zero failed. Azure confirmation remains pending.**

Retry-2 remained stopped after its failed MULTI transition. Its temporary database was independently verified deleted. This continuation made no Azure/provider calls and did not reuse that consumed approval.

## Proven SQL-generation defect

The first active-assignment query in `change_mode()` used `Pin.active.is_(True)`. The installed MSSQL dialect compiles it as:

```sql
WHERE workspace_policy_assignments.active IS 1
```

SQL Server BIT predicates require equality (`active = 1`); `IS 1` is invalid T-SQL. This query is first reached by the MULTI switch after the saved successful LEGACY operations and readiness checks, matching the observed failure boundary. Four application queries used the same predicate: mode transition, MULTI admission/capture, active count and policy listing. Fixing only the transition would leave the subsequent gates broken.

The exact historical native error code was not logged and is not claimed recovered. SQL syntax code 102 is used only in the synthetic diagnostic regression. The invalid statement itself is reproducible with the real installed MSSQL compiler without any database access; this is a proven application SQL portability defect, not a new grant or migration requirement.

## Changes

- `backend/app/services/policy_sets.py`: mode transition and MULTI capture use `Pin.active == true()`.
- `backend/app/routers/workspace_v2.py`: active count uses the same portable equality.
- `backend/app/routers/policies.py`: active-policy EXISTS predicate uses equality.
- `backend/app/exception_handlers.py`: database failures emit an internal structured `database.failed` event with route template and sanitized diagnostic category/SQLSTATE/native code. The public response remains HTTP 503 with the same generic message. No exception text, SQL, parameters, request values or connection strings are logged.
- `backend/app/schema_compatibility.py`: allowlist syntax codes 102/156 in the existing diagnostic extractor.
- `backend/tests/test_multi_policy_bit_sql.py`: reproduce old compilation, compile actual statements issued by a seeded HTTP transition through active count/list/MULTI generation, and verify private sanitized diagnostics/public fail-closed response.

All four predicates retain tenant filters and select only true active values; no security/ETag/fencing checks were removed. Active is non-nullable. Frozen migrations, schema/grant definitions and existing source changes were preserved. No new feature, production change or deployment.

## Verification

The bounded local runner uses inherited Linux seccomp to deny IPv4/IPv6 sockets, fixture providers, blocked repository dotenv loading and disposable SQLite. Outside-sandbox execution avoids the established TestClient sandbox stall. One automatic approval review timed out before starting the first test command; its permitted single retry succeeded. It was not a test failure or an unsafe-action finding.

- `bit-focused backend/tests/test_multi_policy_bit_sql.py -q` — **3 passed**, 2.52 seconds. The seeded transition returns 200, MULTI active count is 1, policy list marks the active policy, and MULTI generation returns ALLOW. Statements from all four paths are compiled by the real MSSQL dialect and reject any `.active IS 1/0` regression.
- `multi-regression backend/tests/test_multi_policy_phase_b.py backend/tests/test_multi_policy_phase_c.py backend/tests/test_multi_policy_phase_d.py backend/tests/test_multi_policy_mssql_contract.py backend/tests/test_schema_compatibility.py backend/tests/test_protected_reviews.py backend/tests/test_release_transition.py backend/tests/test_governance.py::test_database_failure_prevents_release -q` — **284 passed**, 99.72 seconds. Covers mode changes, assignments, tenant/RBAC/ETag/concurrency/fencing, 005/006/007 compatibility, readiness negatives, encryption/audit/cleanup, migrations/rollback and packaged candidates.
- Ruff on the five changed application files and new test — **PASS**. No Boolean `.is_(True/False)` calls remain in application sources.

Commands run through `.venv/bin/python -B docs/evidence/phase6b-multi-fix-local-2026-11-06/run_local.py`, with a 480-second process bound and 45-second traceback diagnostic timer. Logs and JUnit XML are in that evidence directory.

SQLite remains revision **003**, SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. All frozen migration hashes match the previous pins. No Git commit/reset/clean/stash/discard.

## Corrected artifact and next boundary

Local candidate: **1.2-e4d3f0b8116eb37d**, [candidate ZIP](../artifacts/phase6b-multi-fix-2026-11-06/candidate.zip). The existing frontend assets were reused; ZIP CRC and packaged changed-source matches passed. Manifest and SHA-256 provenance are preserved in `artifacts/phase6b-multi-fix-2026-11-06/manifest.json` and `docs/evidence/phase6b-multi-fix-local-2026-11-06/package-preservation.json`. Original artifacts and executed retry evidence remain intact.

The consumed retry-2 harness/pins still describe its original executed candidate; they were not repointed or reauthorized. A future rehearsal must use a newly reviewed window and explicitly pin this corrected candidate. It should test the seeded 006 MULTI transition and generation before proceeding to 007, reusing prior session/schema evidence where valid. Actual corrected SQL execution on Azure, all Azure 007 encryption/security and failure-cycle qualification, recovery/PITR and fallback strategy remain pending. Local success is not Azure qualification or deployment approval.

Exact next approval needed for any Azure mutation: a **fresh Approval A rehearsal window** after target/artifact/budget/cleanup preflight for the new candidate. No B–F or deployment is authorized. Stop after this local continuation.
