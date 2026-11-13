# Local HTTPS Microsoft SSO test on port 5176 — approval plan (13 November 2026)

**Status: EXECUTED 13 Nov 2026 (A–D approved).** Admin (`atiya-tabsum-shaik`) and User (`gayatri-salunke`, mapped 13 Nov in place of demo-user, whose password the owner does not hold) verified with real Microsoft sign-in; User gets 403 on Admin APIs. See PROGRESS item 9.

Goal: real Microsoft Entra sign-in for one Admin and one User on `https://localhost:5176`, against the persistent local database (revision 011) and the existing app registration, with live providers unchanged.

## Facts (verified read-only, 13 Nov)

| Item | Value |
|------|-------|
| App registration | **Governance-Studio-SSO**, client ID `a1a7da0b-ad29-49ec-a9ea-c59219e60df5`, single tenant (`AzureADMyOrg`), tenant `4ac50105-0c66-404e-a107-7cbd8a9a6442` |
| Current web redirect URIs | `https://app-governance-validator-atiya-1026.azurewebsites.net/` and `…/api/sso/callback` (hosted only) |
| Client secrets | One: `Governance-Studio-SSO-Backend` (hint `7Xu`), expires 2027-05-03. Its value is not in the local `.env` |
| Code constraints (`backend/app/sso.py`) | `SSO_PUBLIC_ORIGIN` must be `https://…`; callback is `<origin>/api/sso/callback`; session cookies are `__Host-…; Secure; SameSite=Lax`, so the SPA and the API must share one HTTPS origin |
| Real identities (from `deployment/*.json`) | Admin `atiya-tabsum-shaik` (object `b5d8bfbe-…`, APPROVED file); User `gpv-demo-user` (object `f4799f3f-…`, PROPOSED file) |
| Local memberships today | Only synthetic placeholders (`synthetic-admin`, `synthetic-user`, fake tenant/object IDs), so real accounts would be refused locally |
| Tooling | OpenSSL 3.5.3 available; no mkcert; no new packages needed |

## Design

`https://localhost:5176` is served by Vite with a locally generated self-signed certificate. Vite proxies `/api/*` to the live backend on `http://127.0.0.1:8012`, so pages, API calls and cookies share one origin. The frontend runs with `VITE_LOCAL_DEMO=false` and `VITE_API_URL=` (same origin). The backend runs with `SSO_ENABLED=true`, `SSO_PUBLIC_ORIGIN=https://localhost:5176` and demo token login disabled.

## Changes requiring approval

| # | Change | Where | Reversible |
|---|--------|-------|------------|
| A | **Entra:** add the web redirect URI `https://localhost:5176/api/sso/callback` to Governance-Studio-SSO. Both existing URIs stay. No other registration change (no new secret, permissions or owners) | Entra ID | Yes: remove the URI after the test |
| B | **Client secret on this machine:** you copy the **existing** secret value (from the hosted App Service setting `ENTRA_CLIENT_SECRET` or wherever you keep it) into the local `.env` yourself. I never see or type it. If you no longer have the value, the alternative is a new short-lived secret, which needs its own approval | `.env` (git-ignored) | Yes: delete the line after the test |
| C | **Local identity mapping:** add two memberships to the persistent local DB (`private/live-local-chat/offline.db`) with `scripts/manage_sso_membership.py --apply`: Admin `atiya-tabsum-shaik`/`b5d8bfbe-…` and User `gpv-demo-user`/`f4799f3f-…`, both mapped to the local workspace `clean-demo-local`. The synthetic rows remain. Promotes the User mapping from PROPOSED to used-locally | Local DB only | Yes: disable via the same script |
| D | **Restart Vite on 5176 in HTTPS mode** (frontend only, no data). While SSO mode is on, `http://localhost:5176` and token sign-in are unavailable; switch back afterwards | Local process | Yes |

## Local code and config changes (no cloud effect, done after approval)

1. `frontend/vite.config.ts`: when `GPV_DEV_HTTPS_CERT`/`GPV_DEV_HTTPS_KEY` are set, serve HTTPS and proxy `/api` to `GPV_DEV_API_TARGET`. Default behaviour unchanged.
2. `scripts/run_live_local_demo.py`: add `--sso`, which reads `ENTRA_TENANT_ID`/`ENTRA_CLIENT_ID`/`ENTRA_CLIENT_SECRET` from `.env`, sets `SSO_ENABLED=true`, `SSO_PUBLIC_ORIGIN=https://localhost:5176` and `DEMO_BROWSER_LOGIN_ENABLED=false`, and allows the HTTPS loopback origin. Without `--sso`, behaviour is unchanged.
3. Self-signed certificate for `localhost` (SAN `DNS:localhost`, 7 days) in `private/local-https/` (git-ignored). The browser shows a one-time certificate warning, which you accept.
4. `.env` (git-ignored): `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID` (not secret), plus your `ENTRA_CLIENT_SECRET` (B).

## Test (you sign in; I verify)

1. Admin `atiya.tabsum@Sigmoidanalytics.com` signs in at `https://localhost:5176`. Expect the Admin portal, and policy, audit, reviews and settings reachable. Backend: `/api/sso/me` role Admin; an audit `sso.session.created` with `actor_role=Admin`.
2. Admin signs out; the User account (`gpv-demo-user`) signs in. Expect only the User chatbot. Admin APIs return 403, for example `/api/v2/audit/events` and policy assignment changes. Own conversation history only.
3. An unmapped account (optional) is refused.
4. No paid requests: chat turns are not sent unless you separately approve the bounded live request.

## Rollback (after the test)

Remove redirect URI (A) with `az ad app update --web-redirect-uris` keeping only the two original URIs. Delete the secret line from `.env`. Optionally disable the two local memberships. Restart Vite and the backend in the current token-login mode (`docs/PROGRESS.md`, Port 5176 section).
