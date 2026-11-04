# Phase 5 — FastAPI database integration assessment

Prepared locally. No Azure SQL connection, cloud API call, live HTTP test, root .env
change, running-process configuration change or cloud resource/permission/schema change
is authorized or performed in this phase. The standalone ORM write test is accepted as
user-verified evidence and is not repeated.

## Database architecture and implemented changes

- app/config.py: Settings defaults to SQLite; an explicitly exported DATABASE_URL
  overrides .env only for that process. No new DB selection variable/provider is needed.
- app/database.py:create_database_engine constructs SQLite or the existing Entra-enabled
  mssql+pyodbc engine. No SQL failure falls back to SQLite. SessionLocal binds to that
  selected engine. get_database owns one session per request, commits on success and
  rolls back on failure. There is no repository package: routers/services/CRUD are
  currently app/main.py functions using SQLAlchemy select and ORM records.
- app/azure_sql.py retains tenant/user token pinning, new-connection token acquisition,
  Driver 18, TLS/certificate validation, pool recycling/pre-ping and sanitized failures.
- app/models.py retains eight models, four foreign keys, immutable Version/Audit hooks,
  integer policy/review version counters and client-generated string UUID primary keys.

Local fixes in app/main.py:

1. Depends(get_database, scope='function') finishes session commit/rollback before
   sending an HTTP success response. Default request-scoped yield cleanup occurs after
   response sending in current FastAPI; that could conceal a late commit failure.
   The installed FastAPI 0.162.0 supports function scope. Governance's explicit pre-release
   commit is retained: returning content still requires audit persistence first.
2. Feedback averages use AVG(CAST(rating AS FLOAT)); SQL Server AVG over integers would
   truncate fractional averages. SQLite remains supported.
3. Flush changed policy/review records before serializing so response row_version
   reflects the newly persisted optimistic counter, not the old in-memory value.

No schema/model/migration changes were needed. Existing tenant predicates, server-side
RBAC, immutable audit rules, content withholding and exception sanitization remain.
No deployment/app factory rewrite or extra database abstraction was introduced.

## Complete affected endpoint inventory

All paths below are actual FastAPI routes, including dynamically registered operations.
The database dependency is function-scoped for every DB-backed endpoint. All mutating
workflows append audit metadata in the same request transaction unless noted otherwise.

| Method/path | Tables and operations |
| --- | --- |
| GET /health | No DB/provider access |
| GET /ready | SELECT 1; no application rows |
| GET /api/settings | SELECT 1 and sanitized configuration-presence diagnostics |
| GET /api/policies | policies SELECT with tenant filter/pagination |
| POST /api/policies | policies INSERT; audit_events INSERT |
| GET /api/policies/{id} | policies SELECT, tenant-scoped |
| PUT /api/policies/{id} | policies SELECT/UPDATE/version increment; audit INSERT |
| DELETE /api/policies/{id} | policies SELECT/DELETE only unpublished draft; versions SELECT; audit INSERT |
| POST /api/policies/{id}/simulate | policy SELECT, audit INSERT; moderation may be called outside fixture mode |
| GET /api/policies/{id}/versions | policies/versions SELECT, tenant filtering and ordered pagination |
| POST /api/policies/{id}/submit | policy SELECT/UPDATE; audit INSERT |
| POST /api/policies/{id}/approve | policy SELECT/UPDATE; audit INSERT; Reviewer/Admin |
| POST /api/policies/{id}/publish | policy SELECT/UPDATE; versions SELECT/INSERT unique policy/number; audit INSERT |
| POST /api/policies/{id}/activate | policy/version SELECT; assignment SELECT/INSERT or UPDATE; audit INSERT |
| POST /api/policies/{id}/enable | policy SELECT/UPDATE; audit INSERT |
| POST /api/policies/{id}/disable | policy SELECT/UPDATE; audit INSERT |
| POST /api/policies/{id}/archive | policy/version/assignment SELECT; policy UPDATE unless active; audit INSERT |
| POST /api/governance/validate-input | policy/version/assignment SELECT; execution/audit INSERT; optional review INSERT |
| POST /api/governance/validate-output | Same persistence; inspects supplied output |
| POST /api/governance/generate | Same persistence plus input/generation/output gates; safe response only after explicit commit |
| GET /api/audit/executions | execution SELECT with tenant filter/pagination |
| GET /api/audit/events | audit SELECT with tenant filter/pagination |
| GET /api/audit/summary | policies/versions/assignments/executions/reviews SELECT |
| GET /api/analytics/overview | Same aggregate handler |
| GET /api/analytics/violations | Same aggregate handler |
| GET /api/analytics/compliance | Same aggregate handler |
| GET /api/reviews | reviews SELECT; Reviewer/Admin/Auditor |
| GET /api/reviews/{id} | review/execution SELECT through tenant-owned review |
| POST /api/reviews/{id}/approve | review SELECT/UPDATE/version increment; audit INSERT; metadata-only resubmission |
| POST /api/reviews/{id}/reject | review SELECT/UPDATE/version increment; audit INSERT |
| POST /api/feedback | execution SELECT with tenant filter; feedback/audit INSERT |
| GET /api/feedback/summary | feedback SELECT/count/floating average |
| POST /api/reports/export | export INSERT then UPDATE; execution SELECT; audit INSERT; may upload ADLS before DB commit |
| GET /api/reports/exports | exports SELECT with tenant filter/pagination |

No SQLite-specific business SQL is used by those handlers. SQLite PRAGMA exists only
in its engine branch. MSSQL pagination has ORDER BY. Existing PK/FK/string lengths and
optimistic fields match verified revision 003. No runtime migrations are performed.

## Workflow status / limits

| Workflow | Local acceptance | Live Azure HTTP status |
| --- | --- | --- |
| Temporary explicit DB selection | PASS: settings precedence, Azure engine delegation and no-fallback contracts | NOT TESTED |
| Policy CRUD/lifecycle/version publication | PASS: request integration with disposable DB and mock Azure selector | NOT TESTED |
| First activation/replacement/enable/disable | PASS locally | NOT TESTED |
| Governance, executions and audit | PASS locally with fixture providers; pre-release commit preserved | NOT TESTED |
| Review hold/disposition/concurrency response | PASS locally | NOT TESTED |
| Feedback including fractional averages | PASS locally; MSSQL FLOAT expression compiled | NOT TESTED |
| Exports JSON/CSV and failure recording | PASS locally with stubbed upload; no ADLS call | NOT TESTED |
| Commit errors / stale updates before HTTP success | PASS locally: 503/409 and rollback | NOT TESTED |
| RBAC/tenant filtering/immutable history | PASS local regression suite | NOT TESTED in live Azure HTTP |

The mock Azure selector routes to a disposable SQLite engine; it tests application
selection/session wiring, not live ODBC semantics. Real Azure ORM writes/schema have
already passed separately according to the user, but that is not HTTP acceptance.
No workflow is labeled live HTTP PASS from those lower-layer results.

## Review-gated live HTTP proposal — not executed

This is a COMMITTED SYNTHETIC DATA test, unlike the standalone rollback-only script.
Each request has its own session and transaction. Successful mutation endpoints commit;
governance commits explicitly before releasing any response, then dependency teardown
may close another empty transaction. These commits cannot be undone by a separate
client transaction, test harness rollback, process shutdown or later HTTP error.

Before approval, choose a fresh UUID synthetic tenant, a separate application bearer
credential set (not new Entra identities), an isolated loopback port 8001, and whether
synthetic committed history may be retained. Do not reuse existing demo tenants/tokens
or use any pre-existing policy ID. Preserve a private run manifest with tenant and IDs
returned by the server, request/operation outcomes and credential-file location. Never
log raw bearer tokens. Check all eight tables for that exact tenant before the first
write; nonzero counts STOP rather than adopt/delete existing records.

The server must use fixture generation/moderation, regex PII, and disabled ADLS
configuration. Fixture provider labels remain visible in results. This phase tests
Azure SQL with the actual HTTP/session boundary, not real cloud generation/export.
ADLS success testing is a separate future approval: the current upload occurs BEFORE
DB commit, so a later commit failure can leave an ADLS artifact even if SQL rolls back.
No cross-service atomic transaction/outbox is implemented or claimed.

### Proposed isolated server startup (requires approval; do not run yet)

From root, this future command sets configuration only in its child process, creates
new demo bearer credentials in a private /tmp manifest, and starts a separate server.
It leaves .env, the SQLite process/port and existing Azure CLI cache unchanged. Starting
a SQL-configured process and using it requires explicit review approval.

```bash
.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path
import secrets
import sys
import uuid

root = Path.cwd()
run_id = str(uuid.uuid4())
tenant = 'http-sql-test-' + run_id
sys.path.insert(0, str(root / 'scripts'))
from test_azure_sql_http import create_manifest, demo_accounts
tokens = {}
for role in ('Admin', 'Policy Owner', 'Developer', 'Reviewer', 'Auditor', 'Foreign Admin'):
    token = secrets.token_urlsafe(32)
    tokens[role] = token
accounts = demo_accounts(run_id, tokens)
manifest = Path('/tmp') / ('governance-sql-http-' + run_id + '.json')
create_manifest(manifest, run_id, tokens)
os.environ.update({
    'AZURE_CONFIG_DIR': str(root / '.azure-sql-cli'),
    'DATABASE_URL': 'mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-governance-validator-dev?driver=ODBC+Driver+18+for+SQL+Server',
    'DEMO_ACCOUNTS_JSON': json.dumps(accounts),
    'PROVIDER_MODE': 'fixture', 'PII_MODE': 'regex',
    'ADLS_ACCOUNT_URL': '', 'ADLS_FILE_SYSTEM': '',
    'AZURE_OPENAI_ENDPOINT': '', 'AZURE_OPENAI_API_KEY': '', 'OPENAI_API_KEY': ''})
sys.path.insert(0, str(root / 'backend'))
print('Private run manifest:', manifest)  # Path only; never print its contents/tokens.
import uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=8001, workers=1, log_level='warning')
PY
```

Do not add --reload or multiple workers. Confirm the private CLI cache is authenticated
and identity pins remain correct before startup. A missing driver/configuration must
fail; no login, grant or fallback is allowed. Require GET /api/settings database=mssql
and provider_mode=fixture before mutations. Bound client HTTP requests to 15 seconds,
provider timeouts remain bounded, and bound the overall interactive test session to
an agreed duration (for example 5 minutes). Do not run the existing smoke_demo.py unchanged:
it targets the normal demo and does not supply this run's tenant/credentials/ID manifest.

### Proposed request sequence and acceptance

Use an isolated client reading tokens directly from the private manifest into memory,
never token-bearing shell arguments, logs or screenshots. Before approval, review the
client/driver if automating this sequence; none is automatically executed by this plan.

1. Health/readiness/settings, exact-tenant absence, revision/schema preflight. STOP if
   target, fixture mode or identity differs from the approved configuration.
2. Admin creates one disposable draft; GET/PUT/DELETE only that returned ID. Verify
   deletion and audit persistence. Record each response ID privately.
3. Create main policy; simulate, submit, approve, publish and activate. Compare returned
   counters with fresh GET; versions are immutable. Repeat publication/activation with
   a second version to exercise assignment UPDATE. Verify enabled/disabled behavior.
4. Fixture validate-input, validate-output, safe generate, secret BLOCK and output BLOCK;
   verify no safe response on blocks and execution/audit persisted before success.
5. Publish a HUMAN_REVIEW rule; hold synthetic text, inspect review, approve one and reject
   another; verify counters/metadata-only resubmission and no content release.
6. Submit feedback ratings 2 and 3 against run-created execution IDs; average must be 2.5.
7. JSON/CSV export attempts with ADLS disabled must persist FAILED attempts and audit rows,
   not claim successful uploads. List exports/analytics/audits and compare run IDs/counts.
8. Developer forbidden actions return 403; foreign-tenant access to run-created IDs
   returns 404 or documented withholding; no access to pre-existing tenants is attempted.
9. New independent admin SQL connection verifies retained synthetic rows, references,
   counters, immutable snapshots and sanitized metadata. This acceptance expects
   COMMITTED records, not zero rows. Record these retained counts in the private report.

Readiness/health alone do not certify application writes. PASS requires all reviewed
steps and independent persistence checks; any response/schema/tenant/provider mismatch,
timeout or uncertain commit is FAIL/INCOMPLETE. No negative DB outages/grants are induced
on the live database; local fault-injection tests cover those code paths.

### Failure recovery / retention / cleanup

On failure, stop issuing mutations, preserve tenant/returned IDs, inspect through a
new read-only session, and stop the test server with Ctrl-C. An HTTP timeout or 5xx is
not proof of rollback: a commit may have succeeded before the client lost its response.
Find run-created records by exact synthetic tenant, record any unknown outcomes, and
never blindly retry POSTs. The API does not implement general idempotency keys.

Default recovery is retain labeled synthetic records and keep normal FastAPI on SQLite.
DELETE endpoints cannot remove published versions, audit events, executions or reviews.
No automatic cleanup is provided. A separately approved administrator cleanup must
validate exact run tenant AND explicit PKs/references/counts, check incoming foreign keys
and delete in reverse dependency order in one reviewed transaction. Immutable ORM hooks
mean such cleanup cannot be represented as normal application operations. Never delete
by prefix, reset the database, downgrade, stamp history or broaden runtime permissions.
Credential manifests may be removed only after the test process stops and evidence is
retained privately. No schema/resource/permission changes are part of this proposal.

## Remaining blockers

- Explicit approval for the temporary separate SQL-backed server, committed synthetic
  HTTP writes and data retention; new fixture application tokens are local demo credentials.
- Review the implemented bounded manifest-recording HTTP driver before an automated live run.
- dbo remains administrator access: not least-privilege production runtime.
- Azure-backed HTTP acceptance, fractional SQL Server aggregate behavior and API transaction
  results remain NOT TESTED live. Existing standalone ORM tests must not be repeated.
- ADLS uploads and real provider calls are intentionally out of this SQL integration test.
- Production enterprise identity, durable export recovery and DB privilege isolation remain
  separate work; no new Azure services are introduced by this assessment.

## Implementation continuation — 29 October 2026

Implemented `scripts/test_azure_sql_http.py` and its disposable local tests in
`backend/tests/test_sql_http_plan.py`. The driver targets only `http://127.0.0.1:8001`,
with proxies and redirects disabled, 15-second HTTP timeouts, a 300-second POSIX alarm,
and no request retries. Native SQL calls retain existing connection/query timeouts;
the alarm is not a substitute for those native timeouts. The server is started and
stopped separately using the reviewed startup proposal above. The driver never starts
or reconfigures the normal application.

Safe default, executable without approval and without file/network access:

```bash
.venv/bin/python scripts/test_azure_sql_http.py
```

After separate approval of the isolated server and committed synthetic history, start
the proposed server above and use its printed private manifest path in a second terminal:

```bash
# REVIEW ONLY — live committed writes require separate approval.
.venv/bin/python scripts/test_azure_sql_http.py \
  --execute-approved-http-test \
  --manifest /tmp/governance-sql-http-REPLACE_WITH_RUN_UUID.json
```

The manifest must be an existing owner-only 0600 regular file, without symlinks, with
canonical run UUID, matching `http-sql-test-<uuid>` tenant and the three required tokens.
A nonblocking exclusive file lock prevents two drivers from using the same manifest.
The driver reuses only the existing project `.azure-sql-cli` cache and root identity
pins. It requires the configured default database to remain SQLite. No login, migrations,
provider calls, grants, automatic cleanup or fallback is implemented by the driver.
The startup environment mapping above disables the Azure generation endpoint and keys. Diagnostics
must report all three external provider integrations BLOCKED before HTTP mutations.

Before the first HTTP write, the reviewed schema preflight and exact-tenant zero counts
must pass on the pinned Azure database. Each HTTP operation's intent is flushed and
fsynced to the private manifest before transmission; received statuses and returned
UUIDs are checkpointed afterward. Tokens and response bodies are never printed.
Any manifest with an existing `http_test` entry is refused, including incomplete/failed
runs. This intentionally requires manual inspection after interruption rather than a
resumable sequence that might repeat a committed POST. Preserve a damaged manifest;
never recreate it with the same run UUID to bypass this check.

The actual automated sequence covers draft PUT/DELETE, two publications and replacement
activation, simulation, input/output validation, safe generation, blocked secrets and
output, disable/enable, review approve/reject with counters, fractional feedback, failed
JSON/CSV exports, analytics/audits, developer rejection and foreign-tenant rejection.
Only run-created identifiers are used. Independent SQL verification expects these
retained counts: policies 1, versions 2, assignments 1, audits 29, executions 7, reviews 2,
feedback 2, exports 2. It also checks immutable version snapshots, active-version link,
policy ID, review dispositions/counters, feedback ratings, export statuses and execution
IDs against HTTP evidence. A mismatch cannot report `HTTP_SQL_TEST_PASSED`.

All failures print sanitized exception types and preserve FAILED_OR_INCOMPLETE status
when the manifest remains writable. A hard kill, full disk or interrupted filesystem
write may leave the last durable state incomplete or unreadable; it never constitutes
PASS. Stop mutations and inspect the exact tenant with an independent read-only SQL
connection. A failed write test stays failed even when later reads succeed. Retain
synthetic history; deletion remains a separate reviewed operation.

Local tests exercise the real HTTP sequence on a disposable SQLite fixture with
substituted diagnostic labels, plus the independent-verification logic on that local
transport. This does not establish live ODBC, Azure HTTP, native SQL fractional aggregate,
least-privilege runtime or ADLS acceptance. No live execution was performed in this
continuation. The standalone rollback-only ORM write test was not repeated.

Validation for this continuation: full backend suite **176 passed, 0 failed**, including
five new driver checks; Ruff lint passed across backend/scripts; Ruff format check
passed for all 31 Python files. The existing upstream Starlette/httpx deprecation
warning remains. TestClient integration ran outside the sandbox because of its known
sandbox hang, using disposable local databases only. The default driver invocation
reported OFFLINE_PLAN_ONLY with connection_attempted=false and writes_executed=false.
No frontend files changed, so frontend checks were not repeated.

## Final safety review and local corrections — 29 October 2026

This section supersedes the earlier implementation's manifest/verification details.
Scope was local source review, corrections and disposable SQLite validation only.
No Azure connection, cloud API, SQL-backed server, approved live HTTP workflow, Phase 4
live ORM write test, schema/grant/resource change, credential change, .env edit, or Git
commit/staging operation was performed. SQLite remains the configured default.

### SQLAlchemy version comparison: proved, then made explicit

The original `Connection.execute(select(Version)).mappings().one()` is a Core execution:
it expands the mapped table into column keys. A regression test proves that its mapping
matches the API's six-field version JSON (`id`, `policy_id`, `tenant`, `number`, `document`,
`created`). The similarly spelled `Session.execute(select(Version))` returns an ORM
mapping under `Version`; it is not interchangeable. The original Core comparison was
not a confirmed mapping bug.

The corrected verifier explicitly projects `*model.__table__.columns`. VersionSnapshot
validates both sides with strict types and forbids extra fields; version numbers must
be positive integers, not strings or booleans. It compares all six serialized fields,
canonical UUIDs, exact tenant, main policy ID, version numbers 1 and 2, and the exact
serialized policy documents captured before each publication. A changed snapshot is
rejected even if the API and database agree on the same incorrect document. The active
assignment must reference the second version of this run's policy.

### Confirmed gaps corrected

- Path-based reopening after locking allowed the locked file and checkpoint target to
  diverge. ManifestStore now uses one O_NOFOLLOW, owner-only 0600 regular-file descriptor
  for reading, exclusive nonblocking locking and every checkpoint. It rejects parent
  symlinks, hardlinks, ownership/mode mismatches, path/inode replacement and files inside
  the repository. It checks file identity both before and after each fsynced checkpoint.
- The original truthiness check accepted a falsey `http_test` marker. Presence of that
  key now rejects reuse, including null, empty string and empty object. New manifests
  also require empty record provenance, a canonical UUID/matching tenant, distinct
  credentials and safe bearer syntax. Malformed or interrupted JSON cannot be loaded.
- A secondary failure while recording a failure could escape with an unsanitized
  traceback. The failure path now reports only exception type, FAILED_OR_INCOMPLETE and
  whether its checkpoint was saved. A failed checkpoint poisons its store and cannot be
  retried as if durable evidence existed. The driver also becomes permanently stopped
  after a request/checkpoint failure, even if a caller catches the exception.
- Initial authentication checks covered only Admin. Before HTTP writes, diagnostics now
  verify Developer's actual role/tenant and Foreign Admin's Admin role in the exact
  `<synthetic-tenant>-foreign` tenant. Missing authentication must return 401. The later
  workflow still checks Developer 403 and foreign policy/review/feedback 404 responses.
- Aggregate/status checks did not establish all relationships. The driver now records
  creation provenance and final API snapshots, then independently reads explicit columns
  in all eight SQL tables and compares exact typed rows and counts. It checks policy
  documents, active assignment, execution policy/version/fixture model/decision, review
  execution links/dispositions/counters, feedback links/ratings, export IDs/formats/status,
  and the full audit action/resource multiset derived from successful HTTP operations.
  Execution content fields must remain absent from persisted metadata. All records are
  tenant-scoped; foreign-tenant counts must remain zero before and after the run.
- Default HTTP transport retries are now explicitly zero. Redirects/proxies remain off.
  SIGTERM joins deadline and keyboard interruption handling; there is no reconnect,
  automatic HTTP retry, cleanup or write-based recovery path.

### Manifest creation, credentials and evidence

The future startup proposal now imports the locally tested `demo_accounts` and
`create_manifest` helpers. Account hashing/tenant separation and file creation are
covered with fixed synthetic test strings; no real credentials were generated during
this review. Creation refuses an existing path, uses O_EXCL/O_NOFOLLOW, explicitly sets
0600 and fsyncs both the file and containing directory. Tokens are accepted in Python
memory and stored only in the private manifest; they are not shell arguments or output.
No response bodies, bearer headers or exception messages are printed by the driver.
Tests check normal HTTP logs and failure output for fixture-token leakage.

The manifest must stay outside the repository, normally at the proposed absolute /tmp
path. `.gitignore` additionally excludes `governance-sql-http-*.json` as defense against
accidental copies. It does not make renamed credential files safe to commit, nor remove
already tracked files. No Git repository operations were used during this review.
The startup code in this document remains a future, separately approved action; it was
not executed to validate the helpers.

The retained count contract remains unchanged:

| Table | Expected rows |
| --- | ---: |
| policies | 1 |
| policy_versions | 2 |
| active_policy_assignments | 1 |
| audit_events | 29 |
| validation_executions | 7 |
| human_review_cases | 2 |
| feedback_records | 2 |
| evaluation_exports | 2 |

The disposable local workflow verifies these counts and preserves a separate existing
tenant's rows byte-for-byte. Negative tests mutate only disposable test records and
exercise wrong counts, tenants, immutable documents, IDs, version types and links,
including an incorrect relationship on which API evidence and SQL records agree.

### Acceptance and remaining limits

A live PASS requires process exit 0, stdout HTTP_SQL_TEST_PASSED, a readable private
manifest with that status and complete independent SQL evidence. A manifest status
alone is insufficient: a write/fsync error or hard kill can leave a stale or partially
written report, including a success label whose checkpoint never completed. Nonzero
exit, UNKNOWN operations, missing checkpoints or unreadable evidence remain incomplete.
Do not recreate a manifest with the same run UUID or remove its run marker to retry.
Inspect the exact tenant independently using read-only SQL and retain synthetic data.

The POSIX alarm and per-request/native query timeouts do not guarantee immediate
interruption of a blocked native call. SIGKILL, power loss or storage failure may prevent
failure reporting. File locks are advisory; the manifest and bearer credentials remain
trusted local-user material, not protection from a malicious same-user/root process.
The schema/zero-count preflight cannot prevent a concurrent external writer or DDL
change afterward; keep other development writers stopped as previously required.

Local SQLite and mocked transport tests do not certify native ODBC, SQL Server floating
averages, live Azure HTTP commits, ADLS, enterprise identity or least-privilege runtime.
The proposed SQL identity remains dbo; successful HTTP mutations retain committed
synthetic history. No cleanup is included. The driver is locally ready for a separately
approved test under these limits; no live acceptance or production readiness is claimed.

### Final local validation results

- Targeted driver safety suite: **69 passed, 0 failed**.
- Full backend suite: **240 passed, 0 failed** (includes the 69 driver checks).
- Ruff lint: passed across backend/scripts.
- Ruff format check: passed, 31 files already formatted.
- Default offline CLI: OFFLINE_PLAN_ONLY, connection_attempted=false,
  writes_executed=false.
- One existing upstream Starlette/httpx deprecation warning remains.

Commands executed from backend for pytest and repository root for Ruff/offline CLI:

```bash
timeout 60 ../.venv/bin/pytest -q tests/test_sql_http_plan.py
timeout 60 ../.venv/bin/pytest -q
.venv/bin/ruff check backend scripts
.venv/bin/ruff format --check backend scripts
.venv/bin/python scripts/test_azure_sql_http.py
```

TestClient tests ran outside the restrictive sandbox to avoid its known local hang.
They used disposable SQLite and mocked Azure engine/preflight boundaries. Control-flow
fault tests stubbed SQL/HTTP calls before exercising the execution-mode error handlers;
no approved live HTTP run occurred. Final checks additionally bind each disposition to
its original review ID and require final policy revision 2, row_version 10, PUBLISHED,
enabled, with the exact second draft. A swapped pair of review dispositions fails even
when API evidence and SQL rows agree on the swapped values.

Local review is complete. No approval was requested and no live execution was performed.
