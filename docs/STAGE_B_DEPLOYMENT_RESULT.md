# Stage B result — 4 November 2026

**COMPLETE — deployment and bounded acceptance PASS. Stage C not started.**

The explicitly approved release `1.2-6749226f1af65b63` is serving at https://app-governance-validator-atiya-1026.azurewebsites.net on existing App Service `app-governance-validator-atiya-1026`, resource group `rg_techdemo_Atiya_Tabsum_Shaik`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`.

Both approved candidate/rollback checksums passed. Saved authentication flags were absent: the verified package defaults apply (SSO false, demo true), and the hosted `/api/sso/status` acceptance independently confirmed that effective state. Existing Admin and Developer credentials were compared privately with saved account hashes; accounts, hashes and configuration were not changed. The original rollback ZIP remains preserved.

Deployment `87eec3b9-fb96-407f-ade9-ea7ca059e065` was submitted once. Azure reports status 4, complete and active, with build completion at 15:23:38 UTC (20:53:38 IST). No deployment log errors were reported. The previous worker briefly continued to serve after build success; the expected release appeared during bounded observation without a manual restart or configuration change. The CLI exited successfully.

All 57 bounded acceptance assertions passed, finishing at 15:26:48 UTC (20:56:48 IST): health/readiness, actual SQL revision 004/versioned schema, expected release and supported-schema metadata, checksum-matching hosted HTML/JS/CSS, SPA entry routes, SSO disabled/unavailable and demo enabled, unauthenticated denial, Admin/Developer session creation and restoration, expected role/tenant, tenant-scoped policy list/detail/version reads, nonexistent-policy denial, analytics/audit/review reads, Developer denial of Admin session listing, logout and revoked-session denial. No browser automation was performed; session restoration was checked through a fresh HTTP client with the issued session token. Tenant-scoped returned rows were checked; a separately provisioned second-tenant identity was not created or exercised.

Writes were limited to two demo sessions and their normal audit/rate-limit/logout activity. No policy changes, generation/moderation, export or storage operations occurred. Migration 005, SQL permission/membership changes, SSO activation, new Azure resources and configuration changes were not performed. No unrelated tests were run. Rollback was not required. The original 004-only ZIP remains eligible only while SQL is 004; any later migration changes that applicability.

Evidence: [prechecks](evidence/stage-b-2026-11-04/prechecks.json), [deployment](evidence/stage-b-2026-11-04/deployment.json), [acceptance](evidence/stage-b-2026-11-04/acceptance.json). Earlier evidence is retained.

No outstanding deployment/acceptance blocker was observed within the approved Stage B scope. Migration/recovery/grant/SSO prerequisites remain governed by their separate approval gates. No Stage C action is authorized or initiated.

Credential handling incident: existing hosted demo credential values were inadvertently included in an inspection tool output due to a list/dictionary handling mistake. The user was notified during execution. Values are not repeated in this report or evidence. No credentials were rotated because credential/configuration changes are outside Stage B scope. See [incident record](evidence/stage-b-2026-11-04/credential-output-incident.json).
