# Run locally with existing real integrations

Prepared 31 October 2026. This uses the existing FastAPI/React application and existing
Azure resources. It does not deploy, create infrastructure, run migrations, or edit `.env`.

## Initial verification (before the approved firewall change)

- Existing root `.env`: Azure OpenAI endpoint/deployment/key and moderation key present;
  provider mode live, Presidio selected, SQLite still the persistent default.
- Microsoft ODBC Driver 18, pyodbc and Azure CLI installed; identity pins present.
- Existing Azure SQL server resolves and TCP 1433 is reachable. SELECT-only diagnostic
  failed. A sanitized direct driver check identified SQLSTATE 42000 / error 40615:
  **SQL firewall denied this laptop's client IP**. No database mutations occurred.
- Existing ADLS filesystem `governance-reports` at
  `https://stgovvalidatoratiya1026.dfs.core.windows.net`: read-only properties check PASSED
  using the existing project-local CLI cache. Upload permission was not freshly tested.
- No new generation, moderation, export, migration or deployment was executed.

## SQL firewall prerequisite (resolved on 31 October 2026)

An authorized Azure administrator must allow only this laptop's current public IPv4
on the existing server `sql-governance-validator-dev-atiya`. This is an Azure resource
change and requires explicit approval before this agent performs it. Do not enable
all IPs or broad Azure-services access. Preserve existing firewall rules.

After the approved firewall change, verify read-only access from repository root:

```bash
cd "/home/sigmoid/AI governance policy validator"
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" \
  .venv/bin/python -B scripts/check_azure_sql.py \
  --server sql-governance-validator-dev-atiya.database.windows.net \
  --database sqldb-governance-validator-dev --connect
```

Expected: `connection_status: CONNECTED` and `runtime_permissions_ready: true`.
If authentication fails, use the approved organizational identity already pinned in
`.env`; do not replace pins with an unrelated account or invent credentials.
If permissions/schema checks fail, stop rather than migrate, grant privileges or reset
anything. Prior checks used a broad administrator identity; this remains a controlled
local demo configuration, not a least-privilege production claim.

## Start the live local backend

Ports 8002/5175 separate this from the offline demo on 8010/5174. Inspect port ownership
first with `ss -ltnp`; do not stop another process if either selected port is occupied.

Run in Terminal 1:

```bash
cd "/home/sigmoid/AI governance policy validator/backend"
AZURE_CONFIG_DIR="/home/sigmoid/AI governance policy validator/.azure-sql-cli" \
DATABASE_URL='mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-governance-validator-dev?driver=ODBC+Driver+18+for+SQL+Server' \
AZURE_SQL_AUTH_MODE=cli \
PROVIDER_MODE=live \
PII_MODE=presidio \
ADLS_ACCOUNT_URL='https://stgovvalidatoratiya1026.dfs.core.windows.net' \
ADLS_FILE_SYSTEM='governance-reports' \
CORS_ORIGIN='http://localhost:5175' \
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 --no-access-log
```

These settings apply to this process only. Keys, demo account hashes and identity pins
continue to load privately from root `.env`. Do not copy hosted managed-identity object
IDs into the local CLI configuration. Local backend uses `app.main:app`; hosting's
`app.hosting:app` entry point is for App Service and is not the local launch target.
The launcher performs no migrations. Do not use Docker Compose for this switch because
its normal startup automatically runs migrations.

## Start the connected frontend

Run in Terminal 2:

```bash
cd "/home/sigmoid/AI governance policy validator/frontend"
VITE_DEMO_LOGIN=true VITE_API_URL=http://127.0.0.1:8002 npm run dev -- --host 127.0.0.1 --port 5175
```

Open **http://localhost:5175**, using `localhost` to match CORS.
Backend docs: http://127.0.0.1:8002/docs.

## Sign in and inspect settings

Use the existing **root** demo credentials, not the offline demo's temporary file:

```bash
code "/home/sigmoid/AI governance policy validator/.demo-tokens.json"
```

Copy only the Admin value privately. Sign in and open Settings. Expected:

- role Admin; database mssql; database status CONNECTED;
- provider mode live; PII mode presidio;
- generation, moderation and ADLS CONFIGURED_NOT_VERIFIED until fresh operations verify them.

The offline temporary tokens belong to another server. The application still uses
local demo bearer authentication even when storage and providers use Azure.
No active policy is automatically created. A missing active enabled published policy
correctly blocks generation. Live SQL policy/audit changes persist in the existing
shared database; do not reuse an offline synthetic workflow as automatic write approval.

## Live usage boundaries

Starting the servers and checking health/settings does not itself invoke AI or upload
exports. A live simulator can invoke moderation; a governed generation invokes real
provider calls and persists execution/audit data. Obtain explicit approval for bounded
synthetic inference/write testing before this agent performs those operations.
Do not click Export as part of startup verification. The prior successful ADLS export
remains evidence; a new live upload requires separate explicit approval.
Do not submit real credentials, customer data or personal information as test prompts.

Stop only these terminals with Ctrl+C. This leaves persistent SQL records intact and
restores no settings because root `.env` was never changed. The offline demo is separate.

## Approved temporary firewall change — completed 31 October 2026

User explicitly approved a temporary firewall rule for the laptop's confirmed current
public IPv4. Public-network access was already Enabled and was not changed.

- Server: `sql-governance-validator-dev-atiya`
- Resource group: `REPLACE_WITH_AZURE_RESOURCE_GROUP`
- Rule: `REPLACE_WITH_APPROVED_FIREWALL_RULE_NAME`
- Start IP = end IP = **REPLACE_WITH_APPROVED_LAPTOP_PUBLIC_IP**, confirmed through an IPv4 public-IP lookup.
- All 14 preexisting rules were verified unchanged; exactly one rule was added.
- Post-change SELECT-only diagnostic: CONNECTED; all 21 checked runtime permissions
  GRANTED; runtime_permissions_ready true. No data/schema writes or migrations.
- No generation, moderation, export or deployment was performed. Offline processes,
  credentials and `.env` were not changed.
- Evidence: `docs/evidence/local-live-firewall-2026-10-31/`.

The rule has **no automatic expiry**. Remove it manually after testing, from repository root:

```bash
cd "/home/sigmoid/AI governance policy validator"
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az sql server firewall-rule delete \
  --resource-group REPLACE_WITH_AZURE_RESOURCE_GROUP \
  --server sql-governance-validator-dev-atiya \
  --name REPLACE_WITH_APPROVED_FIREWALL_RULE_NAME
```

This deletes only the newly added rule. A public-IP change can invalidate laptop access;
do not widen the rule or add another IP without a separate approved change.

## 31 October generation/output stabilization follow-up

The local backend on 8002 was gracefully restarted with the commands above after
345 backend tests, 10 frontend tests and 57 Chrome fixture checks passed. Azure SQL,
Admin authentication, policy list and readiness were read-only verified. Frontend
5175 targets this backend. The offline configuration and credentials were untouched.

New playground behavior: policy name/version comes from the active immutable document;
gateway status distinguishes Generation failed, Generation succeeded, and Model not
invoked. A failed request now includes a fixed safe provider category and, when available,
HTTP status/UUID Azure correlation ID. It never includes raw upstream error bodies.
PII FAILED means detected violation, not detector outage; UNKNOWN denotes unavailability.

Original GPT-5 deployments use minimal reasoning effort within the unchanged 700-token
completion cap. Truncated/content-filtered/incomplete responses fail closed. This is
not proof that the two prior live failures are resolved; no new live requests have been
approved or executed. Settings remains CONFIGURED_NOT_VERIFIED by design.

Do not run the live playground/simulator or create new persistent SQL records as an
automated test without the separate agreed operation allowance. Existing approved
offline fixtures remain the appropriate interactive rehearsal.

[Current report](FINAL_LIVE_STABILIZATION_REPORT.md),
[test results](FINAL_END_TO_END_TEST_RESULTS.md),
[deployment approval package](FINAL_AZURE_DEPLOYMENT_VERIFICATION.md).
