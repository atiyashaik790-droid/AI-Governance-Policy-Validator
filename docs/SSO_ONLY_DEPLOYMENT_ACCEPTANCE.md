# Microsoft SSO-only deployment and acceptance — 5 November 2026

**DEPLOYED; READ-ONLY VERIFICATION PASS. Human acceptance pending; final success is not declared.**

User explicitly approved deployment to the existing App Service and the sequential
settings save after replacement-worker verification. No additional resource, SQL,
membership, credential or Entra change is approved or performed.

## Reviewed release and rollback

- App Service: `app-governance-validator-atiya-1026`
- Resource group: `rg_techdemo_Atiya_Tabsum_Shaik`
- Subscription: `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`
- New release: **1.2-5aad19f7eea45a42**
- Deployment ID: `7e34ac03-7643-4d4a-a141-9ebf0cf0e5c0`
- Candidate ZIP: `artifacts/sso-only-20261105/governance-sso-only.zip`
- Candidate SHA-256: `a82a1323a2a7a1a081a914e15b8a4e13c58f4fd14fbc6e7d99ab52db43190a8f`
- Exact prior release: **1.2-6749226f1af65b63**
- Preserved rollback ZIP: `artifacts/sso-only-20261105/rollback-1.2-6749226f1af65b63.zip`
- Rollback SHA-256: `9d81fa9b7700557eac2cb41edd5ab861d19a6b8c4f9052e55068e5eab784df80`

Both ZIP integrity and checksums passed. Baseline worker source hashes matched the
preserved rollback artifact. Both artifacts support existing SQL revision **005**;
no migration is packaged or required. Only `app/security.py` and `app/sessions.py`
differ in backend code. Requirements, startup, SSO validation, schema compatibility,
models and governance implementation are unchanged. Frontend changes remove the
interactive demo/token flow. Tests and environment files are excluded from the ZIP.

## Completed checks

- Hosted baseline: health ok, ready, schema 005, expected prior release, SSO enabled
  and configured, demo enabled. Saved flags and secret-presence boolean agreed.
- Local regression evidence: **561 backend and 31 frontend tests passed**, including
  valid synthetic demo-session rejection and synthetic OIDC/React/API workflows.
  Ruff, ESLint, TypeScript and production build passed. No paid provider tests.
- Exactly one application deployment submitted; Azure reports status 4, complete,
  active, completed 08:04:43 UTC / 13:34:43 IST.
- Recycling was observed explicitly. Early old-release HTTP responses and temporary
  main-container 503s were not treated as proof of a new worker or final failure.
- Platform startup probes passed at 08:07:08 UTC. New worker PID 1965 started
  08:06:50.805 UTC / 13:36:50.805 IST, distinct from baseline by start time.
- Initial new-worker source hashes matched reviewed code; actual environment and
  reconstructed Settings agreed SSO=true, demo=true, secret present.
- Initial new-release health/readiness/status passed, schema remained 005, and every
  served frontend asset matched the candidate checksum. JavaScript contains Microsoft
  sign-in but no demo button, token form labels or demo exchange endpoint.
- One approved settings submission then saved `DEMO_BROWSER_LOGIN_ENABLED=false`,
  `SSO_ENABLED=true`, `ALLOW_LEGACY_API_CREDENTIALS=false`. Readback comparison verified
  every unrelated setting and secret value unchanged; only safe flags/booleans recorded.
  Save verification completed 08:08:54 UTC / 13:38:54 IST.

## Final worker and public verification

- Settings-induced worker: PID **1966**, start **08:12:09.294699 UTC / 13:42:09.294699 IST**.
  Start time differs from both earlier workers; PID reuse was not treated as continuity.
- Actual worker environment: SSO=true, demo=false, legacy credentials=false, secret
  present. Reconstructed Settings agrees; reviewed source hashes match.
- Platform startup probes succeeded at 08:12:36 and 08:12:37 UTC; site-running events
  followed at 08:12:40 UTC.
- Final public health/readiness: PASS, release **1.2-5aad19f7eea45a42**, SQL **005**.
- Final SSO status: enabled=true, configured=true, demo_login_enabled=false.
- Final frontend checksum verification: PASS for every served asset; Microsoft-only
  controls verified by served bundle and local rendering tests. No connected browser.

## Historical verification stop — resolved by approved read-only retest

The final hosted negative suite was planned as 18 checks (unauthenticated and two
synthetic invalid bearer cases across legacy routes and protected reads). Five
completed results passed: all four legacy auth routes returned **403** without
credentials; protected policy GET returned **401**. An HTTP read timeout then
interrupted the suite. This is a **transport verification failure**, not evidence
that an authentication bypass succeeded. At that stop, the remaining outcomes were unknown and
were not labelled passed. Requests already in flight were allowed to finish by
the executor; no retry or additional test was initiated after failure.

The concurrently running passive public verifier had already completed successfully
when its completion was collected. No further hosted verification was launched.

Work initially stopped under the user's explicit stop-on-failure instruction. No settings
were resaved, no rollback or demo re-enablement occurred, and no real login was
initiated. The serving release remains SSO=true/demo=false/legacy=false.
No speculative application fix is justified by this timeout alone. Preserve the
current security posture. The user subsequently explicitly approved completing only
the incomplete read-only checks, with bounded timeouts and limited retries.

## Approved read-only completion — PASS

Current worker source hashes match the exact reviewed release artifact. Runtime
flags remain SSO=true/demo=false/legacy=false, with secret present; no hosted mutation
was performed. Preflight health/readiness/status passed on release
**1.2-5aad19f7eea45a42**, schema **005**. All four served frontend files checksum-match
the release and contain only the Microsoft interactive login flow.

Exactly **13 incomplete denial checks** were repeated; the five completed earlier
checks were retained and were not repeated. Every repeated check returned its expected
HTTP status. All **18 total denial checks PASS**:

| Request type | Unauthenticated | Synthetic provisioned credential | Synthetic preissued-session value |
|---|---:|---:|---:|
| POST `/api/auth/session` | 403 | 403 | 403 |
| POST `/api/auth/logout` | 403 | 403 | 403 |
| GET `/api/auth/sessions` | 403 | 403 | 403 |
| POST `/api/auth/sessions/synthetic/revoke` | 403 | 403 | 403 |
| GET `/api/policies?limit=1` | 401 | 401 | 401 |
| GET `/api/sso/me` | 401 | 401 | 401 |

Requests used 20-second socket timeouts with at most one retry permitted for a
transport timeout, gated by an immediate health probe. **Zero timeouts and zero
retries occurred** in this completion run. Unexpected HTTP statuses and non-timeout
transport failures would stop the run. HTTP denial responses were distinguished from
transport exceptions in the per-attempt evidence; no credential or session body was
exported. Post-check health/readiness/SSO status passed with the same release and flags.
The earlier timeout remains preserved as historical evidence, not reclassified as an
authentication failure or deleted.

No deployment, restart, setting save, SQL write, secret change, real login, or paid
provider call was performed during the retest. Automated work has stopped.

Remaining human acceptance:

1. Fresh Incognito window; confirm only **Sign in with Microsoft** is shown.
2. Complete one Microsoft login within five minutes of clicking the sign-in button.
3. Confirm `atiya-tabsum-shaik`, Admin, workspace `demo-appservice-4e2dcce8d618`.
4. Confirm Dashboard, Policy management and Validation history load; refresh and
   confirm the same authenticated identity persists.
5. Sign out; refresh and confirm protected access is denied. Do not start a second
   login. Stop and report visible error text on any unexpected result.

Final acceptance remains **PENDING**, including real provider/secret validity on this
exact release, until the user reports these results.

No browser is connected to the agent. Frontend verification uses exact served asset
checksums plus local rendering tests; human visual confirmation remains pending.
Hosted negative bearer probes use invalid synthetic values, never existing demo
credentials. Rejection of previously valid demo sessions is established by local
regression tests plus matching hosted backend source and disabled runtime flag, not
by exporting or replaying a real hosted session.

## Controlled recovery

No automatic demo re-enablement, rollback, manual restart, credential rotation or
SQL cleanup is performed. On unexpected failure stop and preserve sanitized evidence.
Use [the reviewed recovery procedure](SSO_ONLY_LOGIN.md) and obtain the approval it
requires before any recovery mutation. The preserved old backend does not enforce the
new demo-blocking switch, so restoring it loses the SSO-only bypass guarantee even
if the demo flag is false. Emergency interactive demo recovery requires separate,
time-bounded approval and the prior frontend; a setting-only change cannot restore
a token form in the new frontend. Re-enabling the gate can reactivate unexpired demo
sessions; no SQL session rows were manually revoked.

Evidence: [preflight](evidence/sso-only-deployment-2026-11-05/preflight.json),
[package manifest](evidence/sso-only-deployment-2026-11-05/package.json),
[deployment status](evidence/sso-only-deployment-2026-11-05/deployment-latest.json),
[initial replacement worker](evidence/sso-only-deployment-2026-11-05/worker-deployed-demo-enabled.json),
[initial public checks](evidence/sso-only-deployment-2026-11-05/deployed-demo-enabled-public.json),
[settings comparison](evidence/sso-only-deployment-2026-11-05/demo-disable.json).

Final evidence: [SSO-only worker](evidence/sso-only-deployment-2026-11-05/worker-sso-only.json),
[settings recycle startup](evidence/sso-only-deployment-2026-11-05/settings-recycle-lifecycle.json),
[final public checks](evidence/sso-only-deployment-2026-11-05/final-public.json),
[partial denial checks and stop](evidence/sso-only-deployment-2026-11-05/denial-checks.json).

No direct SQL writes, migrations, membership changes, secret changes, Entra changes,
new Azure resources, billable provider tests or Git commits were performed.

Approved completion evidence: [current worker](evidence/sso-only-deployment-2026-11-05/worker-readonly-retest.json),
[preflight and frontend](evidence/sso-only-deployment-2026-11-05/readonly-retest-preflight.json),
[13 repeated checks and final health](evidence/sso-only-deployment-2026-11-05/readonly-retest-denial.json),
[all 18 outcomes](evidence/sso-only-deployment-2026-11-05/denial-checks-completed.json),
[current result](evidence/sso-only-deployment-2026-11-05/result.json).
