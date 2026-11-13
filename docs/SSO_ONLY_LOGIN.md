# Microsoft-only login cleanup — local implementation

Scope: local code and fixture verification only. No deployment, hosted setting save,
SQL migration, membership change, resource change, or secret change is authorized.
The current hosted release is not changed by these source edits.

## Runtime controls

The frontend offers only **Sign in with Microsoft**, restores identity from
`/api/sso/me`, and sends cookies and CSRF headers. It never reads or sends a stored
bearer credential. Startup removes the obsolete `governance-token` storage entry.
An unavailable SSO service fails closed without automatic demonstration fallback.

For a separately approved hosted rollout, require:

```
SSO_ENABLED=true
DEMO_BROWSER_LOGIN_ENABLED=false
ALLOW_LEGACY_API_CREDENTIALS=false
```

The demo switch is a backend authorization gate, not only a UI flag. When false,
all `/api/auth/*` routes return 403 and demo credentials and previously issued demo
sessions cannot authenticate protected APIs (401). A valid SSO cookie cannot use
legacy auth routes either. Mixed cookie/bearer requests remain rejected.
Configuration defaults retain existing local recovery compatibility; the explicit
hosted setting above is mandatory. The frontend ignores demo availability flags.

Microsoft ID-token signature/issuer/audience/nonce validation, PKCE/state/binding,
secure HttpOnly cookies, CSRF, session expiry/revocation, live membership resolution,
role enforcement and tenant isolation are retained. No internal validator is removed.
Normal authenticated application actions continue their existing managed writes;
verification uses disposable SQLite and synthetic OIDC/provider fixtures only.

## Deployment gate

Do not deploy or save settings without separate explicit approval. Before approval,
retain the exact current working-tree release package (not merely Git HEAD, because
this repository contains pre-existing uncommitted SSO work), its checksum, and the
current non-secret auth flags. Verify artifact availability before any rollout.

After approval, coordinate the release and false demo switch as one controlled
maintenance sequence. Do not advertise SSO-only readiness while an old worker still
accepts demo authentication. Wait for replacement-worker/startup success and verify
release fingerprint, health/readiness, SSO=true/configured=true/demo=false before
manual acceptance. No additional restart or speculative resave is part of this plan.

Hosted acceptance must be human initiated: fresh Microsoft login within five minutes,
approved Admin/workspace, policy/history reads, refresh, logout and unauthenticated
denial. Verify demo exchange and protected bearer requests are denied without logging
credentials or response session material. Do not run paid inference/moderation tests.
A local synthetic pass is not evidence of a real hosted Microsoft callback pass.

## Exact rollback and controlled emergency recovery

1. Stop acceptance on unexpected failure. Preserve sanitized status/error categories.
   Do not change SQL, memberships, secrets or Entra registration.
2. For a code regression, obtain explicit rollback deployment approval and restore the
   preserved pre-cleanup release artifact. Keep `DEMO_BROWSER_LOGIN_ENABLED=false`,
   `ALLOW_LEGACY_API_CREDENTIALS=false`, and `SSO_ENABLED=true`. The previous backend
   did not enforce the demo switch, so it **does not provide the new SSO-only security
   guarantee**. Do not expose it as an SSO-only release; prefer a forward fix of the
   new backend with the previous frontend if that can be separately reviewed.
3. If SSO is unavailable and emergency demo access is necessary, obtain explicit,
   time-bounded approval for restoring the previous artifact and setting
   `DEMO_BROWSER_LOGIN_ENABLED=true`. Leave `ALLOW_LEGACY_API_CREDENTIALS=false`.
   Keep SSO enabled unless a diagnosed startup failure requires separately approved
   SSO-off recovery. Use only the existing privately held credential; never print it.
4. Record operator, reason, deadline, artifact checksum and non-secret setting changes.
   Wait for worker replacement and verify health before use. The new frontend has no
   token form, so a setting-only change cannot restore interactive demo access.
5. Previously issued, unexpired demo sessions may become valid on re-enabling the
   backend gate. Do not assume disabling the gate revoked SQL rows. Review this risk
   before recovery; any row revocation or credential rotation needs separate approval.
6. When SSO is restored, redeploy the reviewed SSO-only artifact, set demo=false and
   legacy=false, verify replacement-worker health, human SSO acceptance and demo denial,
   and close the recovery window. No automatic fallback or automatic rollback exists.

Local reversal: reverse only the cleanup changes, using the pre-edit copies and
reviewed diff; never use a repository-wide reset or checkout, which would destroy
pre-existing uncommitted work. No Git commit has been made for this cleanup.

## Local verification record — 5 November 2026

The 55 targeted SSO/enforcement tests passed. The frontend suite passed all 31
cases, including the opt-in React-to-disposable-FastAPI workflow using a synthetic
OIDC callback and SSO cookie. The Node transport explicitly maintains fixture
cookies because Node fetch has no browser cookie jar; it does not establish real
browser Secure-cookie behavior. Existing SSO tests assert Secure/HttpOnly/SameSite,
CSRF, membership, tenant and session behavior. Microsoft network calls are mocked.

Backend Ruff, frontend ESLint, TypeScript (`tsc -b`) and the production Vite build
passed. Production JS contains the Microsoft sign-in label and contains none of
`Use demonstration access`, `Access token`, `Connect workspace`, or
`/api/auth/session`. The obsolete storage key remains only for removal.

The initial full backend run had 557 passes and four SQL Server metadata-fixture
failures. All four reproduced in an isolated pre-cleanup auth-code copy. The fixture
incorrectly forwarded SQLite index reflection without the UNIQUE backing indexes
that MSSQL returns. Only the fixture was corrected; schema validation, migrations
and SQL permissions are unchanged. Final full-suite outcome is recorded below.

Sandboxed Starlette TestClient startup stalled, and sandboxed loopback bind was
denied. Verification succeeded using approved local execution outside those sandbox
restrictions, still with disposable databases and fixture providers. No hosted
configuration or cloud resources were accessed by these tests.

Files changed for this cleanup:

- `backend/app/security.py`, `backend/app/sessions.py`
- `backend/tests/test_entra_sso.py`, `backend/tests/test_sso_only.py`
- `backend/tests/test_schema_compatibility.py`, `backend/tests/sso_integration_server.py`
- `frontend/src/main.tsx`, `frontend/src/api.ts`
- `frontend/src/App.test.tsx`, `frontend/src/Sso.test.tsx`
- `frontend/src/Backend.integration.test.jsx`, `frontend/src/test-setup.ts`
- `docs/SSO_ONLY_LOGIN.md`

The production build also regenerates ignored `frontend/dist` output locally.
Existing unrelated working-tree changes are preserved; no commit was created.

Final full backend regression outcome: **561 passed, 0 failed**, with two existing
httpx integration deprecation warnings (Starlette and Authlib). Final frontend:
**31 passed, 0 failed, 0 skipped**. `git diff --check` passed.

Status: local verification complete; ready for deployment review, not deployed.
Hosted SSO-only acceptance and release-artifact capture remain approval-gated.
