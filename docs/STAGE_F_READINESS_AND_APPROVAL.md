> **Latest result: Stage F PASS.** The controlled retry verified the new worker, enabled SSO with demo login preserved, passed health/readiness on 005, and received user confirmation of both login choices. See [controlled retry result](STAGE_F_CONTROLLED_RETRY_RESULT.md). Historical findings below are retained.

# Stage F — final Microsoft SSO readiness, 4 November 2026

**Readiness: BLOCKED pending configuration prerequisites and explicit hosted-change approval. Preparation complete; no hosted changes performed.**

Stages B–E are accepted. Their schema, grants, membership and completed tests were not rerun. Historical documents describing an undeployed SSO-only candidate, missing registration, revision 004 or mandatory new deployment are superseded by the current B–E results and this read-only inventory.

## Verified target, registration and release

- Subscription: `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`.
- Resource group: `rg_techdemo_Atiya_Tabsum_Shaik`.
- App Service: `app-governance-validator-atiya-1026`, Running, HTTPS-only.
- Public origin: `https://app-governance-validator-atiya-1026.azurewebsites.net`.
- Tenant: `4ac50105-0c66-404e-a107-7cbd8a9a6442`.
- Registration: `Governance-Studio-SSO`, application object `53ae1688-20af-403d-89e2-c33ab08a36e0`.
- Application/client ID: `a1a7da0b-ad29-49ec-a9ea-c59219e60df5`. This is distinct from the SQL managed identity and the approved user's object ID.
- Single-tenant audience: AzureADMyOrg. Confidential Web platform; no SPA/public-client redirect URIs; implicit token issuance disabled, appropriate for authorization-code flow.
- Exact registered callback: `https://app-governance-validator-atiya-1026.azurewebsites.net/api/sso/callback`.
- Enterprise application enabled; appRoleAssignmentRequired=false. Application membership still controls access. No assignment/consent/permission change is indicated by this inspection; tenant conditional access/MFA remains subject to real acceptance.
- Tenant discovery returns the expected pinned issuer and Microsoft authorization/token/JWKS/logout endpoints.
- Existing password credential `Governance-Studio-SSO-Backend`: valid metadata window 4 November 2026 to 3 May 2027, key ID `300d88e7-c73a-4bb5-865c-041bde6ebc45`. Its value was not retrieved or tested.
- Existing registration lists delegated Graph access, but the application requests only `openid profile` and makes no Graph call. No Graph scope additions, removals or admin consent are proposed.
- Platform Easy Auth is disabled; the application's own OIDC/session implementation handles authentication.

Live `/ready` reports release **1.2-6749226f1af65b63**, actual revision **005**, supported revisions 004/005, SSO-required revision 005. `/health` and `/api/sso/status` return 200. SSO remains off, configured=false, demo login on.

**No new code release is required for unchanged configuration activation.** The locally preserved ZIP matches the deployed release metadata, backend/frontend fingerprints and Stage B package hash. Packaged SSO and production-hosting source match reviewed repository bytes. Package SHA-256: `9d81fa9b7700557eac2cb41edd5ab861d19a6b8c4f9052e55068e5eab784df80`. A durable local copy is `artifacts/governance-sso-005-compatible-rollback-20261104.zip`.

## Configuration status — names/status only

| Setting | Saved status | Effective interpretation |
|---|---|---|
| SSO_ENABLED | ABSENT | Disabled default, confirmed by public status |
| DEMO_BROWSER_LOGIN_ENABLED | ABSENT | Enabled default, confirmed by public status |
| ENTRA_TENANT_ID | ABSENT | Must add before activation |
| ENTRA_CLIENT_ID | ABSENT | Must add before activation |
| ENTRA_CLIENT_SECRET | ABSENT | Must add existing credential securely; no replacement currently indicated |
| SSO_PUBLIC_ORIGIN | ABSENT | Must add before activation |
| SSO_SESSION_MINUTES | ABSENT | Default absolute lifetime 60 minutes |
| CORS_ORIGIN | SET_NONEMPTY | Exact public-origin comparison passes |
| DATABASE_URL | SET_NONEMPTY | Preserve existing selection |
| AZURE_SQL_AUTH_MODE | SET_NONEMPTY | Managed-identity comparison passes |
| AZURE_SQL_TENANT_ID | SET_NONEMPTY | Preserve existing setting |
| AZURE_SQL_USER_OBJECT_ID | SET_NONEMPTY | Preserve existing runtime identity |
| DEMO_ACCOUNTS_JSON | SET_NONEMPTY | Preserve existing credentials/accounts |
| ALLOW_LEGACY_API_CREDENTIALS | ABSENT | Preserve current default |

No setting values containing credentials, tokens, account hashes or connection strings were printed or persisted. App Insights instrumentation/connection and OTLP endpoint settings are absent. No resource diagnostic-settings exports are configured.

## Security and role review

Source review and existing recorded local security evidence cover the following; no real Microsoft flow has yet passed:

- GET `/api/sso/login`: configured HTTPS authority/origin; allowlisted local return path; random state, browser binding, nonce and PKCE S256 verifier; five-minute SQL transaction; Secure/HttpOnly/SameSite=Lax transaction cookie; rate limit.
- GET `/api/sso/callback`: state/binding/expiry checks, atomic one-use consumption before code exchange; confidential server exchange; RS256 signature, issuer, audience, expiry, nonce and tenant/object validation. Tokens are discarded server-side. Errors never reflect provider details/codes.
- GET `/api/sso/me`: hashed opaque cookie resolves SQL session and enabled membership on every request; absolute expiry and revocation enforced. Secure/HttpOnly/__Host- cookie; CSRF material returned only to same-origin application memory.
- Mutations: exact Origin plus session-derived X-CSRF-Token required. Mixed cookie/bearer identities rejected. Browser never chooses trusted role/workspace.
- POST `/api/sso/logout`: validates CSRF, commits local revocation/audit and clears cookie before redirecting browser to Microsoft's logout endpoint. No front-channel logout receiver is implemented; global logout initiated from another Microsoft application is not promised.
- Admin session listing/revocation: server-side Admin check and workspace-scoped SQL queries.
- Stage E membership `cce108dc-72f1-4db2-9aaa-c7128085661c` maps approved tenant/object `b5d8bfbe-f03a-4132-a13f-ab49aae834b7` to actor `atiya-tabsum-shaik`, workspace `demo-appservice-4e2dcce8d618`, Admin, enabled=true. Callback selects exactly by directory/object/enabled and subsequent requests use that stored role/workspace. Existing Stage E audit `5992685e-0f10-44c1-a98a-19e1e4d84137` is accepted evidence; no reprovisioning or SQL query was run in Stage F.
- Existing Stage D actual-runtime membership INSERT/UPDATE/DELETE=0 evidence is preserved; no grant changes are required.
- Production startup uses `--no-access-log`; application middleware logs route templates/status rather than queries/bodies and applies no-referrer/no-store protections.

## Remaining blockers and exact proposed changes

1. **Logout return registration mismatch.** Code sends `post_logout_redirect_uri=https://app-governance-validator-atiya-1026.azurewebsites.net/`, but the registration currently contains only the callback. After explicit approval, an authorized registration operator must append exactly the site-root URI to existing **Web redirectUris**, preserving the callback and all other registration properties. Leave front-channel logout URL unset; it is a different mechanism. Microsoft requires the post-logout URI to match a registered redirect URI: https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc#send-a-sign-out-request.

2. **Callback-query logging protection.** App Service filesystem HTTP logging is enabled with three-day retention. This is a risk of authorization-code query capture, not evidence that a code has already leaked. Azure's HTTP log schema includes CsUriQuery: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appservicehttplogs. Before first real login, proposed approved change is **HTTP filesystem logging enabled=false only**; retain application filesystem logging at Information, HTTP blob logging already disabled, failed-request tracing/detailed errors disabled. No diagnostic exports or instrumentation settings were found. Verify effective logging configuration without printing callback requests; do not download raw auth logs. No code change or new logging resource is proposed.

3. **Existing secret value availability is unconfirmed.** Entra credential metadata proves existence/expiry, not possession or successful client authentication. The authorized holder must use the already-created secret value through existing approved secure custody. Entra cannot re-display an existing secret value. If unavailable, expired or invalid, STOP; creation/replacement/rotation requires separate approval. Never substitute a secret ID for its value.

4. **Explicit configuration/restart window and rollback authorization.** Saving App Service settings restarts the app. A short interruption is possible on the existing single-worker application; no zero-downtime guarantee or new slot is proposed. The operator must approve the immediate execution window or designate another window. Platform behavior: https://learn.microsoft.com/en-us/azure/app-service/configure-common?tabs=portal.

## Secure configuration and activation procedure — approval required, not executed

An authorized operator uses the existing Azure Portal App Service environment-variable editor. Do not paste secrets into chat, terminal arguments/history, source, .env, screenshots or report files; do not use CLI debug output. Do not create a Key Vault/resource or change credential type. Review the complete pending-change list before Save; preserve all unrelated values.

Proposed non-secret settings for the exact existing app:

| Setting | Proposed value |
|---|---|
| ENTRA_TENANT_ID | `4ac50105-0c66-404e-a107-7cbd8a9a6442` |
| ENTRA_CLIENT_ID | `a1a7da0b-ad29-49ec-a9ea-c59219e60df5` |
| SSO_PUBLIC_ORIGIN | `https://app-governance-validator-atiya-1026.azurewebsites.net` |
| SSO_SESSION_MINUTES | `60` |
| DEMO_BROWSER_LOGIN_ENABLED | `true` |
| SSO_ENABLED | `true`, only after registration/logging/secret prerequisites pass |

Add `ENTRA_CLIENT_SECRET` privately using the existing credential value. Preserve already-correct CORS_ORIGIN, managed identity, SQL/provider settings and DEMO_ACCOUNTS_JSON. Do not add any VITE_* secret. Commit only the enumerated changes in an approved restart window. Verify the same release on 005, healthy/ready and both SSO/demo flags enabled. A readiness result checks configuration shape/schema/permissions; it does not prove secret validity or Microsoft login success.

No ZIP deployment is planned. If source changes become necessary, stop for separate artifact/hash/deployment review. Do not rebuild the dirty tree or deploy older superseded artifacts.

## Rollback compatible with 005 — must be included in approval

On startup/readiness failure, wrong tenant/client/origin, failed login, unexpected credential/log exposure or broken demo access, stop acceptance and perform the approved configuration rollback: set SSO_ENABLED=false, DEMO_BROWSER_LOGIN_ENABLED=true; remove only the newly added ENTRA_CLIENT_SECRET from the app settings; preserve existing demo accounts, SQL 005 and all membership/session/audit rows. Restore other newly added non-secret settings to their recorded absent baseline if full settings rollback is required. Keep HTTP query logging disabled; do not re-enable it while any auth callback may occur. Any reversal of the appended root redirect URI should remove only that addition if approved; preserve the callback.

The already-running bridge is the normal code fallback, so rollback needs no deployment. The verified local 005-compatible ZIP is available for a separately authorized code-recovery incident. Never deploy original release 1.2-5e8064f901573795 against 005, downgrade schema, stamp Alembic history, drop SSO tables or retry membership provisioning. Database restore/rotation is a separately approved incident operation.

After SSO is disabled, old SSO cookies fail closed and can prevent demo use in the same browser context. Use a clean/private demo browser context or remove only this site's old SSO cookie. Verify demo access with the existing account; do not change its credential. Logout cannot be assumed usable after disabling SSO.

## Bounded real Microsoft acceptance plan — separate Stage G approval

Not run in Stage F. Authorize only existing human-approved accounts, normal authentication transaction/session/audit/rate-bucket writes, bounded reads and logout/revocation. Never save HAR/network traces, codes, tokens, cookies, CSRF values or credential screenshots. No policy mutations, provider/moderation/export/storage calls, membership changes or direct SQL editing.

1. Check health/readiness/status, same release/005 and both login modes. In a fresh Microsoft browser context start one login; verify authority/client/callback/PKCE parameter names without retaining state/code values. Human completes organization login/MFA.
2. Callback and `/api/sso/me` must resolve `atiya-tabsum-shaik`, Admin and `demo-appservice-4e2dcce8d618`. Read one existing policy and one page of workspace-scoped session metadata; refresh to verify restoration. Inspect cookie flags only.
3. POST logout with absent/invalid CSRF and with incorrect Origin must return 403 without revocation; ordinary authenticated read must still work. Valid logout must revoke locally, clear the cookie and return through Microsoft's registered root URI. A subsequent protected request must be denied. On the next approved Admin login, inspect the prior non-secret session ID in the workspace session list and require revoked=true; do not retain/export cookies to prove revocation.
4. Re-login once; observe one fresh session. Record its non-secret expiry, leave it to expire naturally at 60 minutes, and verify access is denied and UI requests sign-in after expiry. Do not shorten production lifetime or edit SQL timestamps. If the acceptance window is shorter than the expiry interval, mark expiration acceptance pending rather than claiming PASS. At most three successful Microsoft logins including a final session for post-expiry checks/cleanup.
5. Authorization: unauthenticated protected API denied; Admin session administration succeeds only within approved workspace. If an existing approved unassigned organizational test account is available, one login attempt must produce access_denied and no application session/membership. Lower-role/cross-workspace negatives require existing separately approved test identities/resource references; do not create assignments/data or claim those cases passed without them. Existing local RBAC evidence remains distinct from real-account acceptance.
6. In a separate clean demo context, one existing demo login, refresh, one tenant-scoped policy GET and logout must still succeed. No credential/session sharing between Microsoft/demo contexts. This is post-activation acceptance, not a rerun of B–E suites.
7. Verify sanitized operational evidence and session/audit actions without secrets. Stop on any mismatch; invoke only preapproved configuration rollback. Demo retirement remains separately approved.

## Evidence and requested approval

[Azure read-only inventory](evidence/stage-f-readiness-2026-11-04/azure-read-only-inventory.json), [registration/discovery/logging supplement](evidence/stage-f-readiness-2026-11-04/azure-read-only-supplement.json), [platform-auth confirmation](evidence/stage-f-readiness-2026-11-04/platform-auth-confirmation.json), [logging/telemetry inventory](evidence/stage-f-readiness-2026-11-04/logging-readiness.json), [artifact review](evidence/stage-f-readiness-2026-11-04/artifact-readiness.json), [Stage E accepted result](STAGE_E_EXECUTION_RESULT.md).

**Approval request:** Approve the documented configuration-only Stage F rollout in the next agreed restart window: append the exact logout return URI, disable only HTTP filesystem request logging, securely add the existing client secret and enumerated SSO settings while retaining demo login, and authorize the specified SSO-off rollback; execution is conditional on secure availability of the existing secret. No deployment, rotation, SQL write or Stage G acceptance is included.
