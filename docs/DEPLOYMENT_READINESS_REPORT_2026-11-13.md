# Deployment readiness report — Governance Studio (13 November 2026)

**Verdict: READY TO DEPLOY, PENDING APPROVAL.** The current release is verified end to end locally against live Azure OpenAI and OpenAI Moderation, with real Microsoft Entra SSO for Admin and User. The target Azure SQL database is migrated to revision 011, with the runtime grants applied. Nothing has been deployed. The hosted site still runs the previous release on the previous database. Evidence for every line below is in [PROGRESS.md](PROGRESS.md).

## 1. What is verified

| Area | Result | Evidence |
|------|--------|----------|
| Governed chat, persistent history | Survives restart; per-user and per-workspace isolation; only governed text stored (blocked/held prompts, raw PII, secrets, document text and filenames never stored); readable prompts and deterministic titles | PROGRESS 1, 2, 14 |
| Input governance | ALLOW, REDACT, BLOCK (secret, keyword, moderation), moderation outage fails closed; blocked requests never call the model | PROGRESS 12 |
| Output governance | Generated secret → output BLOCK, nothing leaked | PROGRESS 12 |
| Policy conflicts | Overlapping REDACT vs BLOCK → BLOCK (most restrictive) | PROGRESS 12 |
| Live providers | Real request under Admin SSO: 5 policies evaluated, OpenAI Moderation `SATISFIED`, Azure OpenAI gpt-5-mini generated, output ALLOW | PROGRESS 10 |
| Microsoft Entra SSO | Admin (atiya.tabsum@) → Admin portal; User (gayatri.salunke@) → chatbot only; User gets 403 on `/api/v2/audit/events` and `/api/v2/workspace/policy-assignments` | PROGRESS 9 |
| Audit history | Date filters correct (UTC); event-time roles stored for new events; older rows marked "Historical role unavailable", no backfill | PROGRESS 6, 15 |
| Overview metrics | API figures equal direct database counts | PROGRESS 16 |
| Azure SQL target | `sqldb-gpv-demo-v008-20261108` at revision **011**; counts unchanged by migration (8 policies, 8 versions, 8 active assignments, 2 SSO memberships); runtime role granted on new tables | PROGRESS 8 |
| Tests | Frontend 142 passed / 1 skipped, lint, TypeScript, production build. Backend: all current-schema suites pass; remaining failures are pre-010 schema fixtures and environment cases, none on the 011 path | PROGRESS 11, 15 |

## 2. Hosted state today (read-only, 13 Nov)

| Item | Value |
|------|-------|
| Site | `app-governance-validator-atiya-1026` — Running, Python 3.13, system-assigned managed identity; `/health` ok, `/ready` ready |
| Release | `1.2-ca5df7c1dc19e525` (built 5 Nov); package kept for rollback: `artifacts/structural-only-candidate-2026-11-05/production/governance-structural-only.zip` |
| Database | `sqldb-governance-validator-dev` (revision 005). **Not** the migrated 011 database |
| Settings | SSO on, demo login off, live providers, Presidio, managed-identity SQL; secrets present as settings (values not read) |

## 3. Deployment plan (each step needs approval)

1. **Build:** production frontend build, then `scripts/prepare_app_service.py` creates the allowlisted ZIP (no `.env` or data). Record its SHA-256.
2. **Snapshot for rollback:** save the current app settings (names and non-secret values) and confirm the rollback ZIP hash.
3. **Point the site at the 011 database:** change only `DATABASE_URL` to `mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-gpv-demo-v008-20261108?driver=ODBC+Driver+18+for+SQL+Server`. The old 005 database is left untouched.
4. **Deploy** the ZIP once (`az webapp deploy --type zip`); no other setting changes.
5. **Verify:** `/health`, `/ready` reports schema 011; Admin SSO sign-in; User SSO sign-in plus 403 on Admin APIs; one chat turn (one paid request) only if you approve it.
6. **Rollback** if any check fails: restore the previous `DATABASE_URL` and redeploy the kept ZIP.

**Decision needed before step 5:** the hosted User account. Azure SQL maps `demo-user@Sigmoidanalytics.com`, whose password you don't have. Either approve mapping `gayatri.salunke@Sigmoidanalytics.com` as User in Azure SQL (one membership row plus an audit event, through a short firewall window), or obtain demo-user's password.

## 4. Known limits (not blockers)

- Local workspace has 5 active policies (owner kept the 12 Nov deletions), so Human Review can't be shown on 5176. Azure SQL has all 8 active.
- Point-in-time restore has never been rehearsed (7-day retention available).
- Local-only items: localhost redirect URI on the app registration, client secret in local `.env`, local dev CA (expires 13 Dec 2026).
- The preserved-demo backend on 8011 runs older code on revision 009. Restarting it with current code would break sign-in.
- Three stale temporary operator firewall rules remain on the SQL server.
