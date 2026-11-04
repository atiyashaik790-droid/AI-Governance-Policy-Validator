# Final hosted demo acceptance

31 October 2026, Asia/Kolkata. **DEMO: BLOCKED for required hosted acceptance (local rehearsal remains CONDITIONAL). PRODUCTION: NOT READY.**

This is a pre-approval checkpoint, not a completed deployment acceptance. All eight required source documents were present and read. No source was rebuilt/redesigned, no credentials printed, and no migration, grant, deployment, paid provider call, ADLS write, login/session or existing hosted-data mutation was performed. Existing uncommitted modifications/deletions/untracked files remain preserved; full inventory is recorded.

Status semantics: VERIFIED means observed evidence; FAILED means observed incorrect behavior; BLOCKED means approval/prerequisite prevents execution; NOT TESTED means no direct verification. Table FAIL means the required acceptance criterion is not met; it does not imply that an unexecuted workflow failed at runtime.

| Workflow | Expected behavior | Actual result | Evidence | Status |
|---|---|---|---|---|
| Hosted deployment | Latest release active | Existing deployment 8c2639f4 remains active; candidate not deployed | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — hosted.json; package.json | FAIL — VERIFIED mismatch |
| Azure SQL | Migration 004 verified | SELECT confirms 003; 004 not applied | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — sql.json | FAIL — VERIFIED mismatch; approval BLOCKED |
| Authentication | Authorized access | Local session/RBAC passes; hosted session writes not authorized | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — browser-results.json; backend.xml | FAIL — BLOCKED hosted acceptance |
| Policy lifecycle | Complete workflow | Local lifecycle/rejection/restore passes; hosted synthetic policy mutations not authorized | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — browser-results.json | FAIL — BLOCKED hosted acceptance |
| Azure OpenAI | Real generation succeeds | Adapter reviewed; no paid generation request made | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — backend.xml; package-smoke.json | FAIL — NOT TESTED live; approval BLOCKED |
| PII governance | Correct enforcement | Local synthetic normalization/redaction passes; current hosted policy enforcement unverified | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — browser-results.json; backend.xml | FAIL — NOT TESTED live |
| Moderation | Real provider verified | Local mocked/fixture fail-closed checks pass; no real provider call made | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — backend.xml; browser-results.json | FAIL — NOT TESTED live; approval BLOCKED |
| Human review | Safe review lifecycle | Local assignment/decision/resubmission passes; hosted data writes not authorized | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — browser-results.json | FAIL — BLOCKED hosted acceptance |
| Compliance | Accurate stored score | Local deterministic tests only; no fresh hosted score traced | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — backend.xml | FAIL — NOT TESTED live |
| Audit | Durable records | 87 existing Azure SQL audit rows readable; new hosted workflow persistence untested | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — sql.json | FAIL — partial read VERIFIED; new workflow NOT TESTED |
| ADLS | Real export succeeds | Extracted package proves durable fixture failure; no fresh upload/read-back | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — package-smoke.json; browser-results.json | FAIL — NOT TESTED live; approval BLOCKED |
| Security | Required checks pass | Local suite and Chrome RBAC pass; hosted tenant/session/failure acceptance pending | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — backend.xml; browser-results.json | FAIL — NOT TESTED fully live |
| Frontend | Hosted workflows work | Hosted shell 200; candidate assets verified locally; current hosted candidate absent | [Fresh evidence](evidence/hosted-preflight-2026-10-31/) — hosted.json; frontend-build-match.json | FAIL — partial VERIFIED; hosted workflows NOT TESTED |

## Fresh automated verification

- Backend: **415 passed, 0 failed, 0 skipped**, 58.98 s; one Starlette/httpx deprecation warning. [JUnit](evidence/hosted-preflight-2026-10-31/backend.xml).
- Frontend: **16 passed, 0 failed, 0 skipped**, 6.92 s. [Log](evidence/hosted-preflight-2026-10-31/frontend-unsandboxed.log).
- Real Chrome local fixture acceptance: **49 passed, 0 failed**, no captured critical browser errors; desktop/tablet/mobile. [Results](evidence/hosted-preflight-2026-10-31/browser-results.json).
- Exact extracted ZIP: **15 passed, 0 failed**, disposable SQLite and fixture providers. [Results](evidence/hosted-preflight-2026-10-31/package-smoke.json).
- Ruff lint/format, ESLint, TypeScript, same-origin Vite build and git diff --check passed. All rebuilt frontend bytes match the frozen ZIP; member/backend hashes match. [Summary](evidence/hosted-preflight-2026-10-31/test-summary.json).
- First sandbox frontend run failed setup with loopback EPERM (15 passed, one skipped); first sandbox backend run was interrupted without completed counts. Complete successful reruns used approved escalation. These are environment failures, not silently hidden test results. Initial Azure CLI DNS restriction was resolved with approved read-only network escalation.
- Hosted homepage, health, readiness and OpenAPI: all 200. Actual API remains 1.0.0, new session endpoint absent, current deployment unchanged. No hosted browser login performed. Local Chrome is not hosted UI acceptance.
- SQL: live SELECT connectivity, revision 003, nine dbo tables including Alembic, exact row counts and metadata verified. Management reports seven-day retention and earliest restore 28 October 2026 21:25:06 IST. Azure restore NOT TESTED. Migration/source compilation tests are not actual SQL 004 execution.
- Fresh clean dependency install, dependency audit, Docker, Firefox, formal accessibility, CI and cloud load/failover were not rerun in this checkpoint. Historical results are in FINAL_TEST_RESULTS.md; they are not fresh results here.

## Reviewed release and remaining work

Candidate **1.1-544cbf32d11a251a**, ZIP SHA-256 `3d81bdfca85f4df3b4786562283bce4d599d34662993f2c21623eeb6d3286992`. Runtime ZIP intentionally excludes migration tooling; separate frozen 004 source/SQL are part of the reviewed operation set. No package inconsistency requires changing this tested runtime artifact.

[Exact migration, recovery, permissions and deployment approval plan](FINAL_HOSTED_APPROVAL_PLAN.md) records targets, operation hashes, count baseline, command, downtime estimate, compatibility limits and separate approval scopes. Recovery operator and practical recovery execution remain prerequisites; no restore resource may be provisioned under current authorization. [Panel runbook](FINAL_DEMO_RUNBOOK.md) distinguishes fixture rehearsal from live acceptance.

Approve/review migration recovery prerequisites first, then independently approve SQL 004, runtime permissions and deployment. Verify each before the next operation. Hosted authentication/policy data mutations, one bounded real generation, moderation and one synthetic ADLS export each need their own scope. No required live workflow is marked successful by historical evidence or configuration presence. Update this checkpoint with actual post-operation evidence after approvals.

## Latest execution stop: recovery gate

The latest execution request stopped at Step 1: no designated recovery operator or approved PITR destination; only master and the source application database exist in the inspected approved resource group. The configured migration principal has Contributor, but no restore was executed. A real PITR drill creates a new database, conflicting with current no-provisioning authorization. See [exact blocker, inventory and operator permissions](FINAL_RECOVERY_PREREQUISITES.md). Migration/deployment/live operations remain unexecuted. Prior test counts were not rerun or relabeled as fresh.

## Bounded recovery planning update

The user volunteered as recovery operator. Fresh signed-in identity, pinned SQL user and server Entra administrator match; effective SQL restore/create/cleanup actions are allowed, and source SQL SELECT access/revision 003 are verified. No missing permission was identified. Continuous backup-window and S0 pricing evidence are recorded. [Exact bounded restore/verification/cleanup plan](FINAL_BOUNDED_RECOVERY_PLAN.md) is prepared for explicit approval; no temporary database exists and no restore or migration has run. Recovery readiness remains unverified until the drill succeeds.

## Final execution authorization checkpoint

Latest instruction requests one separately selectable A–H checkpoint. [Concrete scopes](FINAL_EXECUTION_APPROVAL_CHECKPOINT.md) prepared; no selections yet received. Candidate checksum and non-secret hosted integration/tenant targets reconfirmed. All required live criteria remain blocked, not passed. [Completion checkpoint report](FINAL_DEMO_COMPLETION_REPORT.md) covers every requested component.
