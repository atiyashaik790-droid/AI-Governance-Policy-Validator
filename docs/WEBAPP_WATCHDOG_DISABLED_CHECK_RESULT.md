# Disabled WebJob compatibility check — PARTIAL / stopped and rolled back

7 November 2026, Asia/Kolkata. Explicit approval was limited to the 15-minute disabled check. Execution ran **22:23:53–22:25:14 IST** (16:53:53–16:55:14 UTC), **80.64 seconds**, within the limit. Approval is consumed; no automatic retry or later execution is authorized.

**The application is healthy and its original configuration is restored. The WebJobs API failed before any package was uploaded.**

## What passed

- Exact subscription, Web App, existing managed identity, Always On=true, PYTHON|3.13 and one worker verified. Existing authenticated SCM read access worked; conventional WebJob directories were absent.
- Approved ZIP SHA-256 verified: `fc4070ec948fd1465fa2226e7979357eec8def1f9dd9ab97fe2f3ef9bb2d7cd1`. Its exact four-file contents, disabled policy and absence of the deletion flag in run.sh were verified. It contains no SQL database create path; its existing local tests prove disabled mode returns before identity/ARM access. Hosted mutation-gate execution was not reached.
- Original WEBSITE_SKIP_RUNNING_KUDUAGENT setting was absent. Baseline recorded securely and sanitized setting presence/fingerprint retained. Only this setting was temporarily added as false; all other setting values were checked unchanged.
- Public /health and /ready passed at baseline and after enablement. Served application release was **1.2-ca5df7c1dc19e525** and readiness reported revision **005**; this was the observed existing release, not a deployment by this check.

## Failure and immediate stop

After enablement, authenticated SCM **GET /api/continuouswebjobs returned HTTP 500**. The controller stopped with WEBJOBS_ENABLEMENT_FAILED_500 at 22:25:05 IST. It did not upload a package, create a WebJob, attempt startup or retry enablement. Pre-availability polling was bounded; no second compatibility run occurred.

Cause of the WebJobs HTTP500 is **not established**. This is not evidence of Python incompatibility because the Python package had not been uploaded or executed. No attempt was made to change additional settings, credentials, permissions, runtime, worker count or services to work around it.

No job was created or running, so there was no job to stop or delete. Hosted Python startup, sanitized hosted watchdog logs, persistent-path operation and execution independent of the laptop remain **NOT REACHED**. The prior local passes remain valid and are not relabeled as hosted passes.

## Rollback and final state

The controller removed only the newly added WEBSITE_SKIP_RUNNING_KUDUAGENT setting, restoring its original absent state. All app settings matched the complete baseline afterward. The temporary private local snapshot containing full settings was removed after restoration; only sanitized evidence remains in the project.

Final /health=200/status ok and /ready=200/status ready passed at 22:25:14 IST. Complete release metadata matched the baseline, and readiness still reported 005. No application release was deployed. Health was sampled at the stated points; continuous availability between samples is not claimed.

No SQL database was created/deleted, no direct SQL command or permission change was performed, and no production data mutation was requested. Existing /ready checks perform SQL-backed read-only verification. No real Azure OpenAI, Moderation or ADLS operation, rehearsal, recovery drill or additional Azure service. Watchdog arming and all later approvals remain unauthorized. Incremental service capacity was not added; existing App Service charges continue.

## Evidence and verdict

[Approval](evidence/webapp-watchdog-disabled-check-2026-11-07/approval-record.json), [execution/UTC ledger](evidence/webapp-watchdog-disabled-check-2026-11-07/execution.json), [baseline health](evidence/webapp-watchdog-disabled-check-2026-11-07/baseline-health.json), [after-enable health](evidence/webapp-watchdog-disabled-check-2026-11-07/after-enable-health.json), [final health](evidence/webapp-watchdog-disabled-check-2026-11-07/final-health.json), [result summary](evidence/webapp-watchdog-disabled-check-2026-11-07/result-summary.json), [executed controller](evidence/webapp-watchdog-disabled-check-2026-11-07/executed-controller-source.txt), [evidence checksums](evidence/webapp-watchdog-disabled-check-2026-11-07/evidence-sha256.json).

**PARTIAL: safe bounded check and rollback complete; hosted WebJob compatibility remains blocked by the enablement API failure.** All previously passing application/Azure SQL evidence is preserved. No additional diagnosis, enablement retry, permission grant, arming, SQL rehearsal, Recovery B or production C–F will run under this approval. Stop here as requested.
