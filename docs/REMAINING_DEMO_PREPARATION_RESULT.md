# Remaining end-to-end demo preparation — PARTIAL / cloud execution BLOCKED

7 November 2026, Asia/Kolkata. This update supersedes earlier execution requests. All activity in this update was local or read-only. No WebJobs retry, enablement, upload, restart, resource/permission/data mutation, provider operation or application deployment occurred. No new Azure service was created.

## HTTP500 diagnosis and current health

The exact existing Kudu trace proves **an internal forwarding connection was refused**, not a watchdog Python exception: ContainerWebJobsController.ForwardToContainer → JobsController.ForwardJobRequestToContainer → TCP 169.254.130.5:50555, at 16:55:04 UTC. Six earlier trace filenames establish 409 responses while the setting change was propagating. [Sanitized failure trace and hashes](evidence/webjobs-http500-readonly-2026-11-07/failure-traces-sanitized.json), [focused inventory](evidence/webjobs-http500-readonly-2026-11-07/relevant-log-inventory.json).

The container warmup began 16:54:54 UTC. The probe failure at 16:55:19 UTC occurred after setting rollback at 16:55:09 UTC. This timing cannot distinguish a transient not-yet-listening agent, an agent launch fault or rollout cancellation. Startup-log review did not establish the deeper launch cause. It is unsafe to assert permanent Python incompatibility or a verified repair. Increasing timeouts or blindly repeating the failed API is not justified.

Fresh current /health, /ready and /api/sso/status all returned 200 at **17:01:38 UTC / 22:31:38 IST**. Existing served release is **1.2-ca5df7c1dc19e525**, readiness revision **005**. This post-recycle observation is newer than the compatibility check's earlier snapshot. Original enablement flag is absent, webJobsEnabled=false, Always On=true, PYTHON|3.13, one worker. Latest existing deployment remains **17a92576-4b66-405b-938f-7f36570dc5c4**, completed 5 November. [Current state](evidence/webjobs-http500-readonly-2026-11-07/current-readiness-config-sanitized.json), [startup sequence](evidence/webjobs-http500-readonly-2026-11-07/container-startup-sanitized.json).

Documentation supports Python WebJobs on compatible Linux App Service, but it does not prove this runtime's agent is healthy or promise a hard deletion deadline. The existing Web App is **not currently a verified independent expiry safeguard**. Even repaired, its shared host/storage/identity/ARM failure domain can outlast the one-hour cleanup margin. [Platform support](https://learn.microsoft.com/en-us/azure/app-service/overview-webjobs).

A [sanitized support request](WEBJOBS_SUPPORT_REQUEST_DRAFT.md) is prepared with the exact trace, correlation ID, image, timestamps and rollback result. It has not been sent; no support resource/ticket exists. Request a supported agent-level diagnosis and concrete repair before approving another compatibility check.

## Existing-infrastructure alternatives

| Option | Evaluation |
| --- | --- |
| Repair existing WebJob agent | Best existing-host candidate, but needs an established repair, separately approved configuration/restart work, hosted verification, exact-scope permission bootstrap and independent confirmation. Not presently safe for temporary SQL creation. |
| Launch a supervisor alongside the existing web application | Technically possible only through an approved application/startup change. Shares application outages and worsens coupling to production. No hard four-hour guarantee; not implemented or deployed as a workaround. |
| Existing GitHub/Azure DevOps/company runner | Earlier read-only discovery found no repository remote, no accessible DevOps organization and no company runner/server reference. A test YAML alone is not an available executor. No new account/pipeline/authentication configured. |
| SQL self-cleanup/SQL Agent | Not an independent ARM database-deletion controller. SQL Agent is unavailable on Azure SQL Database; Elastic Jobs would require additional resources/authorization. No production T-SQL job or WAITFOR/self-drop workaround. [Microsoft automation options](https://learn.microsoft.com/en-us/azure/azure-sql/database/job-automation-overview?view=azuresql). |
| Existing storage/ADLS or AI services | Storage and model endpoints do not supply an independently scheduled database-deletion executor. No provider call made. |
| Cloud Shell, laptop cron or detached subprocess | Interactive/host-suspension failure remains. Cloud Shell can end noninteractive work after 20 minutes without interaction. No persistent executor guarantee. [Microsoft session limits](https://learn.microsoft.com/en-us/azure/cloud-shell/faq-troubleshooting). |
| Local SQL Server/fixture work | Safe for local contracts but cannot complete Azure SQL or managed-identity/hosted gates. Prior valid local evidence retained rather than rerun. |

**No verified alternative using only discovered existing infrastructure meets the strict lifetime requirement.** No scope/limit was relaxed. Temporary qualification and PITR resources remain prohibited until a separately verified safeguard exists. A new service is neither proposed for automatic creation nor implicitly approved.

## Local release/deployment preparation completed

Application candidate **1.2-240cc70e239a595f**, SHA-256 `274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22`, unchanged. Independent repaired rollback **1.2-230d63e0c546e0ba**, SHA-256 `b52287bbf048a66a9f7233753a3fb95730397016f03074d4deb399c1e74c0d29`, unchanged. All **64** packaged Python modules and **4** frontend files match the current application/build byte-for-byte. Frozen migrations, grants, prior pinned files and local SQLite hashes match. [Preservation evidence](evidence/webjobs-http500-readonly-2026-11-07/release-preservation.json).

No application code changed, so backend/frontend builds and previously passed suites were not repeated. Prior extracted-package, ciphertext, review/session/retention/audit and rollback tests remain reusable only within their stated boundaries. A new review bundle packages the existing immutable release, repaired rollback, migration/grant sources and the current execution/acceptance plans; it is not a new runtime release or deployment authorization.

The consumed retry-9 SQLSTATE08S01 remains historically unclassified beyond transport loss. This new Kudu HTTP500 is a separate incident; no causal link to the old SQL disconnect is established. Existing secure bounded operator diagnostics remain available but were not executed against a new database.

## Shortest remaining SQL qualification

Reuse pinned Azure migrations/readiness008, MULTI/tenant/session/immutability and retry-9 review/cleanup passes. Remaining targeted gates are compatible-copy full readiness/exact original decryption, retained row/ciphertext/catalog preservation, controlled006 preflight denials and transactional007 failure rollback. No need to repeat whole governed/provider suites. A fresh exact candidate/identity/firewall/absence/tier/price/ownership/expiry preflight and fresh explicit Approval A are mandatory **after** the watchdog problem is resolved. No retry-10 request is issued now.

## Recovery preparation

Read-only existing Azure metadata reports source sqldb-governance-validator-dev Online, Standard 10DTU, Local redundancy, seven-day retention and 24-hour differential interval. EarliestRestoreDate observed **2026-10-31T17:02:25.2115438Z**. Inventory contains only source and master. [Recovery metadata](evidence/webjobs-http500-readonly-2026-11-07/recovery-metadata-readonly.json). Hosted readiness revision005 is fresh; direct SQL row/catalog/grant observations remain prior evidence, not fresh SQL scans.

Existing operator identity was verified during the approved compatibility check and remains the proposed recovery operator. Existing SQL admin/grant/read evidence is reused, but eligibility and actual restored access must be freshly checked before any approved drill. Backup metadata is not restore proof. Do not reuse historical003/004 placeholders or expired restore timestamps in older plans.

Concrete review destination: **sqldb-gpv-recovery-20261107-b1** on the existing server/group/subscription, source untouched. This name is proposed, not reserved or created. A possible fixed restore point for planning is **2026-11-07T16:30:00Z**, within the observed window, but it is not an Azure-accepted restore point and must be refreshed/pinned at the recovery approval gate. One S0/10DTU same-server restore with Local backup, no app switch, no new grant/provider operation. Fresh cost and actual-creation-based cleanup proof are prerequisites; the hard-coded qualification watchdog cannot silently be repurposed to this different recovery target. No restoration or billable request submitted.

Recovery B must separately include exact target, timestamp, tier, cost/window, responsible operator and cleanup scope. Require Online + operation success, restored SELECT access, revision/catalog/aggregate/FK consistency, appropriate retained-key/ciphertext validation, source preservation, ARM/inventory cleanup and sanitized evidence. Do not export production plaintext. A historical restore timestamp can legitimately have different counts; do not label every difference data loss.

Forward recovery retains007/008 protections. No migration downgrade, ciphertext dropping, automatic PITR cutover or production overwrite. The current hosted005-era release advertises support only004/005 and is **not an application rollback candidate after008**. Use the separately qualified repaired rollback and stable keys; an approved actual restore/cutover still needs explicit source/write-loss handling.

## Production, SSO and key readiness

Fresh presence-only checks: Entra SSO enabled/configured; correct public origin; client/secret present; demo browser and legacy credentials disabled; SQL auth uses managed identity. This is configuration evidence, not a fresh interactive Admin/User login or proof of client-secret expiry/registration correctness. No login/session writes were performed.

**Human Review capture and cleanup are disabled, active encryption key absent, keyring format not ready.** Do not deploy the feature-complete008 candidate without separately approved stable32-byte key provisioning, protected retention/backup and a secure presence/format check. Do not reuse provider/SSO credentials as review keys or generate replacement keys across rollback. No key material was printed, generated or configured. Integration verification remains disabled and no provider status was marked VERIFIED.

Production plan remains: verify qualification/recovery first; approve quiet/drain and recovery point; capture source/runtime baseline; apply frozen006→007→008 using operator tooling and only reviewed minimum grants; validate retained data/catalog/schema and runtime managed-identity access; configure secure keys/SSO/session settings; deploy exact candidate to existing Web App; health/readiness and authenticated acceptance; abort to the approved compatible recovery strategy on critical failure. No startup migration, service creation or broad grant. The current005 application must not continue receiving writes across an incompatible migration window. Runtime identity must be proven by the actual hosted connection, not operator EXECUTE AS alone.

## Hosted acceptance and stop gate

[All20 required hosted workflows](evidence/webjobs-http500-readonly-2026-11-07/hosted-acceptance-matrix.json) remain pending on the deployed candidate: Admin/User SSO and portals, tenant/role isolation, policy lifecycle/MULTI, PII/secret/keyword/moderation controls, generation/output inspection, Human Review, history/analytics/audit, ADLS read-back, truthful Settings, session expiry/revocation and critical navigation. Synthetic data only. Preserve older passing tests as historical evidence, not new hosted acceptance.

Separate explicit bounded generation/moderation/ADLS and hosted-write approvals remain necessary. Specify exact call/object budgets and synthetic cleanup at that gate; no real operation is authorized merely by public status checks. Settings VERIFIED still requires a successful matching real operation and durable evidence; configuration presence is insufficient.

**PARTIAL overall; cloud qualification/recovery/deployment BLOCKED.** Safe local and read-only preparation is complete. The next practical step is review/submission of the prepared Azure support request and a supported repair proposal for the unavailable Kudu agent. **External support communication and any platform repair/retry require separate explicit approval; none was sent or attempted.** Do not request temporary SQL creation, a blind WebJobs retry or production deployment while prerequisites fail. If the hard four-hour bound cannot be established, do not create a temporary database. READY requires all mandatory hosted gates.
