# Azure App Service deployment runbook — final accepted deployment

> **Current status — 30 October 2026: COMPLETE — CONTROLLED TECHNICAL DEMO READY.**
> Conditional-create package deployed as `eec1e450-11c4-4c0e-939f-f9df9e68999b`;
> exact provider/worker verified, 21 startup checks passed. One fresh ADLS JSON export
> independently verified; temporary reader removed. See the final section below and
> [final acceptance](../reports/FINAL_ACCEPTANCE_REPORT.md). Earlier provisioning, pending approval
> and failed-acceptance sections are historical; do not rerun their commands.

Actual URL: https://app-governance-validator-atiya-1026.azurewebsites.net

## 1. Read-only discovery and exact target

Existing authenticated CLI context was used without login/token output. Management-plane
resource listing, name availability and role summaries were read; SQL data was not queried.

| Item | Discovery / proposal |
| --- | --- |
| Subscription | `Devops_Azure_SV` — `REPLACE_WITH_AZURE_SUBSCRIPTION_ID` |
| Tenant | `REPLACE_WITH_AZURE_TENANT_ID` |
| Existing resource group | `REPLACE_WITH_AZURE_RESOURCE_GROUP` (group metadata location eastus) |
| Reuse SQL | `sql-governance-validator-dev-atiya` / `sqldb-governance-validator-dev`, westus2; TLS minimum 1.2, public network enabled |
| Reuse Azure OpenAI | `aoai-governance-validator-dev`, eastus; deployment/model `gpt-5-mini`, model version `2025-08-07`, GlobalStandard, capacity 250. No capacity/model changes proposed. |
| Other existing AI resource | `atiyatabsum-6397-resource` and its project; not needed or modified |
| Existing storage accounts | None visible in this subscription |
| Existing Web Apps / plans | None visible in this subscription |
| Proposed new plan | `asp-governance-validator-atiya-1026`, Linux B1, one instance, westus2 |
| Proposed new Web App | `app-governance-validator-atiya-1026`, Python 3.13, system-assigned identity |
| Proposed new ADLS account | `stgovvalidatoratiya1026`, StorageV2, Standard_LRS, HNS enabled, westus2 |
| Proposed private filesystem | `governance-reports` |

Both proposed globally unique names were available when checked, not reserved. Recheck
before provisioning; stop on conflicts instead of selecting another name automatically.
Current user's direct assignments include Contributor and User Access Administrator on
this resource group, plus Foundry User. These support the proposed management actions,
but policy/deny/quota and SQL-directory-resolution prerequisites are not guaranteed.
Group memberships were not expanded. No keys/listKeys/publishing credentials were read.

Azure retail API discovery returned Linux B1 westus2 at **USD 0.017/hour**, approximately
**USD 12.41 per 730-hour month**. This excludes taxes, contractual/currency differences,
existing SQL/AI costs, cross-region traffic and storage. New ADLS is pay-as-you-go:
for a bounded demo allowance of at most 1 GB retained and 1,000 small operations, budget
an additional **USD 1/month as a planning allowance, not a price guarantee or billing cap**.
Expected incremental envelope is about USD 13.41/month under those assumptions. No
reserved plan, autoscale or automatic tier upgrade is proposed. B1 memory/performance
with Presidio must be verified after approval; do not auto-upsize if insufficient.

## 2. One Web App, no new architecture/service

Serve the existing React build and FastAPI API from one Linux Python Web App. React
uses `VITE_API_URL=/`, so API requests resolve to `/api/...` on the same HTTPS origin.
`app.hosting:app` validates production configuration, then reuses `app.main:app`; public
SPA routes and `/assets` are registered after existing backend routes. Unknown API,
private files and asset traversal remain 404; existing APIs retain bearer/RBAC checks.

Local `app.main:app`, SQLite, offline fixture launcher and UI design remain supported.
The old Docker CMD runs migrations and the frontend Dockerfile serves a Vite dev server,
so neither is used for this deployment. No registry, Key Vault, Functions, Container Apps,
additional hosting service or application schema migration is introduced.

## 3. Local implementation and artifact

- `backend/app/azure_sql.py`: explicit optional ManagedIdentityCredential, no CLI fallback
  in managed mode. Existing tenant/object-ID token checks, Driver 18, TLS, refresh and
  pooling remain. `AZURE_SQL_AUTH_MODE` defaults to cli for local compatibility.
- `backend/app/database.py`: delegates the configured auth mode without fallback.
- `backend/app/web_assets.py`, `hosting.py`: opt-in hosted startup guards and same-origin
  SPA serving. Hosted startup rejects SQLite, CLI SQL auth, fixture providers, regex PII,
  absent provider destinations, non-HTTPS origin and absent/malformed hashed accounts.
- `backend/app/providers.py`: nested report directories are conditionally created with
  IfMissing/ETag `*`; existing directories/metadata/ACLs are not overwritten. Conflicts
  are verified to be directories. File upload remains overwrite=False. Invalid paths
  fail before credential acquisition. Live directory creation is not executed here.
- `frontend/src/api.ts`: normalizes the base URL trailing slash; `/` no longer produces
  a protocol-relative `//api/...` URL. The old localhost default still works locally.
- `scripts/prepare_app_service.py`: local, exclusive-create, allowlisted ZIP. No .env,
  credentials, DB, tests, CLI cache, migrations or historical evidence is packaged.
- `deployment/startup.sh`: one Uvicorn worker on 0.0.0.0:8000; no reload, install or
  migration command. App Service build automation installs the existing pinned lockfile.
- `deployment/appsettings.example.json`: no-secret mapping template; never deploy its
  placeholders directly.
- `deployment/sql_managed_identity.REVIEW_ONLY.sql`: exact DB/revision/identity checks;
  new contained principal and custom role with 21 table-level DML grants + CONNECT only.
  Static review only; no fixed roles, DDL rights or migration-history access granted.

Built artifact:

`/tmp/governance-appservice-prep-qi0yutlp/governance-validator-app.zip`

SHA-256: `6900d83846b35f12c9f8c23de57e5177e9592623c5e2f309a44668c87857c426`

17 entries: application Python modules, pinned requirements as requirements.txt,
startup.sh and the same-origin React index/CSS/JS. Preserve this artifact for review;
rebuild if source changes. Build outputs and copied dependencies stayed in /tmp.

Rebuild locally with installed dependencies, using a temporary frontend copy if desired:

```bash
cd frontend
VITE_API_URL=/ npm run build
cd ..
.venv/bin/python -B scripts/prepare_app_service.py \
  --frontend-dist frontend/dist --output /tmp/governance-validator-app-NEW.zip
```

## 4. Required identities, access and network changes

All changes below require approval before execution.

1. Enable the new Web App's system-assigned managed identity. Pin its actual principalId
   in AZURE_SQL_USER_OBJECT_ID (legacy setting name; this now holds the managed principal's
   object ID, never the operator ID). Keep AZURE_SQL_TENANT_ID pinned to this tenant.
2. Grant Cognitive Services OpenAI User to that identity on the existing OpenAI account.
   Leave AZURE_OPENAI_API_KEY empty so the existing DefaultAzureCredential path is used.
   This enables access, not permission to issue billable test requests yet.
3. Create the new private ADLS filesystem through the management plane. Grant Storage
   Blob Data Contributor only at its container/filesystem scope to the Web App identity.
   No account keys, public blobs, broad account-wide data role or ACL rewrite is needed.
   That built-in role includes delete capability, although this app has no delete path;
   no live deletion is authorized. Do not claim the role itself is write-only.
4. A database administrator reviews/fills/runs the SQL file for the exact new principal.
   Directory resolution and SID identity validation must succeed. SQL application SIDs
   use the client ID; verify that client ID belongs to the approved managed principal
   object ID. Token oid pinning still uses the object ID. On Graph/identity
   resolution failure, stop; no server identity, broad directory permission or changed
   Entra administrator is implicitly approved. Do not rerun Alembic or grant db_ddladmin.
5. Add SQL firewall rules only for the new Web App's currently returned outbound IPs,
   with unique `gv-appservice-N` names. Preserve existing rules. Do not use 0.0.0.0/
   AllowAllAzureServices or widen all networks. Stop on name collisions. IP ranges and
   effective access must be reviewed after creation; no additional network service is
   proposed. Shared outbound IP allowance is not a substitute for SQL token identity.

## 5. Private application settings

Use the existing App Service application-settings mechanism; no Key Vault is added.
Prepare an owner-only external JSON file from `deployment/appsettings.example.json`
AFTER resource/identity creation is approved. Do not modify root .env or copy CLI caches.
Set CORS_ORIGIN from the Web App's actual defaultHostName, which may differ from a guessed
`<name>.azurewebsites.net` address. Do not expose secret setting values in CLI output.

| Setting | Mapping / state |
| --- | --- |
| DATABASE_URL | Existing Azure SQL target with mssql+pyodbc; no password/user in URL |
| AZURE_SQL_AUTH_MODE | managed_identity |
| AZURE_SQL_TENANT_ID | Discovered tenant UUID |
| AZURE_SQL_USER_OBJECT_ID | New Web App's principalId, known only after approved creation |
| PROVIDER_MODE / PII_MODE | live / presidio |
| AZURE_OPENAI_ENDPOINT / DEPLOYMENT / API_VERSION | Existing discovered endpoint, gpt-5-mini, v1 |
| AZURE_OPENAI_API_KEY | Empty for proposed managed-identity generation |
| OPENAI_API_KEY | Existing key supplied privately; no new key requested |
| ADLS_ACCOUNT_URL / ADLS_FILE_SYSTEM | New approved DFS endpoint / governance-reports; currently absent |
| DEMO_ACCOUNTS_JSON | Reviewed local bearer hashes mapped only to fresh approved synthetic tenants; no raw tokens |
| CORS_ORIGIN | Exact actual HTTPS Web App origin |
| SCM_DO_BUILD_DURING_DEPLOYMENT | true |

The moderation key exists locally, but transfer into App Service settings requires the
deployment approval. The new managed principal does not exist yet. No production bearer
credential set for the new approved synthetic tenants has been generated. Prepare it
privately after approval; do not reuse the failed Phase 5 manifest or silently expose
existing business tenants. Authentication remains the current demonstration bearer/RBAC
model, not enterprise SSO/expiry/revocation; this is production-style hosting of a
controlled technical demo, not a production security certification.

## 6. Reviewed commands — DO NOT EXECUTE BEFORE APPROVAL

Run from repository root with the existing authenticated CLI cache; no login is needed.
All commands in this section are proposals, not executed actions. No extra resource
creation, role widening, region/tier substitution or billable test is implicit.

```bash
export AZURE_CONFIG_DIR="$PWD/.azure-sql-cli"
SUBSCRIPTION='REPLACE_WITH_AZURE_SUBSCRIPTION_ID'
GROUP='REPLACE_WITH_AZURE_RESOURCE_GROUP'
PLAN='asp-governance-validator-atiya-1026'
APP='app-governance-validator-atiya-1026'
STORAGE='stgovvalidatoratiya1026'
# After explicit approval, recheck names and regional price/quota; stop on any mismatch.
az appservice plan create --subscription "$SUBSCRIPTION" --resource-group "$GROUP" \
  --name "$PLAN" --location westus2 --is-linux --sku B1 --number-of-workers 1 --output none
az webapp create --subscription "$SUBSCRIPTION" --resource-group "$GROUP" \
  --plan "$PLAN" --name "$APP" --runtime 'PYTHON:3.13' --output none
az webapp identity assign --subscription "$SUBSCRIPTION" --resource-group "$GROUP" \
  --name "$APP" --output none
az storage account create --subscription "$SUBSCRIPTION" --resource-group "$GROUP" \
  --name "$STORAGE" --location westus2 --sku Standard_LRS --kind StorageV2 \
  --enable-hierarchical-namespace true --https-only true --min-tls-version TLS1_2 \
  --allow-blob-public-access false --allow-shared-key-access false --output none
az storage container-rm create --subscription "$SUBSCRIPTION" --resource-group "$GROUP" \
  --storage-account "$STORAGE" --name governance-reports --public-access off \
  --fail-on-exist --output none
PRINCIPAL=$(az webapp identity show --subscription "$SUBSCRIPTION" -g "$GROUP" \
  -n "$APP" --query principalId --output tsv)
ACCOUNT_SCOPE="/subscriptions/$SUBSCRIPTION/resourceGroups/$GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE"
OPENAI_SCOPE="/subscriptions/$SUBSCRIPTION/resourceGroups/$GROUP/providers/Microsoft.CognitiveServices/accounts/aoai-governance-validator-dev"
az role assignment create --subscription "$SUBSCRIPTION" --assignee-object-id "$PRINCIPAL" \
  --assignee-principal-type ServicePrincipal --role 'Storage Blob Data Contributor' \
  --scope "$ACCOUNT_SCOPE/blobServices/default/containers/governance-reports" --output none
az role assignment create --subscription "$SUBSCRIPTION" --assignee-object-id "$PRINCIPAL" \
  --assignee-principal-type ServicePrincipal --role 'Cognitive Services OpenAI User' \
  --scope "$OPENAI_SCOPE" --output none
```

Then review the exact generated identity/IPs and execute only the approved SQL principal
script and per-IP firewall changes. Example for each reviewed outbound IP:

```bash
# REPLACE values with the reviewed actual app outbound IP/rule index; never 0.0.0.0.
az sql server firewall-rule create --subscription "$SUBSCRIPTION" -g "$GROUP" \
  -s sql-governance-validator-dev-atiya -n gv-appservice-REPLACE_INDEX \
  --start-ip-address REPLACE_ACTUAL_APP_IP --end-ip-address REPLACE_ACTUAL_APP_IP --output none
```

Configure and deploy using only private files, without secret-valued shell arguments:

```bash
# Private file prepared outside the repository with mode 0600; no placeholder values.
APP_SETTINGS_FILE='/tmp/REPLACE_WITH_PRIVATE_REVIEWED_SETTINGS.json'
az webapp config appsettings set --subscription "$SUBSCRIPTION" -g "$GROUP" -n "$APP" \
  --settings @"$APP_SETTINGS_FILE" --output none
az webapp update --subscription "$SUBSCRIPTION" -g "$GROUP" -n "$APP" --https-only true --output none
az webapp config set --subscription "$SUBSCRIPTION" -g "$GROUP" -n "$APP" \
  --startup-file 'sh startup.sh' --always-on true --min-tls-version 1.2 \
  --ftps-state Disabled --generic-configurations '{"healthCheckPath":"/health"}' --output none
az webapp log config --subscription "$SUBSCRIPTION" -g "$GROUP" -n "$APP" \
  --application-logging filesystem --level information --web-server-logging off \
  --docker-container-logging filesystem --output none
# Complete these security changes BEFORE ZIP submission; never overlap management and build.
az resource update --ids "/subscriptions/$SUBSCRIPTION/resourceGroups/$GROUP/providers/Microsoft.Web/sites/$APP/basicPublishingCredentialsPolicies/scm" \
  --api-version 2024-11-01 --set properties.allow=false --output none
az resource update --ids "/subscriptions/$SUBSCRIPTION/resourceGroups/$GROUP/providers/Microsoft.Web/sites/$APP/basicPublishingCredentialsPolicies/ftp" \
  --api-version 2024-11-01 --set properties.allow=false --output none
az webapp deploy --subscription "$SUBSCRIPTION" -g "$GROUP" -n "$APP" --type zip \
  --src-path /tmp/governance-appservice-prep-qi0yutlp/governance-validator-app.zip --async true --output none
```

Do not set WEBSITE_RUN_FROM_PACKAGE: Python uses ZIP deployment with Oryx build automation.
Do not use the old Docker migration CMD. Use supported Entra-authenticated deployment;
do not enable basic publishing credentials or print publishing profiles to work around
a deployment authorization failure. Every step must record sanitized outcome/created
resource IDs privately and stop on failure; do not blindly retry provisioning.

## 7. After deployment approval: safe startup verification

1. Inspect build/startup logs without printing settings, request bodies or tokens.
2. Check installed runtime Driver 18 from pyodbc diagnostics. Microsoft documents it as
   typically present in Linux App Service, not an unconditional guarantee. Stop if absent;
   do not install packages at runtime or change drivers/security silently.
3. Verify actual HTTPS URL, React shell/assets/deep link, unknown API 404, unauthenticated
   protected API 401, health 200, readiness 200 and authenticated sanitized settings.
   Readiness uses SELECT 1; no migration/table creation/data mutation occurs at startup.
4. Health alone does not establish AI/moderation/ADLS operation. Azure settings presence,
   a mocked test or infrastructure deployment is not a successful live data-plane test.
5. Validate native Python 3.13 package installation, Presidio model availability, memory,
   startup time and managed identity before any data-changing test. Local interpreter
   and static package validation cannot certify the managed runtime.

Application logs retain the existing route/status/duration metadata, without access-log
bodies/bearers. Filesystem logs do not introduce Application Insights/another service.

## 8. Separate live acceptance gate

Deployment approval does NOT authorize billable requests, SQL test records or an ADLS
export. A second explicit approval must specify fresh synthetic tenant/accounts, exact
operations/volume, billable-call bound, retained SQL records and one/no-overwrite export.
Never run `scripts/test_azure_sql_http.py`, reuse failed SQL/ADLS manifests, modify
historical rows, clear data or pretend timed-out requests rolled back.

Use existing protected routes: create/validate/simulate policy, submit/approve/publish/
activate, input/output checks and bounded generation, BLOCK/REDACT/HUMAN_REVIEW, audit,
review dispositions, feedback, analytics and one sanitized export. Verify returned IDs
with an independent read-only SQL connection and verify the ADLS artifact at its exact
new UUID path. Retain uncertain outcomes for inspection. Initial directory creation is
part of the explicitly approved export scope; it cannot replace existing directories.
Do not fabricate new acceptance evidence until each live operation actually succeeds.

## 9. Rollback / containment

There is no existing Web App to overwrite, so first-deployment rollback is containment:
stop ONLY the new app; retain logs/artifact/resource IDs and any authorized test records.
Do not delete the existing SQL/OpenAI resources, change their administrator, downgrade
migrations or delete storage contents. Stopping the Web App does not stop plan billing.
Removal of the new role assignments, SQL membership, named firewall rules or deletion of
new plan/app/storage requires the specifically reviewed rollback/cleanup authorization;
never delete the resource group. SQL audit/test rows remain retained.

For a later release, securely snapshot the approved pre-change app settings (without
printing values), retain its previous ZIP/hash/startup settings and redeploy that ZIP
only under approval. Revoke no pre-existing identity/role. No slot is created on B1.
The independent local SQLite/offline demo remains an available fallback throughout.

## 10. Local evidence and limitations

- Backend: **217 passed, 0 failed**, one migration test deselected; 69 prohibited-driver
  checks excluded before collection. Includes 25 new deployment/ADLS contracts.
- Frontend: **7 passed, 0 failed**, including same-origin URL normalization and real
  React-to-disposable-FastAPI workflow. No cloud service used.
- Ruff, formatting (38 files), ESLint, strict TypeScript, Vite build and shell syntax: pass.
- Package successfully built, allowlist verified, no live upload/deployment performed.
- Existing Starlette/httpx deprecation and Vite bundle-size advisories remain non-blocking.

Current direct SQL/AI connectivity evidence remains historical/user-verified; deployed
managed identity, native platform runtime, ADLS access and live deployed workflow remain
NOT LIVE-VERIFIED. No deployed URL exists. Proposed names are not deployed endpoints.

## 11. Consolidated approval request

Approve ONLY the named new Linux B1 plan, one Web App/system identity, HNS Standard_LRS
storage account/private filesystem, the two narrowly scoped runtime role assignments,
reviewed SQL contained identity/21-DML role, exact generated outbound-IP firewall rules,
private settings and ZIP deployment described above. Reuse the named existing SQL and
OpenAI resources without migrations or capacity changes. Estimated new hosting is
USD 12.41/month plus metered ADLS/traffic/tax; no automatic tier increase.

Missing inputs before execution: explicit provisioning/deployment approval; private
moderation-key transfer and reviewed synthetic-tenant account hashes; after creation,
the actual managed principal ID/default hostname/outbound IPs and any necessary DBA
identity-resolution support. Storage destination settings become known only after the
new account/filesystem are approved. Do not request secrets in chat.

Live billable/data-changing workflow tests remain a separate approval. Until approval,
status is **PARTIALLY READY — deployment prepared, not deployed**.

## Official references

- [Linux Python build/startup configuration](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python)
- [ZIP deployment and Oryx automation](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip)
- [Python run-from-package restriction](https://learn.microsoft.com/azure/app-service/deploy-run-package)
- [ODBC on App Service; runtime verification required](https://learn.microsoft.com/en-us/sql/connect/python/mssql-django/deploy-azure-app-service?view=sql-server-ver17)
- [App Service managed identity and permission boundaries](https://learn.microsoft.com/en-us/azure/app-service/overview-managed-identity)
- [ADLS RBAC and ACL model](https://learn.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-access-control-model)
- [Retail Prices API and regional estimates](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)


## Approved deployment execution — 29 October 2026

The user explicitly approved the documented provisioning, permissions, configuration and
deployment scope. Earlier approval-pending statements above describe the preparation
checkpoint, not the current authorization state. Billable inference, synthetic business
records and ADLS uploads remain excluded pending a separate approval.

- Created `asp-governance-validator-atiya-1026`: Linux B1, one worker, westus2.
- Created `app-governance-validator-atiya-1026`, Python 3.13, HTTPS only.
- Actual URL: https://app-governance-validator-atiya-1026.azurewebsites.net
- System identity object ID: `REPLACE_WITH_WEB_APP_PRINCIPAL_ID`.
- Verified directory client ID: `REPLACE_WITH_WEB_APP_CLIENT_ID`.
- Created `stgovvalidatoratiya1026` (StorageV2, Standard_LRS, HNS, TLS1.2,
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
  Deployment ID: `edaf152d-31f7-4e3e-987d-ea1122b94960`.

SQL script correction reference:
[Microsoft application SID semantics](https://learn.microsoft.com/en-us/sql/relational-databases/system-catalog-views/sys-server-principals-transact-sql).

**Build/startup outcome is recorded below after verification.** No AI inference,
synthetic SQL business writes, ADLS uploads, migrations, historical record edits,
original local server changes, commits or pushes were performed.


Deployment sequencing correction: finish all site/security/logging management updates
(including disabling basic publishing) before submitting ZIP deployment. Do not perform
management updates while Oryx is building. A client gateway timeout does not establish
failure; inspect the server-side deployment state and logs. The first deployment reported
SCM-restart failure and later status 4; the resubmitted identical artifact
`dd63d8eb-e68d-4617-869b-5ca3fbc884ea` completed with status 4/active at
2026-10-29 16:10:39 UTC. Its 393-second build installed all pinned requirements and produced
`oryx-manifest.toml` and `output.tar.zst`. Earlier missing-startup-file logs occurred before
that output existed. Linux container filesystem logging was then enabled and only the
new Web App restarted for safe startup verification. No pricing-tier change occurred.


## Final safe startup verification — 29 October 2026, approximately 16:20 UTC

**VERIFIED LIVE: deployment and read-only startup. Overall: PARTIALLY READY.**
Current deployment `dd63d8eb-e68d-4617-869b-5ca3fbc884ea` is status 4,
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


## Bounded acceptance and correction gate — 30 October 2026

Live acceptance ran once in fresh synthetic tenant `live-demo-81a5d4cc190a433bacc1`.
After correcting four zero-key checker errors through read-only SQL-backed comparison,
180 live assertions passed and six failed; the live React DOM/HTTP test passed. See
[final completion report, section 21](../reports/FINAL_PROJECT_COMPLETION_REPORT.md) and
[machine-readable results](../LIVE_ACCEPTANCE_RESULTS_2026_10_30.json). All run records remain.

The SQL eight-table counts are 2 policies, 2 versions, 1 assignment, 24 audits, 5 executions,
1 review, 2 feedback and 1 FAILED export. Foreign tenant remains empty. Moderation and
PII redaction/revalidation are VERIFIED LIVE. Final ALLOW/REDACT generation failed closed.

Local fixes reuse installed sync Azure credentials in a worker thread (the deployed async
transport lacks aiohttp) and remove only the redundant directory etag keyword, retaining
IfMissing and non-overwriting upload. Three focused regressions include the real storage
SDK HTTP serializer. Backend 220/0; existing frontend 7/0; live read-only React test 1/0;
Ruff/39-file formatting, ESLint, TypeScript/build and diff whitespace passed.

Only app/providers.py differs inside the corrected ZIP:
`/tmp/governance-live-acceptance-z1mats42/governance-validator-corrected.zip`.
SHA256: `7058b43850bdd4126d0a936e0e322c7e3bad7c4aba696ea85a7d1e10f784c38d`.

**Do not deploy until approval.** No settings/schema/dependency/resource/tier changes are
required. After approval, deploy only this ZIP to the existing app with the reviewed
Entra-authenticated ZIP command, wait for server-side completion, and perform read-only
startup checks. Do not overlap site management changes and Oryx build. Roll back to the
retained prior ZIP only if startup fails; never roll back or clean SQL test records.

Then, if explicitly approved, issue two fresh generation checks (at most eight moderation
requests) under a new ledger using the existing synthetic policy. A single additional
UUID export needs separate authorization because the original single export attempt is
already consumed. Retain the existing FAILED export record and path. Current CLI HEAD
readback is 403 AuthorizationPermissionMismatch; independent artifact validation needs
approval for temporary Storage Blob Data Reader for the current Azure CLI user at only
the governance-reports filesystem scope (exact scope in the completion report). Snapshot
existing assignments first and remove only a newly added temporary assignment afterward.
No such grant, export or correction deployment has been performed.

## 15. Corrected worker deployed; fresh live acceptance gate

Reviewed ZIP SHA256 `7058b43850bdd4126d0a936e0e322c7e3bad7c4aba696ea85a7d1e10f784c38d`
was approved and deployed as `96fedb1b-e5db-426d-b7df-cf818f599bb7`. The platform confirmed
that version running at **07:08:19 UTC**. Post-switch read-only startup passed **11/11**.
URL: https://app-governance-validator-atiya-1026.azurewebsites.net

The bounded completion attempt ran too early, against the old serving worker while the
replacement started. Result: **51 passed, 9 failed assertions**; two generation requests
failed closed, one new export FAILED. Do not treat deployment status 4 or HTTP 200 alone
as proof of replacement readiness. Require application startup completion, successful
platform warmup, and **Site is running with deployment version [exact new ID]** in runtime
logs before mutating acceptance. Do not replay the consumed ledger or old manifests.
No inference/export calls have been made after the confirmed worker switch.

Both old failed exports are retained, including new UUID
`83317967-1471-4256-b872-3917f4ba47f6`; reader HEAD returned 404 for its exact new path.
The temporary filesystem reader role was removed and all prior roles preserved. Counts
are now 2 policies, 2 versions, 1 assignment, 27 audits, 7 executions, 1 resolved review,
2 feedback and 2 failed exports. Dashboard ALLOW=1, REDACT=0, BLOCK=5, HUMAN_REVIEW=1;
ALLOW is input validation, not successful generation. Historical failures must remain.

Use the hosted UI for read-only policy/history/dashboard/review/feedback demonstration.
Use the existing offline rehearsal for successful generated ALLOW/REDACT until fresh
live checks pass. Do not click Generate, Simulate, Validate or Export against the live
site under the consumed acceptance budget. A fresh approval is needed for up to two
additional generation requests, eight moderation calls, one new UUID export and temporary
filesystem reader/readback/removal. No new code deployment, resource, key or tier is
currently proposed. ADLS authenticates with managed identity; no ADLS API key is needed.

Open existing demo credentials privately in VS Code:

```bash
code "/home/sigmoid/AI governance policy validator/artifacts/demo-access/credentials.json"
```

Copy the appropriate role token directly into Access token on the deployed UI. This is
a JSON data file, not an executable command or a public browser URL. File mode is 0600,
its private directory is 0700, Git ignores it, and deployment excludes it. Do not change
permissions or publish/copy token contents into chat, screenshots or terminal commands.
Do not reuse the acceptance ledger merely to sign in; login only uses the existing token.

See [current machine-readable evidence](../LIVE_COMPLETION_RESULTS_2026_10_30.json) and
[completion report, section 22](../reports/FINAL_PROJECT_COMPLETION_REPORT.md#22-approved-correction-deployment-and-bounded-completion-attempt)
for precise limits and the remaining approval. No missing credential value is requested.

## 16. Final approved conditional-create deployment and recovery

The exact reviewed ZIP was deployed once after explicit user approval:
`/tmp/governance-adls-final-bqcipv0q/governance-adls-create-only.zip`,
SHA256 `b1a3dc0f3d53e98c4ce8c133cbd81d29146299530c42622a11cd384b492d46e1`.
Only app/providers.py changed versus the prior package. No settings, dependencies,
migrations, identities, firewall rules or infrastructure were changed by deployment.

Deployment ID `eec1e450-11c4-4c0e-939f-f9df9e68999b` is complete/active/status 4.
Although the CLI timed out after 300 seconds, it was not rerun. The platform confirmed
this deployment serving at 14:16:57 UTC / 19:46:57 IST. Deployed Oryx provider SHA256
`0da32cb68c09068a107025de001f7f766bde65ee1c09bb51f821ee24df95ecc1` matches the package.
Postdeployment smoke passed 21/21; configuration/tenant checks passed 6/6. No critical
new startup errors were observed in inspected logs. Wait for worker warmup after build;
never submit overlapping deployments or infer the serving version from health alone.

The approved one fresh export and independent file verification passed (41/41 checks),
followed by 72/72 hosted Chrome checks. Existing settings, all prior SQL rows and failed
exports were preserved. Conditional filesystem-reader access was removed; all prior
assignments were preserved. No new AI/moderation calls occurred.

Recovery uses the same ZIP mechanism and preserves data/settings. The retained prior
artifact is `/tmp/governance-adls-final-bqcipv0q/governance-adls-final.zip`, SHA256
`f54ab2adc143a0abcf8014e92d0f9f0a9badeace51d33da1ed484bd4220b0a64`.
Reverting to it would reintroduce the known export defect; only use a reviewed rollback
for an actual regression. No rollback was necessary. Do not stop/delete resources,
replay manifests, or repeat exports as part of routine verification.

[Final deployment, export, browser and regression evidence](../reports/FINAL_ACCEPTANCE_REPORT.md)
is the current handover. The single-export allowance is consumed; further live requests
require a separately agreed allowance.
