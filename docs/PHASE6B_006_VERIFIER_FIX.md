# Revision-006 verifier fix and single retry plan — 6 November 2026

**PASS locally; Azure qualification remains PARTIAL. LOCAL ONLY. No Azure/provider calls or mutations.**

## Proven defect and historical evidence limit

The stopped retry's saved events prove that 006 DDL and retained-row verification passed, then the operator-context schema scan returned generic HTTP 503. No completed 006 catalog or underlying exception was saved. The historical exception category cannot be recovered exactly after deletion; no missing grant or migration defect is established by that record.

The installed SQLAlchemy MSSQL dialect provides a deterministic explanation and a second latent blocker:

1. Its real `get_columns()` conversion drops `sys.columns.scale` for DATETIME2: a synthetic SQL catalog row with scale 7 becomes `DATETIME2()` with `precision=None`, compiling to `DATETIME2`. Every new 006 table has a frozen `DATETIME2(7)` timestamp. The old verifier compared this string to `DATETIME2(7)` and necessarily rejected that correct reflection as `006_PHYSICAL_TYPE_MISMATCH`. The old mocks returned model types with precision 7, hiding the problem. The revised tests execute the installed dialect's actual conversion, not a substitute implementation. This is a proven production-verifier defect, not merely a harness assertion issue. It is the first deterministic failure in 006 detail verification with those real reflected types; the suppressed historical error remains unavailable.
2. `MSDialect.get_check_constraints()` raises `NotImplementedError`. The 006 details verifier and 007 protected-content verifier both called it. The old mocks implemented that unavailable method, hiding this independent blocker.

## Narrow correction

- `backend/app/schema_006_verification.py`: when MSSQL reflection omits datetime precision, query `sys.columns.scale` for the exact table/column and `system_type_id=42`. Require scale 7; wrong or unreadable scale fails closed. Read exact CHECK definitions through parameterized SELECT from `sys.check_constraints` on MSSQL; retain Inspector reflection on SQLite. Existing semantic checks, trusted/enabled constraints, types, FKs, indexes and history triggers remain enforced.
- `backend/app/schema_compatibility.py`: use the same catalog CHECK reader for 007. Preserve sanitized internal category/object/allowlisted SQLSTATE/native-code diagnostics on the 503 exception. Public status/message remain unchanged; no SQL text, parameters, raw driver messages or connection strings are emitted.
- `scripts/phase6b_approval_a.py`: persist catalog before application schema inspection, record sanitized stop diagnostics, and prepare a distinct unexecuted retry-2 window/token with corrected package pins. Reuse completed Azure 005 evidence rather than repeating its full schema/application probe; a new temporary database must still be initialized through the frozen 005 chain and seeded before migrating to 006. No current Azure qualification is claimed for the changed candidate.
- `backend/tests/test_mssql_schema_reflection.py`, `backend/tests/test_multi_policy_mssql_contract.py`: installed-dialect reproductions and realistic 006/007 contracts with negative cases.

No Alembic migration, schema manifest, grant proposal, identity permissions, application feature or frontend was changed. No evidence supports granting broader permissions. Existing least-privilege temporary grants already include object VIEW DEFINITION needed for catalog visibility; production grants remain untouched.

## Local results

Commands use the preserved bounded runner `docs/evidence/phase6b-006-local-2026-11-06/run_local.py` (480-second bound, IPv4/IPv6 denied by inherited kernel seccomp, clean environment, repository dotenv blocked, fixture providers, disposable databases). Outside-sandbox execution avoids the previously demonstrated TestClient sandbox stall; it does not permit network traffic.

- `focused-reflection backend/tests/test_mssql_schema_reflection.py backend/tests/test_multi_policy_mssql_contract.py -q` — **42 passed**, 0.21 s. Real dialect reproductions, 006/007 positive manifests; wrong/missing temporal precision, type/default/nullability/CHECK/include drift; missing grant/table/column/trigger; tenant FK and disabled/untrusted checks; sanitized diagnostics and public 503 preservation.
- `compatibility-migrations-007 backend/tests/test_schema_compatibility.py backend/tests/test_multi_policy_phase_b.py backend/tests/test_protected_reviews.py backend/tests/test_release_transition.py backend/tests/test_session_lifetime.py -q` — **181 passed**, 47.75 s. 005 compatibility, migration/retained-row/tenant regressions, SQL Server DDL compilation, readiness negatives, extracted candidate revisions 004–007, session compatibility, 007 encryption/reveal/audit/expiry/cleanup/tamper/immutability and failure rollback.
- Ruff on all five changed Python files — **PASS**.
- Retry-2 dry-run — seven target negatives and 71 dependency hashes **PASS**; both consumed approval tokens rejected; no execution exists.
- SQLite remains revision **003**, byte-identical SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. Frozen migration hashes unchanged. No Git commit/reset/clean/stash/discard.

## 007 assessment

Locally ready: binary schema compiles to VARBINARY(12)/VARBINARY(MAX), bounded/indexable nonce, composite tenant/review FK, format/retention/byte checks, nonce uniqueness and expiry indexes, update-denying trigger, SELECT/INSERT/DELETE plus metadata visibility without runtime UPDATE, healthy cleanup and retained-key/session behavior. The same CHECK-reflection correction removes its proven latent MSSQL verifier blocker. Migration 007 DDL is unchanged. **007 has not been verified on Azure SQL.**

## Single target-locked retry — requires fresh explicit approval

Prepared candidate **1.2-29ce93fc10de32b3**: `artifacts/phase6b-006-fix-2026-11-06/candidate.zip`; CRC and SHA-256 pins recorded in local evidence. Existing frontend assets reused. `fallback007.zip` is the same compatible code, explicitly not an independent fallback. Original artifacts/evidence were preserved.

1. After fresh approval only, refresh read-only account/server/name absence, S0/cost/locks and source revision/runtime SID/grant baseline. Use the new `retry-2` token/evidence directory; old tokens/windows remain consumed. Reject drift or name collision.
2. Exact target: subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, group `rg_techdemo_Atiya_Tabsum_Shaik`, server `sql-governance-validator-dev-atiya`, temporary database **sqldb-gpv-mig-20261106-a1**. Exclude production/master. Maximum S0/10 DTUs, 250 GiB, matching collation, Local backup redundancy; maximum two sequential incarnations within one combined four-hour window and USD 1 estimated compute budget.
3. Start independent cleanup watchdog before creation. Initialize only the temporary database through 005; seed synthetic baseline and freeze row hashes. Reuse the saved successful Azure 005 session/security evidence. The **first new schema/application gate is corrected 006 readiness**, under operator and temporary runtime permission contexts. Snapshot catalog and safe diagnostics on failure. No 007 unless both 006 gates pass.
4. If 006 passes, migrate to 007; verify schema, minimum grants, tenant/RBAC/SQL denials, encryption/reveal/access audit/disposition/expiry/cleanup, sessions, retained-row integrity and same-code retained-ciphertext behavior. Then use the second incarnation only for the preplanned 006 rejection / transactional 007 THROW cycle.
5. Stop on first unexpected failure or limits. Finally/watchdog delete only the exact temporary database, independently verify ARM 404 and inventory absence, and compare source/SQLite preservation. Testing deadline three hours reserves one hour for cleanup; 1800-second package bounds. No unexplained-failure retry or upsizing.

Fresh pricing must be read after approval; the prior meter's conservative ten billed compute hours were USD 0.201625, not a new live quote or billing guarantee. Helpers and launch configuration are prepared but **not executed** in `docs/evidence/phase6b-approval-a-retry2-2026-11-06/`.

No production mutations, deployment, production settings/grants/keys, customer data, real providers, restore or B–F are included. Remaining blockers: actual 006/007 SQL Server qualification, planned failure/security gates, recovery/PITR and independent fallback/explicit forward-fix strategy before production. Exact next approval: **new Approval A retry-2 only under this target/budget/cleanup scope**. STOP after local verification.
