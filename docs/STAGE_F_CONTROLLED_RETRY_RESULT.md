# Stage F controlled retry — 5 November 2026

**Stage F: PASS.**

| Required result | Verified state |
|---|---|
| New worker verified | YES |
| SSO enabled | YES |
| Demo login enabled | YES |
| Health and readiness | PASS |
| Rollback performed | NO |
| Release / SQL revision | 1.2-6749226f1af65b63 / 005 |
| Login choices | Both visible, explicitly confirmed by user without starting login |
| Next step | Stage G only after Stage F PASS and separate authorization |

## Controlled sequence

The user's confirmation of private Portal secret entry was recorded specifically for this retry. Baseline worker PID 1965 (start 4 November 18:45:30 UTC) was not reused as activation evidence.

The secret-save replacement worker was verified first: PID 1966, start 5 November 05:51:35 UTC; secret present, SSO=false, demo=true, tenant/client/origin matches, reviewed source hashes and a newer platform startup-success event. Only then did the bounded public secret-phase health/readiness/status checks run and pass. No activation setting was saved during the secret-save restart.

Exactly one approved non-secret activation submission occurred at **05:52:59 UTC / 11:22:59 IST**. The six reviewed settings were saved; readback comparison verified all unrelated settings and the secret unchanged. Old-worker observations and temporary main-container 503 responses were treated as in-progress recycling, not failure or rollback triggers.

The activation replacement worker was independently verified: **PID 1966, start 05 November 2026, 11:25:59 IST / 05:55:59 UTC**. PID reuse across containers was handled by comparing start time as well as PID. Its actual environment has SSO_ENABLED=true, APPSETTING_SSO_ENABLED=true, DEMO_BROWSER_LOGIN_ENABLED=true, ENTRA_CLIENT_SECRET present (boolean only), and exact approved tenant/client/origin. Reconstructed Settings agrees; deployed source hashes match the reviewed release; no configured dotenv file exists.

Platform startup probes succeeded at **05:56:12 and 05:56:13 UTC**, followed by site-running events at 05:56:14. Only after this worker/startup verification did public checks run. GET /health reports ok; GET /ready reports ready, schema 005, unchanged release and sso_available=true; GET /api/sso/status reports sso_enabled=true, configured=true, demo_login_enabled=true. Configuration shape/readiness does not prove real Microsoft secret validity or successful authentication; those belong to Stage G.

## Login choices and evidence boundary

The public root page returned 200 and its JavaScript exactly matches the preserved release artifact. Both “Sign in with Microsoft” and “Use demonstration access” are present in that served code. No connected browser was available. The user confirmed that both choices are visibly rendered in a fresh private browser context, without initiating either login flow.

## Preserved state and restrictions

Both exact Web redirect URIs and HTTP filesystem request-logging protection were checked before activation and left unchanged. Application filesystem logging remains Information. No additional manual restart, code deployment, credential rotation, Azure SQL/membership/permission change, provider/storage call, completed B–E suite rerun or Stage G real login/callback occurred. Normal settings-induced restarts were within the approved scope. No Microsoft token, secret value or cookie was printed or persisted in evidence. The existing Entra credential was reused through user-controlled Portal entry.

The previous mismatch was not reproduced once worker replacement and initialization were respected. This establishes that the deployed application can load and serve the approved SSO configuration; it does not retroactively identify every cause of the earlier failed startup probe. The repaired read-only inspection path made the worker-state gate observable.

## Evidence

[User secret-save confirmation](evidence/stage-f-controlled-retry-2026-11-05/user-secret-save-confirmation.json), [prerequisites](evidence/stage-f-controlled-retry-2026-11-05/precheck.json), [baseline worker](evidence/stage-f-controlled-retry-2026-11-05/baseline-worker.json), [secret-save worker](evidence/stage-f-controlled-retry-2026-11-05/secret-save-verified-worker.json), [activation worker and startup events](evidence/stage-f-controlled-retry-2026-11-05/activation-verified-worker.json), [execution and bounded public checks](evidence/stage-f-controlled-retry-2026-11-05/execution.json), [public page/assets](evidence/stage-f-controlled-retry-2026-11-05/public-login-page.json), [asserted result](evidence/stage-f-controlled-retry-2026-11-05/result.json).
