# Stage G callback diagnosis — 5 November 2026

**Root cause: UNKNOWN. Stage G remains FAIL; Microsoft SSO demo readiness remains NOT READY.**

The main-container SELECT-only probe found SSO and demo login enabled, the secret present, and matching approved tenant, client and public origin. Presence and shape do not establish that Microsoft accepts the secret. No credential value was exported.

Exactly one transaction in the inspected acceptance window expires at **06:14:52.085478 UTC / 11:44:52.085478 IST**, with **consumed=0**. The code gives transactions and their browser binding cookie five minutes, placing creation at approximately 11:39:52 IST. Nonce and PKCE lengths match expectations. No SSO session exists for the approved membership; the earlier audit probe found no session-created event.

The callback commits consumed=1 before token exchange. The unconsumed transaction and generic error therefore support rejection at the initial state/transaction/expiry/browser-binding guard. A missing or unmatched state could fail without selecting the stored transaction. There is no observed AADSTS error or evidence that token exchange, ID-token validation, membership mapping or session insertion executed. An exact reason cannot be recovered from the generic error alone.

The runtime identity has required transaction SELECT/INSERT/UPDATE, membership SELECT, session SELECT/INSERT/UPDATE and audit INSERT permissions. Exactly one approved enabled Admin membership matches. These are permission metadata and SELECT results, not new writes or repeated provisioning.

Registration metadata preserves the exact HTTPS callback and site-root logout Web redirect URIs. Stage F verified the serving release and effective configuration. Cookie code uses Secure, HttpOnly, SameSite=Lax, root path and __Host- names; the authorization response mode is query. No browser cookie value was exported. No deployment need is established.

The user supplied the original, unrefreshed error page's performance.timeOrigin: **06:14:57.564 UTC / 11:44:57.564 IST**. This is **5.478522 seconds after transaction expiry**, or approximately 305.48 seconds after transaction creation. Combined with consumed=0 and the five-minute browser binding cookie, expiration is now the leading, strongly supported explanation. It is not conclusively confirmed: browser navigation timing is not a timestamp of the server-side callback guard, clocks may differ, and no retained callback event records which predicate failed. Missing/unmatched state or binding cannot be excluded from historical evidence. Retained platform logs end before this attempt; read-only Entra sign-in metadata was unavailable. No login was retried.

No code, Azure configuration, secret or SQL permission correction is justified yet. Preserve the five-minute lifetime and existing state, nonce, PKCE and cookie protections. Do not rotate or re-enter the secret speculatively.

If further diagnosis is authorized, the smallest live validation would be one separately approved fresh Microsoft login completed within five minutes, stopping on any error. The user currently prohibits retrying until the cause is established; no retry is authorized or underway. Historical evidence alone cannot conclusively establish the guard reason. This tests the expiry hypothesis without hosted changes and does not guarantee success. If a prompt attempt fails, prepare sanitized reason-only callback instrumentation and regression tests before seeking deployment approval. Never log URLs, state/binding identifiers, codes, cookies, tokens, secrets or raw exception text.

No hosted changes, restart, deployment, direct SQL writes, credential rotation or login retry occurred during diagnosis. Demo login, schema 005 and memberships are preserved. No local code correction was made because the cause is unconfirmed.

Evidence: [runtime SELECT-only results](evidence/stage-g-callback-diagnosis-2026-11-05/runtime-readonly.json), [registration metadata](evidence/stage-g-callback-diagnosis-2026-11-05/provider-metadata.json), [recorded inspection command](evidence/stage-g-callback-diagnosis-2026-11-05/runtime-command.RECORD_ONLY.txt), [Stage G result](STAGE_G_ACCEPTANCE_RESULT.md), [Stage F result](STAGE_F_CONTROLLED_RETRY_RESULT.md).

Timing evidence: [original-page timestamp correlation](evidence/stage-g-callback-diagnosis-2026-11-05/browser-timing-correlation.json).
