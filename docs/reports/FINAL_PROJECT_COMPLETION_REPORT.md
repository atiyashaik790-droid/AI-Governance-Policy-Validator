# Final project completion report

Updated 30 October 2026 (Asia/Kolkata). **COMPLETE — CONTROLLED TECHNICAL DEMO READY.**
The approved conditional-create fix is deployed and the exact serving worker/source verified.
One new ADLS export SUCCEEDED; independent readback verified 9 records, 1,745 bytes and
identical SHA-256. Temporary reader access was removed; all prior records/permissions
were preserved. Hosted Chrome 72/72 and disposable fixture Chrome 50/50 passed.
Backend 224/224 and focused subset 40/40 passed; frontend 7/7, lint/type/build passed.
One migration test was deselected and the historical SQL HTTP driver module excluded.
No fresh AI/moderation calls, new service, migration, commit or push occurred.

Demo URL: https://REPLACE_WITH_WEB_APP_NAME.azurewebsites.net

**Current evidence:** [final acceptance report and 22-component matrix](FINAL_ACCEPTANCE_REPORT.md)
and section 26 below. Sections 1–25 retain historical checkpoints and prior failures;
their approval-pending/partially-ready wording does not describe the final acceptance.

## 1. Executive summary

Read `FINAL_READINESS_AUDIT.md` first and verified its findings against current source.
Git initially had one untracked user file, `docs/reports/FINAL_READINESS_AUDIT.md`; it was preserved.
The existing pagination fix, engine/session wiring, API routes and frontend controls
were already implemented and were not rebuilt.

Two confirmed defects were reproduced with failing local tests and fixed narrowly:
analytics lacked deterministic ordering before selecting its latest 100 trend entries;
and a malformed moderation result with an empty category map could be accepted as
ALLOW. The fixes add timestamp/ID ordering and reject empty category maps, respectively.

Added combined adapter/workflow tests and an opt-in rendered-React → real-local-HTTP →
FastAPI integration test. Added a disposable fixture launcher for the same application,
not a separate demo app. It enables rehearsal without modifying .env, existing SQLite,
Azure SQL, the original port-8001 server, historical evidence or Phase 5 manifests.
No dependency, lockfile, model or migration changes were necessary.

## 2. Original audit findings and disposition

| Audit finding | Classification after source review | Status / action |
| --- | --- | --- |
| R1: ADLS destination absent | Blocked by credentials — destination/access configuration | BLOCKED live; successful/failed upload paths VERIFIED WITH MOCKS. Exact missing names below. |
| R2: SQL HTTP acceptance incomplete | Implemented but not live-verified | Engine/session/schema support VERIFIED LOCALLY / VERIFIED WITH MOCKS. Lower-layer connection remains VERIFIED LIVE from user evidence. New live writes not authorized. |
| R3: frontend/backend rehearsal missing | Implemented but not verified | Functional rendered UI + real disposable HTTP workflow now VERIFIED LOCALLY. Full browser visual verification BLOCKED by no connected browser surface. |
| R4: metadata-only review | Outside current project scope for automatic replay | Existing hold/approve/reject/resubmission VERIFIED LOCALLY. Automatic replay NOT APPLICABLE to agreed demo. |
| R5: local bearer auth and possible broad SQL rights | Outside production scope | Existing auth/RBAC VERIFIED LOCALLY; no SSO or principal/permission redesign implemented. Positive grants are not proof of least privilege. |
| R6: upload-before-DB-commit | Outside project scope — durable recovery | Error/status/no-overwrite contracts VERIFIED WITH MOCKS; no outbox or new storage architecture introduced. Explain uncertainty and avoid blind retry. |
| R7: tenant predicates/ORM immutability | Already completed for local scope | Isolation and immutable history VERIFIED LOCALLY. Production RLS/tamper-evident storage NOT APPLICABLE to this task. |
| R8: unordered latest-100 trend | Confirmed defect | Fixed and VERIFIED LOCALLY, including timestamp ties and MSSQL query compilation. |
| R9: visible role/state controls and undisplayed feedback aggregate | Already connected; optional UI polish outside minimum scope | Controls use existing endpoints and retain backend 403/409 protection. Feedback submit/API summary VERIFIED LOCALLY. No new panel/page. |
| R10: stale general documentation | Confirmed defect — documentation | README and architecture overview updated; historical audit/phase reports retained as evidence. New runbook/report state current acceptance limits. |
| R11: bundle/deprecation warnings | Outside project scope — non-blocking warnings | Checks pass; dependency upgrades/code splitting NOT APPLICABLE to minimum demo. |

## 3. Findings resolved

- `backend/app/main.py:analytics` now orders by Execution.created then Execution.id
  before taking the last 100 applicable trend entries. All-tenant counts and authenticated
  tenant filters remain unchanged. Regression inserts reversed dates, timestamp ties and
  more than 100 entries, and checks MSSQL compilation.
- `backend/app/providers.py:moderate_user_prompt` now rejects an empty categories dict
  even when flagged is false. A mocked malformed result now yields moderation UNKNOWN,
  final BLOCK, no generation and no safe response. The integration regression previously
  reproduced ALLOW for that malformed response and now passes.
- The offline rehearsal gap is closed by `scripts/run_offline_demo.py`: existing app,
  new temporary SQLite, private ephemeral role tokens, fixture AI/moderation, explicit
  regex PII, ADLS disabled, loopback-only serving, and graceful cleanup including SIGTERM.
- React controls were exercised against an actual isolated backend over HTTP, including
  authentication/CORS. There was no confirmed disconnected control to reconnect.

## 4. Findings already complete

Existing DB selection, Entra identity pinning, ODBC/TLS, sessions, transaction/error
handling, schema revision 003, SQL pagination fix, lifecycle gates, immutable snapshots,
redaction revalidation, output withholding, audit commit before release, review counters,
feedback Float averaging, and export metadata allowlists were retained. Existing tests
continue to pass. SQL connection/inventory/permissions were not unnecessarily re-probed.

## 5. Remaining blockers

1. ADLS account/filesystem configuration is missing, and authorization of the selected
   existing DefaultAzureCredential identity to that filesystem is not established.
2. Fresh Azure SQL HTTP workflow acceptance after the pagination fix has not been
   authorized/performed. The original Phase 5 run stays FAILED_OR_INCOMPLETE and must
   never be retried or cleaned up automatically.
3. No new billable AI/moderation call or live ADLS upload has been authorized. Historical
   AI/moderation evidence remains valid as historical evidence, not fresh availability.
4. No connected browser surface exists in this session. Real HTTP/DOM functional coverage
   is complete; full browser visual acceptance is not claimed.

No local regression failure remains. Credentials/approvals, not a speculative rebuild,
are the blockers to claiming a complete live four-service demonstration.

## 6. Files modified or added

| File | Change and reason |
| --- | --- |
| `backend/app/main.py` | Deterministic chronological analytics ordering; no route/response/schema change. |
| `backend/app/providers.py` | Empty moderation category maps are unavailable/fail-closed. |
| `backend/tests/test_demo_completion.py` | Eight focused/combined tests: full mocked-cloud workflow, malformed moderation, ADLS failure/no-overwrite, latest-100 order/MSSQL, launcher isolation, versioned Azure route, Entra mock and generation timeout. |
| `frontend/src/Backend.integration.test.jsx` | Opt-in real-HTTP UI integration with a child disposable backend; temporary token read in memory, no token argv/output, graceful child cleanup verified. |
| `frontend/eslint.config.js` | Lint the Node-runtime JSX integration test with scoped globals; existing application TypeScript/hooks rules retained. No Node typings dependency added. |
| `scripts/run_offline_demo.py` | Safe launch/rehearsal of the existing app without using business databases or cloud adapters. |
| `README.md` | Current status links, safe fallback startup and safe verification commands. |
| `docs/ARCHITECTURE.md` | Correct outdated SQL revision/access statement; no historical phase evidence rewritten. |
| `docs/runbooks/TECHNICAL_DEMO_RUNBOOK.md` | Supported startup, UI steps, decisions, feedback, integration approvals and fallback. |
| `docs/reports/FINAL_PROJECT_COMPLETION_REPORT.md` | This report, evidence, blockers and verdict. |

`docs/reports/FINAL_READINESS_AUDIT.md` was already present as an untracked user file and was
not modified. No existing secret manifest, evidence JSON, application database, .env,
model, migration, dependency version or lockfile was changed. No Git commit/push occurred.

## 7. Backend test results

**VERIFIED LOCALLY / VERIFIED WITH MOCKS:** **192 passed, 0 failed, 0 skipped;
1 migration-execution test deselected; 69 HTTP-driver tests excluded before collection.**
The historical 254-pass full-suite result is preserved. This is not a new full 262-test
run: the prohibited driver module was not imported/executed, and migrations were not run.
Mock-only Phase 4 safety contracts do not repeat the live ORM write exercise.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 timeout 60 ../.venv/bin/pytest -q -p no:cacheprovider \
  --ignore=tests/test_sql_http_plan.py -k 'not test_migrations_on_fresh_sqlite'
```

All executed DML/schema setup used disposable local test databases; existing databases
were never used as fixtures. TestClient ran outside the environment's known restrictive
sandbox. This did not authorize any cloud call. Final duration: 7.99 seconds.
Ruff lint passed across backend/scripts; format --check passed for **34 Python files**.
One existing Starlette/httpx deprecation warning remains. The initial two new defect
regressions failed before the targeted fixes; their final regression run passed.

## 8. Frontend test results

**VERIFIED LOCALLY:** **6 passed, 0 failed, 0 skipped**, two test files, with
GOVERNANCE_TEST_PYTHON set to the existing virtualenv Python. Default npm test without
that opt-in runs the original five tests and explicitly skips the new network test.
No tests were deleted/weakened, and no dependency was installed.

The JSX integration test uses Node runtime APIs to start a fresh fixture backend on a
free loopback port and render the existing React screens in jsdom. Its credentials are
read from that new private temporary file into memory, never argv/log output. It stops
only its own child and verifies credential-file cleanup. It does not run the Phase 5
HTTP driver or use cloud services. Application TypeScript remains strict; the Node JSX
test is runtime/ESLint checked without adding Node type dependencies.

ESLint passed. `npm run build` passed strict `tsc -b` and Vite production bundling.
Tests/builds used an isolated copy at `/tmp/governance-completion-verification-artjk82f`.
The build still reports its existing 662.53 kB minified JS chunk advisory; not a failure.

## 9. Azure SQL integration status

**VERIFIED LIVE — existing user-supplied connection/identity/permissions/inventory evidence.**
**IMPLEMENTED BUT NOT LIVE-VERIFIED — corrected complete HTTP/browser acceptance.**

SQLite remains the persistent default. Existing `mssql+pyodbc` process selection and
`create_azure_sql_engine` require no alternate repository abstraction. The current ORM
operations live in main.py and use the selected SessionLocal/get_database dependency.
The real dependency's commit/rollback-before-response behavior is covered by local
request tests, including failure withholding. Entra CLI tenant/user pinning, Driver 18,
token renewal, encryption/certificate validation and no-fallback behavior remain tested.
Static MSSQL schema/pagination and Float aggregate compilation pass. No migration,
permission change, persistent DB switch or live SQL write was performed.

## 10. Azure OpenAI status

**VERIFIED LIVE — recorded 28 October API-key generation and governed gateway success.**
**VERIFIED WITH MOCKS — current adapter/request/pipeline tests.**

Endpoint, deployment and API-key settings are present; values were not disclosed.
Tests cover v1 construction, a synthetic versioned route with deployment URL encoding,
API-key and Entra-token request authentication, response validation, bounded HTTP timeout
construction and unavailable-provider behavior. Entra generation is not separately
claimed live. No billable call was made in this completion.

## 11. OpenAI Moderation status

**VERIFIED LIVE — recorded 28 October moderation and input/output gateway evidence.**
**VERIFIED WITH MOCKS — category handling, failures/timeouts and complete pipeline.**

Existing endpoint/model preserved. Moderation failure cannot silently become a passed
inspection; empty category maps are now rejected as malformed. Output moderation is
performed through the same policy engine as input. Input already blocked/held is not
sent to moderation. No fresh moderation call was made.

## 12. ADLS Gen2 status

**VERIFIED WITH MOCKS — successful JSON/CSV export, allowlist, status and no-overwrite.**
**BLOCKED — live destination/access and approved upload.**

The existing SDK/DefaultAzureCredential implementation was sufficient. Combined tests
exercise the real upload adapter against mocked Azure credential/storage clients, then
verify committed SUCCEEDED exports and retained audit/execution metadata in an independent
local SQL connection. Upload exceptions are verified as FAILED attempts without content
leakage; SDK upload is called with overwrite=False.

The application does not automatically retry export POSTs or implement idempotency keys;
the Azure SDK may apply its own transient retry policy. UUID-per-export paths prevent
intentional overwriting, not duplicate artifacts across repeated POSTs. Upload-before-DB-
commit remains documented: a timeout/error is not proof of no artifact. No new storage
architecture, live upload, overwrite, delete or permission change was introduced.

## 13. Frontend/backend integration status

**VERIFIED LOCALLY:** real HTTP authentication, CORS preflight, create/edit, lifecycle,
version history, enable/disable, simulation, all four decisions, review approval,
feedback, audit/history navigation, and expected failed offline export. The React app
still uses its existing API client, routes, components and professional visual design.
No missing production endpoint or disconnected primary control was found.

The new offline runtime uses API port 8010 and frontend origin localhost:5174; original
ports/processes are unchanged. Default production/local configuration remains compatible
with localhost:8000 and localhost:5173. There is no new UI page or feedback aggregate
panel. Feedback count/average is available through the existing API as documented.

## 14. Security regression results

**VERIFIED LOCALLY / VERIFIED WITH MOCKS:** authenticated role/tenant ownership,
foreign-tenant denial, invalid bearer rejection, immutable history, optimistic policy/
review counters, required detector fail-closed behavior, no generation for blocked/held
input, redaction before external adapters, rejected output withholding, sanitized
execution metadata, export allowlists and persistence failure preventing safe release.

The combined adapter test verifies no email leaves the redaction path and no raw
safe_text/safe_response reaches persisted execution metadata. SDK export bytes exclude
raw content. The offline launcher clears live adapter settings before importing app
configuration and generates only private ephemeral demonstration tokens.

Production SSO, separate least-privilege SQL principal, database-enforced tenant RLS,
cryptographic audit integrity and automatic held-content replay remain NOT APPLICABLE
to this bounded local completion. No security gate or audit hook was weakened.

## 15. End-to-end workflow evidence

| Required workflow | Result / evidence |
| --- | --- |
| 1–3: authorize, create/validate draft, simulate | VERIFIED LOCALLY; real UI/HTTP and backend tests; invalid document rejected 422. |
| 4–6: approve, publish immutable version, activate/enable | VERIFIED LOCALLY; lifecycle order/counters/version history and disabled-policy 409 retained. |
| 7–10: submit, inspect input, decide, invoke eligible provider | VERIFIED WITH MOCKS using real adapter transport construction; fixture real-HTTP UI test also passes. |
| 11–12: inspect output; BLOCK/REDACT/HUMAN_REVIEW | VERIFIED WITH MOCKS / VERIFIED LOCALLY; output-secret withholding and redaction revalidation exercised. |
| 13: audit/history persistence | VERIFIED LOCALLY with independent reads from the new temporary database. |
| 14: review approve/reject and revised resubmission | VERIFIED LOCALLY; no automatic replay/release. |
| 15: feedback | VERIFIED LOCALLY; UI rating plus count/Float average 2.5 backend regression. |
| 16: dashboard/reports | VERIFIED LOCALLY; request-derived totals and corrected chronological latest-100 trend. |
| 17: intended JSON/CSV ADLS output | VERIFIED WITH MOCKS, including exact allowlist/status/no-overwrite; BLOCKED live. |

The combined test persists nine synthetic executions only in a temporary test database.
The running user rehearsal starts empty; no business or retained Phase 5 records were
used or modified. Mocked requests can use provider_mode live to exercise the real
adapters, but those results are explicitly mock-verified, not VERIFIED LIVE.

## 16. Missing configuration variable names

| Variable / prerequisite | Presence / requirement |
| --- | --- |
| `ADLS_ACCOUNT_URL` | Missing. Supply privately for the existing approved DFS account. |
| `ADLS_FILE_SYSTEM` | Missing. Supply privately for the existing approved filesystem. |
| Existing `DefaultAzureCredential` storage identity/access | Not verified for ADLS. An authorized existing identity is required; no new secret-variable requirement is invented. |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY` | Present at redacted inspection. No replacement requested. |
| `AZURE_OPENAI_API_VERSION` | Supported existing setting/default v1; both route styles mock-verified. |
| `OPENAI_API_KEY` | Present at redacted inspection. No replacement requested. |
| `AZURE_SQL_TENANT_ID`, `AZURE_SQL_USER_OBJECT_ID` | Present; live identity matching already supplied by user. |

Do not paste secrets into chat. No existing .env value was overwritten.

## 17. Operations awaiting explicit approval

- Fresh corrected Azure SQL HTTP acceptance using a new reviewed synthetic scope with
  retained committed-record expectations; not the failed manifest and not the prohibited
  driver under the current instruction.
- A persistent database switch, live SQL write or migration, if ever separately needed.
  None is required for the offline demo; do not rerun revision 003.
- Bounded billable live Azure OpenAI/OpenAI Moderation requests, including live simulation.
- A sanitized live ADLS upload to the existing approved destination. No overwrite/delete,
  permission or infrastructure operation is implied by that approval.

All safe independent work has been completed before leaving these operations pending.
No approval is implied by credential availability or by a passing mock test.

## 18. Technical demo readiness

**VERIFIED LOCALLY — disposable offline demo is running and demonstrable.**
Frontend: **http://localhost:5174**. Backend: **http://127.0.0.1:8010**.
Read-only health/readiness/frontend root all returned HTTP 200; settings confirmed
SQLite/fixture/regex and disabled Azure generation/moderation/ADLS. Initial policy list
was empty. Private temporary credentials are at the path printed by the new launcher;
see the runbook for the current path and startup/stop instructions.

The entire policy → decision → review/feedback/audit/dashboard flow is demonstrable
without live costs or business-data writes. An offline export correctly records FAILED.
Successful export bytes and persistence are demonstrated through mocks/tests, not a
pretend live file. Human approval requires resubmission. Full visual browser acceptance
and a live four-service chain remain unclaimed.

## 19. Final verdict

**PARTIALLY READY overall; VERIFIED LOCALLY for the offline technical demonstration.**
All safe required implementation, testing, configuration parsing, error-path verification
and documentation are complete. The remaining work is external ADLS configuration/access
and explicitly approved live acceptance. No rebuild, additional service, schema change,
new UI feature, dependency upgrade or speculative refactor is needed to reach that gate.


## 20. App Service preparation — latest phase

**PARTIALLY READY: prepared locally, not deployed; explicit approval pending.**
Read-only Azure discovery found no storage accounts, Web Apps or App Service Plans in
subscription `REPLACE_WITH_AZURE_SUBSCRIPTION_ID`. Earlier references to supplying an
existing ADLS destination are superseded by the new-account proposal in
[AZURE_DEPLOYMENT_RUNBOOK.md](../runbooks/AZURE_DEPLOYMENT_RUNBOOK.md). No Azure changes occurred.

### Changes made

- `backend/app/config.py`, `database.py`, `azure_sql.py`: explicit managed-identity SQL
  mode; local CLI default, tenant/object pinning, Driver 18 and SQLite remain supported.
- `backend/app/hosting.py`, `web_assets.py`: guarded hosted entry point and React static
  hosting; API routes/authentication retain priority; unknown/private paths return 404.
- `frontend/src/api.ts`: same-origin production paths without protocol-relative URLs.
- `backend/app/providers.py`: validate ADLS paths and conditionally create missing parent
  directories without replacing directories, ACLs or files; uploads remain non-overwriting.
- `deployment/startup.sh`, `appsettings.example.json`,
  `sql_managed_identity.REVIEW_ONLY.sql`: startup, non-secret settings and unexecuted
  SQL principal/21-grant proposal. No startup migrations or dependency installation.
- `scripts/prepare_app_service.py`: exclusive-create ZIP with an explicit file allowlist;
  excludes credentials, databases, migrations, historical evidence and symlinks.
- `backend/tests/test_deployment_preparation.py`, `frontend/src/App.test.tsx`: identity,
  hosted guards, static/API routing, packaging, ADLS path/directory and URL regressions.
- Deployment runbook, this report and technical demo runbook: concrete commands,
  settings, permissions, costs, approval boundaries and rollback.

### Latest results

| Check | Result |
| --- | --- |
| Backend | VERIFIED LOCALLY: **217 passed, 0 failed**; 1 migration execution case deselected; 69 prohibited HTTP-driver cases excluded before collection |
| Frontend | VERIFIED LOCALLY: **7 passed, 0 failed**, including real HTTP against a disposable fixture backend |
| Ruff lint / formatting | Passed; **38 Python files** formatted correctly |
| ESLint / TypeScript / Vite build | Passed in an isolated temporary copy with `VITE_API_URL=/` |
| Shell syntax / diff whitespace | Passed |
| Azure runtime inventory | Read-only query confirms `PYTHON\|3.13` Active; actual platform native dependencies remain unverified |

Prepared artifact: `/tmp/governance-appservice-prep-qi0yutlp/governance-validator-app.zip`.
SHA256: `6900d83846b35f12c9f8c23de57e5177e9592623c5e2f309a44668c87857c426`.
17 allowlisted entries; no upload. Temporary artifacts are ephemeral: rebuild and record
new hashes if missing or application source changes. Existing Vite chunk-size advisory
is non-blocking. Full browser visual acceptance and B1 memory suitability remain unverified.

| Integration | Latest status |
| --- | --- |
| Azure SQL | IMPLEMENTED BUT NOT LIVE-VERIFIED for hosted application; historical connection/revision/permission evidence retained. Managed identity VERIFIED WITH MOCKS. Full corrected HTTP acceptance not repeated. |
| Azure OpenAI | Historical VERIFIED LIVE evidence retained; hosted identity path VERIFIED WITH MOCKS, no fresh live call. |
| OpenAI Moderation | Historical VERIFIED LIVE evidence retained; current error/input/output paths VERIFIED WITH MOCKS, no fresh live call. |
| ADLS | VERIFIED WITH MOCKS; no live account/filesystem discovered. Provisioning and first export await approval. |
| Frontend/backend / policy workflow | VERIFIED LOCALLY / VERIFIED WITH MOCKS; deployed workflow not live-verified. |
| Deployment | BLOCKED by explicit approval gate; no deployed URL exists. |

### Remaining requirements and approval boundary

Approve the exact new Linux B1 plan/Web App and HNS storage/filesystem, scoped Web App
identity roles, SQL principal/21 grants, exact outbound-IP firewall rules, private settings
and ZIP deployment in the deployment runbook. Reuse existing SQL and Azure OpenAI.
Regional B1 estimate is USD 12.41 per 730 hours plus metered storage/traffic/taxes; not a cap.
No migration, historical record change or billable/data-changing acceptance is included.

After approval, populate `AZURE_SQL_USER_OBJECT_ID` from the new managed principal,
`ADLS_ACCOUNT_URL`, `ADLS_FILE_SYSTEM`, actual `CORS_ORIGIN`, private
`DEMO_ACCOUNTS_JSON` hashes and `OPENAI_API_KEY`. The existing moderation key is locally
present and must be transferred privately; no secrets are requested in chat. Azure OpenAI
uses the proposed scoped identity role. Quota/policy, SQL directory resolution, actual
Driver 18/native dependency availability and startup remain platform checks after approval.

Separate approval is required for synthetic SQL writes, billable AI/moderation and a
single non-overwriting ADLS export. Never reuse failed historical manifests or run the
prohibited SQL HTTP driver. Initial rollback stops only the new Web App, retaining data
and evidence; the plan still bills while the app is stopped. Destructive cleanup or role
removal needs separate approval. No environment files, historical records, original servers,
migrations, dependencies, commits or pushes were changed by this preparation.


## Approved deployment execution — 29 October 2026

The user explicitly approved the documented provisioning, permissions, configuration and
deployment scope. Earlier approval-pending statements above describe the preparation
checkpoint, not the current authorization state. Billable inference, synthetic business
records and ADLS uploads remain excluded pending a separate approval.

- Created `REPLACE_WITH_APP_SERVICE_PLAN`: Linux B1, one worker, westus2.
- Created `REPLACE_WITH_WEB_APP_NAME`, Python 3.13, HTTPS only.
- Actual URL: https://REPLACE_WITH_WEB_APP_NAME.azurewebsites.net
- System identity object ID: `REPLACE_WITH_WEB_APP_PRINCIPAL_ID`.
- Verified directory client ID: `REPLACE_WITH_WEB_APP_CLIENT_ID`.
- Created `REPLACE_WITH_ADLS_STORAGE_ACCOUNT` (StorageV2, Standard_LRS, HNS, TLS1.2,
  shared keys/public blobs disabled), private filesystem `governance-reports`.
- Assigned Cognitive Services OpenAI User on the existing OpenAI account and Storage
  Blob Data Contributor only on the new filesystem to the new Web App identity.
- Added `gv-appservice-1` through `gv-appservice-13`, each allowing exactly one current
  outbound IP. Existing rules retained; no AllowAllAzureServices rule added.
- Created the new SQL contained user/custom role, with 21 approved table grants and
  CONNECT. Read-back confirms only custom runtime role membership; no fixed roles.
- Corrected a confirmed SQL script identity comparison: application SQL SIDs represent
  client ID, whereas token `oid` pinning uses object ID. The initial guard stopped and
  rolled back before any grant committed; diagnostic creation was also rolled back.
  Directory lookup tied the exact client ID to the approved object ID before grants
  were applied. No permission expansion or business-row change resulted.
- Applied private settings through a 0600 file outside the repository. Fresh demo bearer
  tokens are stored only in an owner-only temporary file; values were not printed.
- Startup `sh startup.sh`, one worker, Always On, TLS1.2, `/health`, filesystem logs,
  access logs off, FTPS disabled, basic SCM/FTP publishing disabled. No extra service.
- Submitted the reviewed ZIP, SHA256
  `6900d83846b35f12c9f8c23de57e5177e9592623c5e2f309a44668c87857c426`.
  Deployment ID: `REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_10`.

SQL script correction reference:
[Microsoft application SID semantics](https://learn.microsoft.com/en-us/sql/relational-databases/system-catalog-views/sys-server-principals-transact-sql).

**Build/startup outcome is recorded below after verification.** No AI inference,
synthetic SQL business writes, ADLS uploads, migrations, historical record edits,
original local server changes, commits or pushes were performed.


## Final safe startup verification — 29 October 2026, approximately 16:20 UTC

**VERIFIED LIVE: deployment and read-only startup. Overall: PARTIALLY READY.**
Current deployment `REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_08` is status 4,
complete and active. Python runtime 3.13.18 extracted the zstd output and started
Uvicorn successfully. The new Web App was restarted only after build completion;
the original local server was not touched.

Eleven safe HTTP checks passed over HTTPS:

| Check | Observed result |
| --- | --- |
| React root and `/policies` deep link | 200; correct React shell |
| Production JS and CSS assets | Both 200 |
| `/health` | 200, status ok |
| `/ready` | 200, status ready, provider_mode live; SELECT 1 only |
| Unknown API and `/.env` | Both 404 |
| Unauthenticated `/api/policies` | 401 |
| Same-origin CORS preflight | 200, exact HTTPS allowed origin |
| Authenticated `/api/settings` | 200; mssql CONNECTED, live providers, Presidio; integrations CONFIGURED_NOT_VERIFIED |

A first readiness request returned 503 during initial warm-up; a later complete check
passed without permission or firewall widening. The exact cause of that transient failure
was not established. Driver 18 availability is established by the hosted engine's startup
check and successful SQL connection. Presidio/model packages installed in the pinned build;
actual live PII/decision behavior remains part of the separately approved workflow test.

No billable inference/moderation, synthetic business-row write, ADLS upload or directory
creation by the export provider occurred. SQL security-principal/grant changes and ADLS
filesystem provisioning were the explicitly approved infrastructure/access operations.
No migration, historical record/manifest edit, local server change, commit or push occurred.

### Service verdicts

- Azure SQL: VERIFIED LIVE for hosted managed-identity connection and SELECT 1; application
  writes/lifecycle persistence remain IMPLEMENTED BUT NOT LIVE-VERIFIED in this deployment.
- Azure OpenAI: hosted identity/configuration IMPLEMENTED BUT NOT LIVE-VERIFIED. Historical
  live API-key evidence remains separate; no new inference was performed.
- OpenAI Moderation: configured privately; IMPLEMENTED BUT NOT LIVE-VERIFIED on the Web App.
  Historical successful calls do not prove this deployment's current data-plane behavior.
- ADLS: account/filesystem/identity grants VERIFIED LIVE at the management plane; export
  VERIFIED WITH MOCKS only. No live data-plane export has occurred.
- Frontend/backend: VERIFIED LIVE for shell/assets, CORS, auth rejection and authenticated
  read-only settings; interactive policy mutations and full browser acceptance remain pending.

### Demo credentials and remaining approval

Fresh synthetic-tenant demo credentials are privately retained at
`/tmp/governance-approved-deploy-obcsyrz6/demo-credentials.json` (0600; parent 0700).
This file contains bearer secrets: read locally only; do not commit, paste into chat,
log or put tokens in shell arguments. App settings contain hashes, not bearer values.
Private settings/state and build ZIP are temporary; preserve them securely if required
before a reboot. The application is deployed independently of these temporary files.

No missing permission or credential currently blocks the completed startup scope.
The remaining gate is separate live-test approval. Proposed bounded acceptance:
one fresh approved synthetic tenant, at most two new policies/two immutable versions,
one active assignment, up to twelve validation executions, four review cases, two feedback
records, eighty related audit events, one export status record and one new non-overwriting
JSON export (including its new parent directories). Cap Azure OpenAI generation at five
requests and OpenAI Moderation at twenty requests, with safe synthetic inputs only.
Stop on failure, uncertainty or reaching any cap; retain all new records and artifacts.
No historical tenant, failed manifest, prohibited SQL HTTP driver, automatic mutation replay,
resource changes, data cleanup or overwrite is included. Independent SQL/artifact readback
and RBAC/tenant-isolation checks are included; successful outcomes must be observed, not assumed.


## 21. Bounded live acceptance — 30 October 2026

**PARTIALLY READY. Live end-to-end acceptance FAILED; targeted corrections pass locally
and await explicit approval for deployment.** No corrected code has been deployed.

URL: https://REPLACE_WITH_WEB_APP_NAME.azurewebsites.net

Run ID: `d5056ed2-99ec-4fa0-9a43-e1d938c1e69c`. Fresh tenant: `live-demo-81a5d4cc190a433bacc1`.
Foreign administrator tenant: `live-foreign-48de9559fbd4460ea92e`. Both started empty in all
eight tables. Six scoped test identities were appended while preserving the previously
deployed accounts. No business or historical tenant identifiers were used for mutations.

### Actual live results and counts

[Sanitized machine-readable evidence](../LIVE_ACCEPTANCE_RESULTS_2026_10_30.json) records every
final assertion, run-created ID, record count, budget and artifact digest. Private raw
checkpoints/responses, independent SQL snapshot and credentials remain under
`/tmp/governance-live-acceptance-z1mats42` (directory 0700; credential/ledger files 0600). Raw credentials and request
headers are excluded from the committed-format evidence; no Git commit was made.
Temporary raw evidence may be removed by OS cleanup; preserve it securely if required.
The SQL records and this sanitized report are retained independently of those files.

| Check set | Passed | Failed | Notes |
| --- | ---: | ---: | --- |
| Original live HTTP/SQL assertions | 171 | 10 | Raw evidence retained without rewriting |
| Final live assertions | **180** | **6** | 186 total: four checker false positives corrected through GET-only SQL-backed comparisons; three actual deployed bundle checks and two generation-error fail-closed checks added |
| React DOM with actual deployed API GETs | **1** | **0** | Local JSDOM renders existing React source against the live backend; fetch guard forbids non-GET methods. Not a visual browser test. |
| Backend after corrections | **220** | **0** | One migration execution test deselected; 69 prohibited driver cases excluded before collection |
| Existing frontend tests | **7** | **0** | Includes disposable local fixture backend, independent of live results |
| Ruff / formatting | Pass | 0 | 39 Python files formatted correctly |
| ESLint / TypeScript / production build | Pass | 0 | Isolated temporary frontend copy, VITE_API_URL=/ |

Four original dashboard assertions compared a sparse Python Counter with the API's full
four-key decision map. GET-only follow-up, checked against independent SQL, confirmed
that the application correctly reports ALLOW=1, REDACT=0, BLOCK=3, HUMAN_REVIEW=1. No
application analytics change was made. The intended ALLOW/REDACT generation failures
remain failed. Final six failed assertions: ALLOW decision, ALLOW generated/inspected
output, REDACT decision, REDACT generated/inspected output, complete four-decision mix,
and successful ADLS export. These represent two integration defects, not six root causes.

### Verified live workflows

- Add and edit two tenant-owned policies, strict invalid-document rejection, zero/multiple
  record pagination, premature publication rejection and authorized role separation.
- Submit, approve, publish, activate, disable and enable. Disabled/no-active-policy
  requests returned 409 without an execution or provider call.
- Draft simulation returned ALLOW with live Moderation and Presidio satisfied.
- Two immutable versions, ordered numbers 2/1, unchanged first snapshot after draft edit,
  draft edits preserving the old active snapshot and latest active-version references.
  Independent SQL comparisons explicitly checked ID, tenant, policy ID, integer version,
  exact serialized document and creation timestamp.
- Secret input BLOCK and keyword HUMAN_REVIEW, no generation/content release in either.
  Personal email redaction and revalidation passed; final REDACT generation did not.
- Review disposition APPROVED_RESUBMIT_REQUIRED without automatic release; duplicate
  disposition 409; revised input traversed current gates and returned ALLOW.
- Feedback count 2 and mean 3.0; persisted dashboard, history and audit relationships.
- Authentication 401, RBAC 403, foreign administrator read/edit/review/feedback isolation
  404, empty foreign listings and independently empty foreign SQL tables.
- Existing deployed React shell/JS/CSS matched the reviewed deployed ZIP byte for byte.
  React DOM navigation displayed live policy/history/review and FAILED export evidence.
  No connected browser surface was available, so full visual browser acceptance is NOT RUN.
- Real generation failures returned BLOCK with no safe response/output; fail-closed
  behavior was observed live. Provider/moderation outage injection was not performed;
  their mocked negative tests remain VERIFIED WITH MOCKS.

### Independently committed SQL records — all retained

| Table | Exact new-tenant rows |
| --- | ---: |
| policies | 2 |
| policy_versions | 2 |
| active_policy_assignments | 1 |
| audit_events | 24 |
| validation_executions | 5 |
| human_review_cases | 1 |
| feedback_records | 2 |
| evaluation_exports | 1 |

All IDs, policy/version references, assignment, execution/review/feedback relationships,
actor/resource ownership and audit action/resource multisets were checked. All eight
foreign-tenant tables remain empty. Audit metadata excludes raw safe text/responses.
No existing business/history record was modified or deleted, and no migration was run.

### Confirmed defects and exact local corrections

| Issue | Severity / source | Correction and evidence |
| --- | --- | --- |
| Azure generation credential fails before inference | High — `backend/app/providers.py:50` and `:71` | Deployed async Azure identity transport requires aiohttp, absent from the pinned environment. Real SDK initialization reproduced ImportError offline. Use existing synchronous DefaultAzureCredential in asyncio.to_thread; close it within that worker. No dependency install/version change, API-key branch or HTTP payload change. Regression verifies worker-thread execution, token scope/closure and sanitized auth failure without an HTTP POST. |
| ADLS conditional directory argument reaches HTTP transport | High — `backend/app/providers.py:123` | With IfMissing, the pinned SDK supplies If-None-Match=* itself and leaves the redundant etag keyword unconsumed, causing TypeError in requests. Remove only etag; preserve IfMissing and overwrite=False. Regression exercises the real SDK/RequestsTransport with a strict offline session and verifies wildcard non-match conditions for all parent directories and final file flush. Existing directory conflict/ACL-preservation tests remain. |
| Independent export readback lacks operator data permission | Medium — exact filesystem verification scope | Existing Azure CLI identity's HEAD on only the attempted new file returned 403 AuthorizationPermissionMismatch. Runtime role assignment is not evidence of operator read access. No role was added; no successful artifact or absence was inferred from 403. A temporary filesystem-scoped Storage Blob Data Reader grant is proposed below. |

The deployed export status is FAILED. Export ID:
`REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_06`; attempted path:
`governance-reports/2026/10/30/REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_06.json`.
Exactly one export POST was transmitted, never replayed. The route suppresses detailed
provider exceptions, so the live internal ADLS stack was not observed; the blocking SDK
argument defect was independently reproduced with the exact pinned SDK. The current
FAILED record/path must not be reused or rewritten after a fix.

### Provider budget and truthful service status

The driver conservatively reserved four generation slots and twenty moderation slots,
never exceeding the approved five/twenty limits. Two eligible generation attempts
failed at credential initialization; there were zero successful inference responses.
The model_invoked flag marks the gateway's attempted generation and does not establish
a provider HTTP call or a billed response. Five successful moderation inspections are
evidenced by the simulation, inputs and redaction revalidation, using source-confirmed
single-shot HTTP with no automatic retries. This is not cloud billing telemetry.
One export attempt used the entire approved export count; it failed and was retained.

| Integration | Current deployed acceptance status |
| --- | --- |
| Azure SQL | **VERIFIED LIVE** — authorized synthetic writes, committed records/relationships, lifecycle, isolation and pagination |
| OpenAI Moderation | **VERIFIED LIVE** — successful safe-content inspections, including sanitized/revalidated input |
| Presidio | **VERIFIED LIVE** — personal email redaction/revalidation; no runtime model download |
| Azure OpenAI | **FAILED** for hosted managed-identity generation; correction VERIFIED LOCALLY/WITH MOCKS, not deployed |
| ADLS export | **FAILED** — one persisted failed attempt, no successful artifact verified; correction VERIFIED LOCALLY/WITH MOCKS |
| Complete deployed workflow | **FAILED / PARTIALLY READY** — final ALLOW/REDACT generation/output inspection and successful export remain blocked |

### Files modified in this acceptance phase

- `backend/app/providers.py`: the two targeted transport/keyword corrections above.
- `backend/tests/test_live_acceptance_regressions.py`: three focused regressions, including
  real storage SDK serialization with a network-free transport.
- `backend/tests/test_demo_completion.py`: existing identity-route test now verifies the
  installed synchronous credential path instead of mocking an unavailable async transport.
- `backend/tests/test_deployment_preparation.py`: preserve conditional-directory assertion
  with IfMissing; real-wire wildcard protection is additionally tested.
- `docs/LIVE_ACCEPTANCE_RESULTS_2026_10_30.json`, this report, the deployment runbook and
  technical demo runbook: actual evidence, limits, corrections and pending approval.

### Reviewable correction and next approval

Prepared ZIP: `/tmp/governance-live-acceptance-z1mats42/governance-validator-corrected.zip`.
SHA256: `7058b43850bdd4126d0a936e0e322c7e3bad7c4aba696ea85a7d1e10f784c38d`.
Compared with the currently deployed ZIP, **only app/providers.py differs**. No new
resource, tier, setting, model, dependency, migration or frontend change is needed to
deploy the correction. No upload/deployment of this corrected ZIP has occurred.

Your instruction requires approval before live application changes. Proposed consolidated
next approval: deploy this exact ZIP to the existing B1 Web App (retain/redeploy prior ZIP
if startup fails), then make at most two fresh ALLOW/REDACT generation requests and at most
eight moderation requests. Together with the conservatively counted two earlier eligible
generation attempts and five evidenced moderation inspections, this remains within the
original five/twenty limits. Use a new checkpoint ledger and only this run's synthetic
policy/tenant; retain all new executions/audits.

A new export is **additional authorization**, because the one approved attempt is already
consumed: approve exactly one additional UUID export after the correction, never retrying
the failed export ID/path. For independent content readback, approve a temporary Storage
Blob Data Reader assignment for the existing authenticated Azure CLI user, restricted to
`/subscriptions/REPLACE_WITH_AZURE_SUBSCRIPTION_ID/resourceGroups/REPLACE_WITH_AZURE_RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/REPLACE_WITH_ADLS_STORAGE_ACCOUNT/blobServices/default/containers/governance-reports`.
Remove only that newly created temporary assignment after verification; preserve all
pre-existing roles. No further API keys or secrets in chat are needed. No roles, further
billable calls, exports or redeployment have been executed under this proposal.

## 22. Approved correction deployment and bounded completion attempt

The user approved the section-21 proposal. Deployed the exact reviewed ZIP, SHA256
`7058b43850bdd4126d0a936e0e322c7e3bad7c4aba696ea85a7d1e10f784c38d`, to the existing
B1 app. Deployment ID `REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_04` completed at
07:04:43 UTC. No settings, schema, dependency, resource or tier changes were needed.
Only `app/providers.py` differs from the prior package. No further source correction
was justified by this attempt.

### Verification timing defect and correction to the procedure

The verifier treated deployment status 4 plus successful HTTP readiness as replacement
worker readiness. That was insufficient: the old worker continued serving requests while
the new worker extracted its package and loaded the application. Generation responses
finished at 07:05:34 and 07:05:39 UTC; export finished at 07:05:46. Runtime logs show
replacement application startup only at 07:08:16, successful platform warmup at 07:08:17,
and **Site is running with deployment version REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_04** at
07:08:19. These failures do not establish whether the corrected provider works live.
The verification timing mistake consumed the bounded HTTP attempts; none was replayed.

Before any future mutating acceptance call, require the platform runtime log's exact
new deployment version, successful warmup, and application startup completion. Then run
read-only health/readiness/auth checks. Deployment status or a 200 response alone is not
a sufficient gate. This is a procedural correction, with no new feature or endpoint.
A separate compressed-package fingerprint command timed out and was not used as proof.

### Exact results and retained records

- Before mutations: **16 baseline assertions passed**, all prior synthetic rows unchanged
  across eight tables and foreign tenant empty.
- Initial HTTP startup: **11 passed**, but without replacement-worker identity evidence.
- Bounded completion driver: **51 passed, 9 failed, 0 skipped / 60 assertions**.
  Failed assertions: final ALLOW/REDACT decisions (2), inspected released outputs (2),
  successful input-and-output moderation (2; inputs succeeded but outputs absent),
  successful export (1), all four outcomes (1), independent file readback (1).
- Two generation POSTs returned fail-closed BLOCK, withheld output and sanitized provider
  errors. The input checks include successful live moderation and email redaction plus
  revalidation. No successful Azure OpenAI response or output moderation is claimed.
- Exactly one additional export POST returned FAILED. New UUID:
  `REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_03`. Independent reader HEAD on that exact new path
  returned **404 ResourceNotFound**, with no upload/download/overwrite through the reader.
- All pre-existing baseline rows remain unchanged across all eight tables. Only two new
  executions, three matching audits and one new failed export were committed. Foreign
  tenant remains empty. No existing business record was modified or deleted.
- Final counts: policies **2**, versions **2**, assignment **1**, audits **27**, executions
  **7**, review **1**, feedback **2**, exports **2** (both retained FAILED attempts).
  Dashboard: ALLOW **1** (input-only validation), REDACT **0**, BLOCK **5**, HUMAN_REVIEW **1**.
- Current deployed React DOM workflow: **1 passed, 0 failed**, authenticated GET-only
  policies, dashboard, latest execution, resolved review and both retained failed exports.
  The first checker failed because it expected one report.FAILED badge; the corrected
  checker requires both. No application defect or mutation was involved.
- After the platform confirmed the replacement worker: **11 read-only startup assertions
  passed**, including deployed JS/CSS equality, SPA, readiness, SQL/live/Presidio settings,
  unauthenticated denial, private-path denial and exact-origin CORS.
- Local exact-source results remain **220 backend passed, 0 failed**, 1 migration test
  deselected, 69 prohibited driver cases excluded; **7 frontend passed, 0 failed**;
  Ruff, 39-file formatting, ESLint, TypeScript and production build passed. No source
  changed after those checks, so no unnecessary repeat full suite was performed.

Temporary Storage Blob Data Reader was created only at the approved filesystem scope.
Read-only filesystem preflight succeeded. After exact-path inspection, only that new
assignment was removed; independent role inventory verified every pre-existing assignment
remained. The failed export was not retried. No new service, migration, credential value,
.env change, commit or change to the original port-8001 server occurred.

### Current integration status

| Integration | Status |
| --- | --- |
| Azure SQL | VERIFIED LIVE: lifecycle, isolation, immutable history, pagination and current independent committed counts |
| OpenAI Moderation / Presidio | VERIFIED LIVE for input inspection and redaction/revalidation; live generated-output inspection still pending |
| Azure OpenAI | IMPLEMENTED BUT NOT LIVE-VERIFIED on corrected worker; previous attempts FAILED closed |
| ADLS Gen2 | IMPLEMENTED BUT NOT LIVE-VERIFIED for successful export; approved temporary reader access verified and removed |
| Hosted React/FastAPI startup | VERIFIED LIVE on corrected worker, 11/11 read-only checks |
| Full live workflow | BLOCKED by a fresh bounded acceptance approval; not claimed complete |

### Remaining concrete approval, not a new implementation project

No missing API key or new service is identified. ADLS uses the existing managed identity,
not an ADLS API key. No additional deployment is proposed. To finish live verification,
approve **up to two additional generation requests, up to eight additional moderation
requests, exactly one new non-overwriting UUID export**, and the same temporary
filesystem-scoped Storage Blob Data Reader grant/readback/removal. These are additional
attempts beyond the now-consumed completion allowance; conservatively counted eligible
generation attempts would rise from four to at most six. Use a fresh exclusive ledger,
this run's synthetic tenant/policy/version, the now-confirmed corrected worker, preserve
all history, and stop without replay after uncertainty. No such new attempt is authorized
or executed by this report.

### Private demo access and documentation

A private copy of the existing role credentials is now available at
`artifacts/demo-access/credentials.json` (directory 0700, file 0600, exclusive creation,
symlink protection). Existing Git ignore rules cover it; packaging excludes artifacts.
Open it privately in a local editor; never paste its tokens into chat or shell arguments.
Source credentials and server-side accounts were not altered.

This continuation updates this report, `TECHNICAL_DEMO_RUNBOOK.md`,
`AZURE_DEPLOYMENT_RUNBOOK.md`, and adds `LIVE_COMPLETION_RESULTS_2026_10_30.json`.
Historical acceptance evidence is unchanged. Full visual browser acceptance remains
unperformed because no browser surface is connected. The offline fixture rehearsal
continues to demonstrate all decisions without consuming further cloud calls.

## 23. Final approved bounded live verification — 30 October 2026

### Worker gate and request scope

Confirmed deployment `REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_04` active and complete using
read-only deployment inventory, plus actual runtime application startup, successful warmup,
and exact deployment-version serving event. Earlier old-worker termination followed the
new worker switch. Current health/readiness, authenticated SQL/live/Presidio configuration,
React asset fingerprints, SPA, authentication denials, private-path denial and CORS all
passed (11 assertions). Baseline 16/16 proved all earlier records unchanged and the foreign
tenant empty before mutation. No deployment, configuration or application source changed.

Fresh single-use ledger: `/tmp/governance-final-verified-iobu89pf/completion-ledger.jsonl`.
Each request was fsync-checkpointed before transmission; HTTP retries disabled. Exactly
two generation POSTs and one additional export POST were sent. Up to eight moderation
calls were reserved; five successful inspections are evidenced (ALLOW input/output;
REDACT input/revalidation/output). This is application evidence, not billing telemetry.
No failed operation or historical manifest was replayed.

### Azure OpenAI and output inspection — VERIFIED LIVE

| Scenario | Request ID | Actual final result | Output checks |
| --- | --- | --- | --- |
| ALLOW | `30b19444-3c25-4740-903f-c09d27de59f0` | ALLOW, live model invoked, nonempty safe response | Input/output moderation SATISFIED; output policy ALLOW; no provider error |
| REDACT | `d879c256-b4b8-4a03-8b1c-7bd587da7d73` | REDACT, live model invoked, nonempty safe response | Email sanitized, input revalidated, output moderation SATISFIED and policy ALLOW; original email absent from returned JSON |

Both used the same synthetic tenant, approved immutable policy snapshot version 2 and
existing gpt-5-mini deployment. Generated responses were released only after successful
output inspection. No further inference approval is needed merely to establish this
already completed evidence. Additional interactive demo requests consume live usage and
require their own future allowance; do not silently rerun acceptance.

### ADLS — FAILED, no retry

One export POST returned HTTP 201 with persisted status **FAILED**. HTTP 201 is not an
upload success. Export ID `REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_01`; unique attempted path:
`governance-reports/2026/10/30/REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_01.json`.
The approved independent reader's exact-path properties request returned **404
ResourceNotFoundError**; no bytes could be downloaded or compared. No successful artifact
is claimed. Both previous failed exports remain unchanged. The temporary filesystem-only
reader assignment was immediately removed; inventory confirmed every previous role
assignment remained. No storage key was required or requested.

Read-only/offline diagnosis confirmed a separate existing-parent defect at
`backend/app/providers.py:125`: `get_directory_properties()` returns the pinned SDK's
`DirectoryProperties`, which has no `is_directory` attribute. A real SDK serialization
reproduction with mocked existing-directory 409 and HEAD 200 raises
`AttributeError: 'DirectoryProperties' object has no attribute 'is_directory'` before
file upload. The existing three regressions pass but do not cover this real existing-parent
object; current deployment-preparation mocks incorrectly manufacture that attribute.
The live route suppresses provider exceptions, so this is a confirmed blocking code path,
not a directly observed live stack trace. An additional SCM read-only identity diagnostic
reported no identity endpoint/header in that SCM process; this does not describe the app
worker or contradict successful managed-identity generation.

**Severity: High for successful ADLS export. Recommended fix:** replace the unsupported
attribute access with a real SDK-supported directory-type check, preserve conditional
creation/ACLs and overwrite=False, and add real-SDK tests for existing directory and
file-as-parent rejection. Do not blindly ignore conflicts or weaken no-overwrite behavior.
Under the user's explicit no-code-change instruction, no fix, test source change or
redeployment was made. Approve that narrow correction/deployment and exactly one fresh
UUID export plus temporary reader/readback/removal to close the final blocker. No extra
OpenAI requests, new key, service, migration or tier increase is needed for this ADLS fix.

### Exact test results and committed evidence

- Live driver: **58 passed, 2 failed, 0 skipped / 60**. Only failed assertions: successful
  ADLS export and independent ADLS readback. All four outcomes now appear in SQL history.
- Current startup **11 passed, 0 failed**; unchanged-baseline **16 passed, 0 failed**.
- Targeted offline regression module **3 passed, 0 failed, 0 skipped**, one existing
  Starlette/httpx deprecation warning. Fully mocked HTTP; no cloud writes.
- Separate offline existing-parent reproduction: **expected failure reproduced**. This
  diagnostic is not counted as another passing regression and exposes a coverage gap.
- Reused unchanged-source prior full results: backend **220 passed / 0 failed**, one
  migration execution test deselected and 69 prohibited driver cases excluded; frontend
  **7 passed / 0 failed**; read-only deployed React **1 passed**. Lint, format (39 Python
  files), TypeScript and build already passed. No unnecessary full rerun performed.
- Exact tenant totals: **2 policies, 2 versions, 1 assignment, 30 audit events,
  9 executions, 1 resolved review, 2 feedback records, 3 FAILED exports**.
- Dashboard outcomes: **ALLOW=2, REDACT=1, BLOCK=5, HUMAN_REVIEW=1**. One earlier ALLOW is
  input-only; the new ALLOW and REDACT are successful live generation.
- Independent SQL verified all baseline rows unchanged, only the two returned execution
  IDs/three matching audit actions/one returned export ID added, immutable policy/version
  references, sanitized metadata and all foreign-tenant tables empty.

Policy lifecycle, authentication/RBAC, tenant isolation, BLOCK/HUMAN_REVIEW, resolved
review, feedback and audits reuse previous live evidence as requested. This phase modified
only this report, `TECHNICAL_DEMO_RUNBOOK.md`, and new
`FINAL_LIVE_VERIFICATION_RESULTS_2026_10_30.json`. No historical evidence overwritten,
credentials exposed, .env changed, SQL migration, resource creation/deletion, tier increase,
code change, commit or original local server modification occurred.

### Demo readiness and cost control

Live policy/history/dashboard inspection and successful ALLOW/REDACT generation are now
proven. Present stored evidence rather than making unapproved additional requests. The
existing fixture rehearsal supports interactive demonstrations without cloud usage.
Do not present ADLS as working or click Export again until correction and fresh export
approval. No required credential variable is currently missing; managed identity serves
Azure SQL/Azure OpenAI/ADLS and the configured key serves Moderation.

Retain the single B1 worker; do not scale. Avoid repeated inference/export and set a demo
request allowance before another session. After the demonstration, consider stopping the
Web App if it need not serve traffic, but stopping a Web App alone does not stop charges
for its App Service Plan. Plan/storage/SQL usage costs remain; any billable resource
removal or tier change needs separate approval and is not performed here.

## 24. Final authorized ADLS correction and independent live verification

### Minimal implementation and regressions

Confirmed `DirectoryProperties.is_directory` is absent in the installed SDK. Replaced
only that unsupported type check in `backend/app/providers.py:125` with:

```python
properties = directory.get_directory_properties()
if (properties.metadata or {}).get("hdi_isfolder") != "true":
    raise ProviderUnavailable("Report parent is not a directory") from None
```

This uses the real SDK's supported metadata field. Read-only live requests confirmed
all four existing synthetic parent directories return the folder marker `true`.
Missing/false markers, file conflicts and property lookup failures remain fail-closed.
Conditional directory creation (IfMissing) and final upload overwrite=False are unchanged;
no directory ACL, metadata or existing file is overwritten by the check.

`backend/tests/test_live_acceptance_regressions.py` now parameterizes the real SDK and
strict RequestsTransport for new directory success, existing directory 409 plus real
properties success, file-as-parent rejection, and missing-marker rejection. The existing
no-overwrite wildcard assertions remain for directory creation and final flush.
`backend/tests/test_deployment_preparation.py` now models real metadata rather than
inventing an is_directory attribute. Credential tests and workflow tests remain intact.

Targeted tests: **39 passed, 0 failed, 0 skipped**, with one existing Starlette/httpx
warning. Ruff lint and formatting passed across **39 Python files** (backend/scripts).
Whitespace checks passed. Previous full backend/frontend/type/build evidence is reused;
no frontend change or dependency/version/migration change was necessary.

### Deployment and worker readiness

Final deployment ID: **`REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_02`**.
Final ZIP SHA256: `f54ab2adc143a0abcf8014e92d0f9f0a9badeace51d33da1ed484bd4220b0a64`.
Provider member SHA256: `b986ac649012a99f410cf6fa5d2cc675cd4897432f15a686126d2e8a2a87d1da`.
Compared with the previously deployed accepted application, only `app/providers.py`
differs inside the ZIP; no credentials, test data, migrations or artifacts are packaged.
The original corrected package and all historical failure evidence remain intact.

A preliminary response-hook candidate completed deployment before the final smaller
metadata-based implementation was deployed sequentially. No acceptance export was sent
against the preliminary candidate. Builds were not overlapped and settings were unchanged.
The preliminary worker's warmup did overlap final package replacement: at 07:55:38 UTC
it exited with code 2 after reporting a missing manifest/startup.sh. Azure started a fresh
worker after the final package completed. This transient startup failure is retained in
the evidence. Future sequential deployments must wait for worker warmup as well as build
completion before replacing another package.
Final serving-version evidence is the exact platform worker event, not just deployment
status or an old worker's health response. Current startup checks passed **11/11**:
React byte equality, SPA, health/readiness, SQL/live/Presidio settings, auth denial,
private-path denial and CORS. Baseline checks passed **16/16** before export.

### Single export and byte-level independent verification

Export ID: **`REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_07`**. Status: **FAILED**.
Unique path: `governance-reports/2026/10/30/REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_07.json`.
Independent properties/download result: **False**.
Downloaded row count: **unavailable**;
size: **unavailable bytes**;
SHA256: `unavailable`.

The independent reader's exact-path HEAD returned 404 ResourceNotFoundError, so no
file bytes were downloaded or compared. Readback equality remains FAILED, not verified.
Independent SQL checks confirm all nine prior executions and all prior rows across
eight tables remained unchanged; only this failed export and its audit event were added.
No other tenant's record was modified or exported by the test driver.
The three previous FAILED export records remain unchanged. Foreign tenant remains empty.
Final table counts: `{"active_policy_assignments": 1, "audit_events": 31, "evaluation_exports": 4, "feedback_records": 2, "human_review_cases": 1, "policies": 2, "policy_versions": 2, "validation_executions": 9}`.
Dashboard remains ALLOW=2, REDACT=1, BLOCK=5, HUMAN_REVIEW=1, with nine executions.

The exclusive checkpoint/fsync ledger allowed **exactly one export POST** with a new
UUID and no automatic HTTP retry. This phase made **zero generation and zero moderation
requests**. The earlier successful generation/output evidence is reused, not rerun.
No original manifest or failed export path was replayed.

Existing filesystem-properties access did not imply object-read permission; exact
synthetic parent HEAD returned 403. Only then was the approved filesystem-scoped reader
assignment created. The temporary reader assignment was removed after readback;
independent inventory confirms removal **True** and preservation of
all prior assignments **True**.
No storage API key was needed. Managed identity remains the application authentication.

### Final service status and remaining limitations

| Component | Final demonstration status |
| --- | --- |
| Azure SQL | VERIFIED LIVE — tenant isolation, lifecycle, immutable history and independent final counts |
| Azure OpenAI | VERIFIED LIVE — prior successful ALLOW/REDACT generation retained |
| OpenAI Moderation / Presidio | VERIFIED LIVE — prior input/revalidation/output inspection retained |
| ADLS Gen2 | FAILED / see latest exact results |
| React / FastAPI hosting | VERIFIED LIVE — exact final worker and current startup checks |
| Human review, feedback, audit/dashboard | VERIFIED LIVE — prior evidence plus preserved current records |

Final verdict: **PARTIALLY READY** for the agreed controlled technical demo.
Remaining blockers are listed in the machine-readable evidence; do not replay the export.
Full visual-browser acceptance was not performed because no browser surface was connected;
previous rendered-React/read-only HTTP checks and deployed asset checks remain evidence.
Demo bearer auth is existing scoped authentication, not enterprise SSO. Upload-before-DB-
commit uncertainty remains a documented recovery limitation; no outbox/new architecture
was added. These are existing scope limitations, not claims of production certification.

Changes in this phase: providers.py, the two focused test modules, this completion report,
TECHNICAL_DEMO_RUNBOOK.md, and new FINAL_ADLS_VERIFICATION_RESULTS_2026_10_30.json.
No extra service, new resource, tier increase, migration, .env change, business-data
modification/deletion, original local-server change, commit or push occurred.

### Demonstration and cost boundary

Open the hosted URL, sign in using the private existing role token, and show policy/version
history, the prior ALLOW/REDACT input/output evidence, prior BLOCK/HUMAN_REVIEW, resolved
review/feedback, overview/audit, and the new FAILED export in Audit & reports.
Explain independent readback returned 404 and ADLS success is still pending. Keep all
FAILED attempts visible. No additional Export/Generate clicks are authorized by the
completed bounded test; agree an interactive request allowance before another live demo,
or use the existing offline fixture rehearsal. No new credentials or code work is needed
apart from the exact remaining blocker.

Keep the existing single B1 worker; avoid repeated calls. Review ongoing hosting/storage/SQL
costs after the demonstration. Stopping a Web App alone does not stop App Service Plan
charges. No resource deletion, tier change or cost-management change was executed.

## 25. Read-only diagnosis and next concrete correction — no export replay

The authorized export allowance is consumed. Current live result remains **34 passed,
2 failed / 36 assertions**, with export FAILED and exact-path independent readback 404.
All four failed export records remain retained. Temporary reader cleanup is complete.
No more generation or moderation calls occurred. Live generation/output evidence from
the prior successful run remains valid.

Read-only SSH into the running app confirmed the exact deployed provider SHA256
`b986ac649012a99f410cf6fa5d2cc675cd4897432f15a686126d2e8a2a87d1da`, managed identity
present, and successful HEAD on all four existing directories with `hdi_isfolder=true`.
The same worker's HEAD for the new failed UUID returned BlobNotFound 404. SSH sessions
omit App Service settings; the diagnostic read the running app process environment only
in memory, printing no environment values or credentials. No directory creation, upload,
SQL write or provider call was performed by that diagnostic. The export route suppresses
its underlying exception, so no exact live failure stack is claimed.

An additional confirmed SDK upload-sequence defect was reproduced offline: in the pinned
SDK, upload_data(overwrite=False) sends append before creating the new file. A stateful
real-SDK RequestsTransport fixture that rejects append to a nonexistent path reproduced
PathNotFound in both new/existing-directory cases. The former stateless response fixture
accepted append to any path and missed this gap. Red phase: 3 failed / 4 passed in the
focused module; these expected regression failures were corrected, not removed.

The smallest additional local correction is now:

```python
file.upload_data(content.encode(), overwrite=True, match_condition=MatchConditions.IfMissing)
```

The SDK's overwrite=True branch performs initial file creation. **IfMissing is mandatory:**
real serialized Create File carries If-None-Match: *, rejecting any existing file before
append. The SDK then pins flush to the freshly created file's ETag using If-Match. This
preserves no-overwrite semantics; it is not an unguarded overwrite. Directory IfMissing,
metadata checks and fail-closed behavior remain. No ACLs or existing files are changed.
[Azure's upload tests](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/storage/azure-storage-file-datalake/tests/test_file.py)
and the installed SDK source were reviewed alongside the network-free reproduction.

Final local tests: **40 passed, 0 failed, 0 skipped** across provider regressions,
deployment preparation and combined workflows; one existing deprecation warning.
Coverage now includes successful new/existing parent directories, file-as-parent and
missing-marker rejection, and existing output-file conflict with no append/flush.
Real-wire assertions require If-None-Match: * at file creation and If-Match at flush.
Ruff and formatting passed across **39 Python files**, and whitespace checks passed.
`test_demo_completion.py` mock expectations now require the conditional-create arguments;
no security tests or lifecycle gates were weakened.

Prepared, **not deployed**, ZIP:
`/tmp/governance-adls-final-bqcipv0q/governance-adls-create-only.zip`.
SHA256: `b1a3dc0f3d53e98c4ce8c133cbd81d29146299530c42622a11cd384b492d46e1`.
Only app/providers.py differs from the currently deployed final metadata-check package.
No dependency, schema, frontend or setting changes are included.

The user has been asked to approve this exact package deployment and **one additional
fresh synthetic export**, with filesystem reader access only if necessary, exact-path
readback and removal afterward. No new attempt, historical retry or further deployment
has been performed under that pending question. No further AI or moderation test is
needed. This approval boundary follows the explicit instruction not to repeat a failed
export without fresh approval. All safe local correction and reviewable packaging are
complete; independent successful live ADLS content verification is the remaining gate.

## 26. Final stabilization, independent ADLS acceptance and browser handover

The user explicitly approved deployment of the exact create-only package, one fresh
synthetic JSON export, and conditional temporary reader access. All authorized work
completed sequentially; no export was retried. The prepared package matched the source.
The broad baseline found one stale SDK-mock expectation, corrected without weakening
conditional no-overwrite checks or changing application code.

Deployment `REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_11` serves provider SHA256
`0da32cb68c09068a107025de001f7f766bde65ee1c09bb51f821ee24df95ecc1`.
ZIP SHA256: `b1a3dc0f3d53e98c4ce8c133cbd81d29146299530c42622a11cd384b492d46e1`.
The deployment client timed out; Azure server status and the exact worker event were
verified without resubmitting. Startup smoke passed 21/21; configuration/tenant checks
passed 6/6; no critical startup error was observed.

Fresh export `REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_09` SUCCEEDED at
19:48:36 IST, 30 October 2026. Object:
`REPLACE_WITH_ADLS_STORAGE_ACCOUNT/governance-reports/governance-reports/2026/10/30/REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_09.json`.
The first `governance-reports` is the filesystem; the second starts the object path.
Independent download verified 9 records, 1,745 bytes, allowlisted fields, exact bytes and
SHA256 `d561b2df77cee461bdf3a78d9e039ca1d4179dd267202f6d03941075b48e3cfb`.
Temporary filesystem reader removal and pre-existing assignment preservation were verified.
All four FAILED exports remain unchanged. Only the successful export and its audit event
were added; existing approved and foreign synthetic tenant rows were compared unchanged.
The foreign tenant already had records at this turn's baseline; no empty-tenant claim
is made for this phase. All nine prior executions remain unchanged.

Real Chrome/Playwright acceptance: 72 hosted checks and 50 disposable fixture checks
passed. Hosted nine-page desktop/tablet/mobile screenshots and live recorded metadata
were inspected. Interactive mutations used disposable local fixtures, never hosted
policies or additional paid provider calls. Backend 224 passed / 0 failed / 1 deselected;
40 focused passes are a subset. Frontend opt-in integration 7 passed / 0 skipped.
Python lint/39-file formatting, ESLint, TypeScript and production build passed.
The historical SQL HTTP driver module remained excluded. Existing deprecation/chunk
warnings are non-blocking; production identity/recovery remain separate backlog work.

See [full report, scope, evidence and final matrix](FINAL_ACCEPTANCE_REPORT.md),
[browser evidence](../evidence/final-acceptance-2026-10-30/browser-hosted.json),
[ADLS evidence](../evidence/final-acceptance-2026-10-30/export-verification.json),
[regression summary](../evidence/final-acceptance-2026-10-30/regression-summary.json),
[demo section 17](../runbooks/TECHNICAL_DEMO_RUNBOOK.md#17-final-accepted-panel-demonstration--30-october-2026),
and [production backlog](PRODUCTION_BACKLOG.md).

**Final verdict: COMPLETE — CONTROLLED TECHNICAL DEMO READY.** The export allowance is
consumed. Use recorded live evidence or the safe local interactive rehearsal; obtain
a separate allowance before any additional hosted Generate, moderation simulation or
Export request. No application rebuild, unrelated user change overwrite, schema reset,
new cloud service, Git commit or push occurred.
