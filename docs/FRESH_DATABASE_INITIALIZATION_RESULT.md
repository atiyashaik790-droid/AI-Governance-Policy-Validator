# Fresh Azure SQL initialization — PASS

**9 November 2026, 00:49:08–00:50:49 IST.** Approved single-IP rule was present for **94.938 seconds**, within the15-minute maximum. Work stopped after SQL/schema verification, firewall removal and production postchecks.

| Requested check | Result |
|---|---|
| Firewall creation | **PASS** — only `gpv-fresh-init-20261108`, start/end `45.127.46.209` |
| Azure SQL connectivity | **PASS** — exact new target and approved operator confirmed |
| Migration execution | **PASS** — frozen001→008, one Alembic upgrade invocation, no retries |
| Final new database revision | **008** |
| SQL Server schema qualification | **PASS** — schema-only under migration operator |
| Firewall cleanup | **PASS** — temporary rule absent; every original rule unchanged |
| Production website/database unchanged | **YES** — original release and revision005 healthy; source metadata and App Service configuration unchanged |

## Target and preconditions

Subscription `Devops_Azure_SV` / `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, resource group `rg_techdemo_Atiya_Tabsum_Shaik`, server `sql-governance-validator-dev-atiya`, database **`sqldb-gpv-demo-v008-20261108`**, UUID `80dd1ba9-74e5-4d26-8463-081572c9c22e`. Azure SQL engine edition5, compatibility level170, existing operator DATABASE CONTROL verified. All eight migration files matched the reviewed SHA256 pins before execution and again afterward. No user/application tables or user views/procedures/functions/triggers/sequences/synonyms existed initially; Alembic history was absent, as expected for an empty database.

The pinned database identity, approved IP and blocked-client error were freshly rechecked before creating the exact firewall rule. Every original firewall rule was saved. No production SQL connection or query was used; production verification used ARM metadata and the existing read-only health/readiness endpoints.

## Verified schema and limits

The existing revision-aware schema verifier checked required tables/column types, lengths/nullability, primary and unique keys, required indexes, tenant foreign keys, trusted/enabled constraints, required history triggers, MULTI evidence/assignment contracts and encrypted-content binary/retention/immutability contracts.

Inventory: **23 tables, 37 reflected non-PK indexes, 19 foreign keys, 16 CHECK constraints and seven triggers**. Required SSO membership/session/transaction, MULTI state/assignment/event/evidence, encrypted Human Review, audit, execution history and analytics storage objects are present. All22 application tables have **zero rows**; only `alembic_version` has its one revision008 row.

Qualification was intentionally **schema-only using the authorized migration operator**. The verifier's runtime-permission component was replaced for this invocation with an explicitly recorded operator-scope result; its structural checks ran unchanged. An administrative operator cannot prove the future application's least-privilege permissions. **Runtime identity/role/grant qualification remains NOT VERIFIED** and no runtime grants were changed. No user, membership, policy, session, execution, review or audit seed was inserted. API/UI behavior on the new database, actual Entra login, provider/storage operations, controlled failure cycles and PITR were not exercised; this is not production cutover approval or full end-to-end acceptance.

## Cleanup and production preservation

The exact temporary rule was deleted immediately after schema qualification. Read-back inventory confirmed absence and exact equality with the original firewall snapshot. Removal code was exempt from the new-operation deadline; it would still attempt restoration after expiry. No independent supervisor exists, so no automatic expiry guarantee after process/host failure is claimed. This execution's cleanup was actually confirmed in94.938seconds.

Postchecks: existing `/health`200/ok and `/ready`200/ready; release **1.2-ca5df7c1dc19e525**, existing database **005**. Source database metadata and backup settings and App Service configuration matched before/after. No source DDL/data/permission mutation, app/environment change, deployment, provider call, ADLS upload, database creation or deletion occurred. Encryption settings were neither read nor regenerated. Existing evidence and reviewed application artifacts remain preserved.

## Exact next approval

Approve a separately bounded SQL provisioning window for **this new008 database only** to:

1. Reconfirm the existing Web App managed identity, provision its contained user/custom role and grant only the object rights in `deployment/fresh-database-permissions.REVIEW_ONLY.json` / `deployment/fresh-database-runtime-grants.REVIEW_ONLY.sql`. Verify the contained SID independently; do not confuse the managed-identity object ID with its client ID, reuse an unverified SID or grant broad database roles.
2. Initialize the application tenant through the server-managed SSO membership mapping, using the existing reviewed Admin identity/tenant as an explicit new-target proposal. There is no separate tenant-registry table.
3. Add the standard **User** membership only after the owner designates its actual Entra account/object ID. The repository has no approved real User mapping; synthetic UUIDs are not an acceptable substitute. Provisioning both roles needs distinct verified object identities.
4. Read back exact memberships and runtime effective permissions and remove/verify any newly approved single-IP access rule. Today's rule is removed and today's window is closed; it is not reusable authorization for this work.

The [target-bound provisioning proposal](../deployment/fresh-runtime-and-memberships.REVIEW_ONLY.json) contains the exact existing Admin mapping and marks the User mapping unresolved. No policy/demo seed, application release/configuration change, production mutation, real provider call, export or deployment is included. Independent recovery/qualification gates are unchanged and not silently waived.

[Sanitized window journal](evidence/fresh-database-initialization-2026-11-09/result.json), [SQL/schema evidence](evidence/fresh-database-initialization-2026-11-09/sql-result.json), original/final firewall snapshots and unchanged migration hashes are preserved alongside them.
