> **Latest result: Stage F PASS.** The controlled retry verified the new worker, enabled SSO with demo login preserved, passed health/readiness on 005, and received user confirmation of both login choices. See [controlled retry result](STAGE_F_CONTROLLED_RETRY_RESULT.md). Historical findings below are retained.

# Stage F execution result — 5 November 2026 (IST)

**Stage F: BLOCKED. Approved SSO-off rollback completed and verified.**

The user confirmed private Portal secret entry. Fresh prechecks verified the saved secret was nonempty, both exact registered Web redirect URIs were present, HTTP filesystem logging was disabled and application logging remained Information. Secret values were neither requested in chat nor printed/persisted in evidence.

## Applied activation and failed acceptance

Saved only the six approved non-secret settings: ENTRA_TENANT_ID, ENTRA_CLIENT_ID, SSO_PUBLIC_ORIGIN, SSO_SESSION_MINUTES=60, DEMO_BROWSER_LOGIN_ENABLED=true and SSO_ENABLED=true. Management-plane readback verified exact values; comparison confirmed the secret and all unrelated settings were preserved.

However, fresh public HTTP responses continued to report sso_enabled=false, configured=false and sso_available=false while saved SSO_ENABLED was true. This failed the activation acceptance criteria. The exact cause of the saved-versus-serving discrepancy is not established. No claim is made that the secret is invalid, and no real Microsoft exchange was performed.

The original local verifier used a 15-second HTTP timeout, while an independent readiness request took 19.5 seconds. Only that local verifier was stopped to prevent a timeout-only rollback; no hosted process was stopped or manually restarted. Fresh independent checks using a 45-second timeout still confirmed the serving-state mismatch, so the approved rollback was invoked based on that mismatch, not merely a short timeout. Activation was not resubmitted.

## Final rollback state

- Saved SSO_ENABLED=false and DEMO_BROWSER_LOGIN_ENABLED=true verified.
- Newly added ENTRA_CLIENT_SECRET App Service setting removed as preapproved; the Entra credential itself was not rotated/deleted and the user's password-manager copy is unaffected.
- All unrelated settings preserved during rollback. Reviewed non-secret Entra identifiers/origin/session values remain configured; SSO is off.
- GET /health: 200, ok.
- GET /ready: 200, ready, database revision 005, same release 1.2-6749226f1af65b63, sso_available=false.
- GET /api/sso/status: 200, sso_enabled=false, configured=false, demo_login_enabled=true.
- Root logout URI and callback preserved; logging protection retained. Neither rollback settings operation changes registration/logging configuration.
- Existing Admin membership untouched; Stage E evidence accepted without retesting.

No code deployment, direct SQL operation, credential rotation, paid provider/storage operation, completed B–E test rerun or Stage G real Microsoft login occurred. Settings changes caused the approved platform restart behavior; no separate manual App Service restart was issued.

## Login-choice check and limits

The public root page returned 200. Its served JavaScript exactly matched the verified existing release artifact and contained both Microsoft and demonstration choice code. No connected browser was available through computer-use tools, so rendered visibility was not independently verified. No SSO login/callback endpoint was called and no authentication session was created.

## Next action

Diagnose why saved App Service SSO settings did not become effective in the serving process before another activation attempt. Do not re-enter the secret or retry activation blindly. The stopped Stage F workflow has left a verified SSO-off/demo-on state. No Stage G execution is authorized by this result.

## Evidence

[User save confirmation](evidence/stage-f-execution-2026-11-04/user-secret-save-confirmation.json), [prerequisites](evidence/stage-f-execution-2026-11-04/prerequisites.json), [activation journal](evidence/stage-f-execution-2026-11-04/activation.json), [independent HTTP reconciliation](evidence/stage-f-execution-2026-11-04/http-reconciliation.json), [rollback verification](evidence/stage-f-execution-2026-11-04/rollback.json), [public page/assets](evidence/stage-f-execution-2026-11-04/public-login-page.json), [final result](evidence/stage-f-execution-2026-11-04/result.json).
