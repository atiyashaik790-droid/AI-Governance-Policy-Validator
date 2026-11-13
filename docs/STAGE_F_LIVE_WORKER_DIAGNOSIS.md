# Stage F live worker diagnosis — 5 November 2026

**Main-container inspection: PASS. Stage F activation remains BLOCKED pending a separately approved controlled retry.**

**Historical activation root cause: UNKNOWN. Confirmed finding: acceptance checks and rollback overlapped incomplete container recycling.** The replacement activation worker was never verified ready; this was not evidence of a persistent settings-parser or deployment defect. Its subsequent failed startup probe is established, but the application error or exact interruption cause is not retained in the inspected application logs.

## Actual serving worker

- PID: **1965**.
- Start: **5 November 2026, 00:15:30 IST** / 4 November, 18:45:30 UTC.
- Executable: `/tmp/8df3a86dbc4c092/antenv/bin/python`.
- Observed entry point/arguments: `-m uvicorn app.hosting:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log`.
- Active release, verified through public readiness: **1.2-6749226f1af65b63**, schema **005**.
- Current Azure saved flags, actual worker environment, reconstructed Settings and the serving status API agree: **SSO=false, demo=true, client secret absent**. This is expected after rollback, not proof of what the previous activation worker received.
- Both `SSO_ENABLED` and `APPSETTING_SSO_ENABLED` are false. No duplicate case-variant saved SSO key was found.
- Actual deployed `config.py`, `sso.py`, and `hosting.py` hashes match reviewed repository source. Actual startup scripts do not assign SSO_ENABLED. No code deployment is indicated.
- The active config source is `/tmp/8df3a86dbc4c092/app/config.py`. Its configured `.env` resolves to `/tmp/.env`, which does not exist. Environment settings take precedence; no current dotenv override was found.
- Settings is instantiated once at module import. Status and authentication reference that same object. A fresh inspector-process reconstruction is clearly labelled as such; it is not presented as direct access to the Uvicorn process's Python heap. Actual worker environment plus actual HTTP status corroborate its current flags.

## Inspection mechanism repaired locally

The local CLI PTY wrapper exited before producing a shell prompt. The new `scripts/inspect_sso_worker.py` connects to the **same existing main-container** `/exec/shell` WebSocket using the existing approved CLI identity. It bypasses only the local interactive-terminal transport, checks the pinned tenant/operator token claims, keeps TLS certificate verification enabled, and uses the existing runtime/layout discovery.

No Kudu environment was substituted for the application environment. The inspector reads the serving worker's selected `/proc` values, source hashes and existing lifecycle logs, prints only selected non-secret flags/metadata, and writes only local evidence. It neither uploads a probe nor writes hosted files, accesses SQL, enables logging, installs tools, changes permissions or creates resources. CLI token output is consumed in memory and never printed or persisted. The CLI wrapper's own silent exit reason remains undetermined; the alternative transport is verified working.

Invocation from repository root: `/opt/az/bin/python3 scripts/inspect_sso_worker.py` (uses the already-installed CLI Python/WebSocket library). This is a date-scoped diagnostic with fixed safe targets, not a general remote-command interface. Local Ruff check/format passes; the actual read-only inspection passed. Existing product code was not changed and B–E suites were not rerun.

## Timeline and what it proves

All times below are UTC on 4 November; add 5:30 for IST on 5 November.

| Time | Evidence |
|---|---|
| 18:35:28 | Previous container reported site running |
| 18:35:38 | Azure accepted SSO activation config write; saved true verified |
| 18:35:48 | Container termination/stopping recorded |
| 18:38:01–18:38:11 | Independent public mismatch check ran before replacement container start |
| 18:38:14 | Replacement container starting |
| 18:38:15 | Container infrastructure ready; **not application readiness** |
| 18:38:46–18:38:53 | Rollback settings writes started/completed |
| 18:39:09 | Site startup probe failed |
| 18:39:13 / 18:39:50 | Container stopping events |
| 18:44:22 | Rollback replacement container starting |
| 18:45:30 | Current Uvicorn worker started |
| 18:45:38 | Site startup probe succeeded |
| 18:45:40 | Site running |

This disproves the earlier assumption that a saved setting plus a short HTTP polling interval established a completed recycle. At least one decisive mismatch check preceded the replacement container start, and rollback changed configuration before its application startup succeeded. The current worker started after rollback and correctly received rollback settings.

It does **not** establish that the failed activation worker ever reached Python startup with SSO=true, that the secret was invalid, or that a configuration override existed. Do not label normal per-process Settings construction a caching bug. Inspected application stdout logs end at 18:28:15 UTC; they do not contain the failed activation's traceback. Absence of a recorded traceback therefore cannot clear or diagnose its failed startup probe. Platform lifecycle evidence is separate and does cover the interval.

## Public probe results

Hard-bounded parallel curl requests succeeded: `/health` ok, `/ready` ready at 005 on the expected release, `/api/sso/status` SSO=false/configured=false/demo=true. The earlier public timeouts are no longer reproducible in this observation. No login/callback/session endpoint or Stage G test was invoked.

## Smallest safe next action and approvals

No restart, configuration change, secret entry or deployment is needed **now** to preserve the working rollback state. No evidence justifies redeploying or adding dynamic Settings reloads.

The shortest next activation route is a separately approved **configuration-only retry with worker-aware verification**, not another code deployment:

1. Coordinate private Portal secret entry, preserving SSO=false. Wait for that settings-induced recycle to finish and verify a new serving worker and demo readiness before another settings save.
2. Save the already-reviewed non-secret activation settings once. Do not race another save or rollback against its in-progress recycle.
3. Observe instance/startup lifecycle, then inspect the **new** worker PID/start time and SSO_ENABLED=true/secret-presence/demo=true before interpreting public status. Wait for application startup-probe success, not merely container infrastructure readiness. Use hard-bounded probes (45 seconds each) within an explicitly approved maintenance deadline of up to 15 minutes for sequential recycle/warmup observation; this is a limit, not a guaranteed startup duration.
4. If startup fails, collect sanitized contemporaneous error categories before the approved SSO-off rollback. If the deadline expires without a new ready worker, reconcile lifecycle state and use only the approved rollback; do not blindly resave settings or restart repeatedly.

Approval needed: authorize that exact Stage F retry, user-controlled private secret save, its settings-induced restarts, bounded worker/readiness verification, and SSO-off rollback. **No extra manual restart, deployment, credential rotation, SQL change or Stage G testing is proposed.** If a later observation proves an explicit manual restart is necessary, obtain separate approval rather than inferring it from this diagnosis.

## Evidence

[Actual worker, source, startup and sanitized lifecycle data](evidence/stage-f-live-worker-2026-11-05/runtime-final.json), [fresh saved configuration booleans](evidence/stage-f-live-worker-2026-11-05/saved-configuration.json), [public checks](evidence/stage-f-live-worker-2026-11-05/http.json), [existing instance](evidence/stage-f-live-worker-2026-11-05/instance.json), [asserted result](evidence/stage-f-live-worker-2026-11-05/result.json). Prior write timeline: [management evidence](evidence/stage-f-diagnosis-2026-11-05/management.json).
