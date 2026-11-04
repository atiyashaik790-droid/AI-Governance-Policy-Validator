# Final stabilization report — 30 October 2026

## Verdict

**PARTIALLY READY — EXTERNAL BLOCKERS.** All mandatory local application checks passed:
294 backend tests, 7 frontend tests, 52 real-Chrome checks, lint, formatting, TypeScript,
production build, dependency consistency and npm audit. The controlled offline technical
demo is ready. Docker build/runtime verification is blocked by the absence of Docker.
No fresh cloud inference/export/deployment verification is claimed.

See [test execution](TEST_EXECUTION_REPORT.md) for commands/results and
[local run guide](LOCAL_RUN_GUIDE.md) for copy-paste startup, login, tests and troubleshooting.

## Recorded repository state

Root `/home/sigmoid/AI governance policy validator`; branch `main`.
The [initial status snapshot](evidence/final-stabilization-2026-10-30/initial-git-status.txt)
records 21 tracked modifications/deletions and 19 untracked top-level entries before
this task. They include accepted deployment/provider work and documentation moves.
Those existing changes were preserved. No commit, reset, restore, push or deployment occurred.

Actual layout: FastAPI `backend/app/`; tests `backend/tests/`; Alembic
`backend/migrations/` plus `backend/alembic.ini`; React `frontend/src/`; Vite config
`frontend/vite.config.ts`; startup and diagnostics `scripts/`; hosting `deployment/`;
CI `.github/workflows/ci.yml`; Compose `docker-compose.yml`; docs organized as
`guides/`, `reports/`, `runbooks/`, and `evidence/`.

Restructuring checks passed: Python imports/test collection, actual temporary Alembic
upgrades, React imports/TypeScript/build, deployment tests/startup shell syntax,
Compose/CI YAML parsing, Docker COPY/context path inspection, and all local Markdown
file links. Root `.env` resolution remains repository-relative. Relative SQLite paths
still depend on working directory, so use the documented `backend/` launch directory.

## Errors found and corrections

No application defect or failing existing test was reproduced. No application code,
existing test, environment file or dependency lock was changed in this stabilization.
The scope differences in the master checklist are documented rather than implemented
as unrelated features: authentication is opaque demo bearer tokens, not JWT; there is
no policy rejection/rollback endpoint or reviewer assignment workflow. These cannot be
reported as verified features. The schema is validated during draft save and transitions.

The prior browser runner was copied into the new evidence directory, made repository-
relative, given an optional Playwright module override, and made to exit unsuccessfully
when recorded checks/page errors fail. Two explicit simulation assertions were added.
The runner passed 50 checks before and 52 after those evidence improvements.
No test expectation was weakened or removed.

## Database and security

Disposable SQLite tests verify persistent lifecycle records, feedback, audit, reviews,
export success/failure state, session commit/rollback, foreign keys, concurrent updates,
append-only ORM protections and tenant isolation. SQL Server models/queries compile;
Azure engine selection, identity/driver validation and error behavior are mocked.
A fresh read-only local readiness/settings probe confirmed SQLite CONNECTED; hosted
readiness also passed. No live schema changes, write tests, reset or migration occurred.

Valid/invalid/missing tokens, role enforcement and cross-tenant denial passed. The
frontend sends bearer credentials and removes them on logout. No configured credential
values were found in frontend source/build assets. Audit immutability is an application
ORM control, not database-administrator tamper resistance. Demo tokens do not expire;
enterprise SSO, JWT validation and token revocation are outside the accepted architecture.
Governance failures withhold output; human review approval does not automatically replay
or release held content. Existing regex/PII limitations remain documented in prior reports.

## Azure status and evidence

| Integration | Fresh verification | Live qualification |
| --- | --- | --- |
| Azure OpenAI | Mocked request/auth/response/timeout and failure contracts PASS | No new paid call |
| OpenAI Moderation | Mocked parsing/category/fail-closed tests PASS | No new live call |
| Presidio | Real installed local model detection/redaction test PASS | Local processing |
| Azure SQL | Mocked driver/auth/selection, SQL dialect tests; hosted readiness 200 | Prior live schema evidence; no fresh direct inventory |
| ADLS | Mocked SDK transport/upload conditions/export state tests PASS | Historical successful export preserved; no new live export |

All 16 files in the previous real-life evidence manifest retain their SHA-256 hashes.
See [prior final acceptance](reports/FINAL_ACCEPTANCE_REPORT.md) and
[the prior real-life test report](reports/REAL_LIFE_TEST_REPORT_2026_10_30.md).
The accepted deployment ID in historical evidence is
`eec1e450-11c4-4c0e-939f-f9df9e68999b`. Hosted health/readiness/OpenAPI responded 200
again, but its current server-side deployment ID was not freshly authenticated and
verified. This task deployed nothing; local verification is not a deployment claim.

## Files created by this task

- `docs/FINAL_STABILIZATION_REPORT.md`: scope, verdict, changes and limitations.
- `docs/LOCAL_RUN_GUIDE.md`: verified Linux setup/start/login/test/stop/troubleshooting.
- `docs/TEST_EXECUTION_REPORT.md`: exact primary commands, counts and evidence boundaries.
- `docs/evidence/final-stabilization-2026-10-30/initial-git-status.txt`: original dirty state.
- `docs/evidence/final-stabilization-2026-10-30/browser-local.cjs`: reproducible offline
  Chrome runner adapted from prior acceptance, with two additional assertions.
- `docs/evidence/final-stabilization-2026-10-30/browser-local-final.json`: final 52 checks.
- `docs/evidence/final-stabilization-2026-10-30/runtime-readonly.json`: safe fresh server probes.
- Adjacent `local-*.png` screenshots and `local-initial-dom.txt`: synthetic browser evidence.
  The adjacent manifest enumerates every file/hash. None contains demo credential values.

## Remaining actions

Use the disposable launcher on 8010 and frontend on 5174 for the technical demo; normal
servers on 8000/5173 were left running in their existing configuration. Their generation
mode is live, so do not use them for unapproved inference. No extra fixture servers remain.
For container acceptance, install Docker through the normal approved environment setup,
then build/test with isolated fixture configuration; do not automatically use live `.env`
with Compose because its startup runs migrations. Further Azure deployment, paid inference,
live export or live migration requires explicit approval. No application fix is pending.


## Follow-up correction — contextual API-key disclosure

After the baseline, user screenshots exposed a genuine secret-detection gap for
`api key is "..."` and `api key value '...'`. Seven of twelve new focused checks
failed before the fix; five ordinary-discussion checks passed. The initial attempted
shell write used an incorrect relative path and wrote nothing; the test file was then
created at the correct path before running these checks.

Updated `backend/app/engine.py` to recognize spaced API-key assignment labels and
natural-language disclosure of tokens at least 16 characters long containing letters
and digits. Keyword matching now strips surrounding separator whitespace, including
for existing saved documents, without rewriting policy history. Existing configured
BLOCK/REDACT/HUMAN_REVIEW actions remain authoritative. This is heuristic detection;
unknown formats can still evade it, and it is not a guarantee of comprehensive secrets detection.

Added `backend/tests/test_secret_context.py`: six disclosure formats, five legitimate
API-key discussion examples, keyword whitespace, and simulation/input/output/generation
release-gating checks with synthetic values. Generation is asserted not called for blocked
inputs, and audit metadata must not contain the synthetic secret.

Fresh post-fix verification:

- `cd backend && ../.venv/bin/pytest -q`: **307 passed**, one deprecation warning, 41.00 s.
- `../.venv/bin/ruff check app/engine.py tests/test_secret_context.py`: PASS.
- `../.venv/bin/ruff format --check app/engine.py tests/test_secret_context.py`: PASS.
- Frontend tests with `GOVERNANCE_TEST_PYTHON` enabled: **7 passed**, 6.28 s.
- Browser runner extended with the reported contextual simulator case: **53 passed**,
  zero page/runner errors, using a new disposable backend.
- `git diff --check`: PASS.

The existing offline server was deliberately not restarted: its launcher deletes its
policies/history on shutdown. It still needs a restart to load the fix, which produces
a new temporary database and credential file. Do not reuse the previous fixture token.
No live requests, exports, configuration edits, or deployment occurred.
