# Retry-5 cleanup health correction — local PASS; Azure not authorized

## Finding and classification

Retry-5 failed at the former line 127 of `scripts/tests/phase6b_sql_package_probe.py`: `assert secure.health.healthy(engine)`. Expected: **True**, proving a running cleanup worker for the same engine with a recent successful cleanup pass and no expired backlog. Actual: **False** after 100 sleeps of 0.02 seconds, approximately two seconds. The worker starts asynchronously during FastAPI lifespan; startup returns before its first guarded SQL connection, schema check, clock query and expired-row/backlog queries finish. Initial health deliberately stays false until those operations succeed.

The demonstrated defect is a **test harness startup synchronization race**: elapsed polling was treated as evidence that the worker had finished. A deterministic regression holds the first SQL operation on a real disposable revision-008 database in flight through the exact old polling loop. The old assertion fails; after SQL is released, the same worker completes successfully and the unchanged health assertion passes. A simulated permission denial completes the first pass but still fails the assertion.

Historical limit: retry-5 did not record first-pass completion or its swallowed exception. Its log alone cannot prove whether that specific first pass was merely slow or also encountered a SQL/permission error. Passing 008 runtime readiness and SQL security makes no permission/configuration defect evident, but does not prove worker success. The correction resolves the proven harness race and adds the missing distinction for the next qualification; it does not claim a proven historical Azure worker outcome. No encryption/retention application defect has been established.

## Smallest correction

- `CleanupHealth` exposes a per-lifespan first-pass completion event, reset on start and signaled on either success or failure. Stop wakes waiters while leaving health false; foreign-engine results cannot signal completion.
- The SQL package probe waits at most **120 seconds for that first result**, then retains the exact `assert secure.health.healthy(engine)` requirement. Timeout, failed cleanup, stale heartbeat, shutdown and wrong-engine results fail closed. The probe never waits for a later retry to hide an unhealthy first result. It does not invoke cleanup itself or set health.
- Sanitized `cleanup.startup` output records completion, actual health and elapsed time, and is retained by the failure-log filter. No SQL parameters, keys, content or credentials are logged.

Worker scheduling, successful heartbeat calculation/age (960 seconds), retry interval, seven-day encrypted-content retention, bounded cleanup (at most 200 rows and the existing two-second work deadline), conditional deletion, audit, expiry denial, AES-GCM, key handling, tenant checks and authorization are unchanged. Migrations 001–008 and grants are unchanged. No failing security assertion was removed, skipped or replaced with an assumed success.

## Focused local validation

All completed tests ran with kernel IPv4/IPv6 socket denial, blocked repository dotenv loading, fixture providers, synthetic keys and disposable SQLite under `/tmp`. No Azure CLI operation, cloud SQL connection, provider call or deployment occurred. The sandbox TestClient run stalled after eight unit cases and was terminated; the same focused tests completed outside the sandbox with inherited kernel network denial.

- **24 passed**, 9.15 seconds: ten new startup-health regressions; seven existing revision-008 encrypted-review application cases; four unhealthy-capture cases; worker failure/recovery, bounded backlog cleanup and feature-disabled cleanup checks.
- **17 passed**, 6.97 seconds, importing the **extracted candidate**: ten startup-health regressions and seven revision-008 encrypted-review cases, including LEGACY/MULTI capture/reveal, tenant/role denial, session assignment/resolution, expiry cleanup and ciphertext/tenant constraints.
- Ruff passed on the four changed Python files (E731 excluded for the pre-existing probe lambda); AST syntax checks passed. No unrelated suites were rerun.

Evidence: [focused log](evidence/phase6b-health-local-2026-11-07/focused-network-denied.log), [extracted candidate log](evidence/phase6b-health-local-2026-11-07/extracted-candidate.log), [candidate manifest](evidence/phase6b-health-local-2026-11-07/candidate.json), [preservation](evidence/phase6b-health-local-2026-11-07/source-preservation.json), [qualification/evidence pins](evidence/phase6b-health-local-2026-11-07/qualification-pins.json).

## Candidate and evidence reuse

New candidate **1.2-cf0a97a4daffd3e7**, [candidate ZIP](../artifacts/phase6b-health-fix-2026-11-07/candidate.zip), SHA-256 **dbb916e5f2679e482d603e52f349b4de7f85e7d820142ac98ce23999a3d3918d**. The ZIP contains the completion-signal implementation. Only `app/protected_reviews.py` and `release.json` differ from retry-5's ZIP; frontend and all other application bytes are identical. The external qualification probe contains the bounded wait and unchanged health assertion. The original candidate, retry-5 evidence and existing working-tree changes are preserved.

All retry-5 Azure passes remain historical qualification evidence: migrations 005→006→007→008, revision-006 MULTI/tenant isolation, runtime 008 readiness, unchanged SQL security gate including execution UPDATE/DELETE error 51000, and retained hashes. Evidence files are hash-pinned for reuse. The completion signal does not change those contracts. This local work does not invalidate or claim to rerun them.

Local SQLite remains SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`, revision 003. Only three retry-5-pinned source files changed: `protected_reviews.py`, the package probe and its diagnostic filter in `phase6b_approval_a.py`; the new test and local evidence/report files are additive. No Git mutation commands were used.

Remaining blocker: qualify first-pass health on guarded Azure SQL and complete the previously unreached application/preservation/failure-cycle checks. See the [final targeted plan](PHASE6B_FINAL_TARGETED_QUALIFICATION_PLAN.md). **STOPPED before all Azure operations. Fresh Approval A retry-6 is required; recovery B and production C–F remain excluded.**
