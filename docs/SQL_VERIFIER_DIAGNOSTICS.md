# Sanitized Azure SQL verifier diagnosis

4 November 2026. No Azure resource, database/schema/permission, App Service setting or hosted release was modified. No migrations or full application test suites were run for this diagnostic change. No actual SQL connection was established in the agent environment.

## Findings

- `pyodbc` imports successfully; ODBC Driver 18 is registered and its configured shared library loads successfully.
- Existing project-local CLI cached account is accessible. This does not prove live token refresh.
- Agent environment still fails SQL-hostname DNS resolution. Updated verifier reports `DNS_RESOLUTION_UNAVAILABLE`, stage `dns`, with driver/configuration checks passing.
- The operator's Ubuntu terminal independently passed token acquisition, DNS and TCP. Its later generic BLOCKED result cannot establish whether the underlying cause is login, database mapping, permissions, schema mismatch or implementation failure.
- The previous verifier discarded these distinctions: the SQL adapter sanitized native exceptions, the schema contract sanitized individual schema rejections, and the CLI reduced everything to one message. This was a diagnostic implementation defect, not evidence of a database defect.

## Change

`scripts/verify_schema_compatibility.py` now reports the failing stage, passed prechecks, allowlisted categories/SQLSTATE/native codes and, for a schema contract failure, only expected model object names. It reads the already-reviewed database identity/Alembic SELECTs and existing schema/permission contract only after successful connection. An observed revision is printed only in a safe three-digit format.

`scripts/sql_diagnostics.py` traverses wrapped exception contexts internally and emits no raw exception text, token, parameter, connection string or database content. SDK diagnostic logging is suppressed in this CLI. `backend/app/schema_compatibility.py` labels the existing fail-closed rejections without changing their conditions or public HTTP 503 detail.

The verifier explicitly labels permission checks as `executing_cli_identity` and does not claim to verify the separate App Service managed identity. In particular, `REQUIRED_EFFECTIVE_PERMISSION_MISSING` can mean the operator lacks runtime-equivalent CRUD permission; this does not by itself show the actual hosted runtime is missing it. Do not grant write privileges to a deliberately read-only operator merely to obtain PASS.

| Category | Interpretation / smallest safe next check |
|---|---|
| `ODBC_DRIVER_UNAVAILABLE` | Check Driver 18 registration/shared libraries on the machine running the verifier. |
| `DNS_RESOLUTION_UNAVAILABLE`, `SQL_TCP_UNAVAILABLE` | Resolve local network access; token acquisition/SQL permissions are not yet tested. |
| `TOKEN_ACQUISITION_UNAVAILABLE` | Existing context cannot acquire a token. Stop; no automatic login or identity switch. |
| `IDENTITY_PIN_OR_EXPIRY_MISMATCH` | Approved tenant/object pins or remaining SDK token lifetime do not match. Verify the intended identity before any change. |
| `SQL_FIREWALL_DENIED` / 40615 | SQL rejected the client's network route. No firewall edits are authorized. |
| `SQL_LOGIN_DENIED` / 18456 | SQL rejected login; existing identity, target and database user mapping require read-only administrator review. This code alone does not prove a missing user. |
| `SQL_DATABASE_ACCESS_DENIED` / 4060 or 916 | Target database or access/mapping problem. Verify target and existing user access. |
| `SQL_PERMISSION_DENIED` / 229 | A SELECT/metadata query was denied. Establish the exact approved identity and scope before proposing a grant. |
| `ALEMBIC_HISTORY_MISSING_OR_NOT_VISIBLE`, `REQUIRED_TABLE_MISSING_OR_NOT_VISIBLE` | Absence and metadata invisibility remain distinct possibilities. Inspect using the reviewed SQL under an authorized metadata-reading identity. |
| `REQUIRED_EFFECTIVE_PERMISSION_MISSING` | The executing principal lacks the named operation; not proof of actual runtime privileges. |
| `COLUMN_*`, `PRIMARY_KEY_MISMATCH`, `REQUIRED_INDEX_*`, `UNIQUE_CONSTRAINT_MISSING`, `FOREIGN_KEY_MISMATCH`, `HISTORY_TRIGGER_*` | A specific schema contract did not match. Inspect only; do not migrate or repair automatically. |
| `SCHEMA_QUERY_OR_IMPLEMENTATION_FAILURE` | A query/reflection/implementation error occurred. Do not assume a grant is required. |

## Operator rerun

Use the same already-authorized project-local context in the Ubuntu terminal where DNS, token acquisition and TCP passed:

```bash
cd "/home/sigmoid/AI governance policy validator"
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" \
  .venv/bin/python -B scripts/verify_schema_compatibility.py \
  --server sql-governance-validator-dev-atiya.database.windows.net \
  --database sqldb-governance-validator-dev --connect
```

Do not add `--require-sso` when verifying the pre-migration 004 bridge. That flag intentionally requires 005. Share only the resulting sanitized JSON; no tokens, native tracebacks, environment files or secret values are needed.

## Validation and approval boundary

15 focused diagnostic/redaction tests passed; changed-file lint/format and diff checks passed. No full frontend/backend suite was repeated. The earlier compatibility ZIP remains unchanged; these diagnostic-only source changes were not deployed or repackaged into that frozen artifact.

Hosted migration 005 prerequisites remain **NOT ESTABLISHED**: independent schema/revision, actual runtime permissions/metadata visibility and current recovery readiness still need successful read-only evidence. No new hosted-change approval is needed merely to rerun this already-approved read-only verifier in the existing working context. Identity changes, grants, mapping changes, firewall changes, migration, configuration saves, restarts and deployments still require separate explicit approval.

## Confirmed SQL Server reflection defect and fix

The operator subsequently confirmed successful SQL connection, target identity and revision 004, followed by schema-stage failure with no SQLSTATE. Local inspection reproduced the defect: SQLAlchemy 2.0.55's Microsoft SQL Server dialect inherits an unimplemented `get_unique_constraints()` method. The verifier called it on the first table (`policies`, schema `dbo`), raising Python `NotImplementedError` before issuing a unique-constraint SQL query. Earlier mocks delegated reflection to SQLite, where this method is supported, masking the incompatibility.

The smallest fix is in `backend/app/schema_compatibility.py`: for MSSQL, derive expected unique column sets from the already-reflected backing unique indexes returned by the supported `get_indexes()` method. SQL Server's implementation reads `sys.indexes`, `sys.index_columns`, `sys.tables` and `sys.schemas`, including unique-constraint backing indexes. SQLite retains its existing unique-constraint reflection. Missing/non-unique/wrong-column indexes still fail the contract; enabled/filter checks and all other readiness/authentication/permission checks remain intact. No database change is required.

New `backend/tests/test_mssql_schema_reflection.py` reproduces the real dialect's unsupported call and checks valid/missing/non-unique/wrong-column constraint cases for both reviewed revisions without database creation or network access. Combined focused result: **24 passed, 0 failed** (9 reflection regressions and 15 existing sanitized-diagnostic tests). Changed-file lint/format and diff checks passed. No full suites, migrations or hosted operations were run. Rerun the same Ubuntu command above; do not add `--require-sso` for revision 004.
