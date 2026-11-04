# Final implementation report

Updated 31 October 2026, Asia/Kolkata. **CONDITIONAL DEMO READINESS; NOT PRODUCTION READY.**

Baseline commit: `8d12cc4caf78ad2b38c0d81fa297d27ace7aca9a`, branch `main`, with important preexisting changes. No reset, commit, push, existing database migration, deployment or paid provider call occurred. Source is an uncommitted working tree; package fingerprint **1.1-544cbf32d11a251a** identifies the tested application bytes, rather than implying the commit alone contains these changes.

| Item | Previous issue | Fix implemented | Test evidence | Status |
|---|---|---|---|---|
| Live generation | Historical failures discarded upstream details | Preserve existing safe diagnostics/GPT-5 mitigation; require completed `stop` responses; capture provider-reported usage only | Provider status/transport/completion and input/output release tests | PASS locally; live resolution BLOCKED |
| ADLS recovery | Upload preceded durable tracking | SQL snapshot + unique tenant/key, deterministic path/hash, PENDING/UPLOADING/COMPLETED/FAILED states, durable lease, final ownership check, explicit bounded reconciliation | Crash before upload; DB failure after upload; mismatch, duplicate, concurrent and stale-owner tests | PASS locally; cloud verification BLOCKED |
| Authentication | Browser retained permanent demo credential | Exchange for hashed opaque expiring SQL session; server logout/admin revocation; source credential/role changes invalidate sessions | Login, invalid/expired/revoked, logout, RBAC and tenant tests | PASS restricted demo; enterprise identity BLOCKED |
| Request limits | Unbounded inference/moderation access | SQL user/minute, tenant/minute/day, permanent tenant concurrency gate, expiring reservations, request deadline and warning thresholds; includes simulation | Quota exhaustion and concurrent claims | PASS locally; MSSQL concurrency acceptance pending |
| Strict input | Blank prompts/names and coerced ratings | Nonblank validation, strict integer ratings 1–5, strict rule booleans, bounded identifiers, invalid JSON/size checks | Parameterized regressions | PASS |
| PII | Obfuscated and Unicode email gaps | NFKC view, zero-width removal and bracketed markers with original span mapping; Luhn cards; reinspection; original safe text preserved | Synthetic email/phone/card/Unicode/false-positive cases and installed Presidio | PASS for documented cases; incomplete detection remains |
| Policy controls | Shared PII and all moderation categories | Backward-compatible optional entity/category allowlists enforced by engine; unavailable requested recognizers fail closed | Schema, selector and moderation tests; Chrome selector workflow | PASS |
| Analytics/export scale | All records loaded | SQL aggregate queries and bounded latest-100 trends; date windows; metadata-only export limits 10,000/5 MB by default; tenant/date index | 2,000 own/500 foreign fixture records and oversized export rejection | PASS locally; Azure execution plans/load pending |
| Frontend transport | No timeout/cancellation/non-JSON handling | Abort signals, deadline, safe errors, 401 sign-in event; no automatic mutation retry | Six API transport tests | PASS |
| Policy UI | Local-page search; role/state mismatches | Server search/status/enabled filters, duplicate guards, role/state controls, policy rejection and draft restoration requiring all gates | React-to-HTTP and Chrome lifecycle checks | PASS |
| Human review | Metadata-only workflow unclear | Assignment, bounded notes/history, reviewer checks, linked revised resubmission; reinspection always required | Backend and Chrome assignment/disposition/resubmission tests | PASS; direct release deliberately excluded |
| Feedback/usage UI | Aggregate not displayed | Visible feedback count/average and administrative consumption panel | HTTP integration and Chrome | PASS |
| Audit hardening | ORM-only history controls | Additive migration creates SQLite/MSSQL append-only history triggers; original ORM checks retained | Actual migrated SQLite raw UPDATE/DELETE denial; MSSQL SQL compiled | PASS SQLite; Azure trigger execution BLOCKED |
| Operations | Incomplete recovery guidance | Correlation IDs, security headers/no-store, release provenance, SQL revision readiness check, retention target and operations runbook | Header, migration, local restore and package tests | PASS locally; operational ownership/SQL restore drill pending |
| CI | Real frontend/backend test skipped | CI provisions a disposable Python environment and sets GOVERNANCE_TEST_PYTHON | Same command passed locally | CONFIGURED; hosted CI unobserved |
| Performance | 663.68 KB initial JS | Lazy chart/overview route | Initial 294.25 KB (92.75 KB gzip); chart chunk 378.68 KB | PASS; initial payload down about 56% |
| Dependency security | Unreviewed advisories | OSV queried 79 pinned PyPI packages; npm audit recorded | 0 OSV findings; 11 moderate dev-tool findings, 0 high/critical | PARTIAL; dev-tool advisories remain |
| Release | Dirty tree and stale reports | Allowlisted ZIP, member hashes, release metadata, secret scan and commit review plan | 15 extracted-package checks | PREPARED; no commit/deployment |

Schema source head is **004**, while fresh Azure SELECT shows **003** and eight original tables. Six additive tables are demo_sessions, inference_rate_buckets, inference_usage, export_jobs, review_assignments and review_notes. Existing rows and historical failed exports are retained. Export legacy `status=SUCCEEDED` remains compatible; durable job `state=COMPLETED` is the new internal completion state. No fresh live CSV/JSON upload was performed.

No queue, MFA implementation, identity provider, cloud resource or service dependency was introduced. Existing App Service hosting is preserved. The exact cause of the historical failures remains unknowable from the old generic metadata. A completed hosted rollout is not evidence of successful paid inference.

Evidence: [backend JUnit](evidence/final-implementation-2026-10-31/backend-final.xml), [frontend](evidence/final-implementation-2026-10-31/frontend-final.json), [Chrome](evidence/final-implementation-2026-10-31/browser-results.json), [package smoke](evidence/final-implementation-2026-10-31/package-smoke.json).

Clean-install follow-up: fresh locked Python installation repeated all 415 backend tests successfully (25.05 s). A separate npm ci --ignore-scripts installation passed lint and produced the same production asset names/sizes. See clean-install.json.
