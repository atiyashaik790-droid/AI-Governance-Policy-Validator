# Master prompt checkpoint — 10 November 2026

This checkpoint records the state of the existing repository against the new master prompt. It is not a release approval or a claim of production completion. Existing uncommitted changes predate this checkpoint and must be preserved.

## References and scope

- The master prompt was read from the user attachment.
- `Atiya Tabsum Shaik(2).docx` and `Pasted text(20261110-070529).txt` were not found in the workspace or available attachments, so they were not reviewed.
- The existing codebase already contains FastAPI, React, SQLAlchemy/Alembic, SSO, multi-policy governance, custom categories, protected reviews, tests, Azure preparation, and extensive historical evidence. The task is qualification and completion of this codebase, not a blank scaffold.

## Current Azure state from prior recorded evidence

- Existing App Service still serves release `1.2-ca5df7c1dc19e525` against the old revision-005 database. This is historical evidence, not a fresh Azure query in this checkpoint.
- Fresh database `sqldb-gpv-demo-v008-20261108` was initialized through revision 008, has approved Admin/User memberships, eight committed demo policies and eight active assignments. A hosted main-container managed-identity read of this database passed on 9 November. See `FINAL_RECOVERY_GATE_RESULT.md` and `POLICY_SEED_RETRY_RESULT.md`.
- Fresh candidate cutover is **NO GO** under the existing recovery decision: actual PITR restore proof, off-host review-key custody, and safe settings restoration/exclusive writer controls are incomplete. No Azure mutation, paid provider call, or deployment occurred in this checkpoint.
- The candidate and rollback artifacts identified in `FINAL_RECOVERY_GATE_RESULT.md` predate this prompt; source has many uncommitted changes. Rebuild, hash, and requalify a new release before any future deployment approval.
- The workspace-specific Azure CLI profile was subsequently confirmed via read-only inventory. The fresh and old databases both remain online; no Azure mutation or deployment occurred during local implementation.

## Local validation in this checkpoint

### Local candidate continuation

- Revision 009 adds a tenant category catalog, many-to-many policy associations, protected built-ins, draft/category synchronization, and backfill of embedded draft rules. Published policy snapshots remain unchanged. Azure SQL migration 009 is not applied.
- The disposable offline launcher now initializes revision 009, eight synthetic published policies, nine categories, and six local role credentials. The local browser preview uses a fixture-only bearer session; production SSO behavior is unchanged when `VITE_LOCAL_DEMO` is unset.
- Local smoke checks returned `/health` 200, `/ready` 200 at revision 009, eight policies, and nine categories. Frontend build/lint and 135 tests passed with one skipped. The final full backend regression passed: 1,333 tests and three dependency warnings. Browser automation was unavailable in this environment; the running local preview is handed to the user for visual review. None of this proves Azure readiness.
- User requested local inspection before any Azure deployment. Keep the hosted release untouched until explicit approval after preview and recovery gates.

- Frontend production build: PASS (`npm run build`).
- Frontend suite run concurrently with build and backend tests: 129 passed, 4 failed, 1 skipped. The four failed tests all passed on an isolated rerun (48 passed across the four files). The full suite then passed alone: 133 passed, 1 skipped.
- Backend tests hung in the restricted sandbox because even `asyncio.to_thread(lambda: 42)` could not complete there. The same smoke test passed outside the sandbox. With `PII_MODE=regex PROVIDER_MODE=fixture`, the focused backend selection passed outside the sandbox: 135 passed; the full backend suite passed: 1,325 passed, 3 warnings in 131.31 seconds.
- Browser end-to-end and fresh Azure hosted acceptance were not run. No local result is a substitute for hosted verification.

## Requirements traceability

`Implemented` means code is present; it does not imply current full regression or Azure verification. Test references identify relevant coverage, not a fresh passing result unless stated above.

| Requirement | Implementation evidence | Test/verification evidence | Status |
|---|---|---|---|
| Admin and User portals | `frontend/src/workspace.tsx`, `frontend/src/UserPortal.tsx` | `frontend/src/App.test.tsx`, `frontend/src/UserPortal.test.tsx` | Implemented; current full-suite/hosted verification pending |
| Entra SSO, sessions, RBAC, tenant isolation | `backend/app/sso.py`, `backend/app/sessions.py`, `backend/app/user_access.py` | `backend/tests/test_entra_sso.py`, `test_session_lifetime.py`, `test_sso_only.py` | Implemented; new-release hosted sign-in pending |
| Dynamic policies and categories | `backend/app/routers/categories.py`, `backend/app/services/category_catalog.py`, `frontend/src/CategoryManagement.tsx`, `frontend/src/CustomCategories.tsx` | `backend/tests/test_category_catalog.py` (20 policy associations), `test_category_migration.py`, `test_custom_categories.py`, `frontend/src/CategoryManagement.test.tsx` | Implemented and locally tested; hosted acceptance pending |
| Input/output governance and detectors | `backend/app/engine_multi_policy.py`, `backend/app/custom_rules.py`, `backend/app/pii.py`, `backend/app/providers.py` | `backend/tests/test_multi_policy_phase_d.py`, `test_multi_policy_phase_fg.py` | Implemented; full current regression and bounded live providers pending |
| Eight example policies | `deployment/demo-policy-seed.REVIEW_ONLY.json` | `docs/POLICY_SEED_RETRY_RESULT.md` | Seeded in fresh Azure DB; not active on serving site |
| Protected Human Review | `backend/app/protected_reviews.py`, `backend/app/routers/protected_reviews.py` | `backend/tests/test_protected_reviews.py` | Implemented; hosted reveal/retention pending |
| Validator API and integrations | `backend/app/routers/governance_v2.py`, `backend/app/providers.py` | `backend/tests/test_multi_policy_phase_b.py` | Implemented; hosted integration acceptance pending |
| Analytics, audit, feedback, ADLS reports | `backend/app/analytics.py`, `backend/app/routers/audit.py`, `backend/app/routers/feedback.py`, `backend/app/services/reporting_v2.py` | `backend/tests/test_audit_regressions.py`, `test_multi_policy_phase_e.py` | Implemented; current full regression/export reconciliation pending |
| Clean database and migrations | `backend/migrations/versions/005_entra_sso.py` through `009_governance_categories.py` | `backend/tests/test_category_migration.py`; prior Azure revision-008 evidence | Local 009 tested; Azure remains 008 and independent restore/full acceptance pending |
| Deployment, rollback, hosted acceptance | `scripts/prepare_final_cutover.py`, `docs/FINAL_CUTOVER_COMMAND_REVIEW.md` | `docs/FINAL_RECOVERY_GATE_RESULT.md` | Blocked at recovery and separate cutover approval |
| Documentation and presentation | `docs/ARCHITECTURE.md`, `docs/FINAL_TECHNICAL_DEMO_SCRIPT.md`, `docs/SOLUTION_ARCHITECT_INTERVIEW_QA.md`, `docs/presentation_output/AI_Governance_Policy_Validator_Demo.pptx` | New 12-slide deck rendered; package integrity and layout checks passed | Partial: live screenshots and hosted results pending |

## Next actions

1. Verify clean local initialization and at least 20 custom policies through CRUD, all role permissions, browser flows, and report reconciliation with synthetic data.
2. Keep the backend suite on a host where Python worker threads function; use fixture-only provider settings for local regression.
3. Resolve the three recorded recovery controls before preparing a newly pinned deployment request. Reconfirm live Azure inventory, cost, source artifact, database, configuration, and organizational policy read-only.
4. Ask for the exact cloud approval only after the candidate and recovery plan are concrete and reviewable. After approval, deploy and run bounded hosted acceptance. Until then, report hosted items as not verified.
