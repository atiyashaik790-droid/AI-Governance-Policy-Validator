# Final test execution — 30 October 2026

All results below are fresh unless explicitly labeled historical. Repository root:
`/home/sigmoid/AI governance policy validator`; branch `main`.
The first baseline passed; no application changes or failing-test suppression were needed.

## Commands and results

| Directory | Exact command | Result |
| --- | --- | --- |
| root | `.venv/bin/python --version` | Python 3.13.7 |
| root | `node --version` / `npm --version` | v24.22.1 / 11.19.1 |
| root | `.venv/bin/pip check` | No broken requirements |
| root | `git diff --check` | PASS |
| backend | `../.venv/bin/pytest --collect-only -q` | 294 collected; one dependency deprecation warning |
| backend | `../.venv/bin/pytest -q` | **294 passed, 0 failed, 0 skipped, 1 warning; 36.54 seconds** |
| backend | `../.venv/bin/ruff check .` | PASS |
| backend | `../.venv/bin/ruff format --check .` | PASS; 30 files formatted |
| backend | `../.venv/bin/python -m compileall -q app tests` | PASS |
| frontend | `GOVERNANCE_TEST_PYTHON='/home/sigmoid/AI governance policy validator/.venv/bin/python' npm test` | **7 passed, 0 failed, 0 skipped, 2 files; 6.41 seconds** |
| frontend | `npm run lint` | PASS |
| frontend | `npx tsc -b` | PASS |
| frontend | `npm run build` | PASS; 2,148 modules; bundle-size warning |
| frontend | `npm audit --audit-level=high` | PASS; 0 vulnerabilities |
| frontend | `npm ls --depth=0` | PASS; no missing/invalid top-level dependencies |
| root | `node docs/evidence/final-stabilization-2026-10-30/browser-local.cjs` | Initial 50/50, then **52/52** after adding explicit safe/blocked simulation assertions; zero page/runner errors |
| root | `sh -n deployment/startup.sh` | PASS |
| root | `command -v docker` | Docker absent; build/runtime BLOCKED |

Additional read-only Python checks executed through inline `.venv/bin/python` scripts:

- Parsed every `scripts/*.py` and `deployment/*.py` with `ast.parse`: PASS.
- Parsed Compose and CI YAML with `yaml.safe_load`: PASS.
- Compared installed package versions with every versioned requirement in
  `backend/requirements.lock.txt`: zero mismatches.
- Scanned frontend source and production assets for configured API key values and
  local demo tokens without printing those values: zero matches. This is a focused
  credential check, not a general proof that every possible secret is absent.
- Checked relative Markdown file links in root README and all docs: zero missing files.
- Recomputed SHA-256 for all 16 files in the historical real-life evidence manifest:
  zero mismatches. This preserves evidence integrity, not fresh cloud verification.
- Inspected existing process ownership and socket bindings with
  `ps -eo pid,ppid,args` and `ss -ltnp '( sport = :8000 or sport = :5173 )'`:
  original project uvicorn PID 105529 and Vite PID 105551 remained in place.

Backend tests exercised imports, FastAPI/OpenAPI, request validation, lifecycle transitions,
RBAC, tenant isolation, invalid/missing bearer tokens, redaction reinspection, moderation,
fail-closed generation, output withholding, feedback, compliance, audit/version immutability,
optimistic concurrency, rollback on failed requests, database selection and foreign keys.
Cloud SDK/HTTP contracts use synthetic identities/transports; real Presidio uses the installed
local NLP model. All SQL HTTP safety tests were included; the live driver was not invoked.
Actual migrations were executed twice only against a new temporary SQLite file.
No backend static type checker is configured. The existing frontend CI command does not
set `GOVERNANCE_TEST_PYTHON`, so it skips the opt-in HTTP integration there; the local
verification explicitly enabled it and passed. CI has not been executed remotely in this task.

## Browser acceptance and full workflow

[Machine-readable checks](evidence/final-stabilization-2026-10-30/browser-local-final.json)
and the adjacent reproducible runner/screenshots record the results.
The runner launched Chrome against new offline backend/Vite processes on free ports,
using synthetic data, fixture generation/moderation and limited regex PII. It stopped
its own servers; existing normal application servers were not stopped.

Verified in real Chrome: invalid login, valid login, dashboard, draft create/edit,
safe ALLOW and blocked-keyword BLOCK simulations, submit/approve/publish/activate,
disable/enable, immutable version history, ALLOW/BLOCK/REDACT/HUMAN_REVIEW,
feedback, provider-failure blocking, unsafe-output withholding, review approval/rejection
and metadata, unused-draft deletion/archive, history/review/analytics/reports/settings
navigation and logout. Save/submit validate the policy schema; no separate validate
button or endpoint exists. Backend tests separately verify Reviewer authorization.

Responsive checks used desktop 1440×1000, tablet 820×1180 and mobile 390×844 on
Overview, Policies, Create policy, Playground and Reports. All 15 page-overflow checks
passed. Screenshots were captured; the mobile policy editor was visually inspected.
No JavaScript page errors occurred. No comprehensive console-warning audit was performed.
The second browser run added assertions only; no product change was necessary.

## Read-only running-server checks

[Runtime results](evidence/final-stabilization-2026-10-30/runtime-readonly.json):

- Local `/health`, `/ready`, `/openapi.json`, authenticated `/api/settings`: all 200.
  SQLite CONNECTED; live provider mode; Presidio; generation/moderation configured but
  not freshly invoked; ADLS BLOCKED because unconfigured. OpenAPI has 31 paths.
- Hosted `/health`, `/ready`, `/openapi.json`: all 200; live mode; 31 OpenAPI paths.
  Readiness executes a read-only database probe. No direct fresh Azure SQL schema
  inventory or server-side deployment identity verification was performed.
- Existing frontend port 5173 was serving this project's Vite process; fresh browser
  acceptance verified the same source through a separate disposable frontend.

No new live generation, moderation, exports, cloud configuration change or deployment
occurred. Mocked uploads and disabled offline export failures are test data only.
The successful historical export was not repeated.

## Failures, warnings and infrastructure limits

No reproducible application or test failures were found. The first escalated command
with redirected output timed out in automatic approval review before execution; a simpler
retry succeeded. No check remains blocked by that review. The unavailable CUA browser
inventory was worked around using the existing Playwright Core/Google Chrome runner.

Non-blocking: Starlette warns that its httpx TestClient integration is deprecated;
Vite reports a 662.55 kB JavaScript chunk (197.68 kB gzip); pip cannot use its default
cache within the sandbox. None caused a failed gate. No dependency upgrade or cosmetic
bundle refactor was introduced.

External blocker: Docker is not installed, so Docker image builds, Compose startup and
container permissions remain unverified. Fresh paid/cloud mutation tests were intentionally
not performed under the user's constraints. Prior live evidence must retain its original
version/date qualification. JWT expiry/signature tests, reviewer assignment, policy rejection
and rollback are not implemented features of the accepted application; no PASS is claimed
for those features. Human review is metadata-only, with resubmission required after approval.


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
