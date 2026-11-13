> **Encryption staging completed — 8 November 2026:** [PASS result](PRODUCTION_ENCRYPTION_STAGING_RESULT.md). Only the two approved review-key settings were added; release/revision005 unchanged, capture/cleanup disabled. SQL qualification/recovery/deployment remain blocked.

> **Latest priority — 8 November 2026:** all three features are required. See [three-feature production change review](THREE_FEATURE_PRODUCTION_CHANGE_REVIEW.md). Local candidate verified; SQL qualification, recovery and production authorization remain blocked. Earlier reduced-feature demo and consumed rehearsal approvals are not execution authority.

> **Current priority: existing hosted005 demo.** 8 November public health/readiness and SSO configuration PASS at release1.2-ca5df7c1dc19e525. Interactive Admin sign-in/provider operations remain approval-gated; no dedicated User portal exists in this release. Direct operator SQL recheck failed, so 7 November role/policy counts are historical. [Demo guide, exact approval and fallback](HOSTED_005_DEMO_READINESS.md). This does not change later qualification/deployment status.

> **Latest read-only diagnosis and remaining preparation — PARTIAL / cloud execution BLOCKED.** Exact Kudu trace proves internal forwarding refused on port50555; deeper agent-start cause unresolved. No API retry or Azure mutation. Fresh hosted health/readiness PASS; original flag absent; release1.2-ca5df7c1dc19e525 / revision005. Review encryption keys are not configured. Existing candidate/rollback/migrations/SQLite preserved; no test reruns. [Diagnosis, alternatives and exact remaining gates](REMAINING_DEMO_PREPARATION_RESULT.md).

> **Latest approved disabled WebJob check: PARTIAL / stopped, 7 November 2026.** Completed in 80.64 seconds. WebJobs API returned HTTP500 before upload; no job created or run. Original setting fully restored; application /health and /ready PASS, release unchanged, revision 005. Approval consumed; no retry or later authorization inferred. [Result and evidence](WEBAPP_WATCHDOG_DISABLED_CHECK_RESULT.md).

> **Latest review-only watchdog preparation:** local disabled WebJob package and 31 tests PASS; overall PARTIAL, arming/SQL creation BLOCKED. No Azure changes. See [exact configuration, permissions, limits and minimum setup-only approval](WEBAPP_WATCHDOG_REVIEW.md). Prior release/Azure evidence is retained; no previous approval is reused.

# Final end-to-end demo readiness — PARTIAL / AZURE CREATION BLOCKED

7 November 2026, Asia/Kolkata. This report supersedes earlier retry-8/retry-9 approval requests. No approval is carried forward. No Azure mutation, production deployment or real provider operation occurred in this work.

## Release and preservation

Application candidate remains **1.2-240cc70e239a595f**, SHA-256 `274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22`. All packaged Python application sources match the working application. Application/frontend behavior was not changed; prior frontend tests/build remain applicable, so they were not repeated.

New immutable [preparation bundle](../artifacts/final-safety-2026-11-07/preparation-candidate.zip), SHA-256 `b10015d039b39eeccf966a413d985514e46c1ca59dca954372f52e38fb340994`, contains the frozen application candidate, independent repaired rollback, changed operator controls/tests and migration sources. It is preparation evidence, not an authorized deployment or a certified watchdog. [Manifest](evidence/final-safety-2026-11-07/manifest.json).

Repaired independent rollback **1.2-230d63e0c546e0ba**, SHA-256 `b52287bbf048a66a9f7233753a3fb95730397016f03074d4deb399c1e74c0d29`, verified unchanged. Frozen migration hashes match the existing qualification pins. Local SQLite remains SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. Existing source changes and historical evidence retained; no prohibited Git operation.

## SQLSTATE 08S01 investigation

Exact [retry-9 fallback log](evidence/phase6b-approval-a-retry9-2026-11-07/package-fallback-008-failure.txt): healthy startup cleanup took 13.346 seconds; `/ready` subsequently returned 503 / DATABASE_OPERATION_FAILED / 08S01 after 24.354 seconds. The watchdog log records deadline/deletion intent but does not timestamp those lines. Independent Azure activity records creation 10:11:24 UTC and deletion 16:24:14 UTC; local monotonic elapsed was only 674.44 seconds.

**Historical cause cannot be established.** Transport failure is evidenced; TLS validation failure, stale pooling, SQL availability, a long query, timeout and harness disposal cannot individually be established or excluded. Connection creation/use timestamps and the failing SQL stage were not recorded. In particular, the evidence cannot order the disconnect against deletion. Do not infer a schema defect or assert that host suspension caused it.

Existing adapter already disables pyodbc pooling, uses pre-ping/recycling, fresh token acquisition, mandatory TLS/certificate validation and bounded driver timeouts. These remain unchanged. New [operator-only diagnostic](../scripts/sql_connection_confirmation.py) records sanitized stage, SQLSTATE, wall-clock timing and checkout/use duration for fixed read-only SELECT 1. It retries transport failure once with pool disposal. It never replays a write or substitutes for full readiness. This records checkout/use duration, not the unknown historical physical-connection lifetime. It has not run against Azure; no new SQL recovery success is claimed.

## Watchdog safety

Retry-9's four-hour limit was breached by about 2h13m. The previous watchdog used time.time on the same host, while harness checks used monotonic elapsed. It depended on an execution JSON created flag, then called the harness cleanup path, including engine disposal. A detached process protects against some parent failures but cannot execute during whole-host suspension; a UTC timer alone cannot solve that. Available evidence proves enforcement failure, not its precise infrastructure cause.

**Temporary creation is now unconditionally blocked at the beginning of create(), before account/network/resource operations.** No approval token bypass exists. Existing cleanup/read-only paths remain available. Historical execution windows remain consumed; their operator pins must not be silently updated.

[Expiry policy](../scripts/sql_expiry_control.py) derives the test-stop time (creation +3h) and hard deadline (creation +4h) from supplied ARM UTC creationDate, independently of harness state. At expiry it attempts termination, then deletion even after termination failure; it requires both ARM absence and inventory absence, records confirmation time, reports lateness and allows repeated cleanup passes after failure. Exact-target ownership validation and bounded RPCs are requirements for the future adapter, not implemented live guarantees.

**Not certified.** Tests simulate bounded adapter timeouts/crashes, deletion failures/retry, expired deadlines, partial absence, clock anomalies and failed logging. They do not prove actual process termination, Azure deletion latency or an off-host executor. A real independently scheduled executor, durable exact-target/incarnation binding, bounded Azure calls and alerting must be verified before creation can be re-enabled. Azure deletion timing itself has no proven hard upper bound here; no guarantee of the approved lifetime is claimed.

## Local verification

- **12 new control tests passed**; [log](evidence/final-safety-2026-11-07/control-tests.log). Changed operator scripts pass Ruff; [log](evidence/final-safety-2026-11-07/ruff.log).
- Focused backend batch: **109 passed, one outdated diagnostic fixture failed**; [original result](evidence/master-repair-2026-11-07/final-safe-review-external.log). Fixture omitted MSSQL batched catalog execute(). It now returns realistic empty catalog rows. All **16 diagnostic tests passed on recheck**; [log](evidence/master-repair-2026-11-07/final-diagnostic-recheck.log). Counts overlap and are not additive.
- Batch covers SQL token/pooling/reconnection contracts, schema compatibility, two cross-process rollback ciphertext checks, Human Review/retention/authorization, and session lifetime. Kernel IPv4/IPv6 socket denial and dotenv blocking enforced. The sandbox run stalled in TestClient and its child was terminated; the completed external run retained the same network-denial controls.
- Prior valid encryption/cleanup/audit, controlled local failure-cycle, extracted-candidate and frontend tests are reused from [master repair](MASTER_REPAIR_RESULT.md). No application change justifies rerunning all suites. Local tests do not establish remaining SQL Server transactional failure gates.

## Azure, recovery, deployment and hosted status

Fresh read-only [server inventory](evidence/final-safety-2026-11-07/azure-inventory-readonly.json) contains only production and master. Production is Online; earliestRestoreDate is 31 October 2026 16:33:05 UTC. This is backup-window metadata, not proof of successful restore/access. Fresh direct ARM404 and all other create gates must still be established when execution becomes safe. No temporary resource created.

[Retry-9](PHASE6B_APPROVAL_A_RETRY9_RESULT.md) remains valid historical evidence for migrations through 008, SQL expiry cleanup removed=1/healthy=true, assignment/reveal authorization, encryption/retention and purge/audits. Earlier pinned MULTI/tenant/session/immutability passes are retained. Compatible-copy full readiness/exact decryption, final retained/catalog preservation and controlled 006/007 failure cycles remain Azure-dependent and incomplete.

Production's last SQL revision evidence remains **005**, not a fresh SQL revision observation. Recovery B still requires a separately approved actual restore/PITR drill, runtime access, stable encryption keys, retained-data/catalog validation and independent cleanup. No restore or recovery resource was created. [Existing recovery/deployment plan](MASTER_REPAIR_DEPLOYMENT_READINESS.md) remains applicable with this new watchdog blocker; forward recovery retains 007/008 protections and does not downgrade/drop ciphertext. Runtime managed-identity permissions and production key readiness remain unverified here.

Production deployment remains **not performed**. Frozen 006–008, reviewed grants, secure key configuration, Entra/Admin/User routing and existing Web App deployment require recovery qualification and separate explicit authorization. All 20 hosted acceptance items in [hosted acceptance plan](FINAL_HOSTED_DEMO_ACCEPTANCE.md) remain mandatory on the deployed candidate. Existing local or older hosted evidence cannot satisfy them. Settings retains configured-but-unverified status without a successful real operation. No real Azure OpenAI, Moderation or ADLS call; separate bounded approval is still required.

## Shortest remaining path and exact next decision

First identify an **existing independent executor** outside this host's suspension/failure domain that can enforce and observe exact-target cleanup without adding an Azure service. Verify its scheduling, credentials/permissions, durable ARM creation-time/incarnation binding, failed-call retries, both absence checks and breach alerts before preparing a create approval. If the authorized hard lifetime cannot be guaranteed, do not create a temporary database.

No fresh resource-creation approval is requested yet: the prerequisite safeguard is unverified. Once resolved, refresh target/identity/firewall/absence/candidate/price evidence and present one fresh narrowly bounded Approval A for compatible-copy preservation and the remaining controlled failure cycles, reusing valid prior passes. Retry-9 approval cannot be reused. Recovery B, production deployment and real-provider/hosted mutation approvals remain separate.

**Verdict: PARTIAL; Azure creation BLOCKED on the independent expiry safeguard. READY requires all mandatory hosted tests.**
