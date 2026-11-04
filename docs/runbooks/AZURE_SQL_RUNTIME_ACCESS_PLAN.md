# Phase 3 — Azure SQL runtime access preparation

Prepared for review only. No SQL connection, user creation, permission change,
migration, interactive login, .env edit, or runtime switch was performed in this phase.
The user's independently verified revision 003 and eight-table schema are the baseline;
they were not live reverified here. FastAPI remains configured for SQLite.

## Verified application access

| dbo table | Required permissions | Code / operation |
| --- | --- | --- |
| policies | SELECT, INSERT, UPDATE, DELETE | app/main.py:97,141–185,198–238: drafts and lifecycle; DELETE only never-published drafts |
| policy_versions | SELECT, INSERT | main.py:119–120,212–218,242–256: publish immutable snapshots, read versions |
| active_policy_assignments | SELECT, INSERT, UPDATE | main.py:119,220–224,348: create or replace tenant active version |
| audit_events | SELECT, INSERT | main.py:92,325–328: append and list audit events |
| validation_executions | SELECT, INSERT | main.py:304–305,319–322,336,408,436: record decisions, history, analytics and exports |
| human_review_cases | SELECT, INSERT, UPDATE | main.py:310–311,367–399: create/read reviews and update disposition/concurrency counter |
| feedback_records | SELECT, INSERT | main.py:408–423: numeric feedback and aggregate summary |
| evaluation_exports | SELECT, INSERT, UPDATE | main.py:432–460: flush initial export, then persist path/status, list attempts |

Models: backend/app/models.py:23–103. Policies and reviews have SQLAlchemy optimistic
version columns: UPDATE permission covers these counters. Export flush precedes its
status/path assignment, so INSERT alone is insufficient. app/database.py:34–44 handles
commit/rollback; readiness/settings use SELECT 1, with no extra object permission.
No stored procedure EXECUTE, sequences, schema DDL, REFERENCES, TRUNCATE, table ownership,
server login, or alembic_version access is required at runtime. The FK checks do not
require runtime REFERENCES permission on existing constraints.

These are minimum table-level DML grants for the present ORM. SQL table permissions
cannot enforce the application's tenant or draft-only deletion rules: those remain
FastAPI authorization/filtering responsibilities. Runtime access is a trusted backend
boundary, not an end-user database login. ORM hooks also prevent changes to audit_events
and policy_versions; withholding UPDATE/DELETE protects them at the database boundary.

## Recommended identity

Use a separate existing organizational Microsoft Entra **user account**, with no Azure
SQL administrator status, database ownership, privileged Entra-group-derived SQL access,
or broad database-role membership. Map its real UPN to a contained user in only
sqldb-governance-validator-dev. Grant via a new custom database role,
`governance_validator_runtime`, owned by dbo. Do not change the migration/admin account.

The existing app/azure_sql.py:76–144 uses AzureCliCredential, pins token tid and oid,
requests https://database.windows.net/.default, refreshes tokens on physical connection,
and enforces TLS with certificate validation. Therefore use that user's own CLI session
and its own user object ID. A new SQL alias for the existing dbo account does not remove
administrator privileges. A group object ID is not the user's token oid. Subscription
Contributor is not required for data-plane database access. No new Azure service,
SQL password, app registration, service-principal secret, Key Vault, or Docker is needed.
Unattended production/workload authentication is outside this local-user plan.

Prerequisites to confirm privately before approval:

- Separate non-admin organizational user exists in the SQL server's tenant and can
  complete interactive Azure CLI login under organizational MFA/Conditional Access.
  If none exists, organization administrator action is a blocker; do not create one here.
- Administrator verifies the actual user's tenant/object ID and group memberships,
  and confirms it is not the server's Entra administrator or a member of its admin group.
- Existing Driver 18, unixODBC, pyodbc, azure-identity, Azure CLI, firewall and TLS work.
  Do not modify firewall rules or install anything as part of this plan.
- Administrator can resolve the user through FROM EXTERNAL PROVIDER. If directory
  resolution is denied, stop and escalate the identity prerequisite; do not silently
  introduce a server identity, broad directory permissions, or another Azure service.
- Revision 003 and all eight reviewed objects still exist. Provisioning is not a migration.

## Read-only inspection (no approval for SQL mutations implied)

Local code inspection is complete. Review the current runtime matrix in
scripts/check_azure_sql.py:24–33 and the prepared SQL files. No values from .env are
needed in this report. Administrator may inspect existing role/public permissions,
principal SIDs, ownership and Entra-group mappings using the existing SQL editor:

```sql
SELECT DB_NAME() AS database_name, USER_NAME() AS database_principal;
SELECT version_num FROM dbo.alembic_version;
SELECT name, type_desc, default_schema_name, owning_principal_id
FROM sys.database_principals ORDER BY name;
SELECT r.name AS role_name, m.name AS member_name
FROM sys.database_role_members rm
JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
JOIN sys.database_principals m ON m.principal_id = rm.member_principal_id;
SELECT p.name AS grantee, dp.state_desc, dp.permission_name, dp.class_desc,
       OBJECT_SCHEMA_NAME(dp.major_id) AS object_schema,
       OBJECT_NAME(dp.major_id) AS object_name, dp.minor_id
FROM sys.database_permissions dp
JOIN sys.database_principals p ON p.principal_id = dp.grantee_principal_id;
SELECT name, USER_NAME(principal_id) AS owner_name FROM sys.schemas;
```

Group membership in the organizational directory requires separate administrator
verification; database catalog role listings do not establish all Entra memberships.
Keep account identifiers private; no token output or access-token CLI commands.

## Actions requiring explicit approval — not executed

### A. Provision database access

Review `docs/sql/azure_sql_runtime_provision.REVIEW_ONLY.sql`. Replace only its UPN and
user-object-ID placeholders privately. Using an administrator-authenticated SQL query editor (VS Code if already available),
connect directly to:

- server: sql-governance-validator-dev-atiya.database.windows.net
- database: sqldb-governance-validator-dev

Execute the reviewed SQL file only after approval of this specific identity and grants.
It checks the exact DB, dbo/CONTROL context, single revision 003, name/SID collisions,
creates a user using FROM EXTERNAL PROVIDER with default dbo, verifies its resolved SID,
creates the custom role, grants CONNECT plus only the matrix above, then adds membership.
It is transactional and stops on errors. It deliberately refuses existing users/roles
rather than rewriting their access. No schema-wide DML, fixed roles, ownership transfer,
explicit DENY, migration-table access or DDL privileges are granted. Effective inherited
permissions must still be audited; omitting a grant is not proof of no access.

SQL commands are supplied in the file; no sqlcmd executable was found here, and no new
SQL client installation is required. Do not run this file through Alembic or the inventory
script. On failure, stop and inspect transaction outcome; do not repeatedly execute it.

### B. Authenticate the separate runtime user locally

Only after identity/provisioning approval, run from repository root in a subshell.
Replace placeholders privately; identifiers are not secrets. Never reuse or overwrite
`.azure-sql-cli`, the migration administrator's existing cache. Use a private cache
outside the repository so authentication files cannot accidentally be committed:

```bash
(
  set -eu
  umask 077
  export AZURE_CONFIG_DIR="$HOME/.config/governance-validator-sql-runtime-cli"
  export AZURE_SQL_TENANT_ID='<ORGANIZATIONAL_TENANT_UUID>'
  export AZURE_SQL_USER_OBJECT_ID='<RUNTIME_USER_OBJECT_UUID>'
  mkdir -p "$AZURE_CONFIG_DIR"
  chmod 700 "$AZURE_CONFIG_DIR"
  az login --tenant "$AZURE_SQL_TENANT_ID" --allow-no-subscriptions --output none
  # Choose only the approved runtime user in the interactive browser.
  timeout --signal=TERM 45 .venv/bin/python scripts/check_azure_sql.py \
    --server sql-governance-validator-dev-atiya.database.windows.net \
    --database sqldb-governance-validator-dev --connect
)
```

This script explicitly constructs an Azure URL; it does not switch FastAPI or edit .env.
The tenant/object-ID env variables override root .env only in the subprocess. Token
identity mismatch must fail. The command checks positive DML permissions but is not
sufficient by itself to certify least privilege. Do not print tokens or CLI cache files.
No interactive login or directory creation was executed as part of preparing this plan.

### C. Read-only positive and negative verification

Using the actual runtime account (not EXECUTE AS dbo), run
`docs/sql/azure_sql_runtime_verify.READ_ONLY.sql` in an independently authenticated VS
Code SQL connection. If using Python instead, reuse the runtime CLI cache/session from
B and this exact command, still inside that subshell after the probe:

```bash
timeout --signal=TERM 45 .venv/bin/python - <<'PY'
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'backend'))
from app.azure_sql import create_azure_sql_engine
from app.config import settings
from sqlalchemy.engine import URL
engine = None
try:
    engine = create_azure_sql_engine(
        URL.create('mssql+pyodbc', host='sql-governance-validator-dev-atiya.database.windows.net',
                   database='sqldb-governance-validator-dev'),
        settings.azure_sql_tenant_id, settings.azure_sql_user_object_id)
    with engine.connect() as connection:
        cursor = connection.connection.driver_connection.cursor()
        cursor.timeout = 5
        cursor.execute(Path('docs/sql/azure_sql_runtime_verify.READ_ONLY.sql').read_text())
        results = []
        while True:
            if cursor.description:
                names = [column[0] for column in cursor.description]
                results.append([dict(zip(names, row)) for row in cursor.fetchall()])
            if not cursor.nextset():
                break
        cursor.close()
        print(json.dumps(results, indent=2))
except Exception as error:
    print(json.dumps({'verification': 'FAILED', 'error_type': type(error).__name__}))
    raise SystemExit(2)
finally:
    if engine is not None:
        engine.dispose()
PY
```

Expect exact DB, actual runtime UPN (not dbo), dbo default schema; custom-role member 1;
no privileged fixed roles; CONNECT 1 but no database/schema-wide DML, CONTROL, CREATE
TABLE, ALTER, role/user management or impersonation. All 32 application-table DML
checks must exactly match the matrix. ALTER/CONTROL/REFERENCES/TAKE OWNERSHIP must be 0.
Object VIEW DEFINITION may be implied by existing object permissions and is informational;
no broad VIEW DEFINITION grant is needed. No alembic_version permissions may be 1;
NULL can reflect hidden metadata, so obtain the independent administrator audit of
role/public/group/ownership access rather than interpreting NULL as a denial.
Printed query rows are evidence, not an automated PASS decision: review every result.

Do not require the general schema inventory to report COMPLETED under runtime access:
it intentionally withholds broad metadata visibility and history access. Schema/head
checks should continue using the separate migration/admin identity.

### D. Behavioral tests — separate later approval for writes

The read-only HAS_PERMS checks do not prove ORM writes, concurrency handling or SQL
Server behavior. Before runtime rollout, separately approve labeled synthetic test
records in this development database. Test draft CRUD, submit/approve/publish, first
and replacement activation, execution and review creation, review disposition/conflicts,
feedback aggregates, export insert then status update, audit append/list, and tenant
isolation. Use a separate test process, not the live SQLite Uvicorn process; no new
Alembic run. Review provider settings first: real validation/export routes can invoke
Azure OpenAI, Moderation or existing ADLS and create artifacts/costs. Use approved fixtures
or mocks for providers where supported; do not claim SQL tests establish ADLS access.

Negative permission tests must not submit destructive statements merely to see if they
fail: if access is accidentally broad they could succeed. Read-only effective-permission
checks and admin audit are the first gate. Any later transactional DML tests must have
explicit approval, synthetic identifiers and guaranteed rollback. FastAPI handlers can
commit internally, so wrapping HTTP tests in an external transaction does not guarantee
cleanup. Immutable history has no runtime DELETE: retain labeled test records unless a
separate administrator cleanup is reviewed. Do not broaden grants to simplify cleanup.

## Rollback / containment — approval required

Before the provisioning transaction commits, errors roll it back. After commit, stop
test processes and dispose pooled connections first; membership removal is not a
substitute for terminating existing application sessions. Keep the live app on SQLite.
For the reviewed new user only, an administrator can revoke the custom membership:

```sql
-- Replace the placeholder privately. Run only with separate containment approval.
IF DB_NAME() <> N'sqldb-governance-validator-dev'
    THROW 51000, 'Wrong database; stopped.', 1;
ALTER ROLE [governance_validator_runtime] DROP MEMBER [<RUNTIME_ORGANIZATIONAL_UPN>];
```

This removes the role's grants from this user, not access inherited through public,
other roles, group membership or ownership. Inspect those paths rather than assuming
full revocation. If confirmed that only this new user/role were introduced and own no
objects, separately review DROP USER / DROP ROLE for complete provisioning reversal;
no such drop is authorized now. Never drop tables, downgrade migrations, delete history,
or alter the migration administrator. Preserve any test data pending reviewed cleanup.
Local `az logout` must target only the runtime AZURE_CONFIG_DIR; do not erase admin caches.
No .env rollback is necessary because none of these commands change it.

## Blockers and acceptance

The runtime UPN/object ID, account availability, absence of privileged group inheritance,
and administrator directory-resolution rights have not been supplied or verified. No
runtime login, effective grants or live runtime operations were tested here. The current
code supports the planned local user authentication without changes; unattended identity
support is not being claimed. Backend migration approval does not authorize user/grant
creation or a runtime switch. Approve provisioning only after the exact separate user
and SQL files are reviewed; runtime switching requires its own later decision.

Official references:

- https://learn.microsoft.com/en-us/sql/t-sql/statements/create-user-transact-sql?view=sql-server-ver17
- https://learn.microsoft.com/en-us/azure/azure-sql/database/authentication-aad-configure
- https://learn.microsoft.com/en-us/sql/relational-databases/security/permissions-database-engine

## Local validation completed

Executed from backend, without migrations or database object creation:

```bash
../.venv/bin/pytest -q tests/test_migration_preflight.py tests/test_sql_inventory.py tests/test_azure_sql.py -k 'not api_connection_failures'
```

Result: 64 passed, 0 failed, 2 deselected. The API tests were excluded because their
fixtures create local tables. One existing Starlette/httpx deprecation warning remains.
These tests cover existing authentication, pooling, SQL selection, permission-probe
contracts, catalog visibility and static migration compilation; they do not certify
the proposed SQL scripts against the live server. The new SQL was reviewed statically
only and was not submitted to any database. No packages were installed.

Files added: this plan and the two SQL files under docs/sql. No backend, migrations,
configuration, secrets, databases or running services were modified.
