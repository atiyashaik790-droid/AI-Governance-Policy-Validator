# Local run guide — verified 30 October 2026

## Prerequisites and existing configuration

Repository: `/home/sigmoid/AI governance policy validator`.
Verified here: Python **3.13.7**, Node.js **24.22.1**, npm **11.19.1**.
Python 3.12 is the CI/Docker target. Existing Python environment: `.venv/`.
Backend dependencies: `backend/requirements.lock.txt`; frontend: `frontend/package-lock.json`.
The English spaCy model and Presidio are installed and their real local detector test passes.

The disposable demo needs no cloud account or external database. SQLite is built into
Python. It uses fixture generation/moderation and explicitly limited regex PII.
The existing normal local server uses SQLite, live provider mode and Presidio;
its ADLS configuration is currently absent. Do not use that server for an offline rehearsal.

The root `.env` and `.demo-tokens.json` already exist. **Do not overwrite or reprovision them.**
Normal configuration uses `DATABASE_URL`, `DEMO_ACCOUNTS_JSON`, `PROVIDER_MODE`,
`PII_MODE`, and `CORS_ORIGIN`. Approved live integrations additionally require the
Azure/OpenAI/ADLS settings described in [the project README](../README.md).
The demo launcher supplies temporary overrides itself; no `.env` edit is required.
Azure SQL requires ODBC Driver 18 and the previously approved identity; see
[Azure SQL setup](guides/AZURE_SQL_SETUP.md). Do not run live migrations.

## Open and prepare the project

In VS Code choose **File → Open Folder**, select the repository above, then
**Terminal → New Terminal**. Run:

```bash
cd "/home/sigmoid/AI governance policy validator"
source .venv/bin/activate
python --version
node --version
npm --version
```

Dependencies are already installed and consistent. Only if rebuilding dependencies:

```bash
cd "/home/sigmoid/AI governance policy validator"
# Only if .venv does not already exist:
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
cd frontend
npm ci
```

Installation requires network access. Do not run `provision_demo.py` in this workspace.
For a genuinely fresh copy, follow the README provisioning instructions once;
never copy another user's credentials or paste secrets into reports.

## Recommended safe technical demonstration

Terminal 1, from repository root:

```bash
cd "/home/sigmoid/AI governance policy validator"
.venv/bin/python -B scripts/run_offline_demo.py
```

Expected: a JSON notice with `mode: DISPOSABLE_LOCAL_FIXTURE`, a private
`credential_file` path, and port `8010`. This starts the existing FastAPI app against
a new temporary SQLite database. Health: <http://127.0.0.1:8010/health>;
readiness: <http://127.0.0.1:8010/ready>; API docs: <http://127.0.0.1:8010/docs>.

Terminal 2:

```bash
cd "/home/sigmoid/AI governance policy validator/frontend"
VITE_API_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174
```

Expected: Vite ready and `http://127.0.0.1:5174/`. **Open
<http://localhost:5174>** to match the configured CORS origin.
The application visibly labels its fixture generation/moderation and regex detector.
Each launcher run begins with an empty disposable database.

## Login and demonstrate

Authentication uses opaque bearer tokens mapped to server-side roles and tenants;
it does not use username/password or JWTs. Open the exact private `credential_file`
printed by Terminal 1 in your local editor. Copy the `Admin` value privately into
**Access token**, then click **Connect workspace**. Do not paste it into chat.
Available roles: Admin, Policy Owner, Developer, Reviewer, Auditor. Admin may perform
the full demo; Reviewer can approve policies and resolve review cases. Sign out before
switching role. The token is held in tab session storage and removed by **Sign out**.

1. Open Policy management → Create policy. Keep the default `internal-only` keyword,
   secret BLOCK and PII REDACT settings. Save draft.
2. Open Policy simulator, choose the draft, simulate safe synthetic text (ALLOW),
   then `internal-only` (BLOCK).
3. In Policy management run **submit → approve → publish → activate**.
4. In AI playground use Safe prompt, Synthetic secret and Synthetic PII examples;
   expect ALLOW, BLOCK and REDACT. Fixture failure must BLOCK. Rate a safe result.
5. Edit the policy's blocked-keyword action to HUMAN_REVIEW, save, and repeat
   submit → approve → publish → activate. Send `internal-only` in the playground.
6. In Human review approve or reject the pending case. Approval requires a revised
   request to be resubmitted; it never releases the original held content.
7. Inspect Validation history, Compliance analytics, Audit & reports, and Settings.
   Offline exports correctly fail because ADLS is disabled. Existing hosted export
   evidence is separate; **do not trigger another live export**.

## Existing configured local application

The existing project-owned servers were found on ports 8000 and 5173 and left running.
Open <http://localhost:5173>. Backend: <http://127.0.0.1:8000/docs>.
Its approved credentials are in root `.demo-tokens.json`, viewed privately.
This server is in **live** mode: do not click generation/simulation or export controls
without the required approval for live service usage.

If these servers are stopped and you intend to use the existing configured environment,
start the backend in one terminal:

```bash
cd "/home/sigmoid/AI governance policy validator/backend"
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Expected: `Application startup complete` and `Uvicorn running on http://127.0.0.1:8000`.
Start the frontend in another:

```bash
cd "/home/sigmoid/AI governance policy validator/frontend"
npm run dev -- --host 127.0.0.1
```

Open **http://localhost:5173**, matching the normal CORS origin. Startup performs no
migration. Do not run these commands a second time while their ports are occupied.

## Run verification

Backend tests use isolated databases and mocked cloud transports. This run passed
all 294 tests, including the historically excluded HTTP-driver safety tests and
fresh disposable SQLite migration test. The live driver itself must not be executed.

```bash
cd "/home/sigmoid/AI governance policy validator/backend"
../.venv/bin/pytest -q
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
../.venv/bin/python -m compileall -q app tests
cd ../frontend
GOVERNANCE_TEST_PYTHON="$(cd .. && pwd)/.venv/bin/python" npm test
npm run lint
npx tsc -b
npm run build
npm audit --audit-level=high
```

`GOVERNANCE_TEST_PYTHON` is necessary: otherwise the real HTTP integration is skipped.
In Codex's restrictive sandbox TestClient/socket tests need execution outside the
sandbox; ordinary Linux terminals do not have this additional restriction.

Chrome browser acceptance is preserved in the evidence directory. On this workstation:

```bash
cd "/home/sigmoid/AI governance policy validator"
node docs/evidence/final-stabilization-2026-10-30/browser-local.cjs
```

The runner uses installed Google Chrome and existing Playwright Core under
`/tmp/governance-final-stabilization/browser-tools/node_modules/playwright-core`.
That temporary dependency is machine-local. If it has disappeared, install it from npm
outside the project, then pass its path; no project dependency edit is needed:

```bash
npm install --prefix /tmp/governance-browser-tools playwright-core@1.64.1
PLAYWRIGHT_MODULE=/tmp/governance-browser-tools/node_modules/playwright-core \
  node docs/evidence/final-stabilization-2026-10-30/browser-local.cjs
```

Google Chrome must exist at `/usr/bin/google-chrome`. The runner creates and stops its
own fixture backend/frontend on free ports, writes synthetic screenshots/results, and
returns a failing exit code for failed checks or page errors. Its headless Chrome uses
`--no-sandbox` for this constrained test host; this is a test-process setting only.

## Stop safely

Press **Ctrl+C** in each terminal you started, frontend first then backend.
The fixture launcher removes its temporary database and credential file on graceful
exit. Never kill a process solely because it occupies a port. Use `ss -ltnp` to inspect
ownership and return to the terminal that started the intended process.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Port already used | Reuse the known project server or choose unused ports. For fixtures, pass `--port 8011 --frontend-origin http://localhost:5175`, then set `VITE_API_URL=http://127.0.0.1:8011` and Vite `--port 5175`. |
| `python` missing | Use `.venv/bin/python`, or `python3` when creating a new environment. |
| Missing Python module | Run `.venv/bin/python -m pip install -r backend/requirements.lock.txt` from root. |
| Missing npm module | Run `npm ci` inside `frontend/`. |
| Database unavailable | Check `/ready`. Prefer the disposable launcher for rehearsal. Do not reset the existing DB or run Azure migrations; ask for approved identity/network access if live SQL is unavailable. |
| Invalid token | Use the token belonging to the specific backend instance. Fixture tokens change after each restart. Sign out and reconnect. |
| CORS failure | Browser origin must exactly match `CORS_ORIGIN` or launcher's `--frontend-origin`; `localhost` and `127.0.0.1` differ. |
| Frontend cannot reach API | Check backend health, `VITE_API_URL`, ports, and restart Vite after changing its environment. |
| Missing environment setting | Compare field names with `.env.example`; view secrets privately. Fixture launcher requires no cloud settings. Never overwrite `.env` automatically. |
| BLOCK on a seemingly safe request | Check active enabled published policy and provider diagnostics. Live provider failure intentionally withholds content. |

## Hosted Azure application

<https://app-governance-validator-atiya-1026.azurewebsites.net>

Use the separately approved hosted demo credential privately; local fixture tokens
will not authenticate there. Public health/readiness/OpenAPI were checked again and
responded successfully. Prior deployment/export acceptance remains historical evidence
for the accepted version. This stabilization did not deploy anything or prove the
current server-side deployment ID. Do not repeat paid calls or live exports.
