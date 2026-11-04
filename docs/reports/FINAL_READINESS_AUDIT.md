# Final End-to-End Readiness Audit

Audit date: **29 October 2026 (Asia/Kolkata)**. Scope: existing local application, source, supplied verification results and recorded evidence. Verdict: **PARTIALLY READY** for the complete Azure-integrated demonstration; the core local application is implemented and tested.

## 1. Executive summary

The project does not need rebuilding or new Azure services. Policy lifecycle, input/output enforcement, audit persistence, review dispositions, feedback and reporting adapters are present. The frontend calls real backend endpoints. The known Azure SQL pagination defect is corrected in source and covered by local and MSSQL compilation regressions.

The repository records a successful live Azure OpenAI + OpenAI Moderation request with safe release and SQLite audit persistence on 28 October. The supplied manual results establish Azure SQL connectivity, positive permissions and revision/schema readiness. These are distinct from a successful Azure SQL-backed HTTP/browser acceptance run. The original Phase 5 run remains FAILED_OR_INCOMPLETE; no later successful complete run was supplied.

Read-only configuration inspection selects **SQLite**, **live** providers and **Presidio**. Azure generation/deployment and moderation settings are present; both ADLS destination settings are absent. This audit does not attest the configuration loaded by a separately running process. The previously reported isolated SQL server on port 8001 was not contacted, stopped, restarted or reconfigured.

The minimum remaining work is configuration/access for the existing ADLS destination, separately authorized completion of corrected SQL HTTP acceptance with a fresh run, and browser rehearsal against the selected backend. No additional application code change is currently established as necessary for those steps.

### Evidence and classification

| Capability | Classification | Evidence and limit |
| --- | --- | --- |
| Core policies, governance, tenant/RBAC checks, audits, reviews, feedback | COMPLETED AND VERIFIED | Existing 254-pass backend result; this audit's safe subset passed 184 tests. Local disposable databases and mocks are not cloud acceptance. |
| React API boundary, type checking and production build | COMPLETED AND VERIFIED | Five frontend tests, ESLint and build passed in an isolated copy. |
| Azure OpenAI and OpenAI Moderation | COMPLETED AND VERIFIED, historical live evidence | `docs/live-connectivity.json` records nonempty generation, input/output moderation and an audited safe response. No new live request was made. |
| Azure SQL connection, identity, inventory and revision | COMPLETED AND VERIFIED, user-supplied manual evidence | CONNECTED; 21 positive permission checks; inventory COMPLETED; revision/head 003; no readiness notes. Not unnecessarily repeated. |
| Corrected SQL-backed HTTP workflows | IMPLEMENTED BUT NOT LIVE-VERIFIED | Pagination corrected and 14 regression tests previously passed; original Phase 5 acceptance remains failed/incomplete. |
| Successful ADLS export | BLOCKED | Adapter implemented and mock-tested; destination configuration absent and no successful live upload evidence. |
| Browser acceptance against the intended backend | INCOMPLETE | Source and DOM tests reviewed; no browser visual/full workflow run in this audit. |
| Automatic approval/resume of held content | INCOMPLETE, deliberately outside current demo scope | Only metadata dispositions and revised resubmission are implemented. |
| Docker, Azure application hosting, Key Vault, extra Azure services | NOT REQUIRED FOR LOCAL DEMO | No installation, deployment or additional service is needed. |

## 2. Current architecture

| Component | Actual entry point/functions | Responsibility |
| --- | --- | --- |
| FastAPI | `backend/app/main.py:app` | Local ASGI API; routers registered in the same module. |
| React | `frontend/index.html` → `frontend/src/main.tsx:createRoot`, `App` | BrowserRouter, token entry, navigation and all application screens. There is no separate production App.tsx implementation. |
| API transport | `frontend/src/api.ts:API_URL`, `getToken`, `request` | Fetch with bearer header; server errors surfaced to UI. |
| Settings | `backend/app/config.py:Settings`, `settings` | Repository-relative private environment file; process variables override file/defaults. |
| Persistence | `backend/app/database.py:create_database_engine`, `SessionLocal`, `get_database` | SQLite or explicit Entra-enabled MSSQL selection; request transaction ownership. |
| Azure SQL | `backend/app/azure_sql.py:create_azure_sql_engine`, `build_azure_sql_url`, `install_token_provider`, `verify_token_identity` | CLI-user authentication, identity pinning, ODBC token injection, TLS and pools. |
| Policy contracts | `backend/app/schemas.py:PolicyDocument`, `Rules`, request/response models | Versioned JSON, rejected extra fields, bounded inputs and supported actions. |
| Enforcement | `backend/app/engine.py:inspect_text`, `detect_sensitive_information`, `redact_personal_information`, `calculate_compliance_score`, `get_pii_analyzer` | Secret/PII/keyword detection, moderation, redaction/revalidation and explanatory scores. |
| Providers | `backend/app/providers.py:generate_ai_response`, `moderate_user_prompt`, `upload_report` | Azure OpenAI, OpenAI Moderation and existing ADLS filesystem. |
| Identity | `backend/app/security.py:authenticate`, `require_role`, `Identity` | Server-owned tenant/role mapping for local demo bearer credentials. This is separate from Entra SQL identity. |
| Records | `backend/app/models.py` | Eight application tables: policies, versions, assignments, executions, audits, reviews, feedback and exports. |
| Schema history | `backend/migrations/versions/001_foundation.py`, `002_policy_concurrency.py`, `003_review_concurrency.py` | Portable schema and integer optimistic-concurrency counters; `migrations/env.py` shares the configured engine. |

Data flow: React → authenticated FastAPI → active immutable policy → input inspection → approved generation → output inspection → execution/audit commit → safe response. Reports export an explicit metadata allowlist to ADLS. There is no Azure application hosting or Key Vault dependency.

## 3. Backend readiness

### API/workflow map

All paths below exist in `backend/app/main.py`; dynamically registered routes are included.

| Workflow | Routes | Functions |
| --- | --- | --- |
| Health/diagnostics | GET `/health`, `/ready`, `/api/settings` | `health`, `ready`, `diagnostics` |
| Policy CRUD | GET/POST `/api/policies`; GET/PUT/DELETE `/api/policies/{id}` | `get_all_policies`, `create_new_policy`, `view_policy`, `update_existing_policy`, `delete_draft_policy` |
| Simulation/history | POST `/api/policies/{id}/simulate`; GET `/api/policies/{id}/versions` | `simulate_policy`, `policy_versions` |
| Lifecycle | POST `/api/policies/{id}/{submit,approve,publish,activate,enable,disable,archive}` | `register_policy_operation`, `transition_policy` |
| Governance | POST `/api/governance/{validate-input,validate-output,generate}` | `register_governance_operation`, `governance`, `load_active_policy` |
| History and analytics | GET `/api/audit/executions`, `/api/audit/events`, `/api/audit/summary`, `/api/analytics/{overview,violations,compliance}` | `executions`, `audit_events`, `analytics`, `list_records` |
| Review | GET `/api/reviews`, `/api/reviews/{id}`; POST `/api/reviews/{id}/{approve,reject}` | `reviews`, `get_review`, `review_detail`, `register_review_operation`, `resolve_review` |
| Feedback | POST `/api/feedback`; GET `/api/feedback/summary` | `collect_feedback`, `feedback_summary` |
| Reports | POST `/api/reports/export`; GET `/api/reports/exports` | `export_sanitized_report`, `report_exports` |

Request database dependencies use function scope, so commit/rollback completes before HTTP success is sent. Governance additionally commits its execution/audit before releasing content. Feedback averages explicitly cast integer ratings to Float. Policies/reviews flush before returning their updated counters. SQL failures do not fall back to SQLite.

The pagination fix in `main.py:list_records` orders policies by `id DESC` only; models with timestamps use `created DESC, id ASC`. `backend/tests/test_pagination.py` covers both MSSQL pagination compilation modes, empty data, multiple pages, tied timestamps, response records and tenant isolation.

Policy editing resets the draft approval state, retaining historical versions. Only never-published drafts may be deleted; an active policy cannot be archived until another policy is activated. These are enforced backend rules, not missing operations.

## 4. Frontend readiness

`frontend/src/api.ts` uses `VITE_API_URL`, defaulting to `http://localhost:8000`. This setting is resolved at development startup/build time. FastAPI CORS in `main.py` accepts the configured `cors_origin`; inspected configuration matches the normal frontend origin `http://localhost:5173`. Use the matching browser origin; localhost and 127.0.0.1 are different origins.

| Screen/function in `frontend/src/main.tsx` | Wiring and assessment |
| --- | --- |
| `App` | Validates entered credentials with `/api/settings`; sessionStorage token; sign-out removes it. No browser-selected trusted role. |
| `Policies` | List/pagination; create/view/edit navigation; delete/archive, enable/disable and lifecycle requests; version history. Search/status filters intentionally operate on the current page. |
| `Editor` | Loads drafts, structured rules and JSON preview; POST/PUT invoke server schema validation. |
| `Simulator` | Calls the selected draft's simulation endpoint; does not call generation. Enabled moderation can still call the live moderation service. |
| `Playground` | Calls governed generation, displays decisions and safe response/withholding; ratings POST feedback using the returned execution ID. |
| `Overview` | Actual backend metrics, distributions and charts; analytics navigation uses the same aggregate endpoint. |
| `Records` | Paginated execution/audit/review lists; metadata inspection; review decisions; JSON/CSV export attempts and their statuses. |
| `EnvironmentBanner`, `Configuration` | Display fixture/live mode and sanitized diagnostics; configuration presence is not connectivity proof. |

No displayed primary action was found without a corresponding endpoint. Controls are not hidden by role, so a restricted user can see an action that the server rejects with 403. Editing a previously published policy may show Delete after it returns to DRAFT, but the backend correctly rejects deletion of published history. Archived editing is likewise rejected. These are minor UI/state limitations; use supported transitions during the demo.

The feedback summary endpoint is fetched in non-report Records screens but its result is not rendered there. Rating submission is connected; a visible aggregate feedback panel is not implemented and is not necessary to demonstrate feedback persistence. No new panel is recommended for the minimum demo.

Browser visual acceptance and clicks against an actual selected backend remain pending; five mocked-fetch DOM tests do not establish complete browser/backend operation.

## 5. Azure SQL readiness

**Configured default: SQLite. Explicit Azure SQL selection is already supported.** `Settings.database_url` selects `mssql+pyodbc` through the existing factory and pinned Entra adapter. No code change or migration is presently established as necessary to enable the reviewed integration.

The adapter validates tenant/user UUIDs and token tid/oid/lifetime, requests the SQL scope, removes conflicting trusted/password authentication parameters, enforces Driver 18/encryption/certificate validation, and refreshes tokens at new physical connections. SQLAlchemy pre-ping/recycling and bounded pool/login settings are present; native errors are sanitized. CLI process timeout is 15 seconds, connection timeout 10 seconds, pool timeout 10 seconds and pool recycling 2700 seconds. No interactive login is initiated by engine construction.

The eight models use portable types, application-generated string UUIDs, four foreign keys, version uniqueness and integer optimistic counters. Source migration chain is 001 → 002 → 003. Supplied live inventory reports revision 003 matching expected head, with no readiness notes. Static MSSQL schema and pagination compilation support that evidence; they are not live execution tests.

Manual evidence accepted without repetition: Driver 18 installed, CLI installed/authenticated, tenant/user matched, connection CONNECTED, 21 runtime permission checks GRANTED, inventory COMPLETED, actual/expected revision 003 and matching history. A separate raw result file for these latest manual outputs was not located among the reviewed public evidence files; they remain explicitly user-verified. Older READINESS/phase reports saying these prerequisites are missing are historical, superseded evidence.

Positive permissions do not prove least privilege. Earlier plans describe dbo use; current privilege exclusions/group inheritance were not rechecked. The SQL integration is **ready for a separately controlled acceptance test**, not already accepted as a complete HTTP/browser demonstration. Preserve the failed original Phase 5 manifest and committed records. Never retry that manifest. Any future run needs a fresh approved identity/run scope and must load the corrected code; an already-running process is not proved updated by editing source files.

## 6. Azure OpenAI readiness

Implementation: `providers.py:generate_ai_response`. HTTPS Azure endpoint validation, configured deployment, API-key authentication or asynchronous DefaultAzureCredential with Cognitive Services scope. The v1 chat-completions path and a versioned deployment route are supported. Requests send the deployment as model, user content and a completion-token bound; HTTP calls use `provider_timeout` (default 20 seconds). Response status/structure/nonempty content/length are validated; failures become ProviderUnavailable and the gateway withholds content.

`main.py:governance` invokes generation only after ALLOW or successfully revalidated REDACT input, then inspects the result using the same immutable policy. Secret/PII checks occur locally; enabled moderation is external. Safe release also requires persisted audit metadata.

Inspected configuration has endpoint, deployment and generation-key settings present; values are intentionally omitted. `docs/live-connectivity.json` records a nonempty live response and the complete moderated, audited gateway success. That is actual historical evidence, not a fresh availability guarantee. Azure OpenAI's credential-chain fallback is implemented but that evidence does not separately prove its live use; the documented successful path used an API key.

## 7. OpenAI Moderation readiness

Implementation: `providers.py:moderate_user_prompt`; endpoint `/v1/moderations` on the OpenAI API, model `omni-moderation-latest`, server-side bearer key. The adapter validates the flagged Boolean/category mapping, extracts true category names and rejects malformed/failed responses. HTTP timeouts and status errors become ProviderUnavailable.

`engine.py:inspect_text` evaluates enabled controls on input and output. Moderation failure produces UNKNOWN and BLOCK. Earlier BLOCK/HUMAN_REVIEW findings skip sending held text to moderation; the control is not reported as successful. REDACT is revalidated before use. A deliberately disabled policy control is NOT_APPLICABLE, not an outage.

The moderation key setting is present. Existing JSON evidence records a successful live moderation request and satisfied input/output moderation in the live gateway. No new API call was made. Fixture marker buttons are deterministic only in fixture mode; they must not be presented as live service fault injection.

## 8. ADLS Gen2 readiness

Implementation: `providers.py:upload_report`; approved HTTPS DFS endpoint, existing filesystem, DefaultAzureCredential, DataLakeServiceClient with connection/read timeouts and `upload_data(..., overwrite=False)`. No filesystem/account provisioning occurs.

`main.py:export_sanitized_report` constructs JSON/CSV using only request ID, timestamp, decision, policy ID and version. It creates an export attempt, records SUCCEEDED/FAILED and appends an audit event. SDK failures are reflected as FAILED; ordinary validation remains available. The UI exposes both formats and lists attempts. A 201 response alone does not mean an upload succeeded: inspect its status.

**BLOCKED for successful live export:** account URL and filesystem settings are absent in the inspected configuration. No successful live ADLS upload artifact was located. Mock SDK contracts prove request construction, not access to an actual filesystem. Existing approved destination details and a suitable identity/data-plane authorization must be available privately before a separately approved upload test. No new service or infrastructure is needed or recommended.

An upload happens before the request database transaction commits. A later commit failure can leave an ADLS artifact without a committed success record. There is no cross-service transaction or durable export recovery. Do not induce outages or automatically retry uncertain export requests during a demo.

## 9. Security findings and issue register

Severity below is relative to the stated demonstration scope. Production-only limits do not imply that extra implementation is required for a controlled local presentation.

| ID / severity | Relevant paths | Finding / explanation | Recommended resolution |
| --- | --- | --- | --- |
| R1 — High, full-cloud demo blocker | `backend/app/config.py`; `backend/app/providers.py:upload_report`; `backend/app/main.py:export_sanitized_report` | ADLS destination absent; no live export success. | Privately configure only the existing approved destination and identity, then authorize one bounded sanitized export and inspect its result/artifact. No changes made in this audit. |
| R2 — High, SQL acceptance gap | `backend/app/main.py:list_records`; `backend/tests/test_pagination.py`; `docs/guides/FASTAPI_AZURE_SQL_INTEGRATION.md` | Original SQL HTTP run failed; source fix and compilation tests are not a new live PASS. | Preserve failed evidence; separately approve a fresh controlled run loading corrected source. Reuse existing connection/schema evidence, not the original manifest. |
| R3 — Medium, presentation readiness | `frontend/src/api.ts:API_URL`; `frontend/src/main.tsx:App`; `backend/app/main.py` CORS setup | Browser execution unverified; default UI targets port 8000, not the isolated SQL server on 8001. | Rehearse against the deliberately selected backend with matching frontend API URL/origin. A healthy separate SQL server does not automatically change the UI target. |
| R4 — Medium, scope disclosure | `backend/app/main.py:resolve_review`; `frontend/src/main.tsx:Records` | Review approval is metadata-only and requires resubmission; no stored-content preview or automatic resume. | Demonstrate hold → disposition → revised resubmission; do not promise automatic release. No feature addition needed for this scope. |
| R5 — Medium local / High for production | `backend/app/security.py`; `frontend/src/api.ts`; `frontend/src/main.tsx:App`; `docs/runbooks/AZURE_SQL_RUNTIME_ACCESS_PLAN.md` | Local bearer tokens lack enterprise SSO/expiry/revocation; same-origin JS can read sessionStorage. Positive SQL grants do not certify least privilege; earlier plans use dbo. | Keep the demo controlled/local, protect private files and disclose identity boundaries. Separate runtime privileges and enterprise authentication are future production work, not mandatory new demo features. |
| R6 — Medium, operational limit | `backend/app/main.py:export_sanitized_report`; `backend/app/providers.py:upload_report` | ADLS upload precedes DB commit; uncertain failures can leave an artifact. | Verify successful artifact and database status together; retain uncertain outcomes for read-only inspection, without blind retries. Durable recovery is future scope. |
| R7 — Medium for production | `backend/app/models.py`; `backend/app/main.py:get_policy`, `get_review`, `collect_feedback` | Isolation is enforced by application predicates; FKs are not compound tenant constraints. ORM append-only hooks do not prevent administrator mutation. | Retain current tested tenant/RBAC checks for local demo. Database-enforced tenant boundaries and tamper-evident retention are production hardening, not current blockers. |
| R8 — Low, chart interpretation | `backend/app/main.py:analytics`; `frontend/src/main.tsx:Overview` | Execution aggregate query has no ORDER BY before taking the last 100 trend entries. Counts are real, but chronological latest-100 ordering is not guaranteed. | Do not claim chronological latest-100 accuracy. If required later, add deterministic timestamp/ID ordering with a focused test; no change authorized here. |
| R9 — Low, UI limitations | `frontend/src/main.tsx:Policies`, `Editor`, `Records` | Role/state controls can lead to legitimate 403/409 responses; feedback aggregate data is fetched but not displayed. | Use appropriate roles/transitions and demonstrate rating persistence. Role hiding or an aggregate panel is optional future polish. |
| R10 — Low, historical documentation | `README.md`; `docs/reports/READINESS.md`; `docs/reports/AZURE_SQL_PHASE_REPORT.md`; `docs/ARCHITECTURE.md` | Older SQL blockers/test counts conflict with later manual verification and source state. | Use this consolidated report for presentation claims. Update historical summaries only in a later authorized documentation task. |
| R11 — Low, tool warnings | `frontend/vite.config.ts`; `frontend/src/main.tsx`; `backend/requirements.lock.txt` | Build has a 662.53 kB minified JS chunk; backend emits one upstream Starlette/httpx deprecation warning. | Accept for this local demo; neither check failed. Dependency changes/code splitting are unnecessary for present acceptance. |

Verified controls include tenant-bound authentication, backend RBAC, bound SQL parameters, sanitized DB/validation errors, request/text size bounds, immutable policy snapshots, optimistic policy/review counters, no generation for blocked input, withheld rejected output and pre-release audit commit. Logs report route/status/duration instead of bearer headers or content. Private environment/token/cache files are ignored by Git. These are scoped engineering controls, not a penetration-test or regulatory-certification claim.

## 10. Automated checks and audit integrity

Existing full backend result: **254 passed**, accepted from the supplied manual verification and preceding pagination verification. Git working tree was clean at audit start; this was confirmed by read-only status. A final SHA-256 comparison confirmed no pre-existing tracked file changed; workspace file-list comparison found only this report added and no files removed. Git status showed only this new report.

All fresh test/build activity ran in `/tmp/governance-readiness-audit-anhtr954/project`, copied without private environment files, credentials, existing databases or Azure CLI caches. Installed frontend dependencies were copied, not installed. Python bytecode/pytest caching were disabled and test paths/caches redirected into the temporary area. Backend child configuration used disposable SQLite, fixture providers and no real cloud credentials. TestClient checks ran outside the sandbox's known local restriction; this is not authorization for cloud access.

| Check | This audit's result | Scope / caveat |
| --- | --- | --- |
| Safe backend subset | **184 passed, 0 failed; 1 deselected** | All ordinary local/mocked tests, including pagination. The migration-execution test was deselected. |
| HTTP acceptance-driver test module | **NOT RUN: 69 tests excluded before collection** | Avoids importing/executing the expressly prohibited HTTP driver and creating its test manifests. Prior results remain historical evidence. |
| Fresh SQLite Alembic migration test | **NOT RUN: 1 test deselected** | Honors the restriction against running migrations, including in a temporary database. Static migration/MSSQL checks were allowed. |
| Ruff lint | **PASS** | `backend` and `scripts`, no-cache mode in temporary copy. |
| Ruff formatting | **PASS** | All 32 Python files already formatted; check-only. |
| Frontend ESLint | **PASS** | Existing `npm run lint`. |
| Frontend Vitest | **5 passed, 0 failed** | Existing mocked-fetch React tests. |
| Strict TypeScript + Vite build | **PASS** | Existing `npm run build`; generated outputs stayed in temporary copy. |
| Fresh npm vulnerability audit | **NOT RUN** | Would query an external service; no current vulnerability conclusion is made from old npm audit results. |
| Live SQL/AI/moderation/ADLS probes, browser E2E, smoke demo | **NOT RUN** | Unnecessary repeat checks, billable calls/writes or persistent-history creation are outside audit scope. |
| Docker, dependency installation, remote CI | **NOT RUN** | Not required for the local demo; no dependencies or infrastructure changed. |

Fresh commands, executed against the isolated copy:

```text
python -B -m pytest -q -p no:cacheprovider --basetemp <temporary-test-directory> \
  --ignore=tests/test_sql_http_plan.py -k 'not test_migrations_on_fresh_sqlite'
ruff check --no-cache backend scripts
ruff format --check --no-cache backend scripts
npm run lint
npm test
npm run build
```

The omitted 69 plus deselected 1 explain why this audit ran 184 rather than claiming a new 254-test full-suite result. Mock-only Phase 4 safety contracts do not run the completed live ORM write test. No command invoked the prohibited HTTP driver. No migrations, cloud requests or existing-database writes were performed.

## 11. Actual blockers

1. **Full four-service demo:** ADLS destination/access and an actual successful sanitized upload are missing (R1).
2. **Azure SQL-backed end-to-end acceptance:** no successful fresh HTTP workflow after the pagination correction has been supplied (R2). Connection, schema, permissions and head revision are already established and do not need routine repetition.
3. **Presentation acceptance:** browser-to-selected-backend rehearsal is unverified (R3). This audit cannot guarantee existing processes are running current code/configuration.

No unresolved failing local test or critical code defect was established in the checks performed. SQLite + live AI/moderation has historical end-to-end evidence, so these gaps do not mean the entire application is nonfunctional. Application hosting, Docker, Key Vault, new Azure services, automatic review replay and a production identity redesign are not blockers for the agreed local scope.

## 12. Remaining tasks in priority order

1. Decide whether the presentation claims all four services working together or the proven SQLite/live-AI path with SQL/ADLS clearly separated. Keep SQLite as the default until a specific later switch is approved.
2. Obtain private details/access for the existing ADLS filesystem and authorize one sanitized upload validation. Configuration presence and SQL privileges do not establish ADLS access.
3. Separately authorize corrected Azure SQL HTTP acceptance in a fresh isolated scope. Preserve the failed manifest/records and existing server; do not retry, silently clean up or rerun migrations. Load corrected code only through a separately agreed process action. The reviewed fixture SQL driver deliberately disables AI/ADLS, so its PASS alone cannot establish an all-services-live chain.
4. Rehearse the browser with a deliberate API target/origin and appropriate demo roles. Once authorized, demonstrate one governed request persisted to the selected DB and a successful ADLS export if claiming the complete chain. Avoid duplicating lower-layer probes already verified.
5. Freeze the successful evidence and presentation narrative. Disclose metadata-only human review and heuristic scores. Only address a reproducible blocker found in these steps; do not rebuild or add features.

These are future actions, not actions executed or approvals requested by this audit.

## 13. Suggested technical demo workflow

The sequence below is a presentation plan; mutations/provider calls require later authorization and were not performed here.

1. Open Settings: identify selected DB, provider mode, PII mode and local bearer identity boundary. Explain that configured-provider diagnostics are not live probes.
2. Show policy JSON and existing immutable versions. On an approved demo policy, demonstrate draft creation/editing → submit → approve → publish → activate. Use supported draft deletion/archival rules.
3. Simulate safe, synthetic-secret and synthetic-PII input. Explain REDACT revalidation and that live simulation may call moderation.
4. Run one approved harmless playground request. Show input moderation, generation, output moderation, safe release and policy version. Distinguish ALLOW/REDACT/BLOCK from the explanatory score.
5. Show a secret being blocked before generation. Do not describe fixture-only markers as live moderation/outage behavior.
6. For an approved HUMAN_REVIEW policy, show a hold and metadata disposition. Approve one case, explain APPROVED_RESUBMIT_REQUIRED, then demonstrate revised resubmission; approval never releases stored content automatically.
7. Submit numeric feedback; show the corresponding execution/audit data and updated dashboard. Rating UI is present; aggregate feedback has an API rather than a dedicated displayed panel.
8. If ADLS has been separately configured and verified, export sanitized JSON/CSV and show SUCCEEDED plus the matching artifact. Otherwise show the adapter/failure reporting honestly and do not claim live storage success.
9. Explain SQL revision 003 and the already verified connection/inventory evidence. Present SQL-backed HTTP/browser operation as complete only after a fresh successful acceptance; preserve the original failed run as historical evidence.

## 14. Final verdict

**PARTIALLY READY.** Core implementation, safe local checks, frontend build and historical live AI/moderation are strong enough for a carefully scoped local demonstration. Full Azure SQL + Azure OpenAI + Moderation + ADLS end-to-end acceptance remains incomplete because SQL HTTP/browser verification and live ADLS export are outstanding.

No rebuild, additional Azure service, schema change or new feature is currently justified. The only intended repository addition from this audit is `docs/reports/FINAL_READINESS_AUDIT.md`; no application/configuration/credential/database/infrastructure change, Git commit or push is authorized or performed.
