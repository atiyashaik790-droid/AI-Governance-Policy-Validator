# Azure SQL temporary firewall rule — approval request (13 November 2026)

**Status: EXECUTED 13 Nov 2026 (approved: probe only).** Rule added 08:18:17Z and removed 08:18:39Z (22 s). Remaining rules identical to the snapshot. Probe: CONNECTED; database `sqldb-gpv-demo-v008-20261108`; Alembic **008**; no 010 `actor_role` column; no 011 chat tables; 8 policies; 2 SSO memberships. No writes or migrations.

## Why

The single approved read-only probe on 13 Nov failed with `DatabaseConnectionError`. All local prerequisites passed: ODBC Driver 18, pyodbc 5.3.0, and an Entra SQL access token from the repo's Azure CLI profile (`AZURE_CONFIG_DIR=.azure-sql-cli`, `atiya.tabsum@Sigmoidanalytics.com`, tenant `4ac50105-…`). A read-only firewall listing shows that this machine's current public IP, **14.97.164.46**, is not allowed. The 8 Nov temporary rule for the previous IP (45.127.46.209) was removed as planned.

## Target (verified read-only, 13 Nov)

| Item | Value |
|------|-------|
| Subscription | `Devops_Azure_SV` / `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6` |
| Resource group | `rg_techdemo_Atiya_Tabsum_Shaik` |
| Server | `sql-governance-validator-dev-atiya` (state Ready, public network access Enabled) |
| Database | `sqldb-gpv-demo-v008-20261108` |

## Proposed change (smallest possible)

One single-IP rule, live for at most 15 minutes, removed immediately after the probe. This follows the 8 Nov procedure (`docs/TEMPORARY_SQL_FIREWALL_VERIFICATION_RESULT.md`).

| Field | Value |
|-------|-------|
| Rule name | `gpv-operator-20261113-readonly` |
| Start IP / End IP | `14.97.164.46` / `14.97.164.46` |
| Lifetime | ≤ 15 minutes |
| Broad "Allow Azure services" | Not changed |
| Other rules | Not touched |

## Exact steps after approval

```bash
export AZURE_CONFIG_DIR="$PWD/.azure-sql-cli"
SUB=25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 RG=rg_techdemo_Atiya_Tabsum_Shaik SRV=sql-governance-validator-dev-atiya

# 1. Snapshot the current rules (compared again at the end)
az sql server firewall-rule list --subscription $SUB -g $RG -s $SRV -o json > private/firewall-before-20261113.json

# 2. Add the temporary rule
az sql server firewall-rule create --subscription $SUB -g $RG -s $SRV -n gpv-operator-20261113-readonly \
  --start-ip-address 14.97.164.46 --end-ip-address 14.97.164.46

# 3. One read-only probe (SELECT 1, DB_NAME(), alembic_version, 010/011 objects, policy and SSO counts)
.venv/bin/python -I scripts/probe_azure_sql_revision.py

# 4. Remove the rule immediately, whatever the probe result
az sql server firewall-rule delete --subscription $SUB -g $RG -s $SRV -n gpv-operator-20261113-readonly

# 5. Verify the rule is gone and all other rules match the snapshot
az sql server firewall-rule list --subscription $SUB -g $RG -s $SRV -o json > private/firewall-after-20261113.json
```

If step 3 fails, I stop, remove the rule (step 4), and report. No retries.

## Expected outcome

The probe reports the actual Alembic revision. It was last recorded as **008**, with 8 policies, 8 published versions and 8 active pins (9 Nov). Current code needs **010** for audit writes and **011** for chat history. Running the 008→011 migration is a **separate approval**. If you want the migration to follow immediately, the rule could stay up for that step instead of being added twice; that also needs explicit approval.

## Observations (no action taken)

Three earlier temporary single-IP operator rules are still present: `ClientIp-2026-10-28_20-51-52` (180.151.36.234), `local-laptop-temp-20261031-101-0-62-145` (101.0.62.145) and `gpv-verifier-single-ip-20261107` (101.0.62.127). The 13 App Service outbound rules (`gv-appservice-1` … `-13`) are expected. Removing the stale operator rules would be a separate approval.
