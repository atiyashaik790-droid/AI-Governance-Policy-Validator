# Azure SQL integration phase report

## Result

**IMPLEMENTED / LOCALLY TESTED; LIVE AZURE SQL CONNECTION NOT TESTED.** The adapter is ready for the dependency/login/permission validation gates. System dependencies, identity configuration and explicit user approvals remain prerequisites. The live Uvicorn application remains on SQLite; `/ready` and authenticated `/api/settings` both returned HTTP 200 and the database diagnostic reported `sqlite` after implementation. Existing SQLite schema revision is 003 and existing policy records remain present. Private `.env` remains mode 0600 and was not edited.

## Files created or modified

Created:

- `backend/app/azure_sql.py`: explicit organizational CLI identity, tenant/user binding, ODBC token injection, renewal at new handshakes, TLS enforcement, pool setup and sanitized exceptions.
- `backend/tests/test_azure_sql.py`: synthetic identity/transport contracts, local pool tests, shared Alembic engine checks, read-only probe safety and API failure behavior.
- `scripts/check_azure_sql.py`: explicitly requested, SELECT-only target probe and effective runtime-permission checks without application database selection changes.
- `docs/AZURE_SQL_SETUP.md`: exact approval-gated dependency commands, organizational login, configuration, least-privilege permissions, read-only validation and migration/switch gates.
- `docs/AZURE_SQL_PHASE_REPORT.md`: this evidence and handoff report.

Modified:

- `backend/app/database.py`: explicit engine factory and SQLite-preserving selector, no SQL-to-SQLite fallback.
- `backend/app/config.py`: only two new settings, `azure_sql_tenant_id` and `azure_sql_user_object_id`.
- `.env.example`: placeholder-only identity settings; active example database remains SQLite.
- `.gitignore`: ignore the dedicated organizational CLI cache.
- `README.md`: corrected the previous unsupported ODBC authentication advice and linked the runbook.
- `docs/READINESS.md`: updated backend test counts and SQL adapter status.

Unchanged: private `.env`, application data, database models/schema revisions, dependency manifests, Docker files, Azure resource settings, users/grants and firewall rules. Alembic's existing environment already imports the application engine and therefore required no edit.

## Environment and dependencies

Host: Ubuntu 25.10 (questing), x86_64. Existing Python dependencies are sufficient: pyodbc 5.3.0, azure-identity 1.27.0, SQLAlchemy 2.0.55, Alembic 1.20.1. No Python packages were installed.

Missing system dependencies: unixODBC runtime/libodbc.so.2, ODBC Driver 18, ODBC command-line diagnostics and Azure CLI. Microsoft lists ODBC 18.6 for this OS, and its native Ubuntu 25.10 repository contains 18.6.2.1-1 amd64. Azure CLI's tested APT list does not include Ubuntu 25.10; the runbook proposes Microsoft's documented jammy-repository fallback, requiring separate informed approval and actual installation validation. No compatibility success is claimed before that validation.

## Commands executed

Read-only inspection: `pwd`, `rg`, file reads including `/etc/os-release`, `uname -m`, Python package metadata/version checks, `ctypes.util.find_library('odbc')`, pyodbc import checks and command-availability checks. Official Microsoft and SQLAlchemy documentation was reviewed.

Local implementation formatting/checks:

```bash
.venv/bin/ruff format backend/app/azure_sql.py backend/app/database.py backend/app/config.py
.venv/bin/ruff check backend/tests/test_azure_sql.py --fix
.venv/bin/ruff format backend/tests/test_azure_sql.py scripts/check_azure_sql.py
.venv/bin/ruff check backend scripts
.venv/bin/ruff format --check backend scripts
.venv/bin/python -B scripts/check_azure_sql.py --help
```

Tests (authorized execution outside the sandbox's known TestClient restriction):

```bash
cd backend
../.venv/bin/pytest -q tests/test_azure_sql.py  # initial 37 checks passed
../.venv/bin/pytest -q                       # initial combined 81 passed
../.venv/bin/pytest -q                       # final 86 passed after five probe/selector tests
```

Verification also used a read-only SQLite connection (`mode=ro`) to inspect the existing schema revision and policy count, and HTTP GETs to the existing local `/ready` and `/api/settings`. No live Azure SQL connection was attempted. The new SQL read-only probe was exercised only with mocks and `--help`, never against the Azure database.

One auxiliary verification command mistakenly imported a nonexistent module and failed with ModuleNotFoundError. It was corrected; the proper configuration/data inspection passed. This was not a failed automated test and made no database changes.

## Actual test results

- Final backend suite: **86 passed, 0 failed, 0 skipped**, comprising the original 44 tests and 42 added Azure SQL/probe checks.
- Regression failures: **0**.
- Ruff lint: **passed** across backend/scripts.
- Ruff formatting check: **23 files already formatted**, passed.
- One existing upstream Starlette HTTPX TestClient deprecation warning remains.
- Frontend not retested: no frontend code changed in this phase.

Coverage includes SQLite compatibility, token packing/scope, wrong/missing tenant/user, missing CLI credentials, expired/malformed tokens, native-driver failures, TLS downgrade rejection, incompatible connection parameters, pool reuse, renewal after disposal/recycle, failed-pre-ping reconnection, sanitized API/transport errors, no fallback, Alembic engine reuse and a probe that issues only fixed SELECTs and preserves the active configuration.

These tests do not prove native ODBC behavior, organizational sign-in, current firewall accessibility, live Azure SQL permissions, real SQL Server schema execution or full Azure-backed application operation. Those remain controlled integration gates.

## Approval boundary and exact next action

The next action is **review and approve Gate 1 in `docs/AZURE_SQL_SETUP.md`**: native Ubuntu unixODBC/Driver 18.6.2.1 installation and EULA acceptance, plus the explicitly documented Azure CLI jammy repository fallback. No privileged installation has run. If the fallback is not company-approved, agree on an approved supported CLI platform/installation first.

Then authenticate locally with the organizational tenant/user, set the two identifier fields without changing the SQLite URL, verify the driver, and run the SELECT-only probe. Have the administrator review identity/table permissions. Request a **separate explicit approval** for Azure SQL migrations after the target/schema/permission review. Switch the application's active URL only after successful validation and approval; retain SQLite and plan any data copy separately.
