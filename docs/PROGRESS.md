# Progress tracker (single source of truth)

Last updated: 13 November 2026 (Claude Code session taking over from Codex). Update this file at the end of every session; older status documents are historical.

Status keys: **COMPLETE** (verified with evidence below), **FAILED**, **BLOCKED**, **APPROVAL REQUIRED**, **PENDING** (not started / not yet verified).

## Summary

| # | Item | Status | Evidence / next step |
|---|------|--------|----------------------|
| 1 | Revision-011 chat history (backend, migration, UI) | **COMPLETE** | Code was already complete from Codex; focused tests re-run: backend `tests/test_user_portal.py` 60 passed, frontend `UserPortal.test.tsx` 5 passed. |
| 2 | Chat history survives backend restart | **COMPLETE** | Fixture-mode backend on a scratch copy of the persistent DB: 3 turns (ALLOW / REDACT / BLOCK) written, backend stopped and restarted, conversation and 6 messages read back. Stored REDACT prompt was `[REDACTED]`; BLOCK prompt stored as `Request submitted`; raw secret and email absent from DB file; Admin got 403 on the User's conversation. No paid calls. |
| 3 | Git checkpoint of Codex work | **COMPLETE** | Local commit `670c58d` (378 reviewed files; secrets scan clean; excluded `.env`, databases, logs, images, `docs/evidence/`, `docs/presentation_*`). Not pushed. |
| 4 | Persistent upgraded copy of preserved DB | **COMPLETE** | `private/live-local-chat/offline.db` (+ copied `.demo-tokens.json`, mode 0600) created with SQLite online backup from `private/demo-preserved/offline.db` (journal mode `delete`, no WAL). Integrity `ok`, FK check clean, upgraded 009→010→011. Counts identical before/after: 12 policies, 12 versions, 12 assignments, 2 SSO memberships, 99 audit events, 12 executions, 52 evidence rows, 9 categories. Original still revision 009, untouched. |
| 5 | Port 5176 on persistent DB | **COMPLETE** | Approved 13 Nov. Disposable 8012 DB archived to `private/live-local-archive/offline-8012-20261113.db` (integrity ok; 8 policies, 51 audit, 6 executions, 6 usage rows match). 8012 stopped with SIGTERM and restarted with `--persistent-local`: mode `PERSISTENT_LOCAL_LIVE_AI`, live gpt-5-mini + omni-moderation. Verified (no provider calls): `/health` and `/ready` 200; MULTI set revision 21; DB revision 011; User conversation list works; Admin 12 Nov audit total 97 and executions 11; User gets 403 on audit. Log: `private/logs/live-8012.log`. |
| 6 | Audit & Reports "No records found" | **COMPLETE (no code defect; fixed by item 5, verified on 8012)** | Cause: the 5176 backend's disposable DB was created 13 Nov, so a 12 Nov filter is correctly empty. On the persistent copy, `/api/v2/audit/events?start_date=2026-11-12&end_date=2026-11-12` returns total 97 (matches DB), executions 11; 11 Nov returns 0. Date bounds are UTC in both frontend and backend; `tests/test_audit_date_filters.py` 46 passed. Resolved by item 5. Note: dates are UTC days, so 00:00–05:30 IST activity falls on the previous UTC date. |
| 7 | Required eight policies active | **COMPLETE (owner decision: leave as is)** | 13 Nov: owner chose to keep the 12 Nov deletions. Active set in the persistent copy: Customer Personal Data, API Key/Secret, Confidential Company Info, Unsafe Content, Financial and Payment (5). Credit Card, Human Approval for Sensitive Requests, AI Output Data Leakage and Enterprise AI Safety Baseline remain soft-deleted (activation correctly refused with `POLICY_INELIGIBLE`). Acceptance impact: HUMAN_REVIEW and output-leakage scenarios that depend on those policies must be checked against the remaining active set, or demonstrated only on databases where those policies exist (e.g. Azure SQL, last recorded with all eight). |
| 8 | Azure SQL verification and 008→011 migration | **COMPLETE** | 13 Nov (approved): temporary rule `gpv-operator-20261113-readonly` for 14.97.164.46 added 08:18:17Z and removed 08:18:39Z (22 s). Remaining rules byte-identical to the pre-change snapshot (`private/firewall-before-20261113.json` vs `-after-`). One read-only probe (`scripts/probe_azure_sql_revision.py`, result `private/azure-sql-probe-20261113.json`): CONNECTED, `SELECT 1` = 1, `DB_NAME()` = `sqldb-gpv-demo-v008-20261108`, Alembic **008**, no `audit_events.actor_role` (010) column, no chat tables (011), 8 policies, 2 SSO memberships. No writes, no migrations. Initial failure cause was the missing firewall entry for this IP. **Migrated 008→011 on 13 Nov (approved)**: preflight ready, one upgrade, 16 runtime grants, post-check revision 011 with all counts unchanged, firewall window 81 s and restored. See [AZURE_SQL_MIGRATION_008_011_PLAN.md](AZURE_SQL_MIGRATION_008_011_PLAN.md). |
| 9 | Real Entra SSO (Admin + User) | **BLOCKED / APPROVAL REQUIRED** | Local `.env` has empty `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `SSO_PUBLIC_ORIGIN`. `backend/app/sso.py` requires an HTTPS public origin, so SSO cannot run on `http://localhost:5176`. Real SSO needs either the hosted HTTPS app (deployment) or a local HTTPS origin plus a redirect URI on the existing app registration. |
| 10 | Live providers through governed workflow | **COMPLETE (prior evidence)** / re-check **APPROVAL REQUIRED** | Previous Codex live request: 8 policies, HTTP 200, ALLOW, real generation. Not repeated. One bounded re-check after item 5 needs approval (paid). |
| 11 | Full backend suite classification | **COMPLETE (no demo-critical defect)** | 13 Nov full run (fixture providers, live keys and Azure CLI blanked, persistent DBs write-guarded): **1344 passed, 77 failed**. Classification: (a) **Historical-schema compatibility, ~66 tests** — fixtures at revisions 004–009 run current code, which writes `audit_events.actor_role` (added in 010); writes fail with `DATABASE_OPERATION_FAILED`/503 (`test_multi_policy_phase_b`, `_bridge`, `_phase_c/_e`, `test_phase6b_session_assertion` (SSO callback on 005), `test_schema_compatibility[004/005]`, `test_release_transition`, `test_multi_policy_bit_sql`). Not on the 011 path used by 5176. **Deployment consequence:** current code must not run against Azure SQL at 008; migrate to 010+ (011 for chat) before deploying. (b) **Outdated expectations after 011, 4 tests** — `test_empty_chain_schema_and_analytics`, `test_disposable_sqlite_backup_restore_drill`, `test_migration_inventory_matches_current_chain`, `test_upgrade_existing_003_preserves_rows_and_protects_history` expect head 010/table set without chat tables; `test_existing_alembic_revision` expects preserved DB 009-era inventory. (c) **Environment/dependency, ~9 tests** — `test_release_transition` subprocess tests assert empty stderr and fail on authlib's `httpx` deprecation warning; `test_distinct_rollback_preservation` (2) depends on historical rollback zips in ignored `artifacts/`. Test guard added: `backend/tests/conftest.py` now also blocks writes to `private/live-local-chat/offline.db`. |
| 12 | Input/output governance acceptance | **COMPLETE for active set (fixture mode)** / HUMAN_REVIEW **not applicable** | 13 Nov, scratch copy of the persistent DB, fixture providers, no paid calls; all 5 active policies evaluated per request (`execution_policy_evidence`). ALLOW benign → ALLOW, model invoked. Email → REDACT, model invoked, no leak. Secret, `internal-only` keyword, moderation flag → BLOCK, `model_invoked=false`. Moderation outage → BLOCK (fail closed), model not invoked. Email + card number → Customer Data REDACT vs Financial BLOCK → final **BLOCK** (most restrictive wins), model not invoked. Generated secret (`[OUTPUT_SECRET]`) → input ALLOW, output BLOCK, final BLOCK, no secret in response. Keywords stored with a leading space (`" confidential-demo"`, `" restricted-project"`) still match. HUMAN_REVIEW: no active policy has a review action (Human Approval policy deleted; owner decision item 7), so it cannot occur on 5176; review workflow is covered by passing protected-review tests. Live moderation mapping still needs one approved paid request (item 10). |
| 13 | Deployment readiness report | **PENDING** | After 8, 9, 12. |

## Running services (updated 13 Nov 2026 after the 5176 switch)

| Port | Process | Database | Notes |
|------|---------|----------|-------|
| 5176 | Vite frontend (`VITE_API_URL=http://127.0.0.1:8012`, `VITE_LOCAL_DEMO=true`) | — | Preferred frontend; unchanged. |
| 8012 | `scripts/run_live_local_demo.py --persistent-local --port 8012 --frontend-origin http://localhost:5176` (restarted 13 Nov) | **Persistent** `private/live-local-chat/offline.db`, revision **011** | Live Azure OpenAI + Moderation. Survives restarts. Previous disposable DB archived (item 5). |
| 8011 | `scripts/run_preserved_demo.py` (started 12 Nov) | `private/demo-preserved/offline.db` (revision 009) | Fixture mode, CORS 5175; no frontend running on 5175. Left untouched. |
| 5177 | — | — | Not running. |

## Port 5176: safe startup, shutdown, recovery

Switch performed 13 Nov 2026 (steps kept as the procedure for future restarts):

1. Archive the disposable DB first (SQLite online backup) to `private/live-local-archive/offline-8012-20261113.db`.
2. Stop 8012 with SIGTERM (Ctrl+C in its terminal).
3. Start the live backend on the persistent copy (frontend on 5176 keeps working; no restart needed):
   ```bash
   .venv/bin/python -B scripts/run_live_local_demo.py --persistent-local --port 8012 --frontend-origin http://localhost:5176
   ```
   The launcher refuses to start unless `private/live-local-chat/` contains both `offline.db` and `.demo-tokens.json` and the DB is at revision 011; it never migrates or seeds an existing persistent DB and never deletes it on exit.
4. Sign in on http://localhost:5176 with the Admin or User token from `private/live-local-chat/.demo-tokens.json` (same tokens as the preserved demo).

Shutdown: Ctrl+C / SIGTERM; data persists. Recovery: restart with the same command. To roll back, stop the backend and restore `private/live-local-chat/offline.db` from a fresh online backup of `private/demo-preserved/offline.db` and rerun the 009→011 upgrade (procedure in item 4).

## Approvals still required

1. ~~Switch 8012 to the persistent DB~~ (done 13 Nov).
2. ~~Policy activation~~ (owner decided 13 Nov to leave as is).
3. ~~Azure SQL read-only probe~~ (done 13 Nov; revision 008 confirmed).
4. ~~Azure SQL migration 008→011~~ (done 13 Nov; revision 011).
5. SSO test route: deployment of the current release to the hosted HTTPS app, or adding a local HTTPS redirect URI to the existing app registration (item 9).
6. One bounded live governed request after the switch (item 10).
