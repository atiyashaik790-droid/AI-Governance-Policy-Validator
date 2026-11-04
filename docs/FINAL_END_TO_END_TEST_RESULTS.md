# End-to-end test results — 31 October 2026

**Final local result: PASS. Live generation acceptance: NOT RUN / approval required.**

## Exact primary commands and results

From repository root unless directory is specified:

| Directory | Command | Result |
| --- | --- | --- |
| backend | `../.venv/bin/pytest -q` | Baseline 312 passed, 1 warning, 16.40 s |
| frontend | `GOVERNANCE_TEST_PYTHON='/home/sigmoid/AI governance policy validator/.venv/bin/python' npm test` | Baseline 7 passed, 3.57 s |
| backend | `../.venv/bin/pytest -q tests/test_generation_release.py tests/test_providers.py tests/test_demo_completion.py tests/test_live_acceptance_regressions.py` | Focused 63 passed |
| backend | `../.venv/bin/pytest -q --junitxml=/tmp/governance-live-stabilization-20261031/backend-final.xml` | First full post-fix: 344 passed, 1 failed; final rerun: **345 passed, 0 failed/skipped, 1 warning, 17.09 s** |
| backend | `../.venv/bin/pytest -q tests/test_governance.py::test_generation_failure tests/test_generation_release.py` | After constructor compatibility fix: 34 passed |
| frontend | `GOVERNANCE_TEST_PYTHON='/home/sigmoid/AI governance policy validator/.venv/bin/python' npm test` | **10 passed, 0 failed/skipped, 3.91 s** |
| frontend | `npm run lint` | PASS |
| frontend | `npx tsc -b` | PASS; also included by build |
| frontend | `VITE_API_URL=/ npm run build` | PASS; 2,148 modules |
| root | `.venv/bin/ruff check backend` | PASS |
| root | `.venv/bin/ruff format --check backend` | Final PASS, 33 files |
| root | `.venv/bin/python -m compileall -q backend/app backend/tests scripts/prepare_app_service.py` | PASS |
| root | `.venv/bin/pip check` | No broken requirements |
| root | `git diff --check` | PASS |
| root | `node docs/evidence/live-stabilization-2026-10-31/browser-local.cjs` | **57 passed, 0 failed, 0 page/runner errors** |
| root | `.venv/bin/python -B scripts/prepare_app_service.py --frontend-dist frontend/dist --output artifacts/live-stabilization-20261031/governance-live-stabilized.zip` | 17-entry ZIP created; not deployed |

Additional inline Python checks inspected package member hashes, ZIP integrity, absence
of configured credentials/localhost URLs, and all 16 historical evidence SHA-256 entries.
The exact ZIP was extracted and `app.hosting:app` imported under synthetic managed-SQL
settings with network calls prohibited; eight health/SPA/OpenAPI/private-path/API-auth
checks passed. No Azure connection was attempted by this package test.

## Cases A–L

| Case | Deterministic evidence | Result |
| --- | --- | --- |
| A Safe input → generation → inspected output → release | New generation tests + existing integration | PASS with mocked/fixture generation |
| B Email redaction → reinspection → sanitized dispatch | Real local Presidio + mocked generation | PASS |
| C Indian country-code phone redaction → dispatch | Real local Presidio, +91 synthetic number | PASS |
| D Confidential keyword → no generation | Four requested phrases + fixture browser | PASS |
| E Secret → no generation | Existing contextual/assignment patterns + new release tests | PASS |
| F Unsafe generated output → no release | Existing secret output tests/browser | PASS |
| G Output PII → REDACT → reinspect → release | New output action matrix | PASS |
| H Human review → held → authorized decision | Existing/new integration and Chrome; resubmission required | PASS within existing contract |
| I Provider failure → BLOCK, safe diagnostic | HTTP status/transport/empty/incomplete matrix and UI | PASS |
| J Moderation failure → fail closed | Existing input cases + new output outage case | PASS |
| K Unauthorized role → 403 | Existing offline provisioning/RBAC suite | PASS |
| L Cross-tenant access → denied | Existing isolation/security suite | PASS |

Output redaction reinspection failure is also tested and blocks release. Active version
name/rules remain immutable despite unpublished draft edits. Unsupported policy fields
return 422. Truncated/content-filtered/tool-only provider responses fail closed.

## Browser evidence

Real Chrome on new disposable SQLite, fixture AI/moderation and limited regex PII;
no live calls. Covers login, policy CRUD/lifecycle/history, simulations, all four decisions,
withholding, review approval/rejection, feedback, navigation, logout and responsive layouts.
Desktop 1440×1000, tablet 820×1180 and mobile 390×844: all 15 page-overflow checks passed.
An intercepted synthetic provider failure explicitly verifies the Generation failed label,
GENERATION_READ_TIMEOUT diagnostic and absent output inspection. A subsequent actual
fixture HTTP request verifies Generation succeeded. These are not real Azure responses.
Mobile provider-failure screenshot was visually inspected.

## Actual read-only live observations

- Local 8002: health, readiness, OpenAPI, authenticated settings/policies/export list 200;
  invalid/missing credentials denied 401; mssql CONNECTED, live/Presidio/Admin.
- Local 5175: served API module targets 8002.
- Hosted: health/readiness/OpenAPI 200; prior accepted index/JS bytes unchanged.
- Read-only Azure management: existing model deployment and hosted config/startup reviewed.
- No fresh live policy mutations, simulation, generation, moderation, export or deployment.

## Warnings and limitations

Starlette/httpx TestClient deprecation and a 663.66 kB minified JS chunk (197.91 kB gzip)
remain non-blocking. Pip cache is unavailable in the sandbox. Docker is absent; no new
container verification was attempted. The first compatibility failure was fixed in code,
not skipped; no assertions were weakened. JWT tests are inapplicable to opaque demo bearer
authentication. Unknown historical upstream generation cause and unapproved deployment/live
acceptance remain mandatory external gates, not passing tests.

[Machine-readable summary](evidence/live-stabilization-2026-10-31/test-summary.json),
[JUnit](evidence/live-stabilization-2026-10-31/backend-final.xml),
[browser results](evidence/live-stabilization-2026-10-31/browser-local-final.json),
[read-only runtime](evidence/live-stabilization-2026-10-31/runtime-readonly.json).
