# Final SSO rollout approval checklist — 4 November 2026

**Status: PREPARED, NOT AUTHORIZED TO DEPLOY.** Operator schema verification is now PASS at 004. Managed-identity effective permissions, current recovery metadata and hosting availability still require evidence. This task performed local preparation and one unsuccessful read-only ARM lookup; no hosted changes, secret access, migrations, grants, restarts or deployments occurred. No unrelated tests were repeated.

## Recorded evidence and provenance

The user executed the corrected verifier in their Ubuntu terminal and reported:

```json
{
  "status": "PASS",
  "database": "sqldb-governance-validator-dev",
  "revision": "004",
  "versioned": true,
  "sso_schema": false,
  "database_mutated": false,
  "permission_subject": "executing_cli_identity",
  "hosted_runtime_identity_verified": false
}
```

Recorded verbatim in `docs/evidence/sso-compatibility/operator-verified004.json`, marked USER_REPORTED, not an agent rerun. This confirms the reviewed 004 contract under the executing CLI identity, including absence of partial 005 tables visible to that verifier. It does **not** establish the hosted managed identity's effective permissions, saved App Service settings, or backup policy. No further operator tests need to be repeated merely to reconfirm this result before preparation; recheck immediately before an eventual approved mutation if state/time has changed.

The compatibility code accepts verified 004 with SSO disabled and demo enabled. It accepts complete 005 as well. It still rejects unsupported/ambiguous revisions, incompatible objects and missing required permissions. The SQL Server reflection defect was corrected; 24 focused reflection/redaction tests passed. Prior complete compatibility validation was 534 backend tests, 32 frontend tests and 27 browser checks; those are historical pre-diagnostic-fix full-suite results, not a new full-suite run. The reflection fix changes the supported inspection path, not schema or business data.

## Package, target and rollback artifact

The earlier `1.2-7105751bb3be1300` ZIP is superseded for this rollout: it predates the unique-constraint reflection fix. Do not deploy that ZIP.

Corrected compatibility candidate, locally packaged and byte/hash verified:

- Path: `/tmp/governance-sso-compatibility-fixed-004-20261104.zip`.
- Release: **1.2-6749226f1af65b63**.
- SHA-256: `9d81fa9b7700557eac2cb41edd5ab861d19a6b8c4f9052e55068e5eab784df80`.
- Minimum schema 004; supported schemas 004/005; SSO requires 005.
- Includes the fixed MSSQL reflection path. All packaged backend bytes match current source, and member hashes match the package manifest.
- Manifest: `docs/evidence/sso-compatibility/package-fixed004.json`.
- No environment/credential files, databases, test HTTPS keys or synthetic provider are packaged. Source/requirements/static assets/startup only.

Exact intended existing target:

- App Service: `app-governance-validator-atiya-1026`.
- URL: `https://app-governance-validator-atiya-1026.azurewebsites.net`.
- Existing subscription recorded by project context: `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`.
- SQL server: `sql-governance-validator-dev-atiya.database.windows.net`.
- SQL database: `sqldb-governance-validator-dev` (operator verified).
- Resource group, current ARM identity and saved configuration still require live confirmation. Agent read-only `az webapp list` failed DNS/network, so no current ARM resource ID or identity UUID is asserted.

Preserved original hosted artifact:

- `artifacts/restricted-demo-20261101/governance-workspace-policy-delete.zip`.
- Release `1.2-5e8064f901573795`.
- SHA-256 `b44afedb721ae8ed5b4d48c9ea50fe3aab6a586ed8325af7c08ca93969abf776`.
- File exists and matches the recorded checksum now. Current hosting fingerprint was not freshly re-queried here.
- This original artifact requires 004: it is a pre-migration fallback only. After 005 use the corrected compatibility candidate above, with SSO disabled and demo enabled; retain schema/data 005.

## Exact managed identity and required verification

Historical SQL evidence identifies the existing App Service system-assigned identity's contained database user as **`app-governance-validator-atiya-1026`**, type EXTERNAL_USER, with custom role **`governance_validator_web_runtime`**. This is distinct from the new `Governance-Studio-SSO` registration and the operator's CLI user. Current identity object/client UUIDs are **UNKNOWN**, not guessed from the display name.

Run in the same working Ubuntu context (read-only, no secret retrieval):

```bash
cd "/home/sigmoid/AI governance policy validator"
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az webapp list \
  --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 \
  --query "[?name=='app-governance-validator-atiya-1026'].{name:name,resourceGroup:resourceGroup,id:id,state:state,httpsOnly:httpsOnly,principalId:identity.principalId,tenantId:identity.tenantId,type:identity.type}" \
  --output json --only-show-errors
```

Expect exactly one intended app with its existing system-assigned identity. If absent/ambiguous/denied, stop. Do not enable or recreate its identity. Record the returned resource group and immutable resource ID, principal object ID and tenant ID. Using that confirmed object ID, an already-authorized Graph reader may run:

```bash
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az ad sp show \
  --id '<CONFIRMED_APP_SERVICE_PRINCIPAL_OBJECT_ID>' \
  --query '{objectId:id,clientId:appId,displayName:displayName,servicePrincipalType:servicePrincipalType}' \
  --output json --only-show-errors
```

Object ID and client ID are identifiers, not credentials. Do not retrieve tokens, credentials, or pending App Service secrets. If Graph read permission is unavailable, ask the existing authorized operator for this non-secret identity confirmation; do not grant broad directory permissions. Compare the existing contained user's SID appropriately with the managed identity's application ID; do not substitute the SSO registration ID or confuse object ID with client ID. [Microsoft's contained service-principal verification example](https://learn.microsoft.com/en-us/azure/azure-sql/database/authentication-aad-service-principal-tutorial?view=azuresql).

`deployment/verify_managed_identity.READ_ONLY.sql` prepares existing principal/role/SID/grant inspection without changing execution context. Catalog inspection under an administrator is supporting evidence only. For **effective** runtime verification, use an existing App Service console/session under its already-configured managed identity to run the reviewed SELECT contract: `SELECT DB_NAME(),USER_NAME()`, Alembic revision, metadata reflection, and `HAS_PERMS_BY_NAME` for each baseline operation. Do not install tools, edit files/settings, retrieve/print tokens or restart the app. Reuse its existing Python environment and `app.database.SessionLocal`/`app.schema_compatibility.inspect_schema`; print only safe identity/revision/status fields. If the existing deployed package lacks the new schema helper, execute the prepared SQL through its existing SQLAlchemy connection rather than adding code to the hosted filesystem. This tests the actual mapped SQL principal, TLS connection and effective grants together.

An already-authorized DBA's session-scoped impersonation can provide a separately approved effective-permission assessment without persistent grants, but it does not prove live managed-identity token acquisition/mapping and is not executed or authorized by this preparation. Do not request new IMPERSONATE rights. Prefer the actual runtime connection.

## Minimum reviewed permissions after migration 005

Updated `deployment/sso-runtime-permissions.REVIEW_ONLY.sql` is guarded to the exact database, single revision 005, existing custom role, existing external user and verified existing role membership. Its identity guard remains an intentionally invalid placeholder until the actual managed-identity client ID is independently confirmed. It creates no user/role and changes no role membership.

| Object | Additional runtime operations |
|---|---|
| `dbo.sso_memberships` | SELECT |
| `dbo.sso_transactions` | SELECT, INSERT, UPDATE |
| `dbo.sso_sessions` | SELECT, INSERT, UPDATE |

No runtime membership writes, DELETE, DDL, db_owner or broad grants. Existing audit INSERT and rate-bucket permissions must continue to pass; no duplicate grant is needed if already effective. Membership provisioning uses a separately approved operator with its existing privileges and transaction/audit process.

Metadata visibility is a migration boundary prerequisite: the bridge validates 17 objects at 005 even while SSO is off. Either existing runtime metadata permissions already cover the new objects, or reviewed minimum visibility/grants must become visible atomically with the approved migration before 005 commits. The prepared grant script does not automatically solve that transaction boundary. Final operator execution/transaction planning must be reviewed before migration approval. No grants were applied.

## Current backup/recovery verification — prepared only

Use only the confirmed existing resource group and existing SQL server/database. No new service, backup policy change, restore or recovery database is authorized.

```bash
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az sql db show \
  --resource-group '<CONFIRMED_EXISTING_GROUP>' \
  --server sql-governance-validator-dev-atiya --name sqldb-governance-validator-dev \
  --query '{id:id,name:name,status:status,earliestRestoreDate:earliestRestoreDate}' \
  --output json --only-show-errors
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az sql db str-policy show \
  --resource-group '<CONFIRMED_EXISTING_GROUP>' \
  --server sql-governance-validator-dev-atiya --name sqldb-governance-validator-dev \
  --query '{retentionDays:retentionDays,diffBackupIntervalInHours:diffBackupIntervalInHours}' \
  --output json --only-show-errors
```

Record observation time, Online status, retention days and a usable pre-change timestamp inside the current PITR window. Check the designated recovery operator's existing management restore permissions at that exact resource scope; no new RBAC grants. Identify RTO, acceptable loss of post-point writes, incident cutover procedure and ownership. Preserve the current package/settings securely without displaying secret values.

Historical 31 October Azure PITR verification and cleanup are retained evidence, not today's backup verification. Azure SQL PITR creates a new database and cannot overwrite the source; actual restore/target creation, costs and cutover need separate explicit approval. Under current restrictions only policy/window checks can complete. A ZIP rollback is the preferred response to application/SSO failure while the database remains healthy; it is not a database backup. [Microsoft recovery semantics](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql).

## Exact ordered rollout and approval gates

1. **Complete remaining read-only prerequisites:** record exact current app/MI IDs and role mapping; verify actual runtime 004 schema/permissions/metadata; confirm current backup/PITR window, recovery owner and rollout availability plan. Current operator PASS need not be confused with runtime PASS.
2. **Approve compatibility deployment only:** exact corrected ZIP/release/hash above, exact existing App Service/resource group, SSO disabled, demo enabled, existing account hashes and database selection preserved. If saved flags need changes, those setting changes/restart require explicit scope. Leave the pending secret unsaved at this stage. Deployment/startup do not run migrations.
3. **Deploy and accept bridge at 004:** verify serving fingerprint, health/readiness showing actual 004, demo login, refresh, safe policy reads, tenant/role denial and logout. Include bounded session/audit writes in this approval. No provider/storage calls. A single-worker deployment may interrupt service; no zero-downtime assurance without a proven existing mechanism.
4. **Obtain separate migration/grant approval:** freeze 004→005 source/SQL, metadata-visibility transaction plan, exact existing role/principal, current pre-change recovery point and quiet-window controls. No broad grants, source database replacement or manual revision stamping.
5. **Apply only approved 005 and reviewed minimum visibility/grants:** preserve all existing tables/data, then independently verify single 005 row, three SSO tables/constraints/indexes, unchanged history protection, effective runtime permissions and working demo sessions. Stop on drift/partial state; no blind retries or downgrade.
6. **Approve and provision exact memberships:** directory/object IDs, intended existing workspace/actor, approved role/enabled flag, operator and approval reference. Explicit approval for Admin; unknown identities stay denied. Use the prepared operator tool; no runtime membership-write grant.
7. **Approve complete SSO settings activation:** exact tenant/client IDs, server-only existing client secret, exact HTTPS origin/CORS/callback and `SSO_ENABLED=true`; keep demo browser login enabled. Save only reviewed pending changes in the approved restart window. Do not expose the secret. The corrected package already contains SSO, so no second code deployment is needed unless code changes.
8. **Real Microsoft acceptance:** approved organizational account/MFA, callback, expected role/workspace, policy GET, refresh, CSRF rejection, logout/re-login and unknown-user denial. Approve bounded SQL session/audit writes; no paid AI/moderation/ADLS operations.
9. **Retire demo browser access only after acceptance and separate approval.** Preserve legitimate API-client/operator access according to a reviewed plan; no silent credential rotation or account removal.

Rollback before migration may use the verified original 004 artifact. After 005, rollback uses corrected bridge `1.2-6749226f1af65b63` with `SSO_ENABLED=false` and `DEMO_BROWSER_LOGIN_ENABLED=true`, preserving existing demo accounts and all 005 data. Its readiness supports 005. Clear only the browser's old SSO cookie or use a private browser context for demo recovery, because mixed cookie/bearer identities remain rejected. No dropping tables, falsifying Alembic history, or deploying the original 004-only artifact against 005. Rollback package/config changes and any database recovery still require approved scope.

## Approval checklist

| Item | State |
|---|---|
| User-run corrected verifier: exact database, revision 004, versioned schema, no mutation | PASS — operator supplied |
| Required 004 contract / no partial 005 under that CLI identity | PASS — successful verifier contract |
| Compatibility support for 004/005 and local demo/SSO regressions | PASS — recorded local evidence |
| MSSQL unique reflection defect fixed and focused regressions | PASS — 24 focused tests |
| Corrected package includes fix; member/source/checksum integrity | PASS |
| Original hosted rollback ZIP exists/checksum matches | PASS — local artifact verification |
| Exact live ARM target/group/MI UUIDs | BLOCKED — network lookup unavailable here |
| Actual App Service runtime effective permissions and metadata visibility | PENDING — CLI result is not runtime evidence |
| Current STR retention/PITR window/recovery ownership | PENDING |
| Atomic 005 visibility/grant execution plan and availability acceptance | PENDING |
| Approved SSO memberships, complete activation settings, real Microsoft login | PENDING |
| Deployment/migration/grant/membership/configuration/acceptance authorization | NOT GRANTED |

**Next immediate action:** obtain the non-secret managed-identity/runtime/backup results through the prepared read-only procedure in the working Ubuntu environment. No hosted change is needed for that verification.

**Next hosted change requiring explicit approval:** deploy corrected compatibility release `1.2-6749226f1af65b63` only, conditional on the pending runtime/recovery/target checks passing, preserving demo login and leaving SSO disabled. That approval must separately enumerate any necessary settings/restart and bounded demo acceptance writes. It does not authorize migration 005, grants, membership provisioning, SSO activation, a restore or paid provider/storage operations. Unconditional deployment approval is not yet justified.


## Reusable automation prepared — 4 November 2026

Run `bash scripts/verify_sso_deployment_readiness.sh` from the repository root.
See [SSO_READINESS_AUTOMATION.md](SSO_READINESS_AUTOMATION.md) for the exact checks,
exit codes, remaining runtime/recovery blockers and separate B–G preparation commands.
The controller defaults to A only; later plans cannot execute hosted mutations or
cascade approvals. No production mutation executor was enabled.

Latest local automated run: pinned candidate/rollback checksums PASS, project CLI context
PASS, approved selected subscription/tenant PASS. App Service lookup UNKNOWN due to
`AZURE_NETWORK_OR_DNS_UNAVAILABLE`; subsequent hosted checks NOT_ATTEMPTED. This does
not supersede the operator-reported 004 PASS or establish actual runtime permissions.
29 focused automation tests, shell syntax, Ruff lint and formatting PASS. No hosted
changes, new identity, secret access, or unrelated full-suite tests occurred.

## Remaining blockers update — confirmed operator evidence, 4 November 2026

The operator successfully ran the one-command automation on Ubuntu and reported:
App Service PASS, managed identity PASS, exact principal object ID
`600447fe-5fea-4801-9033-ab4aafc474cc`, SQL revision 004/schema/no partial 005 PASS,
compatibility release PASS, backup metadata PASS, retention **7 days**. Runtime SQL
permissions and recovery ownership/drill remain UNKNOWN. This supersedes the earlier
unknown ARM identity at the time of preparation; it is USER_REPORTED evidence, not a
new independent agent ARM/SQL/backup observation. Exact returned resource groups and
earliest restore timestamp were not included in the message and are not invented.
Recorded in `docs/evidence/sso-compatibility/operator-remaining-blockers.json`.

### Why the runtime result was UNKNOWN

`ACTUAL_RUNTIME_CHANNEL_UNAVAILABLE` was hard-coded by the original automation.
It was not a failed SSH/Kudu authorization attempt. The default preflight now labels
this `ACTUAL_RUNTIME_PROBE_NOT_RUN` and points to the separate remaining-only command.
No runtime result has been silently promoted to PASS.

The installed CLI exposes `az webapp exec --mode shell --target app --shell /bin/sh`.
Microsoft distinguishes the main app container from the Kudu container; ordinary
Kudu `/api/command` execution alone is not reliable proof of the app's environment.
Detached exec returns acceptance only, not stdout/completion, so it cannot supply
runtime proof without additional output storage; that method is not used.
Legacy SSH remains an existing interactive fallback if already authorized and enabled,
but this probe does not obtain publishing credentials, enable SSH/basic auth, install
an extension/tool, or switch identity to work around denied access.

One command, from the existing Ubuntu project directory:

```bash
bash scripts/verify_sso_deployment_readiness.sh --remaining-only
```

This skips already-passed full artifact/schema/backup tests. It confirms only the
current CLI target and the exact reported App Service identity, reads current CLI
SQL-server management permission metadata, then opens a bounded main-app shell through
the existing CLI context. The CLI must already support `az webapp exec` (Microsoft
currently documents 2.90+); no upgrade or dependency installation occurs automatically.
The operator needs existing SCM access including `Microsoft.Web/sites/publish/Action`;
that existing capability does not authorize deployment by this task.

`scripts/verify_hosted_runtime.py` streams the checksum-pinned reviewed schema helper
in memory, reusing deployed `app.models` and `app.database.SessionLocal`. Nothing is
uploaded or written to hosted application files. The old 004 package does not contain
the helper; it already contains the baseline models, SQL engine and managed-identity
provider. The probe requires managed-identity mode, exact tenant/principal pins and
SQL host/database; the existing provider validates token identity internally as part
of its normal connection, without returning token content. It checks DB_NAME,
expected mapped SQL user, exactly 004, baseline schema/metadata/effective permissions
and membership in the existing runtime role. All queries are the reviewed SELECT
contract plus read-only identity/role SELECTs. No commit, migration, SQL grant, role
change, application start, HTTP login or paid provider/storage call occurs.
Python bytecode writes and shell history are suppressed for that probe session only;
App Service settings are unchanged. CLI banners, errors, command echo and all
unrecognized remote fields are withheld. Only complete, allowlisted result JSON is
returned. Shell prompt/result timeout, missing existing interpreter/dependencies,
denied access or identity drift returns FAIL/UNKNOWN; no fallback grants or retries.
The 55-second bound closes only the local CLI session, never the App Service worker.

A runtime PASS explicitly means `status_scope=hosted_runtime004_only_not_deployment_authorization`.
It does not prove recovery authority or authorize Stage B. Recovery permissions are
reported separately: current CLI allow metadata for database read/write, not a claim
of effective restore authority or proof about another operator. A successful permission
API read or wildcard is insufficient to establish deny assignments, locks, target
capacity, costs, recovery ownership and cutover. The designated recovery operator must
be named by an authorized owner; automation cannot choose one from broad CLI privileges.

Agent direct attempt still stopped at App Service ARM lookup with
`AZURE_NETWORK_OR_DNS_UNAVAILABLE`; no main-app shell or SQL session was opened here.
15 focused new tests PASS, including a local fake CLI/PTY end-to-end exchange, timeout,
partial-result rejection, pinning, redaction, identity drift, permission-pattern handling
and remaining-only dispatch. Ruff lint/format and all relevant shell syntax PASS.
No previously passing full suite, full hosted schema verifier or backup query was rerun.

### Stage B versus migration 005: preserve the gates, scope recovery correctly

| Prerequisite | Stage B: compatibility code at unchanged 004 | Migration 005 / coordinated minimum grants |
|---|---|---|
| Actual runtime identity, baseline schema/metadata/effective permissions | Required; currently UNKNOWN until probe PASS | Required again for complete 005 at approved boundary |
| Pinned candidate, current target and original rollback artifact | Required; operator reports artifact/target PASS | Corrected bridge must remain rollback-compatible with 005 |
| SSO off, demo on, current account hashes/settings preserved | Confirm before approval; no secrets read by probe | Continue demo until real SSO acceptance |
| Rollback owner/window and accepted deployment interruption | Required; identify an existing authorized app release operator | Required plus migration/recovery owners and quiet-window controls |
| Backup metadata | Operator reports PASS, 7 days; retain current evidence | Refresh exact PITR point/window immediately before change |
| Database restore operator/authority, RTO/RPO and incident cutover | Not the primary code rollback path; remain documented UNKNOWN | Required review before approving schema change |
| New recovery drill/database | No established requirement for this code-only stage | Not established as universally mandatory by repository or Azure; need evidence-based recovery review and explicit risk acceptance if no current rehearsal |
| 005 metadata visibility/grant transaction boundary | No 005/grants executed | Required before approval; avoid a committed-005 readiness gap |

There is no repository instruction requiring a **fresh** restore drill before every
compatibility deployment. Historical 31 October Azure PITR drill evidence exists at
revision 003; it is supporting evidence, not proof of today's window, 004/005 restore
or current authority. Azure PITR creates another database and cannot overwrite the
source. Any new drill/restore/target creation remains separately approved and is not
performed by this workflow. If organizational policy requires a fresh drill, that
policy must be supplied and satisfied before proceeding; no policy exception is assumed.

For Stage B the intended failure response is restoring the exact original 004 application
ZIP while leaving SQL 004 unchanged. Review that package rollback, its operator, saved
settings compatibility and availability window; a database restore drill is not a
substitute. If data integrity is affected, stop and invoke a separately approved
recovery process rather than treating the package rollback as database recovery.
For migration 005, review current backup/PITR evidence, existing restore authority and
target constraints, recovery owner/RTO/RPO/cutover, frozen migration, and the atomic
metadata/grant boundary before separately approving C and D. A new rehearsal is a
separately scoped decision where the available evidence or organizational policy
requires it; do not call migration production-ready from retention metadata alone.

**Shortest path to Stage B:** run the remaining-only command; obtain runtime PASS;
confirm existing rollback operator/window and saved SSO-off/demo-on configuration;
then request **Stage B only** for the pinned `1.2-6749226f1af65b63` ZIP. Enumerate any
settings/restart and bounded demo acceptance writes. No migration/grants/memberships/
SSO activation/recovery database is included. Overall rollout and migration readiness
remain UNKNOWN pending their own prerequisites and explicit approvals.

Sources: [Microsoft main-container access and CLI limitations](https://learn.microsoft.com/en-us/azure/app-service/configure-linux-open-ssh-session),
[existing SCM/Kudu permission requirements](https://learn.microsoft.com/en-us/azure/app-service/resources-kudu#rbac-permissions-required-to-access-kudu),
[Azure SQL recovery mechanisms and permissions](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql).

## Runtime probe failure follow-up — 4 November 2026

Operator reports `MAIN_APP_SHELL_OR_COMPLETE_PROBE_RESULT_UNAVAILABLE` from Ubuntu.
This old category did not retain whether a prompt, Python, SQL or final JSON was
reached. Root cause of that hosted run remains unverified; do not call it an SQL or
SSH authorization failure without evidence. Local inspection reproduced two defects:
ANSI prompt rejection and stopping before queued CLI final output was drained.
Both are fixed, with stage-specific shell/runtime/SQL/parser diagnostics and a manual
existing-console fallback. See [RUNTIME_PROBE_DIAGNOSTICS.md](RUNTIME_PROBE_DIAGNOSTICS.md).

One next command remains `bash scripts/verify_sso_deployment_readiness.sh --remaining-only`.
A direct agent attempt stopped at `app_discovery` / `AZURE_NETWORK_OR_DNS_UNAVAILABLE`,
without reaching the hosted shell/SQL. 31 focused tests, lint/format and shell syntax
PASS. No full schema/backup check was repeated. No deployment, restart, migration,
grants, membership/settings changes or recovery resource creation occurred.
Stage B still awaits actual runtime PASS and its existing review/approval gates;
previous successful operator checks remain recorded, and no recovery drill is newly
required for that code-only deployment.

## Narrow layout fix — latest operator evidence

Operator now confirms main-app shell access and reports `RUNTIME_APP_PACKAGE_UNAVAILABLE`
at `working_directory`. The probe's flat `APP_PATH/app/database.py` assumption failed
before Python/import/SQL execution. Bounded process/root discovery now supports verified
flat and `backend/app` layouts and selects the existing interpreter/import parent.
No particular hosted directory is guessed. The agent's layout-only attempt stopped
at `app_discovery` due to DNS/network unavailability; actual container layout remains
unobserved here. See the final section of [RUNTIME_PROBE_DIAGNOSTICS.md](RUNTIME_PROBE_DIAGNOSTICS.md)
for the one-command main-console fallback. 10 layout tests and 31 affected probe
regressions PASS; no successful schema, backup or package check was repeated and no
hosted state was changed. Stage B still awaits actual runtime proof and its existing
separate approval gates.
