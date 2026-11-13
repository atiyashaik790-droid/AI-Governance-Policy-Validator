# Phase 3 — local session and login verification

## Findings and scope

The inspected application default and examples used `SSO_SESSION_MINUTES=60`. Historical local activation records also specify 60; those records are not evidence of today's hosted configuration. There is no few-minute application expiry timer in the inspected code. The five-minute OIDC transaction expiry applies only to completing a login, not the resulting application session. No hosted login, session revocation, App Service operation or Entra policy inspection was performed, so the reported few-minute hosted logout cannot be causally confirmed here.

The verified warning defect was a global 401 event mapped unconditionally to “Session expired or revoked,” without proving a previously authenticated session or distinguishing reasons. Bootstrap already suppressed ordinary anonymous 401 events; the generic listener and lack of server reason codes still allowed misleading warnings. Timestamp validation previously compared ISO strings; it now compares timezone-aware instants, failing closed on malformed or naive expiry values. Normal existing UTC timestamps had equivalent ordering; this change does not establish timezone handling as the cause of the reported incident.

## Implementation

The default and example setting are now 120 minutes, with a hard configured maximum of 120. Shorter explicit operator settings remain respected; they are not silently bypassed. The effective local setting was verified as 120. A successful callback records one absolute UTC expiry in the existing session row, emits `Max-Age=7200` at the default, and supplies the same expiry as the Secure, HttpOnly, SameSite=Lax, Path=/ cookie deadline (HTTP dates have whole-second precision). Activity and refresh never renew the deadline. Existing sessions keep their persisted expiry; changing configuration does not extend them. No migration or schema change is needed.

Session validation continues to check enabled directory membership, roles and tenant directory on every request. Revocation and logout remain immediate. OIDC state/binding, PKCE, nonce, token validation, session rotation and same-origin CSRF are preserved. Entra tokens are still discarded after callback; no refresh-token or sliding-session mechanism was added.

401 responses from the SSO session resolver include an allowlisted `X-Session-Reason`: anonymous, expired or ended. Unknown/revoked sessions and invalidated memberships use ended. The header contains no IDs or credentials. It is exposed through the existing CORS header allowlist without changing origins, credential policy or CSRF checks. `/me` supplies the absolute expiry and server time as noncredential metadata.

The frontend keeps that metadata only in memory and uses elapsed monotonic time solely to choose a message if an already-authenticated browser's cookie disappears at expiry. It never authenticates, renews or bypasses a server denial. Without a cookie after a fresh page load, the server cannot distinguish a new visitor from a browser that already discarded an expired cookie; such visits correctly show clean login, not a fabricated expiration warning. Explicit server-confirmed expiry shows “Your session has expired. Please sign in again.” Revocation/invalidation shows “Your session has ended. Please sign in again.” A 403 remains a permission error. Cancelled responses do not generate session-end events. Manual logout clears local message/context before redirect, and late events do not invent warnings for anonymous visitors.

The primary button is exactly “Sign in,” including its busy state, with no Microsoft logo. Microsoft Entra remains the sign-in destination. Branding, welcome copy, keyboard access and transient sign-in loading/error states remain; no duration/countdown or steady-state session banner is added. Admin/User routing, Settings sessions and AI Usage & Consumption are preserved.

## Verification and operational limits

Tests use disposable databases, synthetic sessions, controlled clocks and mocked OIDC/provider responses. Coverage includes absolute lifetime/cookie alignment, before/at-boundary expiry, offset timestamps, invalid timestamps, repeated activity/refresh, rotation, logout, revocation, anonymous restoration, reason messages, clean manual logout, button markup, callback validation, CSRF, membership/tenant/RBAC checks, User portal routing and protected Human Review.

No hosted setting was changed. Deployment needs separate approval and an operator check of the effective `SSO_SESSION_MINUTES` value. To obtain the verified default lifetime in a hosted environment with an explicit old value, its application setting must separately be approved for 120. Values above 120 now fail configuration validation instead of permitting a longer session. Do not override shorter upstream security controls; confirm any such controls before rollout. Investigating any continuing few-minute hosted sign-outs requires separately authorized, sanitized runtime evidence (server reason, UTC expiry, cookie delivery, membership/revocation and effective configuration), without logging tokens or cookies.

Files changed in this phase:

```text
.env.example
backend/app/config.py
backend/app/main.py
backend/app/sso.py
backend/tests/test_entra_sso.py
backend/tests/test_session_lifetime.py
deployment/appsettings.example.json
docs/ENTRA_SSO.md
docs/SESSION_LIFETIME_PHASE3.md
frontend/src/api.ts
frontend/src/api.test.ts
frontend/src/main.tsx
frontend/src/App.test.tsx
frontend/src/Sso.test.tsx
```

Final local results: **172 backend tests passed**, **81 focused frontend tests passed**, and the final login-copy check passed all 19 SSO frontend tests (overlapping scope). Ruff, targeted Python formatting checks, frontend lint, TypeScript checks, production build and Git whitespace checks passed. Two existing dependency deprecation warnings were reported by pytest; no failing tests remain. One stale older SSO test was corrected to expect 403, rather than 200, for a chatbot User reading privileged policy APIs; no backend permission was relaxed.
