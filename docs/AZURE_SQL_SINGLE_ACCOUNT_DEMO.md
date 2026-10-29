# Phase 3 — Single-account local demo assessment

Assessment only: no live connection, database writes, migrations, grants, identity
creation, .env edits or running-application changes were performed in this phase.

## Decision and evidence

The existing organizational Azure CLI account can be used for a bounded read-only
integration check against the existing development database. A second identity is not
a prerequisite for checking connectivity and schema/ORM SELECT compatibility. It remains
a prerequisite for demonstrating genuinely separate least-privilege runtime access.

No backend authentication change is needed. backend/app/azure_sql.py:38–144 validates
the tenant/user UUIDs, uses AzureCliCredential with a 15-second process timeout, checks
token tid/oid and lifetime, requests https://database.windows.net/.default, and injects
the ODBC token per new physical connection. Driver 18, encrypted connections and
certificate validation are enforced. Connections use timeout 10, pre-ping and recycling.
backend/app/database.py:13 routes explicit mssql+pyodbc selection without SQLite fallback.
backend/app/config.py keeps SQLite as the default. The runtime access plan's separate
user requirement concerns least privilege; it does not prohibit this diagnostic use
of the current administrator account.

## Limits of this temporary exception

The reported dbo identity has broad database rights. This command is SELECT-only by
construction, not a database-enforced read-only credential. A script defect, compromised
Python process, changed code, or arbitrary application endpoint could exercise the
account's administrative rights. A SQLAlchemy rollback or ApplicationIntent=ReadOnly
would not remove those rights. Do not add a new alias or low-privilege role to this same
administrator and call it least privilege. Do not change the server's administrator as
part of this demo. Microsoft documents dbo as holding all database permissions.

Keep the development database, existing firewall and TLS settings, and private CLI cache
as they are. Run the short-lived diagnostic from the trusted local workspace and stop
on any failure. Do not start another Azure-configured Uvicorn process or expose this
administrator-backed connection through HTTP endpoints. The working demo UI/API continues
to use SQLite; explain that the Azure database integration check is a separate diagnostic.

## Exact read-only verification command

Run from repository root in the authenticated VS Code Ubuntu terminal. The existing
project-local CLI cache and root .env identity pins are reused without printing their
values. No login or cache creation is attempted. DATABASE_URL is not changed or exported.

The command checks SQLite remains selected, SELECT 1, the exact target database and dbo
schema, revision 003, all eight application tables, checked columns/indexes/FKs, and
zero-row SQLAlchemy model reads. It prints no original row data, account IDs, principal
names, connection strings, secrets or tokens. Administrator context is reported only
as a boolean.

```bash
(
  set -eu
  export AZURE_CONFIG_DIR="$PWD/.azure-sql-cli"
  test -d "$AZURE_CONFIG_DIR"
  timeout --signal=TERM --kill-after=5s 45s .venv/bin/python - <<'PY'
import importlib.util
import json
import logging
from pathlib import Path
import sys

root = Path.cwd()
sys.path.insert(0, str(root / 'backend'))
from app.azure_sql import create_azure_sql_engine
from app.config import settings
from app.models import Base
from sqlalchemy import select, text
from sqlalchemy.engine import URL, make_url

logging.getLogger('azure.identity').setLevel(logging.CRITICAL)
engine = None
try:
    if make_url(settings.database_url).get_backend_name() != 'sqlite':
        raise RuntimeError('Default database is not SQLite')
    spec = importlib.util.spec_from_file_location(
        'demo_inventory', root / 'scripts/inventory_azure_sql.py')
    inventory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inventory)
    engine = create_azure_sql_engine(
        URL.create('mssql+pyodbc',
                   host='sql-governance-validator-dev-atiya.database.windows.net',
                   database='sqldb-governance-validator-dev'),
        settings.azure_sql_tenant_id, settings.azure_sql_user_object_id)
    inventory.install_query_timeout(engine, 5)
    with engine.connect() as connection:
        if connection.scalar(text('SELECT 1')) != 1:
            raise RuntimeError('Connectivity check failed')
        actual_db = connection.scalar(text('SELECT DB_NAME()'))
        if actual_db != 'sqldb-governance-validator-dev':
            raise RuntimeError('Wrong database')
        report = inventory.collect_inventory(connection, actual_db)
        context = report.get('context', {})
        history = report.get('alembic_history', {})
        tables = report.get('required_tables', {})
        comparisons = {
            name: {
                'visible': item.get('status') == 'VISIBLE',
                'checks': {kind: result.get('status')
                           for kind, result in item.get('checks', {}).items()}}
            for name, item in tables.items()}
        schema_ok = (
            report.get('inventory_status') == 'COMPLETED'
            and context.get('default_schema') == 'dbo'
            and history.get('status') == 'READABLE'
            and history.get('revisions') == ['003']
            and history.get('matches_expected_heads') is True
            and len(tables) == 8
            and all(item.get('status') == 'VISIBLE'
                    and set(item.get('checks', {})) == {'columns', 'indexes', 'foreign_keys'}
                    and all(check.get('status') == 'MATCHES_CHECKED_REQUIREMENTS'
                            for check in item['checks'].values())
                    for item in tables.values()))
        if not schema_ok:
            print(json.dumps({'verification': 'FAILED', 'schema_checks': comparisons,
                              'inventory_status': report.get('inventory_status'),
                              'error_types': [item.get('error_type')
                                              for item in report.get('errors', [])]}, indent=2))
            raise SystemExit(3)
        for table in Base.metadata.sorted_tables:
            if connection.execute(select(table).limit(0)).all():
                raise RuntimeError('Zero-row check returned data')
        print(json.dumps({
            'verification': 'PASSED',
            'connection_status': 'CONNECTED',
            'database': actual_db,
            'default_schema': 'dbo',
            'administrator_context': context.get('database_principal') == 'dbo',
            'alembic_revision': '003',
            'application_tables_verified': len(tables),
            'schema_checks': comparisons,
            'orm_zero_row_reads_passed': True,
            'database_mutations_occurred': False,
            'migrations_executed': False,
            'default_configuration_is_sqlite': True,
            'active_application_database_changed': False}, indent=2))
except Exception as error:
    print(json.dumps({'verification': 'FAILED', 'error_type': type(error).__name__,
                      'database_mutations_occurred': False}))
    raise SystemExit(2)
finally:
    if engine is not None:
        engine.dispose()
PY
)
```

Exit 0 plus verification PASSED is the success criterion. Exit 2/3, 124, missing cache,
or any timeout means stop; do not retry automatically, invoke login, migrate, grant
permissions or alter the environment. A timeout may produce no JSON. SQLAlchemy disposes
the engine on ordinary exit and closes/rolls back read transactions; these operations
are not application data writes. A successful report describes only this diagnostic,
not the running FastAPI process's configuration independently inspected over HTTP.

## What this verifies / what it does not

This can verify the same Entra/ODBC adapter used by FastAPI, identity pinning, encrypted
connectivity, schema/history consistency, concurrency column definitions, required index
and FK metadata, and SQLAlchemy SELECT compilation/execution against real tables.
TOP 0 reads request no application rows. No snapshots of actual application contents or
checksums are needed: the command contains no DML or schema changes.

This does not verify INSERT/UPDATE/DELETE, optimistic-concurrency races, API transaction
behavior, complete Azure-backed policy workflows, restricted runtime privileges, or ADLS
access. SQLite UI workflows and an Azure read-only check are useful demo evidence but
must not be presented as full Azure end-to-end runtime validation.

Do not use POST/PUT/DELETE endpoints for this check. Even simulation and validation can
append audit/execution rows; export routes also write metadata and potentially ADLS
artifacts. Runtime sessions may commit within handlers, so an outer rollback cannot be
assumed to undo HTTP tests. Future write tests need explicit approval, labeled synthetic
records, a reviewed transaction/retention plan, and no modification of existing data.
No write-test commands are authorized or supplied here.

## Future least-privilege production requirements

Obtain an approved separate runtime principal and keep migration privileges separate.
For a local development user, reuse the existing CLI method with its own identity pins
and private cache. For unattended operation, review a workload identity/credential
appropriate to the eventual deployment and implement an explicit supported provider;
the current default CLI-user path is not a production workload identity design. Do not
introduce services or create identities as part of this phase.

Apply only the table-level DML matrix in docs/AZURE_SQL_RUNTIME_ACCESS_PLAN.md using an
administrator after separate approval. Audit public, group and role inheritance and
ownership; runtime must not enter as dbo. Verify both required and excluded privileges,
then approve controlled behavioral tests and a separate runtime-switch decision. No
production readiness or least-privilege acceptance is claimed by this temporary check.

Official references:
https://learn.microsoft.com/en-us/azure/azure-sql/database/logins-create-manage?view=azuresql
https://docs.sqlalchemy.org/en/21/dialects/mssql.html#connecting-to-databases-with-access-tokens
