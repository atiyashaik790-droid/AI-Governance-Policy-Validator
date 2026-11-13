# Phase 5 consolidated local acceptance — 6 November 2026

> Superseded readiness blocker: [Phase 5A](PHASE5A_SCHEMA_CONTRACT_REPORT.md) resolves all 13 fingerprint failures without changing the approved baseline. The readiness group now has 74 passes. The original findings below remain historical evidence. Local checks support deployment preparation/review; no deployment is authorized.

**PARTIAL. READY FOR DEPLOYMENT PREPARATION: NO, pending review of the pinned hosted-probe schema contract.** Local application acceptance passes; supplementary deployment-tool tests have an unresolved fail-closed contract guard. No deployment was attempted.

## Evidence recovered and reused

The interrupted session left complete JUnit and log evidence in `/tmp/governance-phase5.3AynYc`. Backend finished with **1,112 passed, 6 failed, 35 errors** in 96.15 seconds. Frontend finished with **131 passed across 14 files**, including the actual React-to-disposable-FastAPI integration test. The original browser run failed at `/chat`; it was not accepted as a pass. Ruff passed and the saved formatting check reported three files already formatted.

Recovered backend/frontend XML, frontend log, backend log and original browser result were copied into `docs/evidence/phase5-local-2026-11-06/`. Historical hosted reports and Phase 4 evidence were inspected for context, not counted as current local acceptance. The existing `docs/reports/PHASES.md` describes an older Phase 5 Azure integration scope; no current consolidated checklist was found, so the requested coverage below is the acceptance checklist.

The saved full suites were not repeated. Affected backend files were rerun (161 passed; 35 SQL/API setup errors persisted), followed by the SQL/API verifier and SSO tests after the remaining corrections (**124 passed**). Combining the latest result for each exact JUnit case gives **1,155 unique backend cases passed**, including two new regression cases. This is consolidated evidence, not a claim that one fresh full-suite command passed. `summary.json` maps every case to its evidence file.

## Results and acceptance coverage

| Area | Result and evidence |
|---|---|
| Backend | PASS: 1,155 unique cases, recovered full suite plus affected reruns; no unresolved backend case failures |
| Frontend | PASS: 131 tests, 14 files; fresh TypeScript/Vite production build passed |
| API integration | PASS: recovered React/FastAPI workflow, disposable database integration, SQL/API record comparison and negative corruption tests |
| Clean Sign in and 120-minute sessions | PASS: frontend tests, mocked SSO/session tests and real Chrome secure-cookie/lifetime assertions |
| Microsoft Entra SSO mocks | PASS: callback, membership, session, CSRF, invalid redirect and browser authentication coverage; no Microsoft calls |
| Admin/User portal separation | PASS: backend tenant/RBAC and User portal tests; Chrome User policy access denied, refresh restored chatbot |
| Policy Management | PASS: lifecycle tests and Chrome draft/submit/approve/publish |
| LEGACY/MULTI governance | PASS: backend phase B–FG/bridge and frontend MULTI tests; Chrome decision workflow uses LEGACY |
| ALLOW/BLOCK/REDACT/HUMAN_REVIEW | PASS: API/engine/UI tests and Chrome playground |
| PDF/DOCX/TXT uploads | PASS: isolated extraction/security/governance tests in both modes and frontend attachment tests; no native browser file-picker run |
| Encrypted original-prompt Human Review | PASS: revision-007 synthetic-key tests; Chrome exact reveal and clearing after disposition |
| Reviewer assignment and disposition | PASS: API and Chrome assignment/reveal/approve |
| Audit/execution history and date ranges | PASS: tenant-scoped backend filters, attribution/pagination and frontend filters; Chrome Apply/Clear and history tabs |
| Compliance Analytics | PASS: backend aggregation, frontend analytics and Chrome navigation |
| AI Usage & Consumption | PASS: backend quota/accounting, frontend tests and Chrome reservation progress |
| Workspace Sessions | PASS: session tests/frontend pagination and Chrome refresh |
| Settings & Diagnostics | PASS: frontend tests and Chrome navigation |
| Provider banner removal | PASS: frontend coverage and Chrome route assertions |
| Export JSON/CSV button removal | PASS: frontend coverage and Chrome audit assertions |
| Existing backend export functionality | PASS: mocked successful/failing storage, recovery/idempotency, bounded exports and isolation tests; no real storage calls |
| Tenant isolation and RBAC | PASS: backend cross-tenant and role matrices; Chrome User privileged API denied |
| Migration through 007 | PASS: isolated fixtures only; 003→head twice preserves retained audit row and append-only protections; backup restore integrity; protected-content binary/tenant FK constraints and unsafe downgrade refusal |
| Readiness-script unit tests | PARTIAL: 57 passed, 13 failed; all failures stop at `REVIEWED_SCHEMA_CONTRACT_CHANGED` |

## Defects corrected

1. The User `/chat` bookmark was excluded from both SPA hosting and the SSO local return-path allowlist. Added the existing route to both allowlists. Regression coverage verifies the SPA shell and local SSO return path; invalid/external redirect tests still pass. No authentication architecture or cookie/CSRF behavior changed.
2. Migration recovery/inventory tests still expected head 006 and the 006 table set. Updated them to 007 and `ReviewContentBase`; migration files were not changed.
3. Older endpoint and pagination assertions omitted the document governance endpoint and new derived audit attribution fields. Updated exact expectations to the current contract.
4. The SQL/API verifier rejected legitimate derived audit/execution attribution fields. Added explicit field-name allowlists while preserving exact type/value checks on every database column. Added a regression rejecting an unknown audit API field; existing corruption and tenant/relationship rejection tests pass.
5. Browser runner expected an outdated chatbot heading and inspected usage before asynchronous data arrived. Corrected the selector, waited for loaded data, and added failure diagnostics. Responsive checks wait for loading indicators to clear.

## Unresolved defect and deployment blocker

`scripts/verify_hosted_runtime.py:payload` pins the reviewed schema helper SHA-256 to `e3530bb5af9199ee850f54f71984da4643dbd458c791dcd5b2c9a5b4e7612497`; current `backend/app/schema_compatibility.py` hashes to `b5da9f6e2f593f98be3750fe964260a54802bc375910b2b12312d926d08119e2`. Thirteen probe/layout unit tests consequently fail closed before producing a payload. This is a real deployment-tool compatibility blocker, not a failure of application API acceptance. The pin was preserved: bypassing it or blindly repinning would remove a review boundary. A separate contract review must establish the intended probe compatibility before updating that approval-bound fingerprint and rerunning these tests.

## Safety and limitations

`backend/governance.db` was read through SQLite read-only mode. Its revision remains **003** and SHA-256 before/after is identical: `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. All migrations and integrations used disposable fixtures; no hosted migrations, Azure operations, production SSO, real provider calls or production encryption keys were used. Existing working-tree changes were retained; no Git commit/reset/clean/stash/discard occurred.

Chrome initially could not start inside the sandbox; local fixture/browser execution succeeded outside it. The targeted TestClient run stalled inside the sandbox and only the process started during this turn was terminated before rerunning outside it. Older unrelated/stalled pytest processes found in host inventory were left untouched. No duplicate application service was started; browser fixture services shut down in the runner's finally block.

Local mocks do not establish real Entra registration/redirect/membership readiness, SQL Server migration/permission/concurrency behavior, hosted operation, live provider/storage integration, production key custody/rotation or Docker startup. Those remain separate deployment gates. Native browser uploads and MULTI-mode browser interaction were not exercised; their API/frontend automated coverage passed. Automated responsive checks and screenshots are not a formal accessibility assessment.

## Exact files changed

Source/test/report files changed during this continuation:

- `backend/app/web_assets.py`
- `backend/app/sso.py`
- `backend/tests/test_deployment_preparation.py`
- `backend/tests/test_entra_sso.py`
- `backend/tests/test_migration_recovery.py`
- `backend/tests/test_multi_policy_phase_d.py`
- `backend/tests/test_pagination.py`
- `backend/tests/test_sql_http_plan.py`
- `backend/tests/test_sql_inventory.py`
- `scripts/test_azure_sql_http.py`
- `scripts/tests/phase5_browser.cjs`
- `docs/PHASE5_LOCAL_ACCEPTANCE.md`

All new evidence files are enumerated in `docs/evidence/phase5-local-2026-11-06/changed-files.json`. Production build output was regenerated under ignored `frontend/dist/` (and TypeScript incremental cache); it was not committed or packaged for deployment. Existing modifications in these files were preserved.

## Browser final result

**PASS: 39 checks, zero failures, zero page errors** in real headless Chrome against isolated HTTPS revision-007 fixtures with mocked OIDC/providers. Final desktop/tablet/mobile checks waited for data to load. See `docs/evidence/phase5-local-2026-11-06/browser.json` and the PNGs. Ruff on changed Python files, JavaScript syntax and Git whitespace checks passed.
