# Final test results

Updated 31 October 2026, Asia/Kolkata. **CONDITIONAL DEMO READINESS; NOT PRODUCTION READY.**

| Check | Actual result | Scope |
|---|---|---|
| Full backend pytest | **415 passed, 0 failed, 0 skipped**, 23.70 s | All tests including historical HTTP driver and disposable migrations; providers mocked/fixtures |
| Frontend Vitest | **16 passed, 0 failed, 0 skipped**, 4.20 s | Nine component/boundary + six transport + one real disposable HTTP workflow |
| Python Ruff lint/format | PASS; 43 Python files formatted | Backend, migrations and tests |
| ESLint, TypeScript, Vite | PASS | Same-origin production build |
| Python compileall / git diff --check | PASS | Application/migrations; whitespace checks |
| Chrome | 49 checks passed in the recorded acceptance; final frozen-source rerun evidence in browser-results.json | Desktop 1440×1000, tablet 820×1180, mobile 390×844; fixture providers |
| Exact ZIP smoke | **15 passed, 0 failed** | Extracted package, temporary SQLite, fixture providers, SPA/auth/lifecycle/release gates |
| Migration/restore | PASS | Fresh schema, existing 003→004 with history preservation; repeated upgrade; SQLite backup/restore with integrity and trigger checks |
| Concurrency/recovery | PASS | Two real simultaneous SQLite sessions; one export upload for duplicate key; one successful reservation at quota=1; crash and stale-owner cases |
| Dataset | PASS | 2,000 approved-tenant + 500 foreign records; latest 100 trend rows; bounded export rejection |
| Local read burst | 100 authenticated requests, concurrency 10, all 200 | Timings in local-load-smoke.json; not production capacity certification |
| Dependency audit | OSV: 79 pins, no advisory matches; npm: 11 moderate dev-tool findings, 0 high/critical | Direct-URL spaCy model excluded from registry matching |
| Hosted public smoke | health/ready/OpenAPI/index 200 | Read-only; generation_status present, new session endpoint absent |
| Azure SQL | SELECT connection PASS; actual revision 003 | No schema/data modification |
| Paid inference/moderation and fresh ADLS | NOT RUN | Explicit approval required |
| Docker Compose | UNVERIFIED | Docker executable absent |
| Firefox / formal WCAG / hosted failover | UNVERIFIED | Installed Firefox is a Snap launcher that refuses startup because snapd AppArmor confinement is unavailable; no system security changes attempted. Chrome and keyboard smoke passed. |
| Clean installation | PASS with stated scope | Fresh Python lockfile install: 415 tests pass; temporary npm ci --ignore-scripts, lint and same-origin build pass. Existing OS libraries reused. |
| GitHub-hosted CI | NOT OBSERVED | Workflow updated; no push authorized |

The first implementation runs exposed a moderation exception-path defect and outdated schema/API assumptions in tests. Both were repaired; failures were not converted to skips. The browser runner's Auditor login initially expected the dashboard while retaining a deep-link route; the runner was corrected without weakening authorization. Final green evidence is separate from those initial runs. A Starlette/httpx TestClient deprecation warning remains; no enforcement was disabled to suppress it.

Commands:
```bash
cd backend
../.venv/bin/pytest -q --junitxml=../docs/evidence/final-implementation-2026-10-31/backend-final.xml
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
cd ../frontend
npm run lint
GOVERNANCE_TEST_PYTHON="$(cd .. && pwd)/.venv/bin/python" npm test
VITE_API_URL=/ npm run build
```
Sandbox TestClient operation is restricted here; successful tests ran outside that restriction on disposable data. New tests are test_reliability_controls.py, test_pii_normalization.py and test_migration_recovery.py. Existing migration/inventory/pagination/driver expectations now account for the additive schema and precise computed metadata; stored-column equality, tenant checks and historical integrity checks remain enforced.

Evidence: [backend JUnit](evidence/final-implementation-2026-10-31/backend-final.xml), [frontend](evidence/final-implementation-2026-10-31/frontend-final.json), [Chrome](evidence/final-implementation-2026-10-31/browser-results.json), [package smoke](evidence/final-implementation-2026-10-31/package-smoke.json).

## Later fresh hosted-preflight checkpoint, 31 October 2026

Backend 415 passed (58.98 s), frontend 16 passed, Chrome 49 passed and extracted ZIP 15 passed; lint/format/TypeScript/build passed. These use disposable local data/fixtures. Fresh SQL is 003 and existing hosted deployment unchanged. Initial sandbox restrictions and successful escalated reruns are recorded in [hosted acceptance](FINAL_HOSTED_DEMO_ACCEPTANCE.md). No live migration/provider/storage write performed.
