# Runtime probe diagnosis — 4 November 2026

## What is established

The operator's old `MAIN_APP_SHELL_OR_COMPLETE_PROBE_RESULT_UNAVAILABLE` result means
that no complete final JSON record was recognized during the shell lifecycle. The
old implementation discarded the stage evidence; it does **not** establish whether
SSH/SCM authorization, the CLI, working directory, Python, imports, SQL, timeout or
parsing caused that particular Ubuntu run. Do not infer a permission denial.

The wrapper `scripts/verify_sso_deployment_readiness.sh` correctly selects the existing
project-local CLI context. `scripts/sso_deployment_readiness.py --remaining-only`
correctly skips the successful full CLI SQL/schema/backup checks and delegates to
`scripts/verify_hosted_runtime.py`. The defects were in that delegated probe:

- Prompt matching used raw terminal bytes and required the prompt to end in `#` or
  `$` followed by at most one space. ANSI-colored prompts were not recognized.
- The read loop could break when the local CLI exited before draining its queued
  final output from the PTY.
- All shell exits/timeouts shared one category. Pre-Python failures had no structured
  record, and most runtime exceptions lost their stage and SQL classification.

The parser now removes terminal control sequences, accepts colored prompts, drains
through EOF, distinguishes partial and malformed JSON, and retains bounded fixed-label
progress. These defects are reproduced in focused tests. Whether either transport
bug caused the user's previous run remains unverified.

A single direct agent attempt of the remaining-only command stopped at:

```json
{"status":"UNKNOWN","category":"AZURE_NETWORK_OR_DNS_UNAVAILABLE","stage":"app_discovery","hosted_runtime_identity_verified":false,"database_mutated":false}
```

This agent environment did not reach the main-app shell or SQL. Its network blocker
is separate from the operator's Ubuntu failure. No successful backup or full CLI
schema check was repeated.

## Next command on Ubuntu

```bash
bash scripts/verify_sso_deployment_readiness.sh --remaining-only
```

The command keeps the existing context, identity/target guards and main-container
selection (`--mode shell --target app`). It does not switch identity or use Kudu to
claim application runtime proof. The shell lifecycle is bounded to 55 seconds and
cleanup closes only the local CLI session. Existing app connection/query timeouts
remain unchanged. Read-only queries execute under the existing app connection.

| Evidence/category | Meaning and smallest next action |
|---|---|
| `AZURE_CLI_EXEC_UNSUPPORTED` | Existing CLI does not support the requested command/arguments; use the authorized manual console procedure below. No automatic upgrade/install. |
| `MAIN_APP_SHELL_AUTHORIZATION_DENIED` | CLI returned an authorization denial; an already-authorized operator must use the existing console. No new role/grant/identity is requested. |
| `EXISTING_CLI_AUTHENTICATION_UNAVAILABLE` | Existing CLI authentication is unavailable; stop and have the operator resolve its existing approved context. No login/switch is attempted. |
| `MAIN_APP_SHELL_NETWORK_OR_DNS_UNAVAILABLE` / `MAIN_APP_SHELL_CONNECTION_FAILED` | The CLI reported a network/connection failure; use existing authorized access from a working network. No firewall/settings changes. |
| `SHELL_PROMPT_NOT_RECOGNIZED_TIMEOUT` / `MAIN_APP_CLI_EXITED_BEFORE_SHELL_PROMPT` | No recognizable shell prompt; no payload sent. This does not prove SSH denial. Use manual console. |
| `APP_WORKING_DIRECTORY_UNAVAILABLE` / `RUNTIME_APP_PACKAGE_UNAVAILABLE` | Existing APP_PATH/default directory or `app/database.py` unavailable. Stop; confirm the existing main app console and deployed path without dumping settings. |
| `RUNTIME_PYTHON_EXECUTABLE_UNAVAILABLE` / `RUNTIME_PYTHON_PROCESS_FAILED` | No existing executable was found or Python failed before a complete record. No tools are installed. |
| `RUNTIME_IMPORT_UNAVAILABLE` | Python started but installed runtime imports/config import failed. No exception text/settings are displayed. |
| `RUNTIME_IDENTITY_CONFIGURATION_MISMATCH` | Existing mode/tenant/principal/database configuration does not match the approved target; stop. Never fall back to CLI SQL. |
| SQL diagnostic category, e.g. `SQL_PERMISSION_DENIED` | A fixed-label SQL classifier recognized the error; `stage` distinguishes engine, connection, identity, revision and schema/permissions. No raw SQL exception is printed. |
| `RUNTIME_STAGE_TIMEOUT` | Last observed `stage` identifies the remote operation which did not finish within the outer bound. Do not infer successful SQL access. |
| `PROBE_RESULT_INCOMPLETE_JSON` / `PROBE_RESULT_JSON_INVALID` | A truncated/malformed result was observed; neither is accepted as runtime proof. |
| `LOCAL_PROBE_IMPLEMENTATION_OR_INPUT_FAILURE` | Local code/input failure, with allowlisted error kind; no raw exception content. |

Outputs retain `database_mutated=false`, `hosted_files_written=false` when the hosted
probe was attempted, and `hosted_runtime_identity_verified=false` unless **all**
actual-runtime checks pass. A permission/mapping failure is not repaired automatically.
A runtime PASS remains scoped to the actual runtime 004 contract, not deployment
approval or database restore authority.

## One manual fallback procedure — existing authorized main App Service console

1. On Ubuntu, prepare the exact self-contained command locally (no cloud connection,
   no secrets, no application/environment changes):

   ```bash
   bash scripts/verify_hosted_runtime.sh --manual-console > /tmp/governance-runtime-console.READ_ONLY.sh
   ```

2. Open that local text file in VS Code and copy its complete contents. In the existing
   Azure portal App Service `app-governance-validator-atiya-1026`, open **Development
   Tools → SSH → Go**, using the already-authorized identity. Confirm this is the
   **main app container**, not Advanced Tools/Kudu Debug Console. Do not enable access,
   basic auth, SSH or another identity if unavailable.
3. Paste the copied command into that existing main app console once. It selects the
   existing APP_PATH/application Python environment, checks the app package and runs
   the same reviewed read-only contract using `app.database.SessionLocal`. The helper
   is evaluated in memory; no script is uploaded/written to the hosted filesystem.
   Session-only bytecode/history suppression is not an App Service settings change.
4. Read the final `SSO_MANUAL:{...}` record (preceded by safe progress markers). Only
   PASS with the exact managed identity and full 004 runtime checks is proof. FAIL or
   UNKNOWN retains its category and stage. Do not paste environment dumps, credentials
   or raw console tracebacks into reports.

If both automatic access and the existing main-app console are unavailable, runtime
verification is externally blocked on existing SCM/console authorization, networking
or main-container availability, as indicated by the observed denial/stage. No new
code can establish runtime proof in that condition. Stop; do not repeatedly rewrite
probes or grant permissions/change access settings under this authorization.

## Validation and Stage B decision

31 focused tests PASS: colored prompt/queued output, CLI authorization/connection/
unsupported-command failures, timeout, malformed/partial JSON, missing directory/
package/Python, real payload SQL-permission classification, import failure, identity
mismatch, SELECT-only session behavior, redaction and remaining-only dispatch. Ruff
lint/format and shell syntax (including generated manual command) PASS. No unrelated
suite was run and no hosted mutation occurred.

**Stage B remains BLOCKED on actual runtime PASS**, plus the existing explicit release
approval and confirmed rollback owner/window/saved SSO-off/demo-on settings. Operator
schema 004, no partial 005, package, Running app/MI and seven-day backup results are
preserved. A fresh recovery drill is not an established Stage B prerequisite.
Migration 005, grants, memberships, SSO settings/activation and deployment remain
unauthorized and are not performed by either channel.

## Exact working-directory failure and narrow fix — 4 November 2026

New operator evidence: the main application shell is reachable; the probe returned
`RUNTIME_APP_PACKAGE_UNAVAILABLE` at `working_directory`. This proves the selected
`APP_PATH` (or `/home/site/wwwroot` default) was accessible but did not contain
`app/database.py` immediately beneath it. The old code stopped before choosing Python
or importing the application. It assumed a flat deployment and did not discover the
running app's CWD, `--app-dir`/`--chdir`, a `backend/app` layout or an extracted Oryx
runtime. A particular hosted directory has **not** yet been observed by the agent.

Only directory discovery/interpreter selection/import handling changed:

- `scripts/runtime_layout.py` inspects at most 256 process entries, reading at most
  16 KiB of each command line privately. It never reads `/proc/*/environ` or prints
  command lines, startup-script contents, flags other than the recognized module,
  settings or secrets. It recognizes the expected `app`/`backend.app` Uvicorn/Gunicorn
  targets, process CWD and import-directory options.
- Actual matching process roots take precedence over potentially stale deployment
  roots. It checks only each bounded root and its `backend` child. Fallback roots are
  the existing APP_PATH, console CWD and conventional deployment root; none is claimed
  to be the actual hosted path until required app files are present. There is no
  recursive whole-filesystem search or hard-coded extracted `/tmp` directory.
- A package requires `app/__init__.py`, `database.py`, `config.py` and `models.py`.
  No match returns `RUNTIME_APP_PACKAGE_NOT_FOUND_IN_BOUNDED_ROOTS`; multiple matches
  return `RUNTIME_APP_PACKAGE_LOCATION_AMBIGUOUS`. No arbitrary candidate is selected.
- Python comes from an observed matching app process or an existing adjacent virtual
  environment, existing VIRTUAL_ENV or PATH; only executable files qualify. The
  probe changes only its own CWD and explicitly prepends the verified package parent
  to its own Python import path before executing the original read-only SQL probe.
  No new interpreter/dependencies or hosted files are installed or written.
- Safe `layout` output reports the verified application working directory, package
  location, Python executable, import path and observed startup module/process CWD
  where available. It does not dump the startup command or environment. Layout
  discovery alone never sets `hosted_runtime_identity_verified=true`.

For normal verification after this fix, use the existing command:

```bash
bash scripts/verify_sso_deployment_readiness.sh --remaining-only
```

To inspect only paths, with **no SQL or recovery-permission queries**, the bounded
remote diagnostic is `bash scripts/verify_hosted_runtime.sh --layout-only`. A found
layout reports `layout_status=PASS` alongside UNKNOWN runtime status, because SQL has
not been tested. Agent execution of this mode stopped at `app_discovery` /
`AZURE_NETWORK_OR_DNS_UNAVAILABLE`; no container path/startup/interpreter claim is
based on that failed attempt. Repository `deployment/startup.sh` launches
`python -m uvicorn app.hosting:app`; that is local intended startup evidence, not an
observation of today's running command.

### Exact read-only command for the existing main App Service SSH console

If automatic access from your terminal is unavailable, paste this **one multiline
command** into the existing authorized **main app** SSH console. It only prints
verified paths and recognized module names; it does not import app code or query SQL.
It is a bounded diagnostic, not proof of runtime SQL permissions:

```sh
python - <<'PY'
import json, os, pathlib, shutil, sys
P = pathlib.Path
roots = [P.cwd(), P('/home/site/wwwroot')]
if os.environ.get('APP_PATH'):
    roots.insert(0, P(os.environ['APP_PATH']))
observed = []
try:
    entries = sorted((p for p in P('/proc').iterdir() if p.name.isdigit()), key=lambda p: int(p.name))[:256]
except OSError:
    entries = []
for entry in entries:
    try:
        with (entry/'cmdline').open('rb') as stream:
            args = stream.read(16384).decode(errors='replace').split('\0')
        target = next((s for s in args if s in ('app.hosting:app','app.main:app','backend.app.hosting:app','backend.app.main:app')), None)
        if target and any('uvicorn' in s or 'gunicorn' in s for s in args):
            base = (entry/'cwd').resolve(strict=True)
            roots.insert(0, base)
            observed.append({'working_directory':str(base), 'python_executable':str((entry/'exe').resolve(strict=True)), 'startup_module':target})
            for i, arg in enumerate(args):
                if arg in ('--app-dir','--chdir') and i+1 < len(args):
                    roots.insert(0, base/args[i+1])
    except (OSError, ValueError):
        pass
found = sorted({str(root.resolve()) for base in roots for root in (base,base/'backend') if all((root/'app'/name).is_file() for name in ('__init__.py','database.py','config.py','models.py'))})
print(json.dumps({'package_roots':found, 'package_locations':[str(P(r)/'app') for r in found], 'console_python_executable':sys.executable, 'observed_app_processes':observed, 'status':'FOUND_REVIEW_PATHS' if found else 'RUNTIME_APP_PACKAGE_NOT_FOUND_IN_BOUNDED_ROOTS', 'database_mutated':False}, indent=2))
PY
```

For the exact same discovery implementation used by automation, the existing
`--manual-console --layout-only` generator also prints a self-contained command to
paste into this console. Neither method uploads a file. If no Python command is
available in that existing console, stop and report that specific prerequisite;
do not install tools or alter App Service settings.

Validation: **10 layout tests plus 31 affected probe regressions PASS**. Cases include
flat/backend layouts, active process precedence over stale APP_PATH, `--app-dir`,
existing venv selection, safe proc inspection, missing/ambiguous packages, interpreter
selection, actual child import-path compilation and layout-only/no-SQL behavior.
Ruff lint/format and generated shell syntax PASS. No successful full CLI schema,
backup or artifact checks were repeated. Actual hosted layout/runtime SQL proof is
still pending the operator's corrected run.
