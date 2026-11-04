> **Current release status (1 November 2026):** See [restricted demo completion status](docs/CURRENT_STATUS.md) and [validation results](docs/COMPLETION_VALIDATION.md). Earlier release reports are historical.

# AI Governance Policy Validator

**Current implementation — 31 October 2026:** **CONDITIONAL DEMO READINESS; NOT PRODUCTION READY.** The new reliability release is prepared and locally tested, not deployed. Azure SQL remains revision 003; the candidate requires reviewed additive revision 004. Fresh hosted checks show deployment `8c2639f4-41d7-4787-bce4-e7253ecbb4b2`, superseding earlier deployment observations. Start with [implementation](docs/FINAL_IMPLEMENTATION_REPORT.md), [test results](docs/FINAL_TEST_RESULTS.md), [demo runbook](docs/FINAL_DEMO_RUNBOOK.md), [operations](docs/OPERATIONS_RUNBOOK.md), and [pending approvals](docs/FINAL_PENDING_APPROVALS.md). Older readiness statements below describe their recorded acceptance scope.


A React + FastAPI application that gates prompts **and** generated responses using a versioned enterprise policy. This is an internship demonstration, not a production identity or regulatory compliance system.

**Current readiness — 30 October 2026:** **COMPLETE — CONTROLLED TECHNICAL DEMO READY.** The existing hosted React/FastAPI app, Azure SQL persistence and corrected ADLS export are verified. One fresh export was independently downloaded and matched all nine expected metadata records, 1,745 bytes and SHA-256. Real Chrome acceptance passed 72 hosted and 50 disposable fixture checks. Azure OpenAI/moderation/Presidio use clearly labeled prior live evidence; no fresh paid inference calls were made. See [final acceptance and matrix](docs/reports/FINAL_ACCEPTANCE_REPORT.md), [completion report](docs/reports/FINAL_PROJECT_COMPLETION_REPORT.md), [demo runbook](docs/runbooks/TECHNICAL_DEMO_RUNBOOK.md#17-final-accepted-panel-demonstration--30-october-2026) and [production backlog](docs/reports/PRODUCTION_BACKLOG.md). Local development still defaults to SQLite. Older phase/readiness reports are historical evidence.

**Expanded testing:** [30 October real-life test report](docs/reports/REAL_LIFE_TEST_REPORT_2026_10_30.md) records 231 automated tests and 417 additional checks passing, plus explicit input-coercion and obfuscated-PII limitations. No new paid live calls were made.

## Safe offline technical demo

From the repository root, with existing dependencies installed:

```bash
.venv/bin/python -B scripts/run_offline_demo.py
```

In another terminal:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174
```

Open http://localhost:5174. The launcher prints only the path of a private temporary credential file; open it privately to use the Admin token. It runs the existing FastAPI app on port 8010 against a new temporary SQLite database, with fixture AI/moderation, explicitly limited regex PII and ADLS disabled. It never edits .env or existing application data. Graceful shutdown removes its disposable data and credentials. Fixture exports correctly report FAILED; the hosted JSON export has separate independent live verification. Do not use offline fixtures as proof of live storage or AI behavior. See the runbook for decisions, lifecycle steps and the normal/live startup path.

## Quick start without Docker

These provisioning/migration commands are for a fresh local SQLite copy. Use the disposable launcher above in this existing workspace. Inspect and obtain approval before any existing/hosted database migration; never apply head blindly to Azure SQL.

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
- Azure SQL (opt-in, local Entra-only): keep the current SQLite `DATABASE_URL` until approved integration succeeds. The new adapter uses a tenant- and user-pinned Azure CLI identity, fresh ODBC access tokens, encrypted connections, certificate validation, and no fallback. Only `AZURE_SQL_TENANT_ID` and `AZURE_SQL_USER_OBJECT_ID` are new settings. See [the approval-gated Linux setup and permission runbook](docs/guides/AZURE_SQL_SETUP.md) before installing dependencies or changing database selection. The earlier `Authentication=ActiveDirectoryDefault` ODBC suggestion was incorrect and has been removed.

For Azure SQL, follow [the controlled integration gates](docs/guides/AZURE_SQL_SETUP.md): approved dependency installation → organizational login → read-only connection/permission checks → migration review → **explicit migration approval** → schema validation → approved application switch. Never run Azure SQL migrations or change the active database just because credentials become available. SQL Server dialect compilation is not live migration verification.

Official references: [OpenAI moderation](https://developers.openai.com/api/docs/guides/moderation), [Azure OpenAI REST](https://learn.microsoft.com/en-us/azure/foundry/openai/latest), [Microsoft Linux ODBC installation](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server), [ADLS Python overview](https://learn.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-directory-file-acl-python).

## Tests and verification

```bash
cd backend
../.venv/bin/pytest -q
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
cd ../frontend
npm run lint
GOVERNANCE_TEST_PYTHON="$(cd .. && pwd)/.venv/bin/python" npm test
npm run build  # includes strict TypeScript checking
npm audit
```

The full backend suite now includes the mocked HTTP driver and disposable migration tests; it does not authorize hosted SQL operations. The opt-in frontend integration test starts and stops only its own disposable fixture backend. Tests use disposable databases and synthetic inputs. HTTP provider contract tests are mocked and are **not** live cloud verification. This environment requires running TestClient tests outside its restrictive sandbox; a minimal TestClient health request also hangs inside it. No application enforcement was disabled to make tests pass.

See [readiness](docs/reports/READINESS.md) for final counts and blockers, [phase reports](docs/reports/PHASES.md), [architecture and schema](docs/ARCHITECTURE.md), [demo and viva guide](docs/guides/DEMO.md), and generated [demo results](docs/demo-results.json).

## Repository

```text
backend/
  app/            configuration, authentication, models, providers, policy engine, API
  migrations/     frozen Alembic schema and concurrency upgrade
  tests/          governance, security, adapters, migrations, SQL dialect checks
frontend/
  src/            responsive dashboard, policy editor, simulator, playground, reports
scripts/          private demo provisioning and running-server smoke demonstration
deployment/       hosting startup, settings template, review-only SQL
docs/
  guides/         setup, integration, and demo guides
  runbooks/       deployment and controlled operations
  reports/        acceptance, readiness, phase reports, production backlog
  evidence/       original verification evidence
  sql/            SQL review and verification resources
.github/workflows/ci.yml
.env.example
docker-compose.yml
```

See the [documentation index](docs/README.md) and [repository layout guide](docs/REPOSITORY_STRUCTURE.md) for folder responsibilities and path compatibility.

## Limitations that matter

Human review is **metadata-only**. Approval records an immutable audit event and marks `APPROVED_RESUBMIT_REQUIRED`; it does not resume a stored prompt or release a held response. Revised content must be resubmitted and pass all current policy gates. Original held content is not persisted, so there is no privileged content preview or automatic replay. This deliberate reduced scope avoids an unsafe review bypass, but does not satisfy an automatic review-resume workflow.

Browser login now exchanges a provisioned demo credential for an expiring SQL-backed session with logout and admin revocation. Provisioned root demo credentials remain an operator compatibility path; enterprise SSO/MFA and provider-managed accounts remain pending. Backend model hooks prevent application mutation of historical versions and audits, but a database administrator can modify the database: audit records are not cryptographically tamper-proof. PII and secret recognition are imperfect. No hallucination or bias scoring is claimed. Existing Azure App Service hosting is supported; this new reliability release awaits approved SQL 004, runtime access and deployment.
