# One-hour deployment checkpoint — BLOCKED, healthy site preserved

8 November 2026, fresh read-only observation at08:00UTC /13:30IST. The master prompt expressly withholds mutation authority. No production key generated, settings/grants changed, migration/restore/deployment performed, temporary database created, provider called or WebJobs API retried. Large passed suites were not repeated.

| Requested result | Actual evidence |
| --- | --- |
| Deployed version | `1.2-ca5df7c1dc19e525`; /health and /ready200, Running, correct expected managed identity, Always On, Linux Python3.13. |
| Production revision | Hosted readiness reports005. Direct read-only operator SQL refresh failed with sanitized DatabaseConnectionError; no fresh direct catalog/grant verification claimed. Hosted connection remains ready. |
| Encryption | Keys absent; actual pinned keyring format/AES-GCM synthetic round trip passes locally. No production key generation. |
| Migrations |006–008 unchanged/pinned; prior Azure successful migration evidence reused; no production application. Compatible-copy preservation and controlled failure cycles incomplete. |
| Admin Portal | Existing release has Studio and SSO configuration; fresh interactive login/workflows NOT VERIFIED. |
| User Chatbot | Locally implemented/tested in candidate; UNAVAILABLE in currently deployed release. Named User membership/interactive acceptance still required. |
| MULTI | Locally implemented with pinned Azure qualification evidence; UNAVAILABLE in currently deployed release. Explicit tenant switch and published assignments require authorization. |
| Encrypted Human Review | Candidate encryption/reveal/audit/expiry DELETE passed prior Azure testing; protected reveal UNAVAILABLE in hosted005. |
| Azure OpenAI | Configured deployment gpt-5-mini with managed identity; current real generation NOT VERIFIED. |
| Moderation | Credential present; current real operation NOT VERIFIED. |
| ADLS | Account/filesystem configuration present; current export/read-back NOT VERIFIED. |
| Recovery | Fresh08Nov07:56UTC backup metadata:7day retention,24hour differential interval, Local redundancy, source Online. Actual PITR NOT TESTED. Compatible repaired rollback checksum/local decrypt tests pass; Azure compatible-copy preservation remains incomplete. |

Read-only account/subscription and site identity match approved target. SSO enabled, correct origin/credentials present,60minute session; demo/legacy access disabled. No secret values exposed. [Fresh checks](evidence/one-hour-predeployment-2026-11-08/account-site-health.json), [settings presence](evidence/one-hour-predeployment-2026-11-08/configuration-presence-only.json), [SQL refresh failure](evidence/one-hour-predeployment-2026-11-08/sql-readonly-demo-inventory.json).

Pinned candidate **1.2-240cc70e239a595f**, SHA256 `274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22`. Pinned repaired rollback **1.2-230d63e0c546e0ba**, SHA256 `b52287bbf048a66a9f7233753a3fb95730397016f03074d4deb399c1e74c0d29`. All64 packaged Python modules/four frontend files match tested source/build; frozen006–008 hashes and candidate/rollback confirmed. No release substituted. [Local verification](evidence/one-hour-predeployment-2026-11-08/local-preservation-and-encryption.json).

## Mandatory blockers and shortest safe route

Actual recovery proof, compatible-copy retained-ciphertext/catalog preservation and controlled migration failure cycles are incomplete. There is no verified independent four-hour expiry safeguard; disposable qualification/PITR databases cannot be created. No evidenced existing alternative satisfies that requirement. A key-setting approval cannot remove those gates. Do not migrate production to compensate. Normal encrypted review uses the verified candidate application cleanup worker, not WebJobs; physical seven-day erasure remains outage/backlog/backup-limited as documented.

The [consolidated change review](THREE_FEATURE_PRODUCTION_CHANGE_REVIEW.md) remains the exact deployment/recovery/grants/keys/MULTI/identity/acceptance plan. Entry gates must pass before any production authorization can be executed. Existing005 runtime is not rollback-compatible with008. Do not remove keys/ciphertext/protections or restore/cut over without an explicitly approved recovery scope. Completion in one hour cannot be safely promised with these unresolved prerequisites; no need to consume the remaining hour on prohibited retries.

## Exact available next approval — encryption staging only

- Target: subscription25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6, resource group rg_techdemo_Atiya_Tabsum_Shaik, existing Web App app-governance-validator-atiya-1026.
- Scope:15minutes; securely generate one32byte independent AES key and stable ID; establish a protected independently recoverable encrypted operator copy outside the repository before installation; add only REVIEW_CONTENT_ACTIVE_KEY_ID and REVIEW_CONTENT_KEYS_JSON through a memory-only merged settings payload. No values in CLI arguments/logs/chat. Abort before generation/staging if secure custody cannot be established.
- Keep capture/cleanup/integration verification disabled on005; preserve every unrelated setting. No SQL, permissions, WebJobs, deployment, provider operation or new service.
- Downtime: App Service recycle; allow an estimated1–5minutes of interruption, not a guaranteed bound. Incremental service capacity cost expectedUSD0; existing hosting continues.
- Verify: exact candidate key contract/synthetic round trip without disclosure, unrelated-settings comparison, original served release and health/readiness.
- Stop: unexpected existing keys/settings, concurrent change, missing recoverable backup, validation failure or unhealthy application. Before any capture, restore original values/absence of only these two settings and verify health. After capture, never remove required keys as rollback.

This approval is requested because the user's master prompt explicitly requires separate authorization before production key generation and App Service changes. It is not a production deployment approval.

## Verified fallback for the currently deployed application

Reuse the [10–15minute hosted005 guide](HOSTED_005_DEMO_READINESS.md); no reduced-feature claim is presented as completion of the requested deployment.

Without any new write/provider approval: show the fresh public /health, /ready and /api/sso/status; explain deployed release005, available single-policy Studio/governance/history/analytics/review metadata routes from the preserved exact release and prior matching assets; show dated aggregate prior evidence as historical only. This is a verified configuration/architecture walkthrough, not an authenticated end-to-end demo.

For an interactive walkthrough, obtain bounded login/session-write approval first and use existing approved Admin/MFA access. Read existing policy/history/analytics only. Fresh governance/simulation writes, real generation/moderation and exports require the separately enumerated limits in the guide; no request was executed here. If providers are unavailable, stop without retries and show historical outcome metadata. Do not claim User Chatbot, simultaneous policies or protected reveal exist on005. A connected browser is still required for interactive acceptance; none was available in the last inventory.

**Verdict: BLOCKED for production; PARTIAL safe preparation. Existing healthy website and all prior application/SQL evidence preserved.**
