# Execution-history immutability repair — local PASS, Azure pending

## Proven cause

Retry-4 stopped at `scripts/phase6b_approval_a.py` security()'s `UPDATE dbo.validation_executions SET tenant=tenant`. It succeeded instead of raising 51000. Saved `catalog-1-007.json` has no execution-history trigger; earlier UPDATE/DELETE negatives on audit_events, policy_versions and review_notes passed. This is not a SQL Server no-op optimization or a disabled trigger.

The intended contract is explicit: both `Execution` (models.py) and `Execution006` (models_multi_policy.py) reject ORM updates/deletes, runtime permissions allow SELECT/INSERT only, and the qualification gate requires SQL-level append-only protection. Raw SQL bypasses ORM listeners. Frozen 004 created triggers only on audit_events, policy_versions and review_notes; 006 only on execution_policy_evidence and workspace_policy_assignment_events; 007 only protects review_protected_content UPDATEs. Thus the frozen chain never implemented the required database trigger. SQLite 007 reproduces the same raw-SQL gap. A required earlier protection was omitted; it was not removed by 007.

## Additive correction and compatibility

New `backend/migrations/versions/008_execution_immutability.py`, parent 007, adds only execution-history UPDATE/DELETE triggers. SQL Server uses the same unconditional INSTEAD OF UPDATE, DELETE / THROW 51000 pattern as the existing history tables, guarded by dbo default schema. SQLite uses two BEFORE triggers / RAISE(ABORT). INSERT remains available. No rows, columns, indexes, identities or grants change. Unknown dialects and downgrade fail closed.

**Migrations 001–007 remain byte-identical to the saved approval pins.** No frozen file was edited. 008 needs its own schema-change approval before production; this task performs no Azure operations. DDL takes schema locks and must be rehearsed under operator privileges in a controlled migration window. Old candidates reject revision 008; deploy ordering must use an explicitly approved bridge candidate supporting 005 through 008. Never stamp or remove the new protection for rollback. No new runtime grants are needed; 007 encrypted-content grants remain applicable. Runtime remains SELECT/INSERT-only on executions.

`schema_manifests.py` adds validation_executions to 008's required history, while retaining the exact historical manifests. `schema_compatibility.py` recognizes 008, carries forward all 006/007 checks and grants, requires both execution trigger actions and rejects effective runtime UPDATE/DELETE access (including unknown permission results). `services/policy_sets.py` and `protected_reviews.py` recognize the additive revision, preserving MULTI and encrypted-review capture/cleanup. Release metadata and package builder advertise 008. Local/SQL package probes and release/head tests recognize 008 without removing any assertions.

Candidate **1.2-0b51806b794e3d00**, `artifacts/phase6b-008-fix-2026-11-07/candidate.zip`, SHA-256 `e6e8531e0c28a8fca921e56a38014c9b369b5e9b170c36055f08f7ca5c14eb23`. Frontend bytes unchanged. Old candidate/artifacts preserved. Same-code fallback007.zip is an 008-compatible identical copy, not an independently qualified fallback.

## Focused local evidence

All test databases were disposable under /tmp. Inherited seccomp denied IPv4/IPv6 sockets, repository dotenv loading was blocked, and fixture providers/synthetic keys were used. No Azure CLI, SQL cloud connection or provider call occurred. Each test invocation was bounded to 480 seconds with a 45-second traceback timer. The sandbox run stalled after 13 tests in TestClient and was terminated; the same selection completed outside the sandbox with kernel network denial.

- `run_local.py focused-network-denied backend/tests/test_execution_immutability_008.py backend/tests/test_migration_recovery.py::test_upgrade_existing_003_preserves_rows_and_protects_history backend/tests/test_schema_compatibility.py backend/tests/test_multi_policy_phase_b.py backend/tests/test_mssql_schema_reflection.py backend/tests/test_protected_reviews.py backend/tests/test_release_transition.py -q`: **193 passed**, 113.18s.
- `run_local.py application008 backend/tests/test_execution_008_application.py -q`: **7 passed**, 2.90s; reused established encryption/reveal LEGACY+MULTI, tenant/role denial, session assignment/resolution, expiry/cleanup, ciphertext and tenant-FK assertions on actual 008 fixtures.
- `run_local.py grants008 backend/tests/test_execution_immutability_008.py::test_008_missing_required_grant_fails_closed -q`: **1 passed**, 0.22s.
- **201 passed, zero failures** across these completed focused selections. Includes exact pre-fix reproduction, persisted-row preservation, no-op/real/cross-tenant UPDATE and DELETE denial, successful append, missing UPDATE/DELETE-trigger readiness failures, missing/excess/unknown grants, MSSQL offline DDL compilation, frozen-chain hashes and safe downgrade refusal. Earlier isolated 12-test run also passed, not added to the total.
- Ruff passed on changed files with E731 excluded only for an existing unrelated lambda in the SQL package probe. AST syntax checks passed. Retry-5 dry-run: seven negative target guards, 77 pinned dependencies, candidate/migration hashes PASS. No execution record exists for retry-5.

SQLite remains revision 003, SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. Existing working-tree changes and prior evidence preserved; no Git mutation commands used.

Local changes: new migration008 and two focused test modules; schema_manifests.py, schema_compatibility.py, protected_reviews.py, services/policy_sets.py, release.py; prepare_app_service.py, phase6a_package_probe.py, phase6b_sql_package_probe.py, phase6b_approval_a.py; head/release expectations in test_migration_recovery.py and test_release_transition.py; new artifact/pins, retry-5 helper copies/dry-run and these reports. No existing failing security assertion changed or removed.

Remaining: actual Azure 008 DDL/permission/immutability qualification, fresh encrypted-review/session application probes, retained-ciphertext compatible-copy and planned failure cycles. Prior retry-4 005→006→007 migration, retained hashes, 006 readiness/MULTI and tenant evidence are reused, not rerun locally. Production recovery B and production C–F remain separate blockers/approvals.

Evidence: [focused tests](evidence/phase6b-008-local-2026-11-07/focused-network-denied.log), [008 application](evidence/phase6b-008-local-2026-11-07/application008.log), [grants](evidence/phase6b-008-local-2026-11-07/grants008.log), [candidate pins](evidence/phase6b-008-local-2026-11-07/candidate.json), [prepared dry-run](evidence/phase6b-approval-a-retry5-2026-11-07/harness-dry-run.json).
