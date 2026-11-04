# Restricted demo completion validation

1 November 2026 (Asia/Kolkata). Selected scope: restricted demo authentication. **Local implementation complete; corrected release deployed and healthy. Thirteen hosted functional checks passed; independent ADLS read-back remains permission-blocked.**

| Executed check | Result |
|---|---|
| Full backend regression suite | **434 passed**, one Starlette/httpx transport deprecation warning; 53.70 seconds |
| New audit regression coverage | Stale policy edits, analytics stage masking, assignment theft, exchange-only auth, Unicode secret/keyword spans, deadline/no-release, event-loop responsiveness, review-note redaction, malformed moderation, per-actor feedback, session throttling, author resubmission, safe bookkeeping, capability authorization and unavailable recognizer submission |
| Frontend Vitest with real disposable FastAPI | **16 passed across 3 files** |
| Real Chrome acceptance | **52 passed, 0 failed**, zero captured pageerror events |
| Responsive acceptance | Desktop 1440×1000, tablet 820×1180, mobile 390×844; checked routes fit viewport; scroll guidance added for mobile actions |
| Local read burst | 100/100 successful requests at concurrency 10; p50 53.46 ms, p95 91.95 ms; fixture smoke only |
| Exact release ZIP smoke | **12 passed** in isolated process with disposable SQLite/fixture providers; no live SQL/AI/storage |
| Backend and root scripts Ruff | Lint and format check passed, 55 Python files |
| Frontend ESLint and TypeScript | Passed |
| Same-origin Vite production build | Passed; 2,151 modules; main JS approximately 299 KB, deferred charts approximately 379 KB |
| Isolated clean frontend installation | `npm ci --ignore-scripts`, lint and production build passed with Node 24 |
| Fresh npm advisory lookup | **0 vulnerabilities** after user-approved development-tooling update |
| ZIP integrity and source equality | Passed; 26 allowlisted members; all packaged application source matches current workspace |

Release: **1.2-fd9d6fee6af8aa17**, API 1.2.0, required schema **004 unchanged**. ZIP SHA-256: `390ca1e896a740754e93f7aa7b3881e8ce32912776c2c1b44b2307715c7d88a9`.

Evidence is in [evidence/restricted-demo-2026-11-01](evidence/restricted-demo-2026-11-01). The release package/manifest are under `artifacts/restricted-demo-20261101` (ignored build output). See the [concrete deployment and acceptance plan](RESTRICTED_DEMO_RELEASE_PLAN.md).

After local implementation, the user explicitly approved deployment and bounded live acceptance. The corrected package deployed as `22837d1a-eea5-4d12-89bc-5243c9f232e1`, with one worker refresh and no rollback. Thirteen hosted functional checks and read-only browser checks passed. Retained synthetic data and precise bounds are documented in [live results](RESTRICTED_DEMO_LIVE_RESULTS.md). No schema, permission, resource, account or secret change was made. An independent ADLS checksum read returned 403 AuthorizationPermissionMismatch; it is unverified, not a passing check. Docker is unavailable, so the new production Docker configuration has been prepared but not executed. Formal WCAG, penetration, sustained SQL Server load/failover and production identity certification remain outside the selected demo scope.

The repository already contained extensive uncommitted changes. They were preserved; no commit, push, reset, or wholesale replacement was performed. Historical status reports have been labeled and linked to [CURRENT_STATUS.md](CURRENT_STATUS.md).
