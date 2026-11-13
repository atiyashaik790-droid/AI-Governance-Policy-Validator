> **Superseded candidate design:** The later [compatibility release](SSO_COMPATIBILITY_RELEASE.md) preserves production demo login until SSO acceptance and supports reviewed schemas 004/005. Statements below about an SSO-only production UI or mandatory 005 describe the earlier candidate. Historical test evidence is retained.

# Entra SSO implementation report

4 November 2026, Asia/Kolkata. Local candidate only. The existing Azure application, settings, database records, permissions, registration and infrastructure were not changed. No real credential was printed or copied into source or evidence.

## A. Implementation summary

Implemented Microsoft Entra single-tenant authorization-code login with S256 PKCE, Authlib/joserfc validation, SQL-backed one-use login transactions, secure HttpOnly browser sessions, CSRF, logout and Admin session revocation. React uses Microsoft login, restores its session, displays approved membership and handles denial/expiry. Development token UI requires explicit opt-in and cannot appear through that opt-in in production builds. Existing opaque bearer API compatibility remains separate.

The repository was clean before changes. Existing active entry points remain `backend/app/main.py::app` locally, `backend/app/hosting.py::app` for App Service, and `frontend/src/main.tsx`. Governance business rules remain in place. Reviewer eligibility was extended to SSO membership instead of demo account JSON for SSO callers.

Blocked external work: intended registration/client credential, explicit membership approvals, hosted schema/recovery/grant approval, release-specific deployment approval and real Microsoft acceptance. The local candidate is **not approved or configured for deployment**.

## B. Files changed

| Exact path | Purpose |
|---|---|
| `.env.example` | Disabled-by-default SSO settings and server-secret guidance. |
| `backend/app/config.py` | Typed SSO enablement, Entra identifiers, confidential-client secret, fixed origin and lifetime. |
| `backend/app/sso.py` | OIDC initiation/callback, validation, cookie identity, CSRF, session and Admin endpoints. |
| `backend/app/security.py` | Integrate cookie authentication; reject mixed bearer/cookie identities. |
| `backend/app/models.py` | Membership, login transaction and browser session models. |
| `backend/app/main.py` | Register SSO router; CSRF header; schema 005 readiness; SSO reviewer lookup and safe diagnostics. |
| `backend/app/release.py` | Required schema revision 005 metadata. |
| `backend/app/web_assets.py` | Production startup requires complete SSO settings and disallows development browser login. |
| `backend/requirements.txt` | Add maintained Authlib and joserfc dependencies. |
| `backend/requirements.lock.txt` | Pin Authlib 1.9.4 and joserfc 1.8.0. |
| `backend/migrations/versions/005_entra_sso.py` | Add three isolated tables; preserve existing governance rows; no automatic destructive downgrade. |
| `backend/tests/test_entra_sso.py` | Synthetic cryptographic/OIDC/session/CSRF/RBAC/membership/reviewer security tests. |
| `backend/tests/sso_browser_server.py` | Temporary HTTPS/SQLite/synthetic-provider browser fixture; excluded from deployment. |
| `backend/tests/test_deployment_preparation.py` | Enforce complete SSO production configuration and optional empty legacy account list. |
| `backend/tests/test_migration_preflight.py` | Verify extended chain and objects/foreign keys. |
| `backend/tests/test_migration_recovery.py` | Check new migration head while preserving existing rows and recovery assertions. |
| `backend/tests/test_sql_inventory.py` | Verify inventory recognizes all 17 tables and head 005. |
| `backend/tests/test_sql_http_plan.py` | Update table-count assertion; retain historical workflow safety checks. |
| `frontend/src/api.ts` | Cookie requests, in-memory CSRF, safe login URL, production same-origin default and explicit development bearer mode. |
| `frontend/src/main.tsx` | Microsoft login, refresh restoration, identity display, denial/expiry handling, logout and SSO session administration. |
| `frontend/src/Sso.test.tsx` | Production-mode SSO UI and transport tests. |
| `frontend/src/test-setup.ts` | Explicit demo opt-in for existing legacy workflow tests. |
| `scripts/manage_sso_membership.py` | Validation-only default; separately authorized transactional membership provisioning with audit. |
| `scripts/check_azure_sql.py` | Read-only permission probe covers new tables; runtime has only SELECT on membership. |
| `scripts/run_offline_demo.py` | Explicitly isolate offline mode from any configured SSO settings. |
| `scripts/prepare_app_service.py` | Candidate release metadata requires schema 005. |
| `scripts/tests/sso_browser.cjs` | Chrome acceptance with production React and disposable synthetic-provider backend. |
| `deployment/appsettings.example.json` | Nonfunctional example of required SSO setting names; no real credentials. |
| `deployment/enterprise_identity.REVIEW_ONLY.json` | Updated actual implementation/configuration boundary. |
| `deployment/sso-membership.example.json` | Disabled placeholder mapping; grants no privileges. |
| `deployment/sso-runtime-permissions.REVIEW_ONLY.sql` | Least-privilege reviewed grant preparation; not executed. |
| `deployment/migration-005.REVIEW_ONLY.sql` | Offline SQL Server migration compilation; not executed. |
| `README.md` | Candidate status link and explicit development-token startup opt-in. |
| `docs/CURRENT_STATUS.md` | Update only local demo startup opt-in; hosted release history preserved. |
| `docs/LOCAL_RUN_GUIDE.md` | Explicit development login option for existing token-based local workflows. |
| `docs/LOCAL_LIVE_RUN_GUIDE.md` | Same explicit option for the existing local backend using cloud integrations. |
| `docs/ENTRA_SSO.md` | Beginner/architect explanation, endpoints, configuration, diagrams, operator procedure, test/deploy/rollback gates and interview Q&A. |
| `docs/ENTRA_SSO_REPORT.md` | This handover and validation report. |
| `docs/evidence/entra-sso/backend-tests.txt` | Full final passing backend test output without credentials. |
| `docs/evidence/entra-sso/browser-tests.json` | Synthetic-provider Chrome check results. |
| `docs/evidence/entra-sso/validation.json` | Baseline/final counts and explicit external verification boundaries. |
| `docs/evidence/entra-sso/package.json` | Allowlisted package file hashes and candidate release fingerprint; no credentials. |

## C. Microsoft Entra configuration

Authorized read-only discovery returned no application named `Governance-Studio-SSO` in current directory `4ac50105-0c66-404e-a107-7cbd8a9a6442`. The current project-local CLI identity type is user. Listing access does not establish authority to create/modify a registration or approve application roles. No duplicate registration was created. Confirm the intended directory and authorized operator before the next cloud operation.

No actual client ID exists from this lookup. Client secret, intended registration, and approved user/workspace/role mappings are not supplied. Root `.env` has no entries for `SSO_ENABLED`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` or `SSO_PUBLIC_ORIGIN`; it was not modified. Process or hosted settings were not assumed to match local files. Actual hosted SSO configuration was not changed or freshly verified.

Exact implemented hosted callback:

`https://app-governance-validator-atiya-1026.azurewebsites.net/api/sso/callback`

Register it as a confidential **Web** callback. The initially proposed `/auth/callback` is not used. Request `openid profile` only; no Graph call, broad Graph permissions, offline access or automatic administrator consent. Confidential-client authentication requires a securely provisioned server-side secret in this implementation. No signing key or client secret belongs in React. Local real SSO requires its separately registered same-origin HTTPS callback.

## D. Authentication architecture

React navigates to `/api/sso/login`. FastAPI saves state/binding/nonce/verifier in the existing database and redirects to Entra. After organizational authentication, Entra returns a code to `/api/sso/callback`. FastAPI consumes the transaction, exchanges the code, verifies the signed ID token through maintained libraries and resolves the directory/object ID to an enabled membership. It creates an application session and redirects to the approved SPA route. React calls `/api/sso/me` to restore identity and obtain in-memory CSRF material.

SQL-backed sessions survive workers/restarts, subject to absolute expiry. The application stores no Microsoft tokens. See the architecture and sequence diagrams in `ENTRA_SSO.md`.

## E. Security controls

- Pinned directory/issuer, exact client audience, RS256 allowlist, signature/expiration/nonce validation, TLS discovery and restricted Microsoft endpoints.
- State plus browser binding; five-minute one-use transaction; atomic consumption before exchange; S256 PKCE; no open redirects.
- Random rotated application sessions; hashed credentials; Secure/HttpOnly/SameSite=Lax `__Host-` cookies; absolute expiry; SQL revocation and audit.
- Exact Origin plus session-derived CSRF header on mutations; no production token storage in React.
- Unknown/disabled memberships denied. Stable directory/object identifiers, explicit approved server-side roles and application tenants. No email-domain roles, arbitrary tenant selection or first-user Admin.
- Membership is checked on every request. Changes apply on the next request after commit; already-running requests may complete.
- Cookie authentication and opaque API bearer authentication are distinct; no fallback from a failed cookie to a bearer identity. No pre-existing enterprise JWT API path was present.
- Runtime has no membership-write permission in the prepared grant plan. Provisioning requires a separate operator, exact mapping and approval reference, with transactional audit.
- Production hosting startup rejects disabled/incomplete SSO or development browser login. No auth bypass or new cloud service was introduced.

Application structured logs omit request bodies and query strings. Production access logs are disabled by the existing startup command. Azure/proxy callback-query logging still requires operational review and live acceptance; no live logging claim is made.

## F. Test results

Final counts:

| Check | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Backend, including existing regressions and new security tests | 500 | 0 | 0 |
| Frontend, including disposable FastAPI integration | 29 | 0 | 0 |
| Chrome, synthetic provider over local HTTPS | 11 | 0 | 0 |

Python lint/source formatting, frontend lint/changed-file formatting, TypeScript and production build: PASS. See `evidence/entra-sso/validation.json` for exact boundaries.

 Baseline backend: 443 passed, 0 failed, 0 skipped. Baseline frontend: 21 passed, 0 failed, 1 skipped (opt-in integration not enabled). Baseline lint/typecheck/build passed. Full-tree formatting already reported two Markdown examples and `frontend/src/Backend.integration.test.jsx`; unrelated files were preserved.

Final backend tests include all existing regressions plus synthetic OIDC and production-configuration security tests. The full frontend run enables the real disposable FastAPI integration. Changed frontend formatting and all Python source formatting pass. New browser acceptance uses a test-only HTTPS certificate and synthetic provider with the production React build and real FastAPI SQL sessions.

No new live AI generation, moderation or ADLS export was run. Two existing dependency deprecation warnings concern httpx compatibility with Starlette/Authlib; tests pass and no protocol validation is disabled. Docker was not built/run here. Offline SQL Server compilation and SQLite migration/recovery tests do not prove a hosted SQL migration.

## G. Azure deployment readiness

**BLOCKED; do not deploy.** Local implementation and package preparation are complete, but real registration/client credential, explicitly approved memberships, current hosted schema/recovery verification, migration/grants and specific deployment authorization remain outstanding.

Candidate artifact: `/tmp/governance-entra-sso-candidate-final.zip`, release **1.2-f3f4b3e96adb50e7**. Exact release fingerprint, source/static hashes and file list are in `evidence/entra-sso/package.json`. It contains 27 allowlisted files, including the SSO module, locked dependencies and production frontend. Tests, synthetic provider, environment files, credential files and databases are excluded. Required migration is 005. The ZIP is a local review artifact, not an authorized release.

The plan modifies only the existing App Service's approved settings, the intended Entra registration, and additive tables/grants on the existing Azure SQL after separate approvals. No additional Web App, database, Redis, Key Vault or other service is needed. The existing governed provider/storage integrations are preserved.

## H. Live verification

**PASS:** isolated signed-token validation, FastAPI sessions/RBAC/CSRF tests and production React browser acceptance with a synthetic identity provider.

**NOT VERIFIED / BLOCKED:** real Microsoft organizational login/MFA/callback, actual registration/secret validity, hosted cookie/proxy/logging behavior, real SSO user mapping, hosted migration/grants and release rollout. No real Microsoft account flow completed, and no end-to-end enterprise SSO success is claimed. The existing Azure application was not deployed or mutated.

## I. Rollback procedure

Preserve the existing deployed package/fingerprint and secure settings before rollout. Migration 005 is additive, but the previous release's readiness endpoint expects 004. A rollback must therefore include a tested compatibility package accepting the additive schema or an explicitly approved database recovery plan that accounts for post-recovery-point writes. Do not simply redeploy the old package against 005 and claim success; do not falsify Alembic history or drop new identity/audit evidence.

This candidate intentionally has no production token-entry UI, so setting SSO false alone cannot restore the prior experience. Rehearse and approve the exact package/configuration/database rollback procedure before any hosted migration. This task executed no hosted migration, rollback or restore. Full operator steps are in `ENTRA_SSO.md`.

## J. Demo explanation

“Sign in with Microsoft” asks your organization to confirm who you are, including MFA when required. Microsoft returns a short-lived one-use code to FastAPI. FastAPI checks the result and looks up your approved workspace and role. It gives your browser a protected application-session cookie, so you never paste a token. Every protected request checks that the session and membership still work. Sign out revokes that application session and sends you to Microsoft's sign-out page.

To finish safely, an authorized operator must confirm the directory and registration authority, securely provision the reviewed client credential, approve each exact identity/workspace/role mapping, approve the verified migration/recovery plan, and then approve deployment of the specific fingerprint. Real sign-in acceptance follows deployment approval. Do not send client secrets, tokens or passwords in chat.
