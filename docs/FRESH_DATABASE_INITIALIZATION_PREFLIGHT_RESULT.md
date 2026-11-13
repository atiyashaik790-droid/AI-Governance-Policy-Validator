# Fresh database initialization — BLOCKED at firewall approval

8 November 2026, 18:23–18:24 UTC. No Azure mutation or migration was executed.

- Exact subscription Devops_Azure_SV (`25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`), server `sql-governance-validator-dev-atiya`, and new database `sqldb-gpv-demo-v008-20261108` verified. Database UUID `80dd1ba9-74e5-4d26-8463-081572c9c22e` matches creation evidence; Online, Standard S0/10 DTU.
- All eight migration SHA256 hashes match the reviewed `qualification-pins.json`; AST inspection confirms one linear chain 001→008 with no missing/extra migration. Frozen files unchanged. Previously passed local SQL compilation/SQLite evidence remains preserved; actual SQL Server migration execution is not claimed.
- SQL token acquisition and approved directory/operator identity binding passed. A single new-target SQL connection attempt failed before any SELECT could execute: SQLSTATE42000, native Azure SQL error **40615**, blocked client **45.127.46.209**. No raw connection error or token was stored.
- Consequently, database emptiness, effective migration privileges, engine compatibility, current Alembic revision and schema qualification are **NOT VERIFIED**, not PASS. No migration, schema/table/data write, user creation or grant occurred. Do not infer an applied revision from the database name.
- Existing production source metadata and App Service configuration match their creation-time baseline and remained unchanged during preflight. Final `/health` and `/ready`:200/ok/ready, hosted release `1.2-ca5df7c1dc19e525`, source revision005. Every original firewall rule remained unchanged. No provider call, deployment, restart or WebJobs operation.

## Separate approval required now

The user explicitly required a separate request before any necessary firewall modification. Proposed scope:

| Field | Exact request |
|---|---|
| Subscription / resource group | `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6` / `rg_techdemo_Atiya_Tabsum_Shaik` |
| Existing SQL server | `sql-governance-validator-dev-atiya` |
| New temporary firewall rule | `gpv-fresh-init-20261108` (confirmed absent) |
| Start / end IP | **45.127.46.209 / 45.127.46.209** only |
| Expected access duration | 5–10 minutes; maximum approved window **15 minutes** |
| SQL scope | Existing migration authorization only: verify empty exact new DB, verify permissions/compatibility, apply frozen001–008 once, SELECT-only catalog qualification |
| No additional scope | No source SQL queries/mutations, users, memberships, runtime grants, site changes, seeds, deployment, providers, new databases or broad Azure-access rule |

Before adding the rule: freshly validate exact target, database UUID, current Azure-reported blocked client IP and original firewall inventory; abort on mismatch or if this rule already exists. Start a fixed wall-clock and monotonic budget. Reserve cleanup time and stop new SQL operations before the end of the window. No new operation after deadline. Unexpected migration failure stops execution; inspect partial state read-only rather than retrying or resetting.

Cleanup: remove **only this newly added rule** immediately after success/failure, and attempt removal even if the deadline has expired. Cleanup restores the operation's change and must not be rejected merely because authorization for new work has expired. Verify target rule absence and compare every original rule to the saved baseline; do not modify unrelated rules to conceal concurrent drift. Confirm final hosted health/readiness. Any unverified removal is BLOCKED.

Emergency owner cleanup command below is **review-only**, not executed or currently authorized. It is limited to the proposed rule:

```bash
az sql server firewall-rule delete --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 --resource-group rg_techdemo_Atiya_Tabsum_Shaik --server sql-governance-validator-dev-atiya --name gpv-fresh-init-20261108
```

Local cleanup code cannot guarantee removal if its process/host is lost; no independently verified supervisor has appeared. A named available owner must retain the exact cleanup command/inventory and confirm removal if execution is interrupted. No claim of unattended expiry enforcement is made. This is a temporary firewall rule for a persistent database, not permission to create a temporary database.

No further migration approval is needed within the already approved exact target/scope once the separate access approval is granted and all preconditions pass. If permissions are insufficient or target is nonempty, stop for a new decision. Tenant/real Entra memberships and reviewed runtime permissions remain a **later separate approval**, after successful schema verification; the User object ID and effective new-target grants must be pinned before that request. Production deployment, PITR, failure injection and recovery clone creation remain unauthorized.

[Sanitized preflight evidence](evidence/fresh-database-initialization-2026-11-08/preflight.json).
