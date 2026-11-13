# Persistent Azure SQL database creation — PASS

8 November 2026. Scope: the owner's explicit creation-only approval. No schema initialization, SQL connections, permissions/firewall changes, Web App changes, deployment, providers or deletion.

| Item | Verified result |
|---|---|
| Subscription | Devops_Azure_SV / `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6` |
| Resource group | `rg_techdemo_Atiya_Tabsum_Shaik` |
| Existing server | `sql-governance-validator-dev-atiya.database.windows.net` |
| New persistent database | `sqldb-gpv-demo-v008-20261108` |
| Region | westus2 |
| Actual service objective / SKU | Standard **S0, 10 DTU** |
| Actual current/requested backup redundancy | **Local / Local** |
| Actual short-term backup retention | **7 days**, differential interval 24 hours |
| Final state | **Online** |
| Azure creation timestamp | **2026-11-08 16:03:25.447 UTC** |
| Database resource UUID | `80dd1ba9-74e5-4d26-8463-081572c9c22e` |

Preflight confirmed the exact account/subscription/server and target absence through both resource GET (404) and inventory. Absence was rechecked immediately before the sole creation PUT. Request used `createMode=Default`, without sample/source/copy/restore settings, and specified S0/10 DTU and Local backups. Azure returned HTTP202, request ID `244d2e7a-4c5c-4874-9ce1-e3e505e9aefb`; creation was never retried. Read-only reconciliation confirmed Online and exact configuration. Seven-day retention was already correct; no retention-policy update was necessary. Inventory gained exactly the one approved database.

No SQL connection was made. The database is newly initialized by Azure's default empty-database creation; no application migrations, tables, sample records or seeds were created by this operation. A data-plane catalog inspection is not claimed. Backup configuration is verified; actual backup recovery is not proved.

Source database `sqldb-governance-validator-dev` retained its same UUID, creation date, SKU, Online state, backup settings and recorded configuration. No source mutations occurred. App Service identity/state and web-configuration hash matched before/after; no App Service or environment-setting write was performed. Final `/health` and `/ready` returned200 and confirmed original release **1.2-ca5df7c1dc19e525**, source revision **005**. No secrets were recorded. Existing test, encryption and qualification evidence remains preserved.

## Owner review

Review due **15 November 2026 at 21:33:25 IST** (16:03:25 UTC), seven days after Azure's reported creation timestamp. [Importable calendar entry with a 15-minute reminder](evidence/fresh-database-creation-2026-11-08/owner-review.ics).

**No connected calendar scheduler is available.** The dated calendar entry is prepared locally; import it into the owner's calendar to activate the reminder. No delivered/installed notification is claimed. Review cost, intended cutover and retention; the database remains persistent and billed until a separately approved change. No deletion was scheduled. Estimated capacity charge remains approximately USD0.484/day, subject to actual billing; this operation did not query an invoice.

## Next approval scope — not authorized or executed

Approve **schema initialization and initial Azure SQL schema qualification on `sqldb-gpv-demo-v008-20261108` only**, using the existing authorized operator, frozen migrations **001→008**, and SELECT-only verification of Alembic head, required tables, indexes, constraints and immutability triggers.

Operator SQL access is not established by database creation. The previous single-IP firewall allowance was removed. If access is still blocked, the next approval must also explicitly cover a **maximum15-minute, one-IP firewall window**, with the exact current client IP verified and pinned before any change; do not reuse an old access approval. A proposed distinct rule is `gpv-fresh-init-20261108`; preserve every existing rule, allow one identical start/end IP only, and verify removal after the window. No broad Azure-access rule, SQL permission change or identity grant is included. Stop if existing operator privileges are insufficient. The final exact access window/IP must be validated before execution; today's approval authorizes none of these actions.

Do not reset/drop/recreate the new database, inject migration failures, create a recovery clone, perform PITR, seed users/policies, provision runtime grants, alter the source, change the site or deploy under that schema-only scope. If initialization fails, retain the database/evidence and stop rather than trying an unapproved destructive recovery. Successful initialization/catalog checks will be initial SQL Server qualification, not completion of controlled failure, runtime-identity, PITR or hosted acceptance gates. Those remaining gates still prevent production cutover.

[Sanitized operation journal](evidence/fresh-database-creation-2026-11-08/result.json). The exact executed controller is archived beside it; its write allowlist contains only the approved new database and its retention child. Work stopped after creation and verification.
