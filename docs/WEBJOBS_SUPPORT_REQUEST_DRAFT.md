# Draft Azure support request — not submitted

Subject: Linux Python App Service WebJobs forwarding fails with connection refused on internal port 50555 after documented enablement

Existing resource: /subscriptions/25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6/resourceGroups/rg_techdemo_Atiya_Tabsum_Shaik/providers/Microsoft.Web/sites/app-governance-validator-atiya-1026

Region West US 2; existing Basic B2 plan; one worker; built-in PYTHON|3.13; Always On enabled; startup sh startup.sh. Existing app image recorded as appsvc/python:3.13_20261028.2.tuxprod.

On 7 November 2026, WEBSITE_SKIP_RUNNING_KUDUAGENT was temporarily set to false at 16:54:18 UTC in a bounded compatibility check. No WebJob package was uploaded. Six existing trace files show /api/continuouswebjobs returning 409 between 16:54:23 and 16:54:53 UTC. At 16:55:04 UTC Kudu forwarded the GET through ContainerWebJobsController.ForwardToContainer / JobsController.ForwardJobRequestToContainer and returned HTTP500: Connection refused (169.254.130.5:50555). Correlation X-ARR-LOG-ID ea99f776-8105-49e5-8de3-861564672f96.

Exact trace: LogFiles/kudu/trace/2026-11-07T16-55-02_3e6c5f_002_GET_api-continuouswebjobs_pending.xml. Exception companion dca406aa00c6-829207f9-99f9-43dd-9d5c-f7fb28bf7a1c.txt. Request Authorization headers are sensitive: do not share raw traces without redaction. A sanitized extract and SHA-256 are prepared locally.

Container warmup started at 16:54:54 UTC. The setting was restored to its original absent state at 16:55:09 UTC, with no other app-setting differences. Platform logs then report a startup probe failure at 16:55:19 UTC during the rollout/rollback sequence. We cannot determine whether the initial agent refusal was transient startup timing, agent launch failure or another runtime/platform problem; we are not asserting the subsequent probe failure was independent of rollback.

Current read-only checks at 17:01:38 UTC: /health and /ready 200, release 1.2-ca5df7c1dc19e525, SQL revision005, SSO configured, original setting absent, webJobsEnabled=false. Existing deployment remains 17a92576-4b66-405b-938f-7f36570dc5c4 from 5 November. No database/permission/provider operation, new Azure service or application release deployment was performed. No repeat of the failed API or enablement occurred during diagnosis.

Please identify why the internal Kudu agent did not accept port50555 requests, whether this exact built-in image supports the feature, expected agent/warmup readiness evidence, and the smallest supported repair. Do not apply any repair, restart, scale, runtime or configuration change without the customer's separate approval. We need a concrete change and rollback plan, not a blind retry or timeout increase. The intended job will remain disabled until independently approved.

A single Web App is not being asserted to guarantee a hard four-hour Azure SQL deletion SLA. Exact-database RBAC bootstrap and independent confirmation remain separate blockers.

This is a draft only. No external message or support ticket was created. If support requires a paid plan or operational mutation, obtain separate approval first.
