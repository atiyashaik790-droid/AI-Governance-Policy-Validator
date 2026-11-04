# Technical demo runbook

> **Current status — 30 October 2026: COMPLETE — CONTROLLED TECHNICAL DEMO READY.**
> The corrected ADLS export is live and independently verified. Real Chrome acceptance
> passed 72 hosted and 50 disposable checks. Use **section 17** for the final panel
> sequence; sections 1–10 retain safe offline instructions and sections 11–16 retain
> historical deployment/failure checkpoints. See [final acceptance](../reports/FINAL_ACCEPTANCE_REPORT.md).

The existing application and approved synthetic live history are retained. Interactive
rehearsal uses disposable SQLite with cloud adapters disabled. Do not change root .env,
existing databases, old manifests or pre-existing local servers.

## 1. Start the safe offline rehearsal

From the repository root, using already installed dependencies:

```bash
.venv/bin/python -B scripts/run_offline_demo.py --port 8010 --frontend-origin http://localhost:5174
```

The launcher binds only to 127.0.0.1, creates temporary SQLite tables from the existing
models (no migrations), and prints a JSON startup notice containing only the private
credential file's location. It explicitly disables all four cloud adapters through
child-process overrides. Generation/moderation use existing fixtures; PII uses the
explicitly limited regex detector. No .env or existing database is edited. The new
credential file has mode 0600, lives in a private temporary directory, and is removed
with the disposable database on graceful exit. Never use its temporary credentials as
production credentials. Hard termination can leave its temporary directory behind;
inspect the exact printed path rather than deleting unrelated files by a prefix.

In a second terminal from the repository root:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174
```

Open **http://localhost:5174**. Use this hostname to match the configured CORS origin.
Open the printed private credential file in a local editor and copy its Admin token
into the dashboard's Access token field. Never paste tokens into chat, shell commands,
screenshots or the presentation. The frontend stores the token only in sessionStorage.

Read-only health checks:

```bash
curl --fail http://127.0.0.1:8010/health
curl --fail http://127.0.0.1:8010/ready
curl --fail --silent --output /dev/null --write-out '%{http_code}\n' http://localhost:5174/
```

Expected: backend status `ok`, readiness `ready` with provider_mode `fixture`, frontend
HTTP 200. Settings should show database `sqlite`, provider mode `fixture`, PII `regex`,
and Azure generation/moderation/ADLS BLOCKED. These indicate deliberate offline isolation.
The environment banner identifies deterministic fixtures. An empty dashboard is expected
until this rehearsal creates its own records.

Do not start another instance on an occupied port or stop a pre-existing server. If you
choose another backend/frontend port, update the launcher's `--port`, its
`--frontend-origin`, React's `VITE_API_URL`, and React's `--port` together.

## 2. Policy management and lifecycle

Use the Admin token for the main walkthrough; backend role enforcement remains active.

1. Open **Policy management → Create policy**. Use name `Technical Demo Protection`.
   Keep secret_detection BLOCK, pii_detection REDACT, moderation BLOCK and blocked_keywords
   BLOCK with `internal-only`. Save draft. Invalid/unsupported rule JSON is rejected by
   backend schema validation; the editor shows the JSON preview.
2. Use **View / edit**, change the description, and **Save draft**. Editing preserves
   published snapshots and returns the editable policy to DRAFT.
3. Open **Policy simulator**, select this draft, set Sample prompt to `Safe synthetic text`,
   and simulate. Expect ALLOW. Simulation does not invoke generation; in live mode,
   enabled moderation can still make a real API call.
4. Return to Policy management and click **submit → approve → publish → activate** in
   order. Expect SUBMITTED → APPROVED → PUBLISHED. Activation is a separate action.
   The policy must also be enabled. History displays immutable version 1.
5. Click **disable**. A governed request now returns 409 because the active policy is
   disabled. Click **enable** to restore the assignment. Neither action bypasses gates.
6. For draft deletion, create a separate unused draft and use **delete**. Only
   never-published DRAFT policies may be deleted. To demonstrate **archive**, create a
   separate inactive policy and archive it. An active policy cannot be archived until
   another published policy is activated. Do not try to delete published history.

Policy Owner can author/submit/publish/activate; Reviewer can approve; Admin can perform
both roles for a short demonstration. The visible controls do not grant permissions;
unauthorized operations still return 403. A published policy edited back to DRAFT can
show Delete, but the backend correctly refuses it with 409. Use the lifecycle rules
above rather than interpreting that rejection as lost data.

## 3. Governed decisions

Open **AI playground**, enter each synthetic prompt, and click **Run governed request**.

| Prompt / setup | Expected outcome | What to show |
| --- | --- | --- |
| `Explain the benefits of data governance in simple terms.` | ALLOW | Input inspection, fixture model invocation, output inspection and a safe fixture response. |
| `api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345` | BLOCK | Secret detector failure, no model invocation, no safe response. This is a synthetic example, never a real key. |
| `Contact test.person@example.com about data governance.` | REDACT | PII replaced, revalidation succeeds, only sanitized input reaches generation. The initial score can be below 100 after successful redaction. |
| `[OUTPUT_SECRET]` in fixture mode | BLOCK | Input may pass; model invocation occurs; generated synthetic secret is blocked by output inspection and withheld. |
| `[MODERATION_FLAG]` in fixture mode | BLOCK | Deterministic mocked moderation category. |
| `[MODERATION_UNAVAILABLE]` in fixture mode | BLOCK | Moderation UNKNOWN, fail-closed decision and no generation. |

The last three markers are fixture-only test dependencies, not live-provider fault
injection. Never present them as an Azure/OpenAI live validation result. A score is an
explanation of configured control outcomes; it never overrides a BLOCK or HUMAN_REVIEW.

## 4. Human review

1. Edit the demo policy and set **blocked_keywords action** to HUMAN_REVIEW. Keep
   `internal-only` as the keyword. Save draft, then repeat submit → approve → publish →
   activate to make version 2 effective. Version 1 remains immutable in History.
2. Submit `This is internal-only information.` in the playground. Expect HUMAN_REVIEW,
   no generation and no safe response.
3. Open **Human review**. Inspect metadata and click **approve**. Expect
   APPROVED_RESUBMIT_REQUIRED. Approval records a disposition; it does not release held
   content or replay the original request.
4. Submit a revised harmless prompt through the playground. It must pass all current
   input/output gates. For rejection, submit a second held prompt and reject its case;
   expect REJECTED. A second disposition on an already resolved case returns 409.

Original held prompts/responses are not retained for preview. Automatic approval/resume
is outside this demo's implemented scope.

## 5. Audit history, feedback, dashboard and reports

- On a completed playground result, click a numeric rating. Expect **Feedback saved**.
  Submitting ratings 2 and 3 yields count 2 and average 2.5. The UI provides rating
  submission; aggregate feedback is available through the existing API, not a new panel.
- Open **Validation history** and **Inspect metadata**. Show request ID, policy/version,
  decisions and control findings. No raw safe_text or safe_response is persisted.
- Open **Audit & reports** to see lifecycle and review events. Metadata inspection is
  local; these rows represent real writes only to this rehearsal's disposable database.
- Open **Overview / Compliance analytics**. Counts reflect actual requests. Trend entries
  now use deterministic timestamp/ID order and show the latest 100 applicable entries.
- On **Audit & reports**, try Export JSON/CSV only in this isolated offline rehearsal.
  Expect **ADLS export: FAILED** and a persisted failed attempt, because ADLS is disabled.
  A 201 response is not an upload-success claim. Mocked successful JSON/CSV upload is
  covered by the backend tests; a real upload awaits explicit approval.

To view aggregate feedback without putting a bearer token in a shell argument, set only
the printed temporary file path, then use this read-only helper:

```bash
export OFFLINE_DEMO_CREDENTIAL_FILE='/tmp/REPLACE_WITH_PRINTED_DIRECTORY/.demo-tokens.json'
.venv/bin/python -B - <<'PY'
import json
import os
from pathlib import Path
import httpx
credential = json.loads(Path(os.environ['OFFLINE_DEMO_CREDENTIAL_FILE']).read_text())['Admin']
with httpx.Client(base_url='http://127.0.0.1:8010', timeout=5, trust_env=False) as client:
    response = client.get('/api/feedback/summary', headers={'Authorization': 'Bearer ' + credential})
    response.raise_for_status()
    print(json.dumps(response.json()))
PY
```

The file path is not a token. Do not print the file's contents to shared output. Do not
point this helper or the rehearsal UI at an existing business/Phase 5 database.

## 6. Stop the rehearsal

Press Ctrl-C in the two terminals that launched these new rehearsal processes. Normal
shutdown disposes the new SQLite engine and removes its temporary data/credentials.
Each new run starts empty. Do not stop the original port-8001 process or delete its
manifest/records. Do not use a broad process-kill or temporary-directory deletion command.

At completion of this implementation, a disposable rehearsal was started separately at
backend port **8010** and frontend port **5174**, with HTTP 200 health/readiness/root checks.
Its private credential file is `/tmp/governance-offline-demo-1bheb9ue/.demo-tokens.json`.
This path contains only the new temporary demo credentials; it is not the original
Phase 5 manifest. The running frontend uses an isolated copy at
`/tmp/governance-completion-verification-artjk82f/frontend`. If these task processes
have exited, use the startup commands above to create a fresh rehearsal. No policy was
prepopulated in the running rehearsal, so creation can be demonstrated from the UI.

## 7. Normal existing application startup (not executed here)

This uses the existing private configuration and existing application database. Starting
it is not permission to modify business records or make live provider/export calls.
Use a free port; leave existing processes unchanged.

```bash
cd backend
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

From repository root in another terminal:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Open http://localhost:5173; its default API is http://localhost:8000 and default CORS
matches that frontend origin. `VITE_API_URL` is resolved at dev startup/build time, not
by changing a backend process. These commands run no migrations. Do not rerun
provision_demo.py in this workspace, overwrite .env, or switch DATABASE_URL.

## 8. Live Azure demonstration gates

Existing evidence: Azure SQL connection/identity/permissions/inventory and revision 003
were manually verified; Azure OpenAI and OpenAI moderation had a successful live gateway
request recorded in `docs/live-connectivity.json`. These results were not repeated.
They do not establish a fresh four-service chain.

Before a future live request/upload, explicit approval must identify the exact target,
operation, synthetic data scope, cost/write permission and retention expectation.

- Azure SQL: existing process-only DB selection and Entra adapter already work by design;
  persistent default remains SQLite. A new acceptance run must load corrected source and
  use fresh approved synthetic scope. Never retry the failed Phase 5 manifest, rerun
  migrations, automatically clean records or run `scripts/test_azure_sql_http.py` under
  the current instruction. The old port-8001 process must not be altered implicitly.
- Azure OpenAI/Moderation: endpoint/deployment/key settings are present. No live calls
  were made in this completion. Approve bounded harmless calls before using a live-mode
  playground or simulator. Entra generation fallback is mock-verified; recorded live
  evidence used the API-key path.
- ADLS: provide `ADLS_ACCOUNT_URL` and `ADLS_FILE_SYSTEM` privately through the existing
  configuration approach, with an approved existing DefaultAzureCredential identity
  authorized for that filesystem. No storage key setting or new Azure resource is
  introduced. Only an explicitly approved sanitized upload can establish live success.
- Export uses a new UUID path and overwrite=False. There is no application POST retry
  or general idempotency key; the SDK may have its own transient retries. Upload precedes
  DB commit, so an uncertain HTTP outcome is not proof of rollback or absence of an
  artifact. Stop and inspect read-only; never blindly retry.

## 9. Reproduce local verification

Existing dependencies only; no installation, lockfile change or live service required.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/pytest -q -p no:cacheprovider \
  --ignore=tests/test_sql_http_plan.py -k 'not test_migrations_on_fresh_sqlite'
cd ..
.venv/bin/ruff check --no-cache backend scripts
.venv/bin/ruff format --check --no-cache backend scripts
cd frontend
GOVERNANCE_TEST_PYTHON="$(cd .. && pwd)/.venv/bin/python" npm test
npm run lint
npm run build
```

The 69 prohibited HTTP-driver checks are excluded before collection and the migration
execution test is deselected. All remaining backend tests use disposable databases,
local models or mocked transports. The Node/JSX frontend integration test launches only
its own offline backend on a free port, verifies real HTTP/CORS/UI wiring, and stops it;
without GOVERNANCE_TEST_PYTHON it is explicitly skipped. Application TypeScript remains
strictly checked by the build. This Node-runtime JSX test requires no new Node typings.
Production build artifacts can be generated in a temporary source/dependency copy when
preserving the current worktree's generated files matters. No connected browser surface
was available: DOM/HTTP coverage is verified locally, full browser visual acceptance is
not claimed.


## 10. Prepared Azure deployment — approval pending

The latest scope includes App Service. See
[AZURE_DEPLOYMENT_RUNBOOK.md](AZURE_DEPLOYMENT_RUNBOOK.md) for the exact one-Web-App
proposal, commands, private settings, permissions, costs and rollback. No deployment
commands were executed and no deployed URL exists. Preserve the original port-8001 server.

Latest checks: **217 backend and 7 frontend tests passed**; Ruff, ESLint, TypeScript,
production build and startup shell checks passed. Production uses `VITE_API_URL=/` and
`app.hosting:app` through `sh startup.sh`. Local startup above remains unchanged.

Prepared ZIP: `/tmp/governance-appservice-prep-qi0yutlp/governance-validator-app.zip`.
SHA256: `6900d83846b35f12c9f8c23de57e5177e9592623c5e2f309a44668c87857c426`.
After approved creation, use the actual Azure `defaultHostName` for HTTPS and CORS.

After deployment approval, verify startup, HTTPS, `/health`, `/ready`, assets, deep links
and protected API responses. Readiness performs a database read. Confirm actual Driver 18
and native dependencies; do not trigger simulation, generation, policy changes or exports.

After **separate live-test approval**, use a fresh approved synthetic tenant and existing
lifecycle/decision/review/feedback steps above. Record independent SQL persistence and
tenant isolation, generation plus moderation through the policy pipeline, and one approved
non-overwriting ADLS export with readback. Investigate uncertain requests read-only; never
blindly replay. Historical failed manifests and the SQL HTTP driver remain prohibited.

Until successful live acceptance, demonstrate the disposable offline workflow and mock
export coverage. Azure SQL connectivity and Azure OpenAI/Moderation successes are historical;
ADLS and the deployed four-service chain have no successful live evidence yet.


## 11. Deployed Azure demonstration — safe startup verified

Open https://app-governance-validator-atiya-1026.azurewebsites.net . React root,
production JS/CSS and `/policies` deep link returned 200. `/health` and `/ready` both
returned 200; readiness used hosted managed identity and Azure SQL SELECT 1. Protected
API without a token returned 401, unknown/private paths 404, and CORS preflight passed.
Authenticated read-only diagnostics reported mssql CONNECTED, live/Presidio, and provider
configuration NOT VERIFIED. Eleven safe HTTP checks passed. No AI/export/business mutation
was executed. Deployment ID: `dd63d8eb-e68d-4617-869b-5ca3fbc884ea` (active/success).

Use the existing login UI with privately retained role-specific tokens at
`/tmp/governance-approved-deploy-obcsyrz6/demo-credentials.json` (0600, parent 0700).
Do not print or paste that file, put tokens into shell arguments, or commit it.
Opening the application does not authorize simulation, generation, policy changes or export.
The original offline rehearsal remains available; do not restart or modify port 8001.

For the next stage, obtain separate bounded approval described in the deployment runbook:
fresh synthetic tenant only, retained run-created records, at most five Azure OpenAI and
twenty moderation requests, and one new non-overwriting ADLS export. Use the existing
lifecycle, ALLOW/BLOCK/REDACT/HUMAN_REVIEW, human review, feedback and history workflows.
Stop on any uncertain outcome; inspect read-only and never blindly replay mutations.
Full deployed end-to-end results and visual browser acceptance remain unclaimed.


## 12. Actual live demo outcome and pending correction — 30 October 2026

URL: https://app-governance-validator-atiya-1026.azurewebsites.net

Use the fresh acceptance identities privately stored at
`/tmp/governance-live-acceptance-z1mats42/credentials.json` (0600, parent 0700).
Do not display/copy credentials into documentation, chat, logs or shell arguments.
Tenant `live-demo-81a5d4cc190a433bacc1` contains only retained synthetic acceptance data.
Do not retry the completed acceptance ledger or any historical failed manifest/driver.

Already demonstrable live: both policies, complete approval/publication/activation and
enable/disable lifecycle, immutable versions, BLOCK and HUMAN_REVIEW, review disposition,
feedback, current dashboard and audit/history. Moderation and Presidio redaction/revalidation
passed live. Dashboard truthfully shows ALLOW=1 (input-only validation), REDACT=0, BLOCK=3,
HUMAN_REVIEW=1. It must not be presented as four successful generation decisions.

The ALLOW and REDACT generation requests failed closed with no released response because
the async credential transport requires missing aiohttp. The one export status is FAILED,
ID `cc615711-f115-49ca-b35f-46ca292809e2`; do not click Export again under the consumed
one-export approval. Independent operator HEAD was denied 403; no successful file or
absence has been established. The ADLS conditional etag keyword defect was reproduced
with the actual pinned SDK offline. Full live output inspection remains unverified.

Both fixes are local and tested: use installed synchronous Azure credentials off the event
loop, and remove the redundant etag while keeping IfMissing/overwrite=False. Backend
220 tests and existing frontend 7 tests pass; one read-only React DOM test against the
live backend passes. All lint/type/build/format checks pass. See the exact corrected ZIP
hash, six failed assertions and requested deployment/additional-export/temporary-reader
approval in the [completion report](../reports/FINAL_PROJECT_COMPLETION_REPORT.md).

After approval, deploy the reviewed correction, verify startup, then use a new ledger for
two fresh ALLOW/REDACT generation checks and at most eight moderation calls, using this
run's policy/version. One additional non-overwriting UUID export and independent content
readback require the explicit extra export and filesystem-reader approvals. Retain the
original failure records; never overwrite, delete or replay them. No new service, higher
tier, migration, API key or UI redesign is needed. The existing disposable fixture demo
remains the fallback for ALLOW/REDACT generation until live correction checks pass.

## 13. Corrected worker deployed; fresh live acceptance gate

Reviewed ZIP SHA256 `7058b43850bdd4126d0a936e0e322c7e3bad7c4aba696ea85a7d1e10f784c38d`
was approved and deployed as `96fedb1b-e5db-426d-b7df-cf818f599bb7`. The platform confirmed
that version running at **07:08:19 UTC**. Post-switch read-only startup passed **11/11**.
URL: https://app-governance-validator-atiya-1026.azurewebsites.net

The bounded completion attempt ran too early, against the old serving worker while the
replacement started. Result: **51 passed, 9 failed assertions**; two generation requests
failed closed, one new export FAILED. Do not treat deployment status 4 or HTTP 200 alone
as proof of replacement readiness. Require application startup completion, successful
platform warmup, and **Site is running with deployment version [exact new ID]** in runtime
logs before mutating acceptance. Do not replay the consumed ledger or old manifests.
No inference/export calls have been made after the confirmed worker switch.

Both old failed exports are retained, including new UUID
`83317967-1471-4256-b872-3917f4ba47f6`; reader HEAD returned 404 for its exact new path.
The temporary filesystem reader role was removed and all prior roles preserved. Counts
are now 2 policies, 2 versions, 1 assignment, 27 audits, 7 executions, 1 resolved review,
2 feedback and 2 failed exports. Dashboard ALLOW=1, REDACT=0, BLOCK=5, HUMAN_REVIEW=1;
ALLOW is input validation, not successful generation. Historical failures must remain.

Use the hosted UI for read-only policy/history/dashboard/review/feedback demonstration.
Use the existing offline rehearsal for successful generated ALLOW/REDACT until fresh
live checks pass. Do not click Generate, Simulate, Validate or Export against the live
site under the consumed acceptance budget. A fresh approval is needed for up to two
additional generation requests, eight moderation calls, one new UUID export and temporary
filesystem reader/readback/removal. No new code deployment, resource, key or tier is
currently proposed. ADLS authenticates with managed identity; no ADLS API key is needed.

Open existing demo credentials privately in VS Code:

```bash
code "/home/sigmoid/AI governance policy validator/artifacts/demo-access/credentials.json"
```

Copy the appropriate role token directly into Access token on the deployed UI. This is
a JSON data file, not an executable command or a public browser URL. File mode is 0600,
its private directory is 0700, Git ignores it, and deployment excludes it. Do not change
permissions or publish/copy token contents into chat, screenshots or terminal commands.
Do not reuse the acceptance ledger merely to sign in; login only uses the existing token.

See [current machine-readable evidence](../LIVE_COMPLETION_RESULTS_2026_10_30.json) and
[completion report, section 22](../reports/FINAL_PROJECT_COMPLETION_REPORT.md#22-approved-correction-deployment-and-bounded-completion-attempt)
for precise limits and the remaining approval. No missing credential value is requested.

## 14. Latest final live verification and presentation sequence

The corrected serving worker is deployment `96fedb1b-e5db-426d-b7df-cf818f599bb7`.
Health/readiness and tenanted SQL/live/Presidio settings passed, as did both live generation
scenarios and output inspection. Latest driver **58 passed / 2 failed**: only successful
ADLS export and readback failed. Do not repeat consumed live calls or imply export works.

1. Open https://app-governance-validator-atiya-1026.azurewebsites.net.
2. Open `artifacts/demo-access/credentials.json` privately in a local editor. Copy the
   existing Admin token directly into Access token and click **Connect workspace**.
   Never include token contents in chat, commands, presentation or screenshots.
3. Open **Policy management**. Show the retained published policy, enabled active version
   2 and immutable versions. Reuse previous lifecycle evidence; avoid changing the active
   policy or records merely for this presentation.
4. Open **Validation history**. Inspect live ALLOW request `30b19444` and REDACT request
   `d879c256` (ID prefixes). Show input findings/revalidation, live model metadata, output
   moderation and decision. Stored metadata intentionally excludes raw safe response.
   The machine-readable acceptance evidence records nonempty safely released outputs.
5. Show earlier BLOCK and HUMAN_REVIEW execution metadata, then **Human review** with
   APPROVED_RESUBMIT_REQUIRED. Explain approval requires a newly inspected resubmission;
   it does not auto-release held content.
6. Show **Overview / Compliance analytics**: 9 executions, ALLOW 2, REDACT 1, BLOCK 5,
   HUMAN_REVIEW 1; two policies, one active, zero pending reviews. Historical provider
   failures remain truthful BLOCK outcomes. Show prior feedback/audit evidence.
7. Open **Audit & reports** to show lifecycle and generation events. Explain all three
   export attempts are FAILED; do not click Export under the consumed allowance.
8. For an interactive decision demo without new live usage, start the existing offline
   fixture rehearsal using section 1, then follow sections 2–5. Label fixtures clearly.

Successful live prompts already executed once, **not authorization to repeat**:

- ALLOW: `Reply with exactly the short sentence: Protect data carefully.`
- REDACT: `Contact demo.person@example.com. Reply with exactly the short sentence: Protect data carefully.`

Both reached Azure OpenAI and returned usable responses. Input/output moderation succeeded;
REDACT removed the email and revalidated before generation. No more inference tests are
necessary to close the remaining ADLS issue.

The only remaining completion task is the narrowly scoped ADLS existing-directory fix
and a fresh approved single-export/readback test. `DirectoryProperties.is_directory` at
`backend/app/providers.py:125` does not exist in the installed SDK; a network-free real-SDK
conflict-path diagnostic reproduces AttributeError. No source was changed under the
no-code-change instruction. The route suppresses detailed provider errors, so the exact
live exception is not asserted. Preserve conditional creation, directory/file distinction,
ACLs and overwrite=False when fixing it.

Current failed export UUID `1dfbf584-bfd2-4d5e-8614-5d244a61fa89` has an independently
observed 404 at its unique path. Temporary reader permission was removed with all prior
assignments preserved. ADLS uses managed identity; no API key is needed. Do not reuse
any failed export UUID, path or ledger.

[Latest exact live results](../FINAL_LIVE_VERIFICATION_RESULTS_2026_10_30.json) and
[completion report](../reports/FINAL_PROJECT_COMPLETION_REPORT.md#23-final-approved-bounded-live-verification--30-october-2026)
contain the retained evidence and approval boundary. Keep one B1 worker, avoid further
live calls without an allowance, and review recurring hosting costs after the demo.
Stopping the Web App alone does not eliminate App Service Plan charges. No cloud cost
configuration or resource lifecycle action was performed during verification.

## 15. Final end-to-end demonstration — current result

Final status: **PARTIALLY READY**. Serving deployment `5197c62d-7fc9-45ba-bec4-c3709bd42623`.
Current startup **11/11**, baseline **16/16**, ADLS acceptance **34 passed /
2 failed**, focused backend regressions **39 passed / 0 failed**.
No AI or moderation requests were made during the ADLS correction phase.

1. Open **https://app-governance-validator-atiya-1026.azurewebsites.net**.
2. Open `artifacts/demo-access/credentials.json` privately in VS Code. Copy the existing
   Admin token directly into Access token, then **Connect workspace**. Do not show tokens.
3. Show **Policy management**: the existing enabled active policy and immutable version 2;
   refer to the earlier recorded full approval/publication/activation lifecycle evidence.
4. Show **Validation history** ALLOW request `30b19444` and REDACT `d879c256`. Explain
   Azure OpenAI was called only after input approval and outputs were inspected before
   release. Show moderation SATISFIED and REDACT revalidation. Raw outputs are deliberately
   not stored in audit metadata; the retained test evidence records successful release.
5. Show earlier BLOCK/HUMAN_REVIEW, **Human review** APPROVED_RESUBMIT_REQUIRED, feedback,
   and **Overview / Compliance analytics**: nine executions, ALLOW 2, REDACT 1, BLOCK 5,
   HUMAN_REVIEW 1; two policies, one active, zero pending reviews.
6. Open **Audit & reports**. Show export **`d99ccce6-2726-462f-b42b-827d09500c0f`**, status **FAILED**,
   and its corresponding audit event. Keep the three historical FAILED exports visible.
7. Show [independent export evidence](../FINAL_ADLS_VERIFICATION_RESULTS_2026_10_30.json):
   exact-path 404, unchanged synthetic SQL records and successful reader cleanup.
   No downloaded file exists for this failed attempt; do not claim content equality.
8. Explain SQL/Azure OpenAI/ADLS managed identity and configured Moderation key use. No
   ADLS API key or additional Azure service is required.

No additional Generate, Simulate, Validate, lifecycle mutation or Export call is included
in the now-consumed bounded test. To interactively exercise more live requests, obtain a
new specific allowance. Use section 1's existing offline fixture rehearsal for interactive
practice without cloud usage; clearly label fixture output. Full visual browser QA remains
unperformed, while rendered UI/real HTTP and deployed asset checks passed.

The final correction checks supported `hdi_isfolder` metadata, retains conditional parent
creation and overwrite=False, and rejects missing/false folder markers. Both new and
existing-directory real-SDK paths have regression coverage. Temporary reader permission
was removed and previous roles preserved. Historical evidence files were not overwritten.

[Completion report section 24](../reports/FINAL_PROJECT_COMPLETION_REPORT.md#24-final-authorized-adls-correction-and-independent-live-verification)
is the authoritative latest status. Keep one B1 worker and avoid repeated live requests;
review recurring costs after the demo. Stopping the Web App alone does not eliminate its
App Service Plan charge. No resource/tier changes were performed.

## 16. Remaining gate after the single failed ADLS attempt

The directory-property fix is live and the exact worker/source verified. The one export
still failed (UUID `d99ccce6-2726-462f-b42b-827d09500c0f`), readback returned 404, and its
record plus all three prior failed exports remain. Temporary reader access was removed.
Latest live assertions: **34 passed, 2 failed**; no AI/moderation requests in this phase.

A second SDK issue is fixed **locally only**: new file upload must enter the SDK's create
branch with IfMissing, rather than appending before a new file exists. The guarded upload
uses overwrite=True plus mandatory MatchConditions.IfMissing; wire tests prove wildcard
non-match at creation, ETag match at flush, and no append to an existing output file.
Local targeted checks now **40 passed / 0 failed**, Ruff/39-file formatting passed.
The reviewed package SHA256 is
`b1a3dc0f3d53e98c4ce8c133cbd81d29146299530c42622a11cd384b492d46e1`.

Do not click Export or replay a failed path. A fresh approval for this package deployment
and exactly one new synthetic UUID export/readback/temporary-reader cleanup is pending.
Present existing successful generation, policies, review/audit/dashboard evidence and
label ADLS as pending. Existing offline fixture rehearsal remains available.
No extra Azure/OpenAI credential or new service is required.

## 17. Final accepted panel demonstration — 30 October 2026

### Prerequisites and access

Use https://app-governance-validator-atiya-1026.azurewebsites.net over HTTPS.
The accepted serving deployment is `eec1e450-11c4-4c0e-939f-f9df9e68999b`.
Keep this URL and [final evidence/matrix](../reports/FINAL_ACCEPTANCE_REPORT.md) ready.
Use the privately provisioned existing synthetic-tenant role token. Never put tokens in
slides, chat, shell arguments, screen recordings, screenshots or documentation.

| Role | Panel use |
| --- | --- |
| Admin | Main read-only hosted walkthrough; full disposable local workflow |
| Policy Owner | Local policy authoring/submission/publication/activation |
| Reviewer | Local policy approval and review dispositions |
| Developer | Local governance requests; hosted export access is correctly denied |
| Auditor | Hosted audit/export history; no new export request |

Local demonstration tokens are hashed and mapped server-side; they are not enterprise
SSO and have no time expiry. Sign-out removes the tab session credential. Invalid-token
API errors remain denied and visible; sign out/reconnect with the correct existing token.

Read-only availability checks (no credential required):

```bash
curl --fail https://app-governance-validator-atiya-1026.azurewebsites.net/health
curl --fail https://app-governance-validator-atiya-1026.azurewebsites.net/ready
```

Expected: HTTP 200, status ok / ready, provider_mode live. Settings shows mssql CONNECTED,
live providers and presidio. CONFIGURED_NOT_VERIFIED labels describe diagnostics only;
use independent evidence to substantiate actual prior live/provider/export success.

### Hosted walkthrough — recorded live evidence

1. Sign in through **Access token → Connect workspace**. Show Overview: 9 validations,
   2 policies, 1 active policy, ALLOW=2, REDACT=1, BLOCK=5, HUMAN_REVIEW=1, pending reviews=0.
2. Open **Policy management**, search/filter and open the immutable history for the
   existing Live Acceptance policy. Explain editable drafts versus immutable versions.
   Do not edit/activate/disable/archive the hosted policy during this recorded-evidence demo.
3. Open **Validation history → Inspect metadata** for existing ALLOW and REDACT cases.
   Explain input inspection, PII revalidation, approved model invocation, output
   inspection and audit commit before safe release. Raw safe responses are deliberately
   not stored in metadata; prior live execution evidence supports the release claim.
4. Show existing BLOCK and HUMAN_REVIEW results. Explain control precedence, withholding,
   and why a score cannot override a block. Use Compliance analytics for heuristic weights.
5. Open **Human review** and inspect the resolved case. Approval is metadata disposition
   requiring revised resubmission, not automatic release. Show existing feedback summary
   via approved read-only API evidence; there is no dedicated aggregate feedback UI panel.
6. Open **Audit & reports**. Show the four retained FAILED attempts and SUCCEEDED export
   `eae2ead0-2a52-4a34-a5dd-bcfb071a7df5`. Do **not** click Export JSON/CSV again.
   Explain independent readback: 9 allowlisted records, 1,745 bytes, SHA256
   `d561b2df77cee461bdf3a78d9e039ca1d4179dd267202f6d03941075b48e3cfb`.
   Show the [verification report](../reports/FINAL_ACCEPTANCE_REPORT.md) and matching audit event.
7. Explain architecture: same-origin React/FastAPI, server bearer/RBAC/tenant gates,
   immutable policy snapshots, Azure SQL, Azure OpenAI, moderation/Presidio, ADLS metadata.
   No extra cloud service or architectural redesign was introduced.
8. Sign out. State the controlled-demo verdict and separate [production backlog](../reports/PRODUCTION_BACKLOG.md).

The single new export allowance has been consumed. There were no new live Generate or
Moderation calls in final acceptance. Further hosted Generate, moderation-enabled
simulation or Export requests require an agreed additional allowance.

### Interactive policy and governance walkthrough — safe local fixtures

Use an unused port; do not stop an existing process. From repository root:

```bash
.venv/bin/python -B scripts/run_offline_demo.py --port 8010 --frontend-origin http://localhost:5174
```

In a second terminal:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174
```

Open http://localhost:5174 and privately use the temporary Admin token from the printed
credential-file path. Confirm the DETERMINISTIC LOCAL FIXTURES banner and PII regex.
Follow sections 2–6: create/edit/save a synthetic draft, validate through save/schema and
simulate, submit/approve/publish/activate, disable/enable, and inspect immutable history.
Demonstrate safe ALLOW, synthetic secret BLOCK, PII REDACT and fixture moderation failures.
For output withholding use fixture marker `[OUTPUT_SECRET]`; it never invokes a real model.
Set a draft keyword action to HUMAN_REVIEW, republish/activate and exercise approve/reject
with revised resubmission. Submit a numeric rating and inspect audit/analytics.
Use a separate unused draft for delete/archive. These exact supported UI workflows were
exercised in real Chrome against a fresh disposable database. Do not call them live AI.
Offline ADLS is disabled, so use the verified hosted file evidence for export success.
Gracefully stop only these rehearsal processes when done; the launcher removes its
own temporary database and credentials.

### Troubleshooting

- 401: sign out and reconnect with the correct privately provisioned token; never weaken auth.
- 403: use an authorized existing role; a visible button does not grant permission.
- 409: check lifecycle/active-enabled snapshot; do not reset the database.
- Hosted health outage: inspect deployment/worker logs and exact version first; no blind redeploy.
- Export failure or uncertain result: preserve records, collect exact-path evidence and obtain
  fresh approval before another attempt. Never replay an old UUID or overwrite a file.
- Mobile tables: scroll horizontally inside the table to reach action buttons. Chart
  animations settle after a short pause; scroll charts into view for screenshots.
- Full details/counts/screenshots: [final acceptance](../reports/FINAL_ACCEPTANCE_REPORT.md).

## 31 October 2026 — generation/output stabilization, awaiting deployment approval

Current local fixes and candidate package are documented in
[the live stabilization report](../FINAL_LIVE_STABILIZATION_REPORT.md),
[test results](../FINAL_END_TO_END_TEST_RESULTS.md) and
[deployment approval gate](../FINAL_AZURE_DEPLOYMENT_VERIFICATION.md).

Fresh results: 345 backend tests, 10 frontend tests, 57 Chrome fixture checks, eight
extracted-package checks passed. Local-live backend 8002 was restarted and SQL/readiness
verified using GET only; frontend 5175 targets it. Offline settings were preserved.
The hosted app still serves accepted deployment eec1e450; no new package is deployed.
The new live root cause/result remains unverified until separately approved API tests.
Do not reinterpret historical completion evidence as acceptance of the new candidate.

Before approval, demonstrate the new UI and all policy/release cases with the disposable
fixture launcher. For a later approved live walkthrough, sign in privately as Admin,
inspect the intended policy's immutable name/version and active enabled assignment,
then perform only the approved synthetic requests. Successful generation must be followed
by output inspection before any safe response is shown. Provider failure must display
Generation failed and withhold content. Input REDACT may retain its compliance violation
score while sanitized input and approved output are handled correctly. Human review
requires resubmission after disposition. Inspect compliance/audit/history via read-only
pages; preserve prior ADLS export history and do not export again without approval.
