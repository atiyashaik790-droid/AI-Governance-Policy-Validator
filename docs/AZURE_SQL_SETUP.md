# Azure SQL integration: local Linux, Entra-only, approval gates

## Current status

The Entra authentication adapter and tests are implemented. The running application remains on its existing SQLite configuration and data. `.env` has not been changed. No Azure SQL connection, schema migration, user provisioning, firewall change, system installation or database switch was performed in this phase.

Target: `sql-governance-validator-dev-atiya.database.windows.net`, database `sqldb-governance-validator-dev`, West US 2, Standard S0, Entra-only, public endpoint with restricted firewall, minimum server TLS 1.2. No Docker, Key Vault or additional Azure cloud service is required.

Inspected host: **Ubuntu 25.10 (questing), x86_64 / amd64**, Python 3.13.7. Installed Python packages: pyodbc 5.3.0, azure-identity 1.27.0, SQLAlchemy 2.0.55, Alembic 1.20.1. Missing: unixODBC runtime `libodbc.so.2`, registered Microsoft ODBC Driver 18, `odbcinst`, `isql`, and Azure CLI. Consequently, importing pyodbc currently fails. No Python package installation is necessary for the implemented adapter.

## Authentication and configuration

Only two new application settings are needed:

```dotenv
AZURE_SQL_TENANT_ID=<organizational-directory-UUID>
AZURE_SQL_USER_OBJECT_ID=<intended-user-object-UUID-in-that-directory>
```

Both identifiers must be explicit valid UUIDs. They are not passwords or access tokens. Populate them locally only after the operator confirms the intended organization/account. Do not paste credentials, cached tokens or `.env` contents into chat. `.env.example` retains placeholders.

The existing `DATABASE_URL` remains the backend selector. **Keep its current SQLite value until a separately approved switch.** The future Azure URL has no username/password:

```dotenv
DATABASE_URL=mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-governance-validator-dev?driver=ODBC+Driver+18+for+SQL+Server
```

`create_database_engine()` routes SQLite and `mssql+pyodbc` explicitly. SQL mode obtains tokens with `AzureCliCredential`, pinned to the configured tenant. Before opening a connection it checks the trusted SDK token's `tid` and `oid` against the configured tenant and user, and rejects expired/nearly expired tokens. This account-binding check decodes SDK-provided claims; it is not a replacement for Azure SQL's token signature/audience validation. The scope requested is `https://database.windows.net/.default`.

There is no `DefaultAzureCredential` fallback to an unrelated environment credential, personal account or managed identity. A dedicated CLI cache further isolates this local workflow. User interaction occurs during the deliberate CLI login step, not inside a FastAPI request.

The SQLAlchemy `do_connect` handler requests a valid token for every new physical connection, packs it as a little-endian length prefix plus UTF-16-LE token bytes, and supplies ODBC attribute `1256` (`SQL_COPT_SS_ACCESS_TOKEN`). Azure CLI/identity tooling manages token acquisition/renewal; the application never stores a token in `.env` or in a static connection URL. Driver-owned pooling is disabled before SQL connections are created. SQLAlchemy owns pooling: pre-ping enabled, recycle at 2700 seconds, pool size 5, overflow 5, queue timeout 10 seconds. Reused live connections do not request a token on every query. Recycling, disposal and failed-ping reconnection acquire a valid token for the new handshake.

A new token is required for new connections; token expiry does not necessarily terminate an already authenticated SQL session. The recycle setting bounds connection age but is not a claim that all tokens have a fixed lifetime.

The adapter builds a canonical ODBC string with `Encrypt=yes`, `TrustServerCertificate=no`, `Connection Timeout=10`, `LongAsMax=Yes`, and Driver 18. The server's minimum TLS setting remains 1.2. URL options that weaken TLS, change the driver, inject a raw ODBC string, or include authentication fields are rejected. `UID`, `PWD`, `Authentication` and `Trusted_Connection` are excluded; SQLAlchemy-inserted `Trusted_Connection=Yes` is removed defensively. SQL mode never silently selects SQLite on configuration, authentication, network or driver failure.

Connection/configuration/authentication exceptions have fixed sanitized messages. API database errors retain the existing non-releasing HTTP 503 behavior. Alembic imports the same engine and therefore uses the same token mechanism. No schema revision was changed in this phase.

The old README suggestion `Authentication=ActiveDirectoryDefault` has been removed: that is not the ODBC Driver authentication mode for this adapter.

## Gate 1 — Review and approve system installation (NOT EXECUTED)

The following commands modify system packages/repositories. Installing the Microsoft driver accepts Microsoft's ODBC EULA. They must not run until the user explicitly approves these specific changes.

Official sources:

- [Microsoft ODBC Linux installation](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
- [ODBC operating-system compatibility matrix](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/system-requirements?view=sql-server-ver17)
- [Official Ubuntu 25.10 driver package index](https://packages.microsoft.com/ubuntu/25.10/prod/pool/main/m/msodbcsql18/)
- [Azure CLI APT installation and earlier-distribution fallback](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?view=azure-cli-latest#no-package-for-your-distribution)

**Compatibility decision:** Microsoft's matrix lists ODBC **18.6** for Ubuntu 25.10. The official Ubuntu 25.10 repository contains **18.6.2.1-1 amd64**. Pin that version rather than assuming that the newest package in the repository is covered by the OS support matrix. Verify availability with `apt-cache policy` before installation.

Azure CLI's current tested APT distributions list Ubuntu 22.04, 24.04 and 26.04, not 25.10. Microsoft's documented fallback for an unavailable distribution is the `jammy` repository. The commands below make that fallback explicit; they are **not a claim of native Ubuntu 25.10 certification**. Approval must include this compatibility choice. If the company rejects it, stop and agree on a company-supported CLI installation/platform rather than silently substituting repositories.

Commands proposed for approval, executed individually with failures reviewed before continuing:

```bash
# System prerequisites and driver manager (system changes).
sudo apt-get update
sudo apt-get install --no-install-recommends ca-certificates curl gnupg libodbc2 unixodbc odbcinst

# Official repository matching the actual Ubuntu release.
curl --fail --show-error --location \
  https://packages.microsoft.com/config/ubuntu/25.10/packages-microsoft-prod.deb \
  --output /tmp/governance-microsoft-prod-ubuntu2510.deb
dpkg-deb --info /tmp/governance-microsoft-prod-ubuntu2510.deb
sudo dpkg -i /tmp/governance-microsoft-prod-ubuntu2510.deb
sudo apt-get update
apt-cache policy msodbcsql18

# STOP if 18.6.2.1-1 is unavailable; do not silently choose another version.
# This next command accepts the ODBC driver license.
sudo env ACCEPT_EULA=Y apt-get install msodbcsql18=18.6.2.1-1
```

Azure CLI fallback commands, **separate approval required for the fallback repository**. Stop if either destination configuration file already exists; review rather than overwrite it.

```bash
sudo install -d -m 0755 /etc/apt/keyrings
curl --fail --show-error --location https://packages.microsoft.com/keys/microsoft.asc \
  --output /tmp/governance-microsoft-signing-key.asc
gpg --dearmor --output /tmp/governance-microsoft-signing-key.gpg \
  /tmp/governance-microsoft-signing-key.asc
sudo install -m 0644 /tmp/governance-microsoft-signing-key.gpg \
  /etc/apt/keyrings/governance-azure-cli.gpg

printf '%s\n' \
  'Types: deb' \
  'URIs: https://packages.microsoft.com/repos/azure-cli/' \
  'Suites: jammy' \
  'Components: main' \
  'Architectures: amd64' \
  'Signed-by: /etc/apt/keyrings/governance-azure-cli.gpg' \
  | sudo tee /etc/apt/sources.list.d/governance-azure-cli.sources
sudo apt-get update
apt-cache policy azure-cli
apt-get --simulate install azure-cli
# Review the simulated package changes before proceeding.
sudo apt-get install azure-cli
```

`unixodbc-dev` is not needed for the installed pyodbc wheel; it is only a build dependency if compiling from source. `mssql-tools18` is optional and is not required by the backend or Python read-only probe.

## Gate 2 — Organizational login and driver verification

After approved installation, run locally from the repository root:

```bash
.venv/bin/python -B -c "import pyodbc; print(pyodbc.drivers())"
odbcinst -q -d
az version
```

The registered drivers must include `ODBC Driver 18 for SQL Server`. Verify the installed package version too:

```bash
dpkg-query -W msodbcsql18 libodbc2 unixodbc odbcinst
```

Use a private dedicated CLI cache; do not reuse an unrelated personal-account cache:

```bash
install -d -m 0700 .azure-sql-cli
export AZURE_CONFIG_DIR="$PWD/.azure-sql-cli"
az login --tenant '<organizational-directory-UUID>' \
  --allow-no-subscriptions --use-device-code --output none
```

Complete the sign-in yourself with the intended organizational account and required MFA. Never share the temporary login code or an access token. Obtain/confirm the directory tenant ID and the signed-in user's object ID locally with your administrator (or the CLI's account/directory queries), then populate the two identifier settings. Keep `DATABASE_URL` unchanged. An organizational guest's object ID must be the object ID in the configured resource tenant, not the home tenant.

All subsequent probes, Alembic invocations and eventual Uvicorn startup must inherit the same `AZURE_CONFIG_DIR`. A wrong account fails the object-ID check rather than being silently accepted. Do not use `az account get-access-token` to print tokens.

## Gate 3 — Read-only target connection, without switching the application

Run only after dependencies/login and the two identity identifiers are configured:

```bash
.venv/bin/python scripts/check_azure_sql.py \
  --server sql-governance-validator-dev-atiya.database.windows.net \
  --database sqldb-governance-validator-dev \
  --connect
```

This command creates a separate probe engine for the explicit target; it does not mutate `settings.database_url`, `.env`, database schemas, grants or the running backend. It executes only `SELECT DB_NAME()` and fixed `HAS_PERMS_BY_NAME` checks, then closes/disposes its connections. It does not return database users, tokens, connection strings or application content.

Exit 0: connection succeeded and required runtime permissions were visible. Exit 3: connection succeeded, but schema/permissions are not yet ready. Exit 2: connection, identity, configuration or probe failed. Missing or invisible objects return an explicit permission-not-ready status, not an assumption that migrations already ran. A successful read-only connection is not proof that migrations or the complete application work on Azure SQL.

If connectivity fails, report the sanitized failure type and inspect the existing approved DNS/network/firewall route with the administrator. Do not change the firewall or broaden access automatically. Public endpoint access requires the actual workstation's current egress IP to be allowed and the SQL connection route/ports permitted by company policy.

## Gate 4 — Database users and least privileges (ADMIN REVIEW ONLY)

Entra authentication and SQL authorization are separate. The Microsoft Entra administrator must provision any non-admin runtime/migration identities in **the target database**. Azure subscription roles alone do not grant table access. No provisioning SQL has been executed.

The intended application runtime needs `CONNECT` plus these effective permissions:

| Object in dbo | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| policies | yes | yes | yes | yes — only draft deletion is allowed by application logic |
| policy_versions | yes | yes | no | no |
| active_policy_assignments | yes | yes | yes | no |
| audit_events | yes | yes | no | no |
| validation_executions | yes | yes | no | no |
| human_review_cases | yes | yes | yes | no |
| feedback_records | yes | yes | no | no |
| evaluation_exports | yes | yes | yes | no |

No application procedure execution or schema modification permission is needed. Runtime does not need access to `alembic_version`. Avoid broad `db_owner` / `db_datawriter` assignments that permit mutation of historical tables. Runtime table grants do not override privileges inherited through other roles or administrator status. Tenant isolation remains enforced by the application's authenticated queries; these grants do not implement SQL row-level security.

Example principal/role provisioning for administrator review; substitute approved identities and execute only after explicit approval:

```sql
-- Run connected to sqldb-governance-validator-dev as the Entra administrator.
CREATE USER [<approved-runtime-UPN-or-group>] FROM EXTERNAL PROVIDER;
ALTER USER [<approved-runtime-UPN-or-group>] WITH DEFAULT_SCHEMA = dbo;
CREATE ROLE governance_runtime;
ALTER ROLE governance_runtime ADD MEMBER [<approved-runtime-UPN-or-group>];
GRANT CONNECT TO [<approved-runtime-UPN-or-group>];
-- Grant SELECT and INSERT separately on each of the eight application tables.
GRANT SELECT, INSERT ON OBJECT::dbo.policies TO governance_runtime;
GRANT SELECT, INSERT ON OBJECT::dbo.policy_versions TO governance_runtime;
GRANT SELECT, INSERT ON OBJECT::dbo.active_policy_assignments TO governance_runtime;
GRANT SELECT, INSERT ON OBJECT::dbo.audit_events TO governance_runtime;
GRANT SELECT, INSERT ON OBJECT::dbo.validation_executions TO governance_runtime;
GRANT SELECT, INSERT ON OBJECT::dbo.human_review_cases TO governance_runtime;
GRANT SELECT, INSERT ON OBJECT::dbo.feedback_records TO governance_runtime;
GRANT SELECT, INSERT ON OBJECT::dbo.evaluation_exports TO governance_runtime;
GRANT UPDATE, DELETE ON OBJECT::dbo.policies TO governance_runtime;
GRANT UPDATE ON OBJECT::dbo.active_policy_assignments TO governance_runtime;
GRANT UPDATE ON OBJECT::dbo.human_review_cases TO governance_runtime;
GRANT UPDATE ON OBJECT::dbo.evaluation_exports TO governance_runtime;
```

The object grants require the corresponding tables to exist: review them now, apply them after approved schema creation. Principal/role creation can be reviewed separately before that. Directory-resolution permissions or company tenant restrictions can affect `FROM EXTERNAL PROVIDER`; an administrator must resolve those, not the application. The adapter pins the authenticating **user's** object ID even when SQL permissions come from group membership.

If your signed-in account is also the server's Entra administrator, it has elevated database privileges. It can bootstrap or perform explicitly approved migrations, but that is not a least-privilege runtime identity. Use an approved separate runtime user/group for the final application configuration.

For migrations 001–003, the migration principal needs:

- `CONNECT` to the target database.
- Database `CREATE TABLE`, schema `ALTER` on `dbo`, and appropriate `REFERENCES` rights for foreign keys. Schema ALTER is powerful; keep it separate from runtime and time-bound.
- Access to the schema metadata being inspected; schema `VIEW DEFINITION` can be granted explicitly if needed by the approved provisioning model.
- `SELECT`, `INSERT`, `UPDATE`, `DELETE` on `dbo.alembic_version` for Alembic version tracking.

Those migrations do not perform application-data backfills, so they do not need blanket application-table DML. Before the initial migration, `alembic_version` does not exist: either the administrator runs the approved initial migration, or a separately approved bootstrap creates that bookkeeping table and grants the migration principal its object-specific DML. Do not issue grants on a nonexistent table or quietly solve the bootstrap by granting broad permanent ownership. No migration principal needs permission to create users, change firewall rules or grant itself database roles.

References: [Entra database principal provisioning](https://learn.microsoft.com/en-us/azure/azure-sql/database/authentication-aad-configure), [CREATE TABLE permissions](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-table-transact-sql?view=azuresqldb-current), [SQLAlchemy token connections](https://docs.sqlalchemy.org/en/20/dialects/mssql.html#connecting-to-databases-with-access-tokens), [AzureCliCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.azureclicredential?view=azure-python).

## Gate 5 — Migration review and explicit approval

Review frozen revisions 001, 002, 003 against the new database and its current contents. Local tests compile every current table/index with the SQL Server dialect and apply actual revisions only to disposable SQLite databases. Alembic's token-enabled engine reuse is tested with synthetic tokens and a local transport. **These are not real Azure SQL migration tests.**

No destructive schema changes or migration revisions were added in this phase. Existing `String`/`Text` mappings compile to SQL Server types, but full Unicode/large-text round-trip behavior and actual constraints/index operations must be verified on Azure SQL; compilation alone is insufficient. Revision 002 introspects existing columns and therefore cannot be assumed to work as a pure offline SQL export. Existing downgrade functions refuse destructive downgrades.

Before any Azure migration, present the exact target, existing schema/version, migration plan, migration identity/permissions and command, then request the user's explicit approval. Do not execute `alembic upgrade head` against Azure before that approval. Keep the running Uvicorn process and `.env` on SQLite throughout this gate. A process-scoped URL for a separately approved migration does not require changing the application's active configuration.

## Gate 6 — Validate and approve the database switch

After approved migrations and grants, rerun the read-only probe as the runtime identity. Validate schema/version and a separately authorized application smoke test against Azure SQL. Present those results and obtain approval for the switch. Only then change `DATABASE_URL` to the Azure URL and restart Uvicorn with the intended organizational CLI cache. SQLite files remain intact. Changing the selected database does **not** copy SQLite policies or audit history to Azure; data transfer/seeding requires its own reviewed plan and authorization.

Verify `/ready`, tenant-scoped policy operations and audit persistence. A selected SQL failure must produce a sanitized failure, never a silent SQLite fallback. To return to SQLite, explicitly restore the previously preserved URL and restart; do not delete either database.

## Phase test evidence and execution boundary

See `AZURE_SQL_PHASE_REPORT.md` for final test counts and files. No privileged package command above, CLI login, Azure SQL probe, Azure migration, permission grant, firewall modification, or active database switch was executed in this phase.

## Phase 1 schema inventory — 29 October 2026

Use the standalone inventory script after the successful connection probe. It reuses `app.azure_sql.create_azure_sql_engine()` and the two existing SQL identity settings. It does not import the application database engine, run Alembic, or change `DATABASE_URL`. The dedicated existing CLI cache is selected only inside its isolated worker process. It never invokes interactive login or creates a CLI cache.

Run this exact command from the **repository root**, in your authenticated Ubuntu terminal:

```bash
.venv/bin/python -B scripts/inventory_azure_sql.py \
  --connect \
  --server sql-governance-validator-dev-atiya.database.windows.net \
  --database sqldb-governance-validator-dev \
  --cli-config-dir "$PWD/.azure-sql-cli" \
  --timeout-seconds 60 \
  --query-timeout-seconds 5
```

The script prints JSON to stdout. It includes the current **database principal**, which is an identity identifier; keep the report private. No credential, access token, connection URL, application row data, raw driver error or environment value is printed. Importing the script and `--help` never connect. `--connect` is mandatory. `--timeout-seconds` accepts 5–180 seconds and bounds the worker's wall-clock work; termination/cleanup can take up to three additional seconds. Query timeout accepts 1–30 seconds and defaults to five. Existing token acquisition and login connection timeouts remain in the shared adapter.

The inventory contains:

- Database name, database principal and default schema; a wrong target database stops further inspection.
- Relevant effective database/dbo permissions, retaining SQL `NULL` rather than calling it granted.
- Visible schemas and user tables. Catalog queries have row caps; truncation is explicit and makes negative findings inconclusive.
- The eight required application tables and their required columns, primary/unique keys, indexes and foreign keys derived from the current ORM models.
- Observed column types, lengths/nullability, index uniqueness/ordering/enforcement, and foreign-key targets/actions/trust/enforcement.
- Alembic history visibility/SELECT access and actual revisions only when readable. An absent, hidden, unreadable or empty history table has a distinct status.
- Migration declarations and expected head `003`, obtained by parsing source syntax. No migration is imported or executed.
- Explicit flags that no database mutations, migrations or application database switch occurred, and that migration approval remains required.

Interpretation:

| Result | Meaning |
|---|---|
| `UNKNOWN_NOT_VISIBLE` | Cannot distinguish an absent table from metadata filtering. Never treat this as an empty database. |
| `NOT_FOUND_WITH_BROAD_METADATA_PERMISSION` | Not found despite a relevant broad metadata permission. Review explicit denials/default schema before concluding absence. It is not a blanket empty-database certification. |
| `EXISTS_BUT_NOT_READABLE` | History table is visible but SELECT is not granted. No history query was attempted. |
| `READABLE_NO_REVISION` | History table exists and is readable but contains no revision. |
| `UNKNOWN_MISSING_OR_HIDDEN_METADATA` | A visible table's required subcomponents were not observed with limited permissions. |
| `MATCHES_CHECKED_REQUIREMENTS` | The visible metadata matches the checks performed; this is not runtime or migration execution proof. |
| `COMPLETED` / exit 0 | Inventory completed with broad metadata permission; **not permission to migrate**, and not a claim all tables exist. Read the per-object findings. |
| `COMPLETED_WITH_LIMITATIONS` / exit 3 | Metadata/history could not be inspected completely. |
| Failure, unavailable cache or timeout / exit 2 | No usable complete inventory; use the existing authenticated terminal or resolve the reported prerequisite. No interactive login is attempted. |

All SQL issued by the inventory's catalog reader must match a frozen SELECT-only allowlist. Expected schema comparisons are deliberately limited to column presence/type family/minimum length/nullability and the listed index/FK properties; defaults, collation, triggers and every possible SQL Server feature are not certified. The script cannot prove a database is empty from an empty `sys.tables` result.

Migration chain: `001_foundation.py` creates all eight application tables; `002_policy_concurrency.py` conditionally adds `policies.row_version` for older baselines (already present in the current 001 baseline); `003_review_concurrency.py` adds `human_review_cases.row_version`. Alembic itself manages `alembic_version`. If tables exist without readable consistent Alembic history, stop for reconciliation; do not stamp revisions or rerun baseline creation automatically.

Local verification for this phase:

```bash
cd backend
../.venv/bin/pytest -q tests/test_sql_inventory.py
cd ..
.venv/bin/ruff check scripts/inventory_azure_sql.py backend/tests/test_sql_inventory.py
.venv/bin/ruff format --check scripts/inventory_azure_sql.py backend/tests/test_sql_inventory.py
```

Final result: **19 passed, 0 failed, 0 skipped**; lint and formatting passed. The initial test run caught an omitted allowlist definition, which was corrected before the passing runs. All inventory tests use mocked catalogs/processes or a real child process with an intentionally missing cache, so they do not connect to Azure, perform interactive login, run migrations, or create database objects. Existing broader backend tests were not rerun in this phase because some intentionally execute disposable SQLite migrations; this phase's strict boundary was preserved.

Files changed in this phase: `scripts/inventory_azure_sql.py`, `backend/tests/test_sql_inventory.py`, and this setup document. `.env`, models, migration revisions, the authentication adapter and the active SQLite database were not modified. Live inventory remains pending execution in the authenticated terminal; no live schema result is claimed from the fixture tests. Stop after reviewing the resulting report and request separate explicit approval before any migration, grant or database switch.
