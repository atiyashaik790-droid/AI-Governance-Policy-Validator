> Superseded runtime-channel limitation: main-container inspection now passes. See [live worker diagnosis](STAGE_F_LIVE_WORKER_DIAGNOSIS.md) for process, source, environment and lifecycle evidence. Historical findings below are retained.

# Stage F configuration mismatch diagnosis — 5 November 2026

**Root cause: UNKNOWN. Rollback state preserved.**

No hosted configuration, secret, restart, deployment, SQL operation or Stage G flow was performed during this diagnosis. No product code change is justified by the evidence.

## Established facts

- Fresh ARM inspection resolves the exact intended production resource and hostname. Slot list is empty; the prior commands specify no slot. No wrong-slot evidence was found.
- Azure Activity Log records successful `Microsoft.Web/sites/config/write` at 18:35:38 UTC for activation, and 18:38:47/18:38:53 UTC for rollback. These prove management-plane writes, not worker restart completion.
- Prior activation journal and independent management readback established saved SSO_ENABLED was exactly `true`. Current saved value is `false`, demo flag `true`, secret absent, matching rollback. Tenant/client/origin comparisons pass.
- Saved startup command matches `sh startup.sh`, Python runtime is 3.13, Always On enabled. The reviewed release startup runs `uvicorn app.hosting:app` with access logs disabled and no SSO environment assignment. It does not run migrations.
- Current deployed release evidence identifies 1.2-6749226f1af65b63, which includes SSO and supports schema 005. Prior public served assets matched the preserved release exactly. Current on-disk Python source hashes could not be obtained because the runtime shell probe never reached the container.
- Source `app.config.settings = Settings()` is constructed once per imported process. Pydantic reads environment plus the configured `.env`; isolated synthetic checks confirm an environment variable overrides a conflicting `.env` value. No dynamic settings reload exists.
- Status and authentication routes use the same `app.config.settings` object; `configuration` binds this same object as its default argument. Invalid or absent secret/configuration can make configured=false, but cannot by itself make status.sso_enabled=false if this shared object has sso_enabled=true.
- Isolated local status check with synthetic secret and stubbed schema inspection returned `{sso_enabled:true, configured:true, demo_login_enabled:true}` without SQL or OIDC. Existing Settings objects do not change when environment changes; a new Settings instance sees the new flag. This is expected process-scoped behavior, not proof of a production caching defect.

## Critical missing evidence

The existing read-only `az webapp exec --mode shell --target app` channel exited with code 1 before a shell prompt, with no diagnostic text captured. Both sh and the documented default bash variant failed before any payload was sent. Thus no hosted file was written, no application module was imported by the probe, and no process environment/start time was read.

The historical activation's actual worker environment, loaded settings object and process start/restart times remain UNKNOWN. Successful config writes do not independently prove a serving-worker restart. Current post-rollback values cannot reconstruct historical values. Old worker, ineffective restart, worker-specific override and other runtime causes remain hypotheses; neither browser cache nor wrong release is confirmed as the cause.

The final no-cache public /ready and /api/sso/status requests both timed out at the 45-second request timeout. Consequently no fresh cache headers or public release body were obtained in this diagnosis. This does not establish an SSO failure or prove the current application is unhealthy; current public availability is unverified. The last successful rollback health/readiness result remains historical evidence.

## Smallest safe correction

No hosted or product-code correction can responsibly be selected until runtime evidence is available. Do not add dynamic settings reloads, alter authentication semantics or redeploy the dirty tree merely to treat a hypothesis.

A separate, confirmed verifier defect was corrected in a **local review-only command artifact**: the original 15-second readiness timeout was shorter than an observed 19.5-second response. The prepared artifact uses 45 seconds. It was not executed, and this verifier defect does not explain why successful status responses reported SSO=false. Prior longer-timeout reconciliation also observed the flag mismatch.

## Required next evidence and approvals

Restore access to the existing main-container read-only shell, or have the authorized operator use the existing Portal SSH console to collect only: selected SSO_ENABLED/DEMO_BROWSER_LOGIN_ENABLED flags, secret-presence boolean (never its value), actual serving-worker PID/start time, deployed config/sso/startup source hashes, and loaded settings flags. Do not use Kudu's separate environment as proof of the serving worker, dump process environments, install tools or write a hosted probe file. The prepared runtime command prints only selected non-secret diagnostics and accesses no SQL.

Read-only runtime inspection is already authorized; it needs a working channel, not new SQL/Azure permissions. If evidence proves a worker failed to recycle, the smallest candidate correction is a single explicitly approved existing-app restart, followed by bounded configuration checks; it is not executed or asserted necessary here. No deployment is currently indicated.

The client-secret setting must be privately re-entered before a future approved activation because rollback removed it. No re-entry or replacement is needed for diagnosis. The password-manager copy and Entra credential remain unaffected. Any future hosted correction/activation/restart requires explicit scope and a coordinated private secret save; no rotation is indicated.

## Evidence

[Management target, slots, saved flags and activity](evidence/stage-f-diagnosis-2026-11-05/management.json), [runtime channel result](evidence/stage-f-diagnosis-2026-11-05/runtime.json), [sanitized channel failure](evidence/stage-f-diagnosis-2026-11-05/shell-channel.json), [isolated status check](evidence/stage-f-diagnosis-2026-11-05/isolated-settings-status.json), [environment precedence check](evidence/stage-f-diagnosis-2026-11-05/settings-precedence.json), [public serving state](evidence/stage-f-diagnosis-2026-11-05/public-serving-state.json).
