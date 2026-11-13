# Azure SQL 008 → 011 migration plan (approval request, 13 November 2026)

**Status: EXECUTED 13 Nov 2026 (approved). Azure SQL is now at revision 011.**

| Step | Result |
|------|--------|
| Restore point (UTC) | 2026-11-13T08:22:48Z (`private/migration-011-restore-point.txt`) |
| Firewall window | `gpv-operator-20261113-migrate011` for 14.97.164.46, 08:22:51Z → 08:24:12Z (81 s); the other 16 rules are byte-identical to the snapshot afterwards |
| Preflight | ready: revision 008, runtime role present, no new objects, 1 embedded custom category, 0 conflicts |
| Upgrade | One `alembic upgrade 011` invocation, exit 0, no retries |
| Grants | 16 expected permission rows read back for `governance_validator_web_runtime` |
| Post-check | Revision **011**; `actor_role` present; `title` nvarchar(120), `content` nvarchar(max); 9 governance categories (8 built-in + 1 custom), 1 policy-category link; all 10 counted tables identical to the preflight (8 policies, 8 versions, 8 assignments, 10 assignment events, 43 audit events, 2 SSO memberships) |
| Not done | No App Service change, deployment, seeding, or new database |

Evidence files: `private/migration-011-*.json/.log` and `private/firewall-*-migration-011.json` (private, not committed).

## Target and current state (verified 13 Nov, read-only)

| Item | Value |
|------|-------|
| Subscription / RG | `Devops_Azure_SV` (`25ddf5d2-…`) / `rg_techdemo_Atiya_Tabsum_Shaik` |
| Server / database | `sql-governance-validator-dev-atiya` / `sqldb-gpv-demo-v008-20261108` (Standard, Online) |
| Alembic revision | **008** (probe 08:18Z) |
| Data | 8 policies, 2 SSO memberships |
| Point-in-time restore | Available. 7-day retention, earliest restore point 2026-11-08 16:54Z, local backup redundancy |
| Operator identity | `atiya.tabsum@Sigmoidanalytics.com` via `AZURE_CONFIG_DIR=.azure-sql-cli` (Entra token; the same operator that ran 001→008 on 8 Nov) |
| Runtime role | `governance_validator_web_runtime` (existence re-checked in preflight) |

## What changes (additive only)

| Rev | Change | Data touched |
|-----|--------|--------------|
| 009 | Creates `governance_categories`, `policy_categories`; inserts 8 built-in categories; moves any `custom_categories` embedded in non-deleted policy drafts into the new tables (updates those drafts' `revision` and `row_version`) | Policy drafts only if they contain custom categories. The preflight counts these and predicts the migration's conflict guard |
| 010 | `ALTER TABLE audit_events ADD actor_role VARCHAR(30) NULL` | None; existing rows stay NULL ("unattributed") |
| 011 | Creates `chat_conversations`, `chat_messages` and 3 indexes | None |

Exact DDL for 010–011, rendered offline: `alembic upgrade 009:011 --sql`. The 009 data step can't be rendered offline; the preflight mirrors its logic read-only.

**Change made while preparing this plan:** migration 011 and `backend/app/chat_models.py` now pin SQL Server types: `title NVARCHAR(120)` and `content NVARCHAR(max)`. Before, they rendered as `VARCHAR(120)` (non-Latin chat titles would become `?`) and, offline, the deprecated `NTEXT`. SQLite is unaffected. Tests: `test_user_portal`, `test_mssql_schema_reflection`, `test_audit_actor_role` — 74 passed.

**Compatibility:** all three revisions are additive. Any older application release using this database keeps working, because new tables and the nullable column are ignored. Current code needs 010 or later for audit writes (see PROGRESS item 11), so this migration must come before any deployment of the current release.

## Failure behaviour

`backend/migrations/env.py` runs the whole upgrade in **one transaction**, and SQL Server DDL is transactional. If any step fails, including 009's conflict guard, the entire upgrade rolls back and the database stays at 008. No partial state is possible.

## Procedure (one firewall window, ≤ 20 minutes)

```bash
cd "/home/sigmoid/AI governance policy validator"
export AZURE_CONFIG_DIR="$PWD/.azure-sql-cli"
SUB=25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 RG=rg_techdemo_Atiya_Tabsum_Shaik SRV=sql-governance-validator-dev-atiya
IP=$(curl -s https://api.ipify.org)   # must equal the approved IP, else stop

# 0. Record the restore point (UTC) and snapshot the firewall
date -u +%FT%TZ > private/migration-011-restore-point.txt
az sql server firewall-rule list --subscription $SUB -g $RG -s $SRV -o json > private/firewall-before-migration-011.json

# 1. Temporary single-IP rule
az sql server firewall-rule create --subscription $SUB -g $RG -s $SRV -n gpv-operator-20261113-migrate011 \
  --start-ip-address $IP --end-ip-address $IP

# 2. Read-only preflight; the migration runs only if it exits 0 ("ready": true)
.venv/bin/python -I scripts/azure_sql_011_preflight.py | tee private/migration-011-preflight.json

# 3. One Alembic upgrade invocation, no retries
cd backend && DATABASE_URL="mssql+pyodbc://@sql-governance-validator-dev-atiya.database.windows.net/sqldb-gpv-demo-v008-20261108?driver=ODBC+Driver+18+for+SQL+Server" \
  ../.venv/bin/alembic upgrade 011; cd ..

# 4. Runtime grants: deployment/migration-008-011-runtime-grants.REVIEW_ONLY.sql, executed as one batch
#    through the same Entra-token engine (sqlcmd is not installed); the file aborts unless the revision is 011.

# 5. Post-check (read-only): revision 011, actor_role column and chat tables present, row counts equal to preflight
.venv/bin/python -I scripts/probe_azure_sql_revision.py | tee private/migration-011-postcheck.json

# 6. Remove the rule (always, even after a failure) and verify the other rules are unchanged
az sql server firewall-rule delete --subscription $SUB -g $RG -s $SRV -n gpv-operator-20261113-migrate011
az sql server firewall-rule list --subscription $SUB -g $RG -s $SRV -o json > private/firewall-after-migration-011.json
```

Stop conditions (remove the rule, then report): IP mismatch; preflight `ready` false (wrong revision, missing runtime role, objects already present, or predicted category conflict); any Alembic error; grant script error; post-check counts differ.

## Rollback

| Situation | Action | Approval |
|-----------|--------|----------|
| Upgrade fails | Automatic: the single transaction rolls back and the database stays at 008. Verify with the probe | Covered by this approval |
| Upgrade succeeds but 011 or 010 must be undone | `alembic downgrade 010` drops the chat tables; `alembic downgrade 009` drops `actor_role` | Separate approval |
| 009 must be undone | Its downgrade is intentionally disabled. Use point-in-time restore to the recorded restore point; this **creates a new database** | Separate approval |

## Not included

No App Service setting change, no deployment, no data seeding, no policy changes, no new databases, no other firewall rules touched. The three stale operator firewall rules (28 Oct, 31 Oct, 7 Nov) are left as they are.

## Verification after approval-gated deployment (later)

Once a release is deployed against this database: the hosted `/ready` check reports schema 011; a User chat turn is stored; an Admin audit event has `actor_role` set.
