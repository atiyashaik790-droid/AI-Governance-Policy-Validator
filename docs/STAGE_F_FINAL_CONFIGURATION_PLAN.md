# Stage F final configuration-only rollout — awaiting approval

Secret custody prerequisite: user confirms the complete client-secret Value is securely saved in their password manager. The value has not been requested, accessed or validated by the agent. No hosted changes, tests or SQL access occurred during this preparation.

Target: App Service `app-governance-validator-atiya-1026`, resource group `rg_techdemo_Atiya_Tabsum_Shaik`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`. Existing release `1.2-6749226f1af65b63` supports SQL 005; no code deployment is required.

Execute only after explicit approval, in this order:

1. Entra > App registrations > Governance-Studio-SSO (client ID `a1a7da0b-ad29-49ec-a9ea-c59219e60df5`) > Authentication > Web redirect URIs. Append `https://app-governance-validator-atiya-1026.azurewebsites.net/`. Preserve `https://app-governance-validator-atiya-1026.azurewebsites.net/api/sso/callback`. Leave front-channel logout URL and all other registration settings unchanged.
2. On the exact existing App Service, disable HTTP filesystem/web-server request logging. Retain application filesystem logging at Information. Preserve existing disabled HTTP blob logging, detailed-error and failed-request tracing flags. Use the Portal App Service logs controls where available; otherwise make a guarded update only to `httpLogs.fileSystem.enabled=false` through the existing ARM logs configuration, preserving the other fields. Verify configuration status, never raw callback logs. Do not assume Linux Portal exposes every logging toggle. No access-log/HTTP/OAuth debug logging.
3. User privately opens Azure Portal > App Services > exact app > Settings > Environment variables > App settings (older Portal: Configuration > Application settings). Add the settings below. For ENTRA_CLIENT_SECRET, use Add > Name `ENTRA_CLIENT_SECRET` > Value: paste directly from the password manager into the Portal Value field. No quotes, no Secret ID. Never pass the value through chat, agent tools, terminal/history, files or screenshots. The user performs this secret entry themselves. Do not use a VITE_* variable or Connection strings tab. Review pending edits; avoid Advanced edit/exports that expose other values. Do not save partial configuration with SSO enabled and missing prerequisite values.

| Setting | Required value |
|---|---|
| ENTRA_TENANT_ID | `4ac50105-0c66-404e-a107-7cbd8a9a6442` |
| ENTRA_CLIENT_ID | `a1a7da0b-ad29-49ec-a9ea-c59219e60df5` |
| ENTRA_CLIENT_SECRET | User enters complete Value privately in Portal |
| SSO_PUBLIC_ORIGIN | `https://app-governance-validator-atiya-1026.azurewebsites.net` |
| SSO_SESSION_MINUTES | `60` |
| DEMO_BROWSER_LOGIN_ENABLED | `true` |
| SSO_ENABLED | `true` only in the approved final settings save |
| CORS_ORIGIN | Preserve existing exact `https://app-governance-validator-atiya-1026.azurewebsites.net` |

4. Preserve DEMO_ACCOUNTS_JSON, database/managed-identity/provider settings and all unrelated settings. User reviews and saves/applies only the approved settings in the accepted restart window. Saving triggers an App Service restart and can briefly interrupt the existing demo. No extra manual restart is required just to apply settings.
5. Bounded Stage F checks only: verify both exact Web redirect URIs; logging status; setting presence and identifier comparisons without printing the secret; GET /health returns 200/ok; GET /ready returns 200/ready on 005 and unchanged release with sso_available=true; GET /api/sso/status reports sso_enabled=true, configured=true, demo_login_enabled=true; load the public sign-in page to confirm Microsoft and demo choices. Do not call /api/sso/login or callback, exchange codes, create sessions, or run Stage G. These checks establish configuration readiness, not real secret validity/Microsoft authentication. Stop on mismatch.

Rollback included in proposed approval: on failed startup/readiness/configuration, set SSO_ENABLED=false and DEMO_BROWSER_LOGIN_ENABLED=true, remove only the newly added ENTRA_CLIENT_SECRET setting and preserve existing accounts/SQL 005/membership/session/audit records. Restore newly added non-secret settings to their recorded absent baseline if full settings rollback is needed. Keep request-query logging disabled. Preserve the callback; any removal of the newly appended root URI must remove only that addition. Saving rollback settings also restarts the app. Verify health/readiness and SSO-off/demo-on status. Use a clean demo browser context if old SSO cookies exist. No code rollback is normally needed; never deploy a 004-only build against 005. No SQL modification, migration, credential rotation or Stage G tests are authorized.

Approval request: approve only this configuration-only Stage F rollout, user-controlled secret entry, resulting settings restart in an immediate agreed window, bounded read-only checks and the specified SSO-off rollback. No deployment, SQL writes, credential rotation or Stage G execution.

References: [reviewed readiness/rollback](STAGE_F_READINESS_AND_APPROVAL.md); [Microsoft App Service settings/restart](https://learn.microsoft.com/en-us/azure/app-service/configure-common?tabs=portal); [logging controls](https://learn.microsoft.com/en-us/cli/azure/webapp/log?view=azure-cli-latest).
