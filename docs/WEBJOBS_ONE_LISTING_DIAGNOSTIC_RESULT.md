> **Correction from read-only follow-up:** the09:18:20 marker was warmup-in-progress, not completed startup. Actual probe success was09:18:55, after the failed request. See [corrected diagnosis](HEALTH_NETWORK_READONLY_DIAGNOSIS.md). Rollback evidence remains valid.

# WebJobs configuration diagnostic — PARTIAL; rollback PASS

8 November 2026,09:16:32–09:19:11UTC (14:46:32–14:49:11IST);158.494seconds total, within15minutes. Exact existing Web App, identity, Python3.13/AlwaysOn/single worker and baseline release005 verified. Latent WebJob directories were absent.

An initial read-only transport failure occurred before configuration changes; the same approved deadline and single-listing limit were preserved when resuming pre-change reads. Only WEBSITE_SKIP_RUNNING_KUDUAGENT=false was then added at09:17:43UTC. All other app settings matched baseline; WEBSITES_ENABLE_APP_SERVICE_STORAGE remained absent.

**New evidence:** the changed container emitted a startup-complete marker at09:18:20.6665441UTC, observed in the platform docker log. This establishes successful main-container startup under the enabled flag, not internal-agent50555 readiness.

Before stable health/readiness samples could be established, a public health/readiness request failed with URLError at09:18:48UTC. No HTTP error status or application failure cause was established. The diagnostic stopped and restored configuration rather than proceeding. **WebJobs listing requests:0. HTTP listing status:NOT REACHED.** No second HTTP500 occurred in this run; no agent repair or WebJobs availability is claimed.

Rollback restored the original absent flag at09:18:52UTC. Final full app-settings comparison and selected web configuration match baseline. Final two health/readiness samples passed, complete release metadata matched, release1.2-ca5df7c1dc19e525 and revision005 unchanged. Staged encryption keys and every unrelated setting remained unchanged. webJobsEnabled returnedfalse.

No WebJob created/uploaded/executed, SQL command/migration/permission change, database creation, release deployment, provider call or added service. Added service capacity costUSD0; continuous website availability/downtime duration was not measured.

[Execution ledger](evidence/webjobs-one-listing-diagnostic-2026-11-08/execution.json), [startup evidence](evidence/webjobs-one-listing-diagnostic-2026-11-08/new-startup-evidence.json). Diagnostic approval consumed. No further attempt performed; stopped after verified restoration.
