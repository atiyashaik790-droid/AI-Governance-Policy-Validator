# Implementation baseline — 31 October 2026

Repository: `/home/sigmoid/AI governance policy validator`; branch `main`; commit `8d12cc4caf78ad2b38c0d81fa297d27ace7aca9a`.
Working tree is deliberately dirty; the initial inventory is in `evidence/final-implementation-2026-10-31/baseline-git-status.txt`. Existing source fixes, reports, moved documentation and untracked tests are preserved. No commit/push is authorized.

## Functionality and current failures
React/TypeScript/Vite → FastAPI → SQLAlchemy; migration chain 001 → 002 → 003. Server-owned opaque hashed demo bearer identities, not JWT or enterprise SSO. Versioned policies, input/output governance, metadata-only human review, feedback, SQL persistence and ADLS exports exist. Existing generation fixes add safe diagnostic codes and completion checks; their live effectiveness remains unverified. Historical provider failures discarded upstream evidence, so their precise cause cannot be recovered.

Latest 31 October stabilization evidence supersedes the 30 October demo acceptance: local fixes are not deployed. Last recorded hosted deployment is `eec1e450-11c4-4c0e-939f-f9df9e68999b`. This is historical evidence, not a fresh hosted observation. Existing hosting is Azure App Service; preserve it and create no resources.

## Verification baseline
Previous report: 345 backend tests, 10 frontend tests, 57 Chrome checks. Fresh preceding review: Python lint/format PASS; frontend ESLint/build PASS; 9 frontend tests PASS and 1 integration test skipped without its opt-in environment. Sandbox backend run timed out. An isolated backend rerun outside the sandbox is in progress. These are distinct evidence sets.

## Startup and migrations
Offline: `.venv/bin/python -B scripts/run_offline_demo.py`; frontend: `cd frontend && VITE_API_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174`.
Normal backend: `cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`. Hosted: `sh startup.sh`, entry point `app.hosting:app`. Inspect process-only live settings via the existing local-live run guide; do not replace `.env`.
Migration source head 003; no hosted migration has been executed in this audit. Local disposable migration tests are permitted.

## Pending work and security
Priorities: verify live generation after deployment approval; prepare durable exports, bounded inference, strict validation, safe normalization, configurable controls, lifecycle/search UI, resilient transport, session lifecycle, scalable analytics, CI integration, operations and release evidence. Root demo tokens lack server-side lifetime/revocation unless supplemented. Export writes precede SQL commit; analytics/exports load all records. Input coercion and Unicode PII gaps are confirmed. ORM-only immutability is not tamper-proof storage.

## Approval boundaries
No paid inference/moderation, deployment, hosted schema/data modification, permission/cloud change, secret rotation, or existing ADLS mutation without explicit approval. Prepare additive migrations and packages locally. Enterprise identity needs an approved provider and configuration. Direct human-review release remains out of scope. No existing database/data cleanup. No custom MFA or unsupported SSO claim.

## Subsequent read-only correction
Fresh hosted observation found a newer already-serving deployment 8c2639f4-41d7-4787-bce4-e7253ecbb4b2, completed 31 October 19:18 IST; generation_status is present. The initial report above described the latest narrative report available at baseline, which lagged actual deployment evidence. This task did not deploy it. Fresh Azure SQL SELECT confirms revision 003. See final-implementation evidence and final Azure report.
