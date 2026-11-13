# WebJobs configuration diagnosis — read-only; repair unverified

8 November 2026. Fresh ARM observation09:12:53UTC: existing `app-governance-validator-atiya-1026`, kind`app,linux`, reserved=true, Running, linuxFxVersion`PYTHON|3.13`, AlwaysOn=true, one worker, webJobsEnabled=false. No custom-container image configuration found. Both `WEBSITE_SKIP_RUNNING_KUDUAGENT` and `WEBSITES_ENABLE_APP_SERVICE_STORAGE` are absent, not explicitly false. [Current evidence](evidence/webjobs-settings-diagnosis-2026-11-08/current-settings.json).

This is Linux code hosting using the platform-managed Python image. Existing startup evidence identifies appsvc/python:3.13_20261028.2.tuxprod; that managed image does not make this a custom-container deployment.

Microsoft's [WebJobs quickstart](https://learn.microsoft.com/en-us/azure/app-service/quickstart-webjobs) explicitly requires WEBSITE_SKIP_RUNNING_KUDUAGENT=false for all Linux apps. Python code WebJobs are supported by the [execution guide](https://learn.microsoft.com/en-us/azure/app-service/webjobs-execution). The [Azure Linux platform documentation](https://github.com/Azure/app-service-linux-docs/blob/master/Things_You_Should_Know/things_you_should_know.md) marks storage-persistence setting control for containers rather than code. The [Linux FAQ](https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/faqs-app-service-linux-new) discusses the storage-enable recommendation under custom containers. Do not infer disabled /home persistence from an absent setting on this built-in runtime. No live mount test was performed. Setting storage=true is not an evidenced repair for this configuration and is excluded from the proposed change.

## Failure interpretation

Prior Kudu trace proves forwarding to an unavailable169.254.130.5:50555 agent. No watchdog package was uploaded, so Python/watchdog code cannot explain that failure. Missing enablement explains the currently disabled feature but is not sufficient to explain the previous HTTP500, because false was already temporarily set then.

Existing container trace: new container started16:54:54UTC; WebJobs request began16:55:02; configuration rollback at16:55:09; failed warmup recorded16:55:19. Thus the earlier check did not establish a fully warmed new container/agent before the request; earlier health samples could have reached the outgoing worker. A premature request/startup interruption is a plausible, testable explanation, not a proven agent defect or proof that waiting fixes it. Logs did not expose an agent-specific launch exception. No evidence establishes that storage mounting caused the failure.

## Smallest reversible proposal — explicit approval required

A15minute enablement/startup diagnostic window on this existing Web App only:

1. Fresh account/target/health/release005/settings baseline; preserve all settings in protected process memory. Abort on drift. Do not expose encryption or any credentials.
2. Add only WEBSITE_SKIP_RUNNING_KUDUAGENT=false. Leave WEBSITES_ENABLE_APP_SERVICE_STORAGE absent and preserve every unrelated setting, including staged review keys. Accept the resulting recycle; no extra manual restart.
3. Establish from a new startup log sequence that the changed container has actually completed startup, plus stable matching health/readiness/release. Allow at most5minutes. Record sanitized agent-start/listener evidence if present. This new prerequisite is the justified difference from the consumed compatibility check.
4. Only after the new startup-complete evidence, permit one authenticated read of the WebJobs listing API. No polling of that API, upload, job creation or execution. If startup cannot be established, do not repeat the API. If500 recurs, capture only sanitized failure timing/signatures and stop; do not claim a repair.
5. Remove only the newly added setting at completion, success or failure, restoring its original absent state; preserve all other values and verify health/readiness/release005. Reserve time for rollback inside the15minute total. If API succeeds, classify enablement as verified for that window, not watchdog/deletion reliability. Leaving it enabled or uploading any job requires separate explicit authorization.

Expected disruption: one recycle on enablement and another on restoring absence, budget approximately1–5minutes per recycle; actual duration is not guaranteed. Existing single-worker hosting can interrupt requests. No new resource/support plan/service capacity; estimated added service costUSD0. Rollback is exact removal of this flag, not wholesale replacement of current settings. Stop on unexpected configuration change, failed startup, critical health failure or window budget exhaustion; attempt rollback and report any unverified recovery.

This is a supported enablement diagnostic and possible timing-related recovery, **not a demonstrated repair**. It does not establish a hard temporary-database deadline or authorize watchdog permissions, any job, SQL, provider calls or deployment. No configuration, restart or WebJobs API call occurred in this read-only investigation.
