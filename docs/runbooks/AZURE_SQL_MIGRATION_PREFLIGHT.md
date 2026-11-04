# Azure SQL migration preflight — 2026-10-29

Status: HOLD FOR EXPLICIT APPROVAL. No migration has been executed.

## Evidence and gates

The supplied live Phase 1 inventory reports CONNECTED, principal/default schema dbo,
CREATE TABLE/ALTER dbo/CONTROL database/VIEW DEFINITION enabled, no visible user
tables, and NOT_FOUND_WITH_BROAD_METADATA_PERMISSION for Alembic history. This is
strong evidence of an empty user schema, rather than an inference from restricted
metadata. There is no recorded revision: this is an unversioned database, not revision 001.
A new bounded read-only probe in this execution environment failed with
DatabaseConnectionError. Its error was sanitized. Fresh live state remains unverified here.

| Gate | Result | Evidence / condition |
| --- | --- | --- |
| Reported database and baseline | PASS on supplied inventory | sqldb-governance-validator-dev, no user tables or history |
| Independently refreshed live baseline | FAIL / HOLD | Read-only recheck could not connect here; repeat from authenticated terminal |
| Migration identity / default schema | PASS on supplied inventory | dbo with database CONTROL; unqualified objects resolve to dbo |
| Alembic bootstrap | PASS | Existing identity can create/read/write dbo.alembic_version |
| Revision chain | PASS | None → 001 → 002 → 003; one head |
| Table / FK creation order | PASS | All referenced tables created before dependents |
| Indexes / SQL Server DDL | PASS locally | Bounded string keys, no cascade cycles, MSSQL compilation tests |
| Shared Entra authentication / TLS | PASS locally | Alembic imports app.database.engine; explicit SQL selector fails closed |
| Recovery procedure | PASS as plan | Stop, inspect rollback, separately approve any repair; destructive downgrade refused |
| Runtime least privilege | FAIL for runtime rollout | dbo is migration-only; separate runtime identity must be provisioned later |
| Execution authorization | FAIL / HOLD | Explicit approval still required |

Runtime provisioning does not block schema creation; it blocks switching FastAPI to Azure SQL.
Static compilation is not a live SQL Server migration rehearsal.

## Exact migration behavior

`backend/migrations/versions/001_foundation.py:11` creates, in order:
audit_events, evaluation_exports, policies, validation_executions, feedback_records,
human_review_cases, policy_versions, active_policy_assignments. There are eight
application primary keys, nine secondary indexes, and UNIQUE(policy_id, number)
on policy_versions. Alembic additionally creates its own version table.

Four foreign keys: feedback_records.execution_id and human_review_cases.execution_id
reference validation_executions.id; policy_versions.policy_id references policies.id;
active_policy_assignments.version_id references policy_versions.id. There are no
cascade actions. validation_executions.policy_id is intentionally not a foreign key.

`002_policy_concurrency.py:11` inspects policies and adds row_version only if absent.
The frozen 001 already includes that column, so 002 performs no schema alteration
on this baseline and advances history. `003_review_concurrency.py:11` adds the review
row_version INTEGER NOT NULL DEFAULT '1'. Both version fields are integer optimistic
concurrency counters, not SQL Server ROWVERSION/TIMESTAMP types.

No SQLite-specific upgrade DDL or incompatible key sizes were found. Existing
VARCHAR/Text types are not Unicode-specific; multilingual fidelity depends on
collation/encoding and needs a later runtime test. Modern MSSQL large-text compilation
uses VARCHAR(MAX). Do not replace the frozen migrations or autogenerate a new baseline.

`backend/migrations/env.py:7` uses the application's token-enabled engine and wraps
the chain in a transaction. It supports online execution only: do not use `--sql`
as an offline rehearsal. Migration 002 also requires database introspection.
Migration 003 is not idempotent if a column was manually added without matching history.
Stop on any baseline drift, duplicate object, unexpected revision, or partial schema.

## Identity permissions and administrator actions

Current dbo/database CONTROL is sufficient for this bootstrap; no extra grants are
required for this approved migration identity. Do not use it as the runtime identity.
A narrower future migration principal requires CONNECT, CREATE TABLE at database
scope, ALTER on dbo, REFERENCES on referenced tables (or dbo for bootstrap), metadata
visibility, and version-table SELECT/INSERT/UPDATE for this linear chain. General
Alembic branch/downgrade workflows may additionally need DELETE. Bootstrap grants
must account for alembic_version not existing yet; object grants cannot be applied
to a nonexistent table. Metadata-only inspection also needs appropriate visibility.

After schema verification, an administrator must separately provision a distinct
Microsoft Entra runtime database user (default dbo) and explicit object permissions:

| Runtime operation | Tables |
| --- | --- |
| SELECT, INSERT | All eight application tables |
| UPDATE | policies, active_policy_assignments, human_review_cases, evaluation_exports |
| DELETE | policies only |

No runtime CREATE TABLE, ALTER, CONTROL, db_owner, db_datawriter, or Alembic write
permissions are required. Pin its own tenant/object ID and CLI session when validating
that identity; a successful check as dbo does not prove runtime least privilege.
No principals or permissions were changed in this phase.

## Controlled execution plan

All commands below run from the repository root. Only step 1 is permitted before approval.
Use the existing authenticated project-local CLI cache; do not initiate login here.

1. Repeat the bounded read-only inventory immediately before execution:

```bash
.venv/bin/python scripts/inventory_azure_sql.py \
  --server sql-governance-validator-dev-atiya.database.windows.net \
  --database sqldb-governance-validator-dev \
  --cli-config-dir "$PWD/.azure-sql-cli" \
  --connect --timeout-seconds 30 --query-timeout-seconds 5
```

Require COMPLETED, the exact database, dbo principal/default schema, broad metadata
permission, no user tables, no history, and the same effective migration permissions.
If any result differs or connection fails, STOP. Keep all application processes using
SQLite. Ensure no other operator is migrating this database. Capture the inventory
privately; do not commit account identifiers or CLI-cache files.

2. Obtain explicit approval for revisions 001–003 on this named development database.
3. Only after approval and the successful unchanged inventory, run exactly:

```bash
(
  set -eu
  export AZURE_CONFIG_DIR="$PWD/.azure-sql-cli"
  export DATABASE_URL='mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-governance-validator-dev?driver=ODBC+Driver+18+for+SQL+Server'
  cd backend
  timeout --signal=TERM 180 ../.venv/bin/alembic -c alembic.ini upgrade 003
)
```

The subshell overrides DATABASE_URL only for this command, leaving .env, the parent
shell and running application unchanged. Settings environment precedence and
`backend/app/database.py:13` route this explicit mssql+pyodbc URL to the Entra adapter.
`backend/app/azure_sql.py:46` enforces Driver 18, encryption and certificate validation;
identity is pinned to tenant/object ID. SQL selection/configuration/authentication/
transport errors raise; there is no SQLite fallback. Revision 003 is pinned instead
of a potentially changing head. A timeout is a failure requiring read-only inspection,
not proof of rollback and not permission to retry.

4. Run the same inventory command from step 1 again. Require revision list ["003"],
expected head match, all eight required tables VISIBLE with every column/index/FK check reporting
MATCHES_CHECKED_REQUIREMENTS,
no section errors or metadata limitations. Expect nine total user tables including
alembic_version; the eight application tables have 18 index structures (eight PK,
one unique constraint, nine secondary indexes), plus the history table's own PK.
Both concurrency columns must be nonnullable integers; all four FKs must be enabled
and trusted. Inspect actual comparison statuses rather than accepting COMPLETED alone.
5. Independently confirm Alembic's recorded revision (read-only command):

```bash
(
  set -eu
  export AZURE_CONFIG_DIR="$PWD/.azure-sql-cli"
  export DATABASE_URL='mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-governance-validator-dev?driver=ODBC+Driver+18+for+SQL+Server'
  cd backend
  timeout --signal=TERM 45 ../.venv/bin/alembic -c alembic.ini current --verbose
)
```

6. Keep FastAPI on SQLite. Separately review runtime-user provisioning, permissions,
and runtime tests before requesting approval for any active database switch.

## Recovery plan

Before execution, retain the initial inventory and reviewed migration files; confirm
there is no application data and record the execution time. The administrator should
check existing Azure SQL backup/restore availability if restore protection is needed;
do not assume an immediately created database already has a usable restore point.

If execution errors or times out, stop and rerun only the bounded inventory after the
connection recovers. Alembic's MSSQL implementation supports transactional DDL and the
environment requests a transaction, so rollback is expected for ordinary failures,
but the observed schema/history must establish what actually persisted.

If still empty/unversioned, diagnose the failure and obtain renewed approval before
retrying. If any partial objects or history exist, preserve them and prepare a reviewed
forward repair or reconciliation; never stamp head, drop tables, delete history,
recreate the database, or blindly rerun 003. If revision 003 committed but validation
fails, retain SQLite operation and review a forward fix. All existing downgrade
functions deliberately raise; `alembic downgrade` is not a recovery option.
Any restore/replacement database or destructive reset requires separate explicit
approval. No recovery mutations are authorized by this plan.

## Approval wording

“Approve running Alembic revisions 001, 002, and 003 on
sqldb-governance-validator-dev at
sql-governance-validator-dev-atiya.database.windows.net, only after a fresh read-only
inventory confirms the reviewed empty dbo schema and permissions. Keep .env and the
active SQLite application unchanged; do not grant permissions or switch runtime.”

References: https://learn.microsoft.com/en-us/sql/relational-databases/security/permissions-database-engine
and https://github.com/sqlalchemy/alembic/blob/main/README.rst .

## Validation performed in this phase

Files added: this report and backend/tests/test_migration_preflight.py. No application,
adapter, migration, environment or database files were modified.

Executed from backend:

```bash
../.venv/bin/pytest -q tests/test_migration_preflight.py tests/test_sql_inventory.py tests/test_azure_sql.py -k 'not api_connection_failures'
```

Final result: 64 passed, 0 failed, 2 deselected. The two API tests were excluded because
their application fixtures create local test tables. One existing Starlette/httpx
deprecation warning remains. An initial new compiler test failed because its synthetic
column lacked SQLAlchemy Table binding; the fixture was corrected and the complete
selected set passed. No production change was needed. Ruff lint and formatting checks
passed for the new test file. Only in-memory DDL compilation and read-only/mock
connections were exercised; no migration upgrade function ran.

A bounded live inventory command was also executed with --connect and a 20-second
wall limit; it returned FAILED_OR_INTERRUPTED / DatabaseConnectionError with no
successful live schema refresh. No interactive login or privilege escalation occurred.
The migration and Alembic-current commands above were prepared, not executed.

Database mutations occurred: false. Migrations executed: false. Permissions changed:
false. .env changed: false. Active application database switched: false.
