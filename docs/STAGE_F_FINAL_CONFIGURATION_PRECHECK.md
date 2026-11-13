# Stage F final configuration precheck

**BLOCKED — no hosted changes performed.**

Fresh read-only checks confirm the existing single-tenant registration/client ID from the approved plan. Its only Web redirect URI is the exact `/api/sso/callback` URL. Required addition, preserving that callback: `https://app-governance-validator-atiya-1026.azurewebsites.net/`. Add this under Web redirect URIs; do not substitute the front-channel logout URL.

HTTP filesystem request logging is still enabled. The planned protection is not yet applied: disable that logging only, retaining application filesystem logging at Information. HTTP blob logging, detailed errors and failed request tracing are already disabled.

ENTRA_CLIENT_SECRET is absent from hosted settings, this process environment and the workspace .env. No accessible secure handoff was found. The existing non-expired credential metadata cannot provide its value; custody outside this workspace remains unconfirmed, not proven absent.

User action: check the existing approved password manager/secure custody. If the current value is available, retain it privately and confirm availability only. If lost, an authorized registration operator can create a replacement in the existing `Governance-Studio-SSO` registration (client ID `a1a7da0b-ad29-49ec-a9ea-c59219e60df5`): Certificates & secrets > Client secrets > New client secret; choose an organization-approved lifetime, Add; copy its one-time Value, not Secret ID, directly to an existing approved password manager. Do not put it into chat, files, screenshots or shell history. Do not delete the previous credential or configure/save App Service yet. This procedure is supplied for the user; no credential was created or rotated by this precheck.

Microsoft procedure: https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-credentials.

The exact planned settings remain verified against the implementation: ENTRA_TENANT_ID=`4ac50105-0c66-404e-a107-7cbd8a9a6442`; ENTRA_CLIENT_ID=`a1a7da0b-ad29-49ec-a9ea-c59219e60df5`; SSO_PUBLIC_ORIGIN=`https://app-governance-validator-atiya-1026.azurewebsites.net` (no trailing slash); SSO_SESSION_MINUTES=60; DEMO_BROWSER_LOGIN_ENABLED=true; SSO_ENABLED=true only after explicit activation approval and secret/logging/redirect prerequisites. ENTRA_CLIENT_SECRET is provided privately. Existing CORS matches the reviewed origin. No deployment is needed.

Saving the approved settings restarts the app and can briefly interrupt demo access. Rollback uses the existing 004/005-compatible release: SSO_ENABLED=false, DEMO_BROWSER_LOGIN_ENABLED=true, remove only newly added client-secret setting and preserve SQL 005, existing accounts, membership/audit/session data; use a clean demo browser context if stale SSO cookies remain. No old 004-only deployment, downgrade or SQL repair is included.

Demo login remains effectively enabled and SSO disabled by current defaults. No membership operation or other SQL access occurred; Stage E's exact enabled Admin membership/audit remains the accepted evidence and was not changed or retested. No B–E tests, Stage G tests, deployment, restart, setting/registration/logging change or rotation occurred.

Next user action: secure the existing secret value, or create/store a replacement as described if lost, then confirm only that the value is securely available. Explicit Stage F configuration/restart/rollback approval is still required before any hosted changes.

[Fresh evidence](evidence/stage-f-readiness-2026-11-04/final-configuration-precheck.json). [Exact rollout/rollback plan](STAGE_F_READINESS_AND_APPROVAL.md).
