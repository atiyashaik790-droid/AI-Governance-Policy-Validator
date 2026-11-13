# Stage G Microsoft SSO acceptance — 5 November 2026

**Stage G: FAIL. Overall Microsoft SSO demo readiness: NOT READY. Acceptance stopped at the first unexpected failure.**

| Requested result | Outcome |
|---|---|
| Microsoft login, end to end | FAIL — returned to Governance Studio with generic authentication error |
| Admin access | NOT VERIFIED — no application session established |
| Session persistence/logout/revocation | NOT TESTED — stopped on login failure |
| Existing demo login | NOT TESTED in Stage G — stopped on failure; enabled flag remains true |
| Unauthorized unauthenticated access | PASS — protected policy and /api/sso/me requests returned 401 |
| Health/readiness after failure | PASS — same release 1.2-6749226f1af65b63, schema 005 |

Untested items are deliberately not labelled failed: no evidence shows that demo login, role mapping or logout is broken. A successful Microsoft provider authentication alone is also not claimed; the user observed a Microsoft-sign-in/callback failure, then identified the app's generic error label.

## User observations and failure boundary

The user was guided through one real-account attempt in a fresh private context and reported **“Microsoft sign-in or callback failed.”** Their follow-up identified **“Governance Studio: Microsoft sign-in could not be completed.”** They were told not to retry and not to share passwords, MFA codes, secrets, tokens, cookies or callback URLs. None were received.

A targeted SELECT-only aggregate probe through the actual main-container managed-identity connection found **zero** sso.session.created or sso.session.revoked audit events for the approved actor/workspace since the acceptance start, and **zero application SSO sessions** tied to the known approved membership. No session credentials, digests, row identifiers or Microsoft token claims were exported. Thus this attempt did not establish the approved application's SSO session.

The generic authentication failure can arise from state/binding/expiry validation, provider callback errors, code exchange or ID-token validation. These possibilities are not distinguished by the available evidence. No secret-invalid, consent, MFA, membership or code-defect diagnosis is asserted. No repair or further login attempt was performed. The probe's inherited wrapper initially labelled sql_accessed=false incorrectly; the raw record is retained and the corrected record explicitly identifies SELECT-only SQL access and no direct database writes.

## Baseline and preservation

Before the user's attempt, health/readiness/status passed and both login modes were enabled. Cookie-free GET /api/policies?limit=1 and GET /api/sso/me returned 401. The status endpoint had Cache-Control: no-store and Referrer-Policy: no-referrer. Sensitive callback/session data was not captured; successful-session cookie/browser-storage/privacy acceptance remains incomplete because login failed.

After failure, only passive health/readiness/status and the read-only aggregate audit diagnostic were performed. Public results remain healthy/ready at schema 005 on the unchanged release, sso_enabled=true, configured=true, demo_login_enabled=true. Configuration readiness does not prove a valid client-secret exchange or a successful Microsoft login.

No application code/settings, Azure SQL schema, users, memberships or permissions were modified. No deployment, restart, credential rotation, destructive policy operation or billable provider/storage request occurred. Normal application-managed login transaction/rate-limit writes may occur when the user starts the approved login flow; they were not directly altered or cleaned up. No logout/re-login, demo-login or other acceptance action followed the unexpected failure. Stage F configuration is preserved; no automatic configuration rollback is authorized in this Stage G scope.

## Next step

Diagnose the callback authentication failure using sanitized, read-only evidence before approving another login attempt or any repair. Do not request or expose the secret, log raw callback query strings, rotate credentials speculatively or assign new roles.

## Evidence

[User failure report](evidence/stage-g-acceptance-2026-11-05/user-microsoft-login-result.json), [generic app error label](evidence/stage-g-acceptance-2026-11-05/user-error-label.json), [baseline and unauthorized denial](evidence/stage-g-acceptance-2026-11-05/preflight.json), [safe response headers](evidence/stage-g-acceptance-2026-11-05/security-headers.json), [read-only aggregate session/audit result](evidence/stage-g-acceptance-2026-11-05/session-audit-latest.json), [post-failure health](evidence/stage-g-acceptance-2026-11-05/post-failure-health.json), [final result](evidence/stage-g-acceptance-2026-11-05/result.json).
