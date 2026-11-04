# Bounded Azure SQL recovery drill — approval plan

31 October 2026, Asia/Kolkata. **PREPARED; NOT EXECUTED.** No application changes, migrations, provider calls or provisioning performed. Previously passing development suites were not repeated.

## Operator eligibility — verified

The user has volunteered as recovery operator, conditional on permissions. The current Azure CLI account is type user, in the expected subscription/tenant; Graph signed-in-user object ID matches the application's pinned SQL user. The server Entra administrator SID also matches this same identity. Exact identity equality was checked without printing tokens or account credentials. Evidence: preflight.json and extra-checks.json.

Effective management permissions were read from the existing server and source database scopes, rather than inferred solely from a role label. The permission sets allow all Microsoft.Sql actions needed here, including server/database read, databases/write for PITR destination creation, restorePoints/read, readBackups/action, and databases/delete for the exact temporary destination cleanup. Contributor is assigned at the approved resource group. No applicable notAction excludes these operations. Resource-group/server/source deny-assignment enumerations returned empty; resource-group lock enumeration returned empty. A same-server create inherits this resource-group assignment. No missing RBAC permission was identified and no role changes are proposed.

Actual SQL access with the token-bound identity was verified separately: source database is accessible, IS_MEMBER('db_owner')=1 and SELECT reads revision 003 and aggregate counts. The matching server Entra administrator is the planned way to access the restored database. Contributor alone would not establish SQL data-plane access; these are separate observations. Restored access itself cannot be proven before restore. Azure Policy, quota, transient capacity and request validation can still reject creation; stop and report rather than changing policy/permissions/tier silently.

## Exact bounded scope

- Subscription: `REPLACE_WITH_AZURE_SUBSCRIPTION_ID`.
- Resource group: `REPLACE_WITH_AZURE_RESOURCE_GROUP`.
- Existing server: `REPLACE_WITH_AZURE_SQL_SERVER`, West US 2.
- Original/source: `REPLACE_WITH_SOURCE_SQL_DATABASE` — preserve this database and application configuration.
- One temporary destination: **`REPLACE_WITH_RECOVERY_SQL_DATABASE`**. Fresh database inventory shows it does not exist. Recheck immediately before create and abort if it exists; never overwrite/reuse/delete an unrelated target.
- Exact destination ARM ID: `/subscriptions/REPLACE_WITH_AZURE_SUBSCRIPTION_ID/resourceGroups/REPLACE_WITH_AZURE_RESOURCE_GROUP/providers/Microsoft.Sql/servers/REPLACE_WITH_AZURE_SQL_SERVER/databases/REPLACE_WITH_RECOVERY_SQL_DATABASE`.
- Same source performance tier: Standard **S0**, 10 DTUs; standalone, Local backup redundancy, no zone redundancy or additional identity. Source max size is 250 GiB, matching S0 included database capacity. Actual source used space approximately 23.5 MiB, allocated 32 MiB. No automatic upsize or higher tier is authorized. Source is not Hyperscale and not in an elastic pool.
- One restore submission; no paid automatic retries, new server, storage account, Key Vault, infrastructure service, app switch, source overwrite, role grant, migration or live model call.

## Backup and restore-point evidence

Source is Online. Seven-day short-term retention, 24-hour differential interval, Local backup redundancy. REST restorePoints lists a CONTINUOUS restore point with earliestRestoreDate **2026-10-28T15:55:06Z**.

Proposed fixed drill point: **2026-10-31T17:28:47Z** (31 October 2026, 22:58:47 IST). This was chosen approximately 30 minutes before preflight to allow normal transaction-log backup lag and is later than the earliest restore date. It is a candidate in the published continuous window, not a claim that Azure has already accepted this exact second. The continuous point does not enumerate individual log-backup completion times. Definitive restore-point validity is established by successful restore; if Azure rejects this time, stop and report without submitting a second billed request.

Before execution reconfirm current identity, window, unchanged source name, absence of destination, eligible S0 and evidence scope. If approval arrives after this timestamp falls out of retention, stop for an updated reviewed point. No near-current pre-migration backup freshness is inferred from a successful older-point drill: recheck the source recovery window and record the pre-DDL timestamp before separately approved migration.

## Exact restore command — not executed

```bash
# REVIEW ONLY — run only after explicit bounded restore approval.
# Run from repository root. Existing authenticated organizational cache only.
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az sql db restore \
  --subscription REPLACE_WITH_AZURE_SUBSCRIPTION_ID \
  --resource-group REPLACE_WITH_AZURE_RESOURCE_GROUP \
  --server REPLACE_WITH_AZURE_SQL_SERVER \
  --name REPLACE_WITH_SOURCE_SQL_DATABASE \
  --dest-name REPLACE_WITH_RECOVERY_SQL_DATABASE \
  --time '2026-10-31T17:28:47Z' \
  --edition Standard --service-objective S0 \
  --backup-storage-redundancy Local \
  --zone-redundant false --no-wait --only-show-errors --output none
```

CLI help was checked locally. The initial restore-point CLI alias was unavailable; the supported ARM restorePoints GET returned the continuous window successfully. No restore command was run.

Poll only the exact destination's status and database operation result, using short read-only requests and regular user updates. Completion means Online and management operation Succeeded, not merely CLI request accepted. If the submit result is uncertain, inspect destination/operation state before any further action; never repeat the restore blindly.

## Cost and duration

The live Microsoft Retail Prices API returned West US 2 **SQL Database Single Standard / S0 DTUs: USD 0.4839 per day** (Consumption), approximately **USD 0.0201625/hour**. Expected 1–2 billed hours is about **USD 0.0202–0.0403** for the S0 compute meter; 24 hours would be USD 0.4839. This estimate excludes tax, negotiated pricing and any separately billed backup/storage/network consumption. No cross-region transfer is proposed. The API rate is evidence, not a guaranteed invoice or hard budget cap. [Pricing evidence](evidence/bounded-recovery-2026-10-31/extra-checks.json); [Microsoft Retail Prices API](https://prices.azure.com/api/retail/prices).

Proposed spending allowance: **USD 1 estimated total**, with **at most two hours after the destination becomes Online** before approved temporary-target cleanup. This is an operational allowance, not an enforced Azure budget. Monitor elapsed time; stop before adding any resource or raising tier. Azure restoration may continue for some time before Online; inspect progress at 30 and 60 minutes. If still restoring at 60 minutes, report the delay and use the approved cleanup scope to cancel/delete only this temporary target, then verify cancellation/deletion. If deletion fails, report immediately and keep monitoring; never claim charges stopped until deletion is verified.

Planning estimate for this small database: **10–30 minutes for restore plus 5–10 minutes for read-only checks**. This is an engineering estimate, not an Azure completion guarantee; actual restore can take longer. Microsoft states restore duration depends on size, activity and infrastructure load. Normal database charges begin after restore completion.

## Access and recovery success criteria

After Online, connect explicitly to the recovery database using the same approved token-bound Entra identity, existing network route and TLS-validating SQL adapter. Do not point FastAPI or the hosted UI at it, alter firewall rules, add users or run migrations.

1. `SELECT DB_NAME()` exactly equals the recovery destination; source connection separately equals the original.
2. Sole Alembic revision is **003**. Existing eight core application tables, index and constraint definitions match the expected 003 schema. No 004 tables are expected.
3. Record aggregate counts for policies, versions, active assignments, audits, executions, human review, feedback and exports. Latest source counts are 6 / 6 / 4 / 87 / 20 / 3 / 4 / 7 respectively. Because the selected restore timestamp precedes this count observation, do not assume equal counts prove exact historical recovery, or call a genuine post-point difference data loss.
4. Validate aggregate consistency: no orphan active-policy/version assignments; no orphan review→execution, feedback→execution or other declared FK relationships; published/active policy consistency; expected audit/export records present by nonsensitive metadata/counts. Use only allowlisted schema, identifiers, timestamps and aggregate checks; never export full row contents or raw prompts. A difference must be explained against the selected timestamp using safe metadata evidence before PASS; otherwise mark data verification inconclusive and stop before migration.
5. Confirm restored database users/roles and operator SELECT access. Do not use the admin connection as proof of application's managed-identity runtime access. Existing demo-account authentication comes from approved runtime configuration; restore drill does not itself test hosted login.
6. Re-read original revision/schema/counts and public health/readiness. No source mutation is intended; reconcile any concurrent legitimate activity without assuming exact equality. Record restore operation ID, chosen timestamp, observed completion time, target ID and sanitized evidence. No deliberate source modification or destructive rollback test.

Automatic approval review rejected an earlier proposed full-row hash scan due to potentially sensitive data access. It was replaced by aggregate counts and schema metadata, which succeeded. The source counts evidence was saved successfully; its console formatting then encountered a Decimal serialization error. That did not fail SQL verification or modify data. No full-row fingerprint scan is needed for this plan.

Recovery readiness passes only when management restore, operator SQL access, revision/schema, data/relationship checks, source preservation and saved evidence all pass. Backup metadata alone is insufficient. A successful drill demonstrates the ability to recover into an isolated database; production replacement/cutover and any acceptance of lost post-point writes remain separate approvals.

## Cleanup — included only if explicitly approved with the drill

After verification and evidence are saved, delete **only** the created recovery database; likewise clean up this exact target on failed/timed-out drill after capturing diagnostics. Check its full ARM ID matches the recorded newly created resource and differs from the source, verify the app was never pointed at it, then run:

```bash
# REVIEW ONLY — explicit approval must include cleanup of this exact temporary resource.
# Verify target ARM id equals recorded recovery target and differs from source id first.
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az sql db delete \
  --subscription REPLACE_WITH_AZURE_SUBSCRIPTION_ID \
  --resource-group REPLACE_WITH_AZURE_RESOURCE_GROUP \
  --server REPLACE_WITH_AZURE_SQL_SERVER \
  --name REPLACE_WITH_RECOVERY_SQL_DATABASE \
  --yes --only-show-errors --output none
```

Verify the destination is absent via successful database list/read and source remains Online at revision 003. Do not treat any generic CLI/network error as proof of deletion. Deleting the temporary target removes its isolated data copy; preserve sanitized evidence locally. Do not delete the original database, its backups, policies/audits/exports, or change backup retention/LTR settings. Azure-managed backup retention after deletion may have separate storage implications; do not claim deletion erases every retained backup. No application cutover or migration is bundled with cleanup.

## Approval requested

Approve **one same-server S0 PITR restore to this exact temporary name at the proposed point**, read-only verification under your verified identity as recovery operator, and **deletion of only that temporary database after evidence capture or at the stated timeout**, within the proposed USD 1 allowance and two-hour Online lifetime. If cleanup is not included in your approval, provisioning must wait for an agreed retention/cost owner. This is the narrowly scoped exception to the previous no-provisioning restriction; it is not approval for other infrastructure.

After successful recovery verification, request **separate migration 003→004 approval**, then separate runtime-grant and deployment approvals. Subsequent inference, moderation, ADLS writes and hosted policy/auth/audit mutations still require their explicit bounded scopes. They have not been approved by this planning request.

## Fast safe fallback if restore fails

Preserve the currently hosted release and SQL 003. Use existing public homepage/health/readiness/OpenAPI to show availability without logging in or changing data. For complete policy, PII, moderation, review and audit interaction, use the already verified disposable local fixture demonstration in FINAL_DEMO_RUNBOOK.md and label it as local/fixture. Do not represent fixture generation/moderation/ADLS failure handling as successful live integrations. Do not connect new reliability code to SQL 003.

## Sources

[Microsoft recovery behavior and permissions](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql); [Azure CLI restore command](https://learn.microsoft.com/en-us/cli/azure/sql/db?view=azure-cli-latest#az-sql-db-restore). These establish expected API behavior, not successful execution of this planned drill.
