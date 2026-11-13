> **Latest approval preparation:** See [final SSO deployment approval](FINAL_SSO_DEPLOYMENT_APPROVAL.md). The operator has now verified SQL revision 004. The original compatibility ZIP below predates the MSSQL reflection fix and is superseded by corrected release `1.2-6749226f1af65b63`; runtime-identity and current recovery checks remain pending.

# Governance Studio — SSO compatibility release readiness

Prepared 4 November 2026 (Asia/Kolkata). **Local candidate complete; hosted rollout BLOCKED pending independent verification and approvals.** No hosted query, deployment, migration, settings change, restart, grant, membership write, resource operation, paid AI/moderation request or ADLS operation was performed during this task. No client secret was accessed. Tests used synthetic values and disposable databases.

## A. Code changes and rationale

Initial branch: `main`. HEAD: `60fa94ef9ec01be0d0b4af347a3251255cf7565c`. The working tree already contained the earlier uncommitted SSO implementation and documentation. Those changes were preserved and extended; no reset, checkout replacement or commit was performed. No migration source/history or downgrade implementation was changed.

`backend/app/schema_compatibility.py::inspect_schema()` implements a SELECT-only contract for exactly 004 and 005. Production Azure SQL must have exactly one readable Alembic row with a supported revision. It verifies required table/column types and lengths, nullability, primary keys, expected indexes, uniqueness and foreign keys. Versioned databases must retain history-protection triggers. SQL Server checks include enabled indexes/triggers, trusted foreign keys and the current runtime identity's effective required permissions. Missing, unreadable, unknown, multiple or inconsistent revision/schema states produce a safe 503. Partial SSO tables with a 004 marker fail readiness rather than being treated as a successful upgrade.

`/ready` uses that contract and reports the actual observed revision, whether it was versioned and whether SSO is available. It does not merely accept two numbers or disable validation. `/health` remains process liveness. Production startup separately validates SQL managed-identity mode, existing provider configuration, HTTPS origin and an available configured authentication mode. Dependencies remain in the pinned requirements; no dependency/provider network probe is run by readiness.

Existing unversioned SQLite fixture databases retain a local-only structural-validation path for the established disposable demo/test infrastructure. They are explicitly reported as `UNVERSIONED_LOCAL`, never as a verified Alembic revision. Azure SQL cannot use that exception. New compatibility tests instead run the actual Alembic migrations to 004/005.

All SSO data endpoints require the 005 contract. Cookie authentication checks that contract as well as existing session/membership/CSRF controls. A misconfigured `SSO_ENABLED=true` on 004 produces unready/503, never a partial SSO session. No OIDC exchange occurs on 004. At 005, SSO requires complete configuration and its additional runtime privileges. The initiation/status flow exposes no credentials.

At 005 with SSO disabled, readiness still verifies all 17 required tables but does not require SSO DML permissions. It **does need metadata visibility** on the three new tables. This distinction is important for avoiding a readiness gap during migration. Baseline runtime CRUD permissions are always checked on Azure SQL.

Production demo login remains available through `DEMO_BROWSER_LOGIN_ENABLED=true` (the bridge default). With SSO disabled, complete Entra settings are unnecessary. With both modes enabled, React offers an explicit demonstration-access alternative. Existing stored demo sessions are restored only after a backend validation request; server account, tenant, role, expiry and revocation rules remain authoritative. The browser flag does not grant API privileges. Existing legitimate bearer API clients remain supported independently.

Demo bearer credentials/sessions keep their existing tab sessionStorage behavior. Microsoft ID/access/refresh tokens are never placed there. SSO uses HttpOnly cookies and in-memory CSRF. Mixed cookie/bearer credentials remain rejected. There is no automatic Admin or membership enrollment, no disabled audience/issuer check, and no authentication fallback on invalid credentials.

Release metadata now distinguishes minimum schema 004, supported schemas `[004,005]`, and SSO-required schema 005. The SSO migration itself remains unchanged.

## B. Files modified in this compatibility task

Earlier SSO changes remain in the working tree. The compatibility delta is:

| Path | Purpose |
|---|---|
| `backend/app/schema_compatibility.py` | New read-only revision/object/runtime-permission contract. |
| `backend/app/main.py` | Validated readiness for 004/005; minimum-schema diagnostics and actual revision reporting. |
| `backend/app/sso.py` | Schema-gated SSO endpoints and cookie authentication; safe backend browser-mode discovery. |
| `backend/app/config.py` | Preserve demo login by default for the bridge. |
| `backend/app/web_assets.py` | Permit reviewed demo-only hosting without Entra credentials and dual-mode hosting; reject missing authentication configuration. |
| `backend/app/release.py` | Minimum/supported/SSO-specific migration metadata. |
| `frontend/src/api.ts` | Backend-selected demo transport; retain cookie/CSRF transport for SSO. |
| `frontend/src/main.tsx` | Preserve production demo form, explicit mode selection and validated restoration. |
| `frontend/src/Sso.test.tsx` | Add demo-only, dual-mode and existing-demo-session restoration regressions. |
| `backend/tests/test_schema_compatibility.py` | Actual migrated 004/005, drift, permissions, session continuity and SSO compatibility tests. |
| `backend/tests/test_deployment_preparation.py` | Validate demo-only/dual/SSO-only production configurations. |
| `backend/tests/sso_browser_server.py` | Actual disposable migrations for local HTTPS browser fixtures; synthetic provider only. |
| `scripts/tests/sso_browser.cjs` | Production React browser checks for demo 004, demo 005 and synthetic SSO 005. |
| `scripts/prepare_app_service.py` | Package compatible schema metadata. |
| `scripts/verify_schema_compatibility.py` | New explicit-connect SELECT-only verification command with safe output. |
| `deployment/verify_sso_compatibility.READ_ONLY.sql` | Exact target/history/object/index/trigger/permission inspection queries. |
| `.env.example` | Bridge settings preserve demo login while SSO remains disabled. |
| `deployment/appsettings.example.json` | Matching non-secret example settings. |
| `README.md` | Current compatibility candidate entry point. |
| `docs/ENTRA_SSO.md`, `docs/ENTRA_SSO_REPORT.md` | Mark earlier SSO-only candidate behavior superseded; retain historical evidence. |
| `docs/SSO_COMPATIBILITY_RELEASE.md` | This readiness, verification and rollout/rollback report. |
| `docs/evidence/sso-compatibility/*` | Passing test output, browser results, candidate package hashes and validation summary. |

## C. Test results and candidate artifact

| Final local check | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Full backend, including all existing regressions | 534 | 0 | 0 |
| Frontend, including real disposable FastAPI integration | 32 | 0 | 0 |
| Chrome production build, demo on actual migrated 004 | 8 | 0 | 0 |
| Chrome production build, demo on actual migrated 005 | 8 | 0 | 0 |
| Chrome production build, synthetic OIDC on actual migrated 005 | 11 | 0 | 0 |

Python lint/source formatting, frontend lint, changed frontend formatting, TypeScript and production build: PASS. Package integrity and source-byte comparison: PASS. Two existing dependency warnings concern httpx compatibility/deprecation; they do not disable validation. Historical unrelated Markdown/example formatting issues remain untouched.

The backend suite includes a real local 004→005 upgrade while preserving an existing demo session and its existing audit rows, plus a successful synthetic OIDC/session/logout flow on actual migrated 005. It rejects missing tables/indexes/triggers, unknown/multiple history rows, partial SSO schema, missing runtime privileges, disabled indexes/triggers and untrusted foreign keys. Existing role denial, tenant isolation and CSRF tests continue to pass.

Source/runtime tests passed on the existing local environment. Azure SQL reflection, effective managed-identity grants, readiness latency/load, real Microsoft authentication, Azure proxy behavior, Docker and a hosted upgrade/rollback are **NOT VERIFIED** by these tests. SQL Server permission/metadata branches are tested with controlled mocks around real migrated object definitions; that is not a live SQL Server test.

Candidate: `/tmp/governance-sso-compatibility-20261104.zip`

- Release: **1.2-7105751bb3be1300**.
- SHA-256: `0aa9aa3842a01e29277ceed8a8a52ddae30890337612443ee71152bcd295d579`.
- 28 allowlisted files; min 004, supported 004/005, SSO requires 005.
- No environment files, credential files, databases, test HTTPS keys, tests or synthetic-provider code.
- Not deployed, not approved and not marked production-ready.

Full results: `docs/evidence/sso-compatibility/validation.json` and `package.json`. The ZIP packages backend, locked dependencies, startup and static frontend; migrations/grants remain separately reviewed inputs.

## D. Compatibility matrix

| Database | SSO setting | Demo browser setting | Expected outcome |
|---|---|---|---|
| Clean, supported 004 with complete baseline schema/permissions | false | true with approved demo accounts | Ready; demo login/session/reads/RBAC work; SSO returns unavailable. |
| 004 | true | either | Readiness 503; SSO endpoints 503. No SSO transaction/session is created. |
| Complete 005, baseline permissions and all required metadata visible | false | true | Ready; demo remains operational; SSO disabled. No SSO DML privileges needed in this mode. |
| Complete 005 with full SSO runtime permissions and complete OIDC settings | true | true | Ready; demo remains available and SSO is offered; only approved memberships authorize users. |
| Same complete 005/configuration | true | false | SSO-only production login. Disable demo only after successful approved SSO acceptance. |
| Unknown/003/future/multiple revision, missing/unreadable objects, partial upgrade | either | either | Not ready; no inference of a valid hosted version. |
| Both authentication modes disabled | false | false | Hosted startup rejected. |

No schema marker is rewritten to make an incompatible application appear ready. Reflection/permission checks are uncached and can be relatively expensive, especially for SSO cookie requests; measure Azure latency and capacity under an approved non-billable verification scope before wider use. Current readiness is more demanding than the old one, so existing metadata visibility and grants must be checked **before** deployment.

## E. Azure SQL verification commands — prepared, not executed

The documented target is `sql-governance-validator-dev-atiya.database.windows.net`, database `sqldb-governance-validator-dev`. An operator must confirm this is still the saved hosted target before executing. Do not infer it from local SQLite configuration or change `DATABASE_URL` to perform the check.

Use the existing organizational CLI identity matching the repository's approved `AZURE_SQL_TENANT_ID` and `AZURE_SQL_USER_OBJECT_ID` pins for operator read-only access. It needs access to the exact database, SELECT on Alembic history and sufficient metadata visibility. These settings identify the SQL operator, not the new SSO registration. On App Service, independently verify effective runtime permissions under its existing managed identity. An administrator's successful permission check does not prove runtime access. Exact identity authority and current access remain to be confirmed; no credentials are requested here.

After explicit approval for the hosted read-only check, from repository root and the intended **already authenticated** CLI context:

```bash
.venv/bin/python -B scripts/verify_schema_compatibility.py \
  --server sql-governance-validator-dev-atiya.database.windows.net \
  --database sqldb-governance-validator-dev --connect
```

For the SSO-ready contract on 005, add `--require-sso`. Neither command selects/replaces the application's database, runs migrations or prints connection strings/tokens. Missing credentials/access/schema/grants returns a generic BLOCKED result. Do not initialize a new login, change identity pins, modify environment files or activate another credential context without authorization.

For detailed operator review, run `deployment/verify_sso_compatibility.READ_ONLY.sql` in an approved SQL query tool under the exact authorized identity. It guards the database name and returns:

1. Exact database/principal/default schema, engine and observation time.
2. All Alembic rows; exactly one supported row is required.
3. The complete 17-table manifest, marking which objects are required now; at 004 the three SSO tables must be absent.
4. Expected columns/length/nullability and actual type metadata for review.
5. Required primary/unique/ordinary indexes and key columns; inspect enabled/filter flags.
6. Actual foreign keys, target columns and trusted/enabled states.
7. Required immutable-history triggers, enabled state and definitions for comparison with reviewed migration 004.
8. Effective operation permissions; new SSO CRUD is required only when enabling SSO. All 005 objects must be visible to readiness even while SSO is off.

The SQL file contains SELECTs and local T-SQL variables only, plus safety THROW statements. It does not read business record contents or contain grants/DDL/data mutation. Lack of metadata access is a blocker, not proof an object is absent. Compare actual results against the reviewed migration/model contract rather than treating every listed row as a pass.

Prepared management-plane read-only checks, **not run** (replace the resource-group placeholder only with the independently confirmed existing group):

```bash
az account show --query '{subscription:id,tenant:tenantId}' --output json
az sql db show --resource-group '<CONFIRMED_EXISTING_GROUP>' \
  --server sql-governance-validator-dev-atiya --name sqldb-governance-validator-dev \
  --query '{name:name,status:status,earliestRestoreDate:earliestRestoreDate}' --output json
az sql db str-policy show --resource-group '<CONFIRMED_EXISTING_GROUP>' \
  --server sql-governance-validator-dev-atiya --name sqldb-governance-validator-dev \
  --query '{retentionDays:retentionDays,diffBackupIntervalInHours:diffBackupIntervalInHours}' --output json
```

Do not run appsettings-list commands or access the pending client secret for this verification. Current hosted SQL revision is **not independently verified** in this task. Earlier HTTP 200/readiness metadata is historical indirect evidence, not a substitute for these queries.

## F. Recovery prerequisites and preserved deployment artifact

The preserved current-release artifact exists locally and its complete SHA-256 matches the recorded manifest:

`artifacts/restricted-demo-20261101/governance-workspace-policy-delete.zip`

- Recorded current release: `1.2-5e8064f901573795`.
- SHA-256: `b44afedb721ae8ed5b4d48c9ea50fe3aab6a586ed8325af7c08ca93969abf776`.
- Manifest: `docs/evidence/workspace-delete-package.json`.

This task verified that local artifact; it did not re-query the serving website or claim a fresh hosted fingerprint observation. That old artifact expects exactly 004 and is **not** the primary rollback package after 005.

Existing repository evidence records an Azure SQL PITR drill on 31 October at revision 003 with successful structural/data checks and temporary-target cleanup. Historical application rollback evidence concerns SQLite 004. Neither proves today's restore window, current grants or Azure 005 rollback. Prior one-off restore authorization is not reused for a new resource.

Before any hosted change, designate a recovery owner and verify the exact source, current automated-backup retention, usable pre-change point, operator permissions, recovery-time objective, acceptable post-point write loss and a fully approved cutover path. Securely retain previous settings without printing credentials. Preserve package hashes and a baseline schema/aggregate-data inventory. Confirm no inference/export is in flight and agree how concurrent writes are controlled.

Azure SQL PITR uses the existing managed backup facility but creates a **new database**; it cannot overwrite the existing one. A new target, cost, service tier, lifetime, validation and cleanup/cutover need explicit approval. No current existing recovery target or reusable current recovery guarantee was established here. If no new resources are permitted, an already validated, approved alternative must be supplied; do not pretend a local SQLite backup or ZIP alone is a database recovery plan.

The expected primary fallback is application/configuration rollback to this tested bridge while retaining additive schema 005. Database restore is reserved for a separately approved data/schema-recovery incident. Migration 005 downgrade remains deliberately disabled; do not drop tables or edit Alembic history to force rollback.

Primary platform references (verified during the preceding read-only assessment): [Azure SQL backup recovery](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql), [App Service configuration/restarts](https://learn.microsoft.com/en-us/azure/app-service/configure-common?tabs=portal). They describe mechanisms, not evidence of a restore or restart performed here.

## G. Ordered deployment and rollback procedure

All hosted steps below require explicit approval; none was executed.

1. **Freeze and review.** Confirm current website fingerprint, exact saved database target, current settings by safe presence checks, actual SQL revision/schema/permissions, source diff and bridge ZIP/hash. Keep the pending portal secret unsaved until an approved configuration operation. Saving settings restarts the application.
2. **Approve availability/recovery.** Review the backup/recovery gates above. A single-worker ZIP deployment/settings restart may interrupt requests for minutes; no zero-downtime guarantee was established. If uninterrupted availability is mandatory, prove an approved mechanism on existing resources first. Do not create a slot, app or service to solve this without approval.
3. **Approve and deploy only the bridge on verified 004.** Keep `SSO_ENABLED=false`, `DEMO_BROWSER_LOGIN_ENABLED=true`, existing reviewed demo account hashes, provider/database configuration and existing runtime identity. No Entra secret is required for this stage. Validate required metadata visibility first; strict readiness can expose previously hidden permission/schema drift.
4. **Accept the bridge.** Verify serving fingerprint/minimum/supported schema metadata, `/health`, `/ready` actual revision 004, demo login, refresh/session restoration, safe tenant-scoped policy GET, existing role denial and logout. Login/logout create session/audit writes and must be included in acceptance scope. No paid provider/storage operations are included.
5. **Approve the exact migration boundary.** After bridge acceptance and recovery validation, recheck that SQL is still clean 004 with no partial SSO objects. Freeze reviewed migration 005 and approved operator/migration permissions. Do not run `upgrade head` blindly if source changes or another head appears.
6. **Preserve readiness through 005 visibility.** The bridge needs visibility of all 005 object definitions immediately when the 005 marker commits. If existing permissions already supply this, record the evidence. Otherwise an operator must prepare/review an atomic migration-and-minimum-metadata-permission execution plan before approval, so the marker is not committed while runtime cannot inspect new objects. Object-scoped VIEW DEFINITION or the already reviewed minimum table permissions may provide visibility; actual effective scope must be reviewed. Do not automatically grant broad DDL/db_owner/schema-control rights. This transaction/grant plan is an outstanding hosted execution prerequisite, not an implemented permission change.
7. **Apply only approved 004→005.** Use the existing authorized migration identity in the approved quiet window, with reviewed transaction/error handling. Stop on any failure; inspect actual history and partial schema before retrying. Do not manually stamp a success marker. Migration source/history remain unchanged.
8. **Verify 005 with SSO still off.** Confirm exactly one 005 row, all constraints/indexes/trigger preservation, original records/counts/relationships, application runtime metadata access, healthy bridge and existing demo sessions. Local tests prove continuity only on disposable SQLite; independently verify Azure results.
9. **Approve and apply SSO grants/memberships.** Runtime needs SELECT on membership and SELECT/INSERT/UPDATE on transaction/session tables, plus existing audit/rate-bucket privileges. Provision exact approved directory/object/workspace/actor/role mappings using the separate operator process. Unknown users stay denied; Admin requires explicit approval. Do not replace the existing SQL runtime identity with the SSO app registration.
10. **Approve SSO configuration activation.** Securely save the complete reviewed `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, fixed HTTPS public origin, matching CORS and `SSO_ENABLED=true`. Keep `DEMO_BROWSER_LOGIN_ENABLED=true` until SSO acceptance succeeds. Do not reveal the secret or save incomplete unrelated pending portal edits. The same reviewed bridge ZIP already contains gated SSO; a second code deployment is unnecessary unless its code/hash changes, in which case obtain new package approval.
11. **Accept real SSO.** Verify readiness 005, exact callback, real approved organizational account/MFA, authorized role/workspace, policy GET, refresh, missing/invalid CSRF rejection, logout, repeat login, unknown-user denial, and safe logs. Include bounded session/audit writes in approval. Do not run billable AI/moderation or ADLS checks under this scope.
12. **Optionally retire demo browser login later.** Only after successful SSO acceptance and separate approval, set `DEMO_BROWSER_LOGIN_ENABLED=false`. Review legitimate API clients and operator recovery separately. Never silently rotate or remove their credentials.

Rollback triggers include unready/unhealthy app, incorrect fingerprint, unavailable demo login, failed role/tenant isolation, unexpected schema/data differences, broken session/logout/CSRF, or incomplete real SSO callback. Stop on an authentication/isolation failure; do not bypass validation to keep a demo running.

**Before SQL 005:** the preserved exact old package/configuration remains an eligible fallback after its current-state compatibility is reconfirmed. A package rollback/restart itself needs approval.

**After SQL 005, including failed SSO acceptance:** retain 005 and its records. Restore this exact tested compatibility ZIP if needed, and approved configuration `SSO_ENABLED=false`, `DEMO_BROWSER_LOGIN_ENABLED=true`, with unchanged approved demo account hashes. This bridge supports 005 and does not need an Alembic downgrade. Verify actual revision, health/readiness, fingerprint, demo login, policy reads and tenant/role denial again. Existing demo sessions remain subject to normal expiry/revocation/account checks.

SSO users may still have an HttpOnly SSO cookie after SSO is disabled. Because mixed cookie/bearer authentication remains rejected, use a fresh private browser context for demo recovery or explicitly clear the site's SSO cookie before demo sign-in. Disabling SSO blocks those sessions but does not erase SQL records or claim global Microsoft sign-out. Session revocation/cleanup requires its approved operator scope; no automatic delete occurs.

If the database itself is damaged or cannot satisfy the bridge contract, stop and invoke the separately authorized database recovery plan. Do not redeploy the exact 004-only old package against 005, force-stamp 004, drop SSO tables, disable readiness/authentication, or start an unapproved PITR resource. Preserving post-point business writes is part of recovery approval.

## H. Remaining blockers

- Independent hosted SQL revision, object definitions, effective runtime permissions and metadata visibility.
- Approved read-only identity/context and confirmed saved target/resource group.
- Current backup/restore-window verification, accountable recovery owner and approved incident cutover scope.
- Proven hosting availability/restart strategy; Azure readiness/SSO reflection latency and load are unmeasured.
- Exact approved migration/visibility transaction plan if new metadata is not already visible.
- Explicit identity/workspace/role approvals and least-privilege SSO grants.
- Real registration/client configuration validation through approved presence checks and actual Microsoft acceptance.
- Exact bridge deployment/configuration/migration/grant/membership/acceptance approvals.

No production readiness certification or successful live SSO is claimed. Docker execution is not newly validated. Hosted database revision remains independently unknown in this task.

## I. Exact operations requiring explicit approval

1. Any hosted read-only SQL/management inspection under an existing approved identity, including confirmation of runtime permissions and backup policy. Prepared queries are not permission to execute them.
2. Deploying bridge release `1.2-7105751bb3be1300` with the exact ZIP/hash above to the existing App Service, plus its bounded demo acceptance writes.
3. Any App Service settings save or restart, including the currently pending secret, enabling SSO, disabling demo login, or rollback configuration.
4. Applying migration 004→005, including the reviewed metadata visibility transaction, only after prerequisite evidence passes.
5. Runtime grants and exact SSO membership provisioning/changes; no automatic Admin mapping.
6. Real SSO acceptance session/audit writes under a bounded account/tenant scope.
7. Any recovery resource, restore, data recovery/cutover, resource cleanup or package/configuration rollback.
8. Any billable AI generation, moderation or ADLS operation, separately from authentication acceptance.

The first proposed hosted action is **read-only SQL and backup/permission verification only**. Approving that step must not be interpreted as approval to save settings, migrate, grant, provision memberships or deploy.
