# AI Governance Policy Validator

A local React + FastAPI application that gates prompts **and** generated responses using a versioned enterprise policy. This is an internship demonstration, not a production identity or regulatory compliance system.

**Current execution:** frontend http://localhost:5173 · backend http://localhost:8000 · Swagger http://localhost:8000/docs. Azure GPT-5 mini and OpenAI moderation are LIVE VERIFIED using private credentials. A complete live request passed input moderation, Azure generation, output moderation, safe response release, and SQLite audit persistence. The backend runs in live mode. Presidio performs real local PII inspection. Azure SQL and ADLS cloud verification remain pending. See `docs/live-connectivity.json` for the latest probe.

## Quick start without Docker

Prerequisites: Python 3.12 recommended (this workstation has 3.13, on which tests were run), Node 24, npm, network access for dependency installation.

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock.txt
python3 scripts/provision_demo.py
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal from the repository root:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

The provisioner refuses to overwrite `.env`. It creates private `.env` and `.demo-tokens.json` files, excluded from Git. Open the latter **locally**, copy the Admin token, and enter it into the dashboard. Do not paste credentials into chat or commit them. Roles and tenant are server-controlled; the browser cannot select a trusted role. Tokens persist only in the browser tab's session storage and are removed on sign out.

For this workspace these files already exist. **Do not rerun provisioning** unless starting a fresh copy. No default policy is silently activated. Create one through the UI and run Submit → Approve → Publish → Activate, or run:

```bash
.venv/bin/python scripts/smoke_demo.py
```

This creates real local policy versions and real persisted fixture inspection records. Repeating it creates additional demonstration records. It does not provision or call live cloud services. Output is stored in `docs/demo-results.json` without prompts, tokens, or responses.

## Docker Compose

```bash
python3 scripts/provision_demo.py  # fresh copy only
docker compose up --build
```

Compose binds both services to loopback. The backend runs migrations before serving; the frontend waits for database readiness. SQLite persists in a named volume. Dockerfiles use unprivileged application users; the backend image installs Microsoft ODBC Driver 18. This machine has no Docker executable, so image builds, container permissions, and Compose startup are **BLOCKED / NOT VERIFIED** here. Do not describe Docker as tested.

`DATABASE_URL_DOCKER` overrides the container database URL; local `DATABASE_URL` is intentionally not used inside the container because relative SQLite paths differ. `.env` still supplies provider credentials.

## Environment and cloud integrations

`.env.example` contains placeholders only. `.env` is resolved relative to the repository, so launching from `backend/` works. Never enable fixture mode accidentally for a live demonstration.

- `PROVIDER_MODE=fixture`: deterministic generation and special moderation fixture markers; every gateway result is labeled. **Not live Azure or moderation.**
- `PROVIDER_MODE=live`: real approved-provider adapters; missing or failed inspection blocks content.
- `PII_MODE=presidio`: installed English spaCy model plus Presidio recognizers. Model download happens during installation, never during inspection. Missing models block inspection.
- `PII_MODE=regex`: explicitly limited email, SSN-shaped, and phone-shaped local fallback; not comprehensive PII detection.
- Azure generation: set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` (`v1` default), and optionally `AZURE_OPENAI_API_KEY`. With no key, `DefaultAzureCredential` uses an authorized Entra identity and the Cognitive Services scope. API-version deployment routes are also supported. No resources are created.
- Moderation: set `OPENAI_API_KEY`, server-side only. Uses the official `/v1/moderations` endpoint with `omni-moderation-latest`. Moderation does not detect PII, secrets, hallucinations, or comprehensive bias.
- ADLS: set `ADLS_ACCOUNT_URL=https://<account>.dfs.core.windows.net` and existing `ADLS_FILE_SYSTEM`. Uses `DefaultAzureCredential`. Export failure is persisted accurately without disabling core validation. The identity needs an authorized data-plane role on that existing filesystem.
- Azure SQL (opt-in, local Entra-only): keep the current SQLite `DATABASE_URL` until approved integration succeeds. The new adapter uses a tenant- and user-pinned Azure CLI identity, fresh ODBC access tokens, encrypted connections, certificate validation, and no fallback. Only `AZURE_SQL_TENANT_ID` and `AZURE_SQL_USER_OBJECT_ID` are new settings. See [the approval-gated Linux setup and permission runbook](docs/AZURE_SQL_SETUP.md) before installing dependencies or changing database selection. The earlier `Authentication=ActiveDirectoryDefault` ODBC suggestion was incorrect and has been removed.

For Azure SQL, follow [the controlled integration gates](docs/AZURE_SQL_SETUP.md): approved dependency installation → organizational login → read-only connection/permission checks → migration review → **explicit migration approval** → schema validation → approved application switch. Never run Azure SQL migrations or change the active database just because credentials become available. SQL Server dialect compilation is not live migration verification.

Official references: [OpenAI moderation](https://developers.openai.com/api/docs/guides/moderation), [Azure OpenAI REST](https://learn.microsoft.com/en-us/azure/foundry/openai/latest), [Microsoft Linux ODBC installation](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server), [ADLS Python overview](https://learn.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-directory-file-acl-python).

## Tests and verification

```bash
cd backend
../.venv/bin/pytest -q
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
cd ../frontend
npm run lint
npm test
npm run build  # includes strict TypeScript checking
npm audit
```

Tests use disposable databases and synthetic inputs. HTTP provider contract tests are mocked and are **not** live cloud verification. This environment requires running TestClient tests outside its restrictive sandbox; a minimal TestClient health request also hangs inside it. No application enforcement was disabled to make tests pass.

See [readiness](docs/READINESS.md) for final counts and blockers, [phase reports](docs/PHASES.md), [architecture and schema](docs/ARCHITECTURE.md), [demo and viva guide](docs/DEMO.md), and generated [demo results](docs/demo-results.json).

## Repository

```text
backend/
  app/            configuration, authentication, models, providers, policy engine, API
  migrations/     frozen Alembic schema and concurrency upgrade
  tests/          governance, security, adapters, migrations, SQL dialect checks
frontend/
  src/            responsive dashboard, policy editor, simulator, playground, reports
scripts/          private demo provisioning and running-server smoke demonstration
docs/             architecture, decisions, phase evidence, demo, readiness
.github/workflows/ci.yml
.env.example
docker-compose.yml
```

## Limitations that matter

Human review is **metadata-only**. Approval records an immutable audit event and marks `APPROVED_RESUBMIT_REQUIRED`; it does not resume a stored prompt or release a held response. Revised content must be resubmitted and pass all current policy gates. Original held content is not persisted, so there is no privileged content preview or automatic replay. This deliberate reduced scope avoids an unsafe review bypass, but does not satisfy an automatic review-resume workflow.

Local bearer authentication has no enterprise SSO, MFA, token expiration, or revocation service. Backend model hooks prevent application mutation of historical versions and audits, but a database administrator can modify the database: audit records are not cryptographically tamper-proof. PII and secret recognition are imperfect. No hallucination or bias scoring is claimed. No cloud hosting is included.
