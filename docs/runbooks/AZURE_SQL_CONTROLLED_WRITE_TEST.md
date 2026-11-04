# Phase 4 — Controlled Azure SQL ORM write-test proposal

Status: PREPARED, NOT APPROVED OR EXECUTED LIVE. Baseline is the user's successful
read-only verification of revision 003, all eight application tables and SQLite default.
No Azure connection or write was attempted while preparing this phase.

## Scope and isolation

The implementation is scripts/test_azure_sql_writes.py. FastAPI keeps using SQLite.
The script imports models, settings and the existing Entra adapter only; it does not
import app.database, main, SessionLocal, HTTP handlers or provider code. There is no
separate repository layer: current application CRUD is in backend/app/main.py. The
new test deliberately bypasses those handlers because some commit independently.
No Azure OpenAI, Moderation or ADLS calls occur.

The existing dbo account remains fully privileged. These safeguards constrain the
reviewed test code, not the identity's database permissions. This does not establish
least-privilege runtime isolation or approve production use.

## Minimal representative records

A new random run UUID determines one unique synthetic tenant and nine deterministic
UUID primary keys. The active assignment uses the synthetic tenant as its primary key.
Ten total records cover every table and each operation required by the application:

| Insert order | Synthetic records | Tested behavior |
| --- | --- | --- |
| 1 | policies: main + disposable draft | INSERT/SELECT, UPDATE main, DELETE only disposable draft |
| 2 | policy_versions: versions 1 and 2 of main | INSERT/SELECT; immutable, never UPDATE/DELETE |
| 3 | validation_executions: one linked by historical policy ID | INSERT/SELECT only |
| 4 | active_policy_assignments: one pointing to version 1 | INSERT/SELECT then UPDATE to version 2 |
| 4 | human_review_cases: one referencing execution | INSERT/SELECT then UPDATE disposition and counter |
| 4 | feedback_records: one referencing execution | INSERT/SELECT only |
| 4 | audit_events: one synthetic audit event | INSERT/SELECT only; immutable |
| 4 | evaluation_exports: one metadata record | INSERT/SELECT then UPDATE status/path; no upload |

Four actual foreign keys are satisfied: versions→main policy, assignment→version,
review→execution, feedback→execution. Execution.policy_id is a historical string, not
an FK. Two versions exercise the UNIQUE(policy_id, number) constraint with distinct
numbers. The disposable draft has no dependents. Synthetic lifecycle values test ORM
storage, not the application's policy lifecycle or API authorization rules.

No models use database IDENTITY columns or sequences: IDs are strings supplied by the
script. created timestamps are client-generated strings. Test values stay within the
mapped lengths; all required attributes/defaults are supplied. Policy and Review have
SQLAlchemy integer optimistic counters, not SQL Server native ROWVERSION. The test
verifies both counters move from 1 to 2 after updates. It does not test a concurrent
stale writer race. No deliberate invalid/FK-violating INSERTs are attempted because
XACT_ABORT can terminate the entire transaction.

## Protection of existing records

Before any INSERT, read-only counts require no records with the synthetic tenant in
any of the eight tables AND no records with any proposed primary key, even under a
different tenant. Collisions abort: existing rows are never adopted, overwritten,
merged or cleaned up. The run UUID should be newly generated for every write attempt.

All ORM instances are constructed by this test. Reads use the exact synthetic tenant;
updates and the single delete operate only on those inserted instances and their PKs
(and optimistic versions where applicable). There is no bulk UPDATE/DELETE, upsert,
merge, unfiltered delete or cleanup DELETE. A before_flush hook also rejects foreign
IDs/tenants, historical-record mutation and deletes other than the disposable draft.

Before writes the script verifies exact database, dbo principal/default schema, broad
metadata visibility, revision 003, expected columns/indexes/FKs, exact column-name sets,
absence of identity/computed columns, exactly the four reviewed incoming/outgoing
foreign keys (including references from other schemas), and no enabled database DML triggers. Extra
triggers/schema drift stop the test; triggers could affect existing rows or interfere
with SQL Server OUTPUT. Existing data is not dumped, modified or used as a fixture.
Run with other development database writers stopped to avoid schema/data changes during
the check. Dbo privileges mean safety ultimately depends on the reviewed local code.

## Transaction ownership and rollback

One Connection owns one explicit transaction. The Session is bound to that exact
Connection with join_transaction_mode='rollback_only'; it uses flush/refresh and never
commit. Session before_commit and engine commit events explicitly refuse commits.
DBAPI autocommit must be false. SQL Server @@TRANCOUNT=1 and XACT_STATE()=1 are required
before and after the ORM exercise. No independent sessions, HTTP clients, autocommit
execution or provider side effects are involved.

The connection uses SET LOCK_TIMEOUT 5000 and SET XACT_ABORT ON. All cursors have a
five-second query timeout; adapter login/connection timeouts remain enabled. Finally,
the externally owned transaction is rolled back even if preflight or ORM operations
raise. The Session closes before that rollback. No schema DDL or migrations occur.

The engine is then disposed (pyodbc pooling is disabled by the adapter) and a NEW
physical connection performs only SELECT counts for the same exact tenant/PK scope.
All eight counts must be zero. This avoids interpreting uncommitted rows or an old
session identity map as evidence of cleanup. No independent transaction commits are
allowed or assumed to be covered by this outer rollback.

SQLAlchemy installed locally: 2.0.55. MSSQL/pyodbc versioned-row support is documented
for SQLAlchemy 2.0.5 onward. The actual live write path remains unverified until approved.

## Commands for review

Run from repository root. Do not execute the write flag until explicit approval.
The server/database are pinned; alternative targets are rejected. Existing private
.azure-sql-cli authentication and root .env identity pins are reused; no login occurs.
The script requires the default configured database to still be SQLite and constructs
its own explicit Azure SQL URL. It never edits .env or changes the running application.

1. Generate and retain a fresh synthetic run UUID and inspect the OFFLINE plan (no SQL):

```bash
WRITE_TEST_RUN_ID=$(.venv/bin/python -c 'import uuid; print(uuid.uuid4())')
.venv/bin/python scripts/test_azure_sql_writes.py --run-id "$WRITE_TEST_RUN_ID"
```

Preserve this UUID privately until verification completes. It is a synthetic test ID,
not an account identifier or credential. Keep the same terminal variable for step 2.

2. ONLY AFTER EXPLICIT APPROVAL, execute the proposed INSERT/SELECT/UPDATE/DELETE test:

```bash
.venv/bin/python scripts/test_azure_sql_writes.py \
  --execute-approved-write-test \
  --server sql-governance-validator-dev-atiya.database.windows.net \
  --database sqldb-governance-validator-dev \
  --cli-config-dir "$PWD/.azure-sql-cli" \
  --run-id "$WRITE_TEST_RUN_ID" \
  --timeout-seconds 90
```

A subprocess imposes a 90-second wall limit covering connection, preflight, test,
rollback and the new-connection absence check. Default invocation only prints an
offline plan; --execute-approved-write-test is the explicit write gate. A flag is not
a substitute for the user's approval in this session. No retries are automatic.

3. Independent SELECT-only check, also used after an interrupted/failed attempt:

```bash
.venv/bin/python scripts/test_azure_sql_writes.py \
  --verify-only \
  --server sql-governance-validator-dev-atiya.database.windows.net \
  --database sqldb-governance-validator-dev \
  --cli-config-dir "$PWD/.azure-sql-cli" \
  --run-id "$WRITE_TEST_RUN_ID" \
  --timeout-seconds 60
```

If the terminal variable was lost, substitute the recorded run UUID directly.
--verify-only never calls the transaction/ORM exercise; it only checks target/default
schema and counts matching records. It can establish absence but cannot turn a failed
write attempt into a successful write test.

## PASS / FAIL and interruption handling

PASS requires exit 0, mode ORM_WRITE_TEST and verification WRITE_TEST_PASSED from the WRITE invocation, inserted=10,
selected_tables=8, updated_tables=4, deleted_synthetic_drafts=1, concurrency counters
verified, cleanup_status=VERIFIED_ABSENT_ON_NEW_CONNECTION and zero counts in every table.
The worker and parent both enforce every acceptance criterion, including complete
zero counts for the exact eight table names and strict operation count/boolean types.
--verify-only reports mode READ_ONLY_ABSENCE_VERIFICATION and verification ABSENCE_VERIFIED,
never WRITE_TEST_PASSED. Exit 0 in that mode establishes only record absence, not successful
ORM writes. A failure remains FAILED even if absence verification succeeds.
Successful ORM operations alone are insufficient. No original application data is read
into the output; errors print only sanitized exception type. Reported IDs are synthetic.

Any collision, wrong target/schema/revision, unexpected trigger/column, missing config,
identity mismatch, stale/version counter discrepancy, DML failure, rollback error,
nonzero residual count, query timeout or worker timeout is FAIL. A write failure remains
FAIL even when the subsequent read-only check establishes successful rollback.

On worker termination, rollback is not verified: the report says UNKNOWN_NOT_VERIFIED.
The server may need time to notice disconnect and complete rollback. STOP and use only
the recorded-run SELECT-only command when connectivity recovers; never automatically
retry writes or assume timeout means no writes happened. A blocked absence check is
inconclusive and stays FAIL. The parent does not reconnect or attempt cleanup.

If matching records remain, the report says RECORDS_PRESENT_REVIEW_REQUIRED. Stop,
preserve the synthetic run UUID and sanitized report, inspect with the administrator,
and request a separately reviewed cleanup. Never delete by tenant prefix or assume a
colliding row belongs to this test. No automatic cleanup, grants, destructive rollback,
Alembic downgrade, migration re-run or retry is authorized. If verification is unavailable,
leave the outcome unknown and the FastAPI application on SQLite.

## Approval boundary

Prepared script and local mock tests are authorized. Live SELECT-only checks may be
run separately; this phase itself stops before all live execution. The proposed DML
requires approval such as:

“Approve one execution of the reviewed rollback-only ORM write test on
sqldb-governance-validator-dev using a fresh synthetic run UUID, followed by new-connection
absence verification. Keep SQLite active; no schema, grants, HTTP tests or automatic
cleanup. Stop on failure or uncertainty.”

Future API tests, independently committed test records, cleanup or runtime switching
need separate review. The existing runtime least-privilege plan remains required for
production and is not replaced by testing as dbo.

Official implementation references:
https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.join_transaction_mode
https://docs.sqlalchemy.org/en/20/dialects/mssql.html#rowcount-support-orm-versioning
https://learn.microsoft.com/en-us/sql/t-sql/statements/set-xact-abort-transact-sql

## Local validation completed

Files added:

- scripts/test_azure_sql_writes.py
- backend/tests/test_sql_write_plan.py
- docs/runbooks/AZURE_SQL_CONTROLLED_WRITE_TEST.md

Executed: Ruff formatting/lint for the script/tests, installed SQLAlchemy version check,
and default OFFLINE_PLAN_ONLY invocation with a synthetic example run UUID. The offline
invocation confirmed connection_attempted=false and writes_executed=false.

Executed from backend:

```bash
../.venv/bin/pytest -q tests/test_sql_write_plan.py tests/test_migration_preflight.py tests/test_sql_inventory.py tests/test_azure_sql.py -k 'not api_connection_failures'
```

Final results: 88 passed, 0 failed, 2 deselected. New safety tests are mock-only and
compile predicates without executing DML/DDL. Coverage includes default offline mode,
explicit target/run-ID gates, collision predicates, immutable-record/delete guards,
commit rejection, session binding, rollback on mid-test error, independent verification,
residual-record handling, sanitized errors, timeout handling, and trigger/identity/
computed-column/extra-column/extra-FK/revision drift rejection. The two API tests were
excluded because their fixtures create local test tables. One existing Starlette/httpx
deprecation warning remains. These tests do not prove real SQL Server write behavior;
that is the purpose of the proposed approval-gated execution.

No live network connection, database writes, migrations, schema/grant changes, new
resources, .env edits or running FastAPI changes were performed during preparation.

## Final safety correction review

The earlier 88-test result above records initial preparation. After the requested
mode/acceptance corrections, the same selected suite reports **115 passed, 0 failed,
2 deselected**, with one existing Starlette/httpx deprecation warning. Ruff lint and
format --check pass for scripts/test_azure_sql_writes.py and
backend/tests/test_sql_write_plan.py.

Read-only success is now explicitly mode READ_ONLY_ABSENCE_VERIFICATION with result
ABSENCE_VERIFIED. Write success is mode ORM_WRITE_TEST with result WRITE_TEST_PASSED.
Both the worker and parent require exact operation counts (10/8/4/1), the literal True
concurrency flag, verified fresh-connection absence, and integer zero counts for the
exact eight application tables. Missing/wrong evidence, mode mismatches, residual rows
or errors cannot be promoted to success. Timeouts stay FAILED/UNKNOWN_NOT_VERIFIED and
make no retry. Offline-mode tests prohibit engine creation, workers and filesystem writes.

Commit-guard review: the dedicated engine's commit event is distinct from rollback
and pool reset-on-return. Local tests exercise SQLAlchemy SELECT and transaction
rollback using a mocked DBAPI (no database exists), while verifying no DBAPI commit
occurs. Session commit rejection remains in place. No application engine was modified;
this review does not claim a live ODBC test. All prior transaction, collision, scope,
target/schema, identity and timeout protections are retained.

No Azure connections, live writes, SQLite data changes, .env edits, migrations,
permission/resource changes or running FastAPI changes occurred. Stop for review;
prior preparation is not authorization to execute this revised write test.
