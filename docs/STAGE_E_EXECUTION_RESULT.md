# Stage E execution result — 4 November 2026

**Stage E: PASS. Stopped after Stage E.**

- Operator SQL connection: PASS during the approved temporary firewall window.
- Admin membership: CREATED; enabled=true, exact approved identity/workspace/actor.
- Audit event: VERIFIED through a fresh independent SQL connection.
- Duplicate/conflicting membership check: PASS; exactly one matching membership.
- Temporary firewall rule: REMOVED AND VERIFIED; all 15 preexisting rules unchanged.
- SSO enabled: NO. Demo browser login enabled: YES.
- App Service: health/readiness/status checks PASS after firewall cleanup; database revision 005.

## Connectivity and firewall lifecycle

Public IPv4 `101.0.62.148` was reconfirmed immediately before applying the user's explicit approval. Only `stage-e-temp-20261104-101-0-62-148`, start=end=`101.0.62.148`, was created on `sql-governance-validator-dev-atiya`, resource group `rg_techdemo_Atiya_Tabsum_Shaik`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`.

This resolved SQL firewall error 40615. The operator connection used the existing Entra CLI token pinned to tenant `4ac50105-0c66-404e-a107-7cbd8a9a6442` and object `b5d8bfbe-f03a-4132-a13f-ab49aae834b7`. Fresh SQL reads verified database name, schema revision 005, workspace policy count 8 and required operator membership/audit permissions.

The temporary rule was deleted after fresh post-write verification. A server-rule inventory confirmed it absent and all 15 preexisting rules unchanged. Public network settings were not modified. Operator access was intentionally not retained through the temporary rule.

## Exactly scoped provisioning

Fresh pre-write reads found no matching membership or provisioning audit. The reviewed `apply_mapping` workflow was called unchanged inside a serializable transaction with locked conflict checks, target/revision/permission guards and count assertions. Only one membership and one audit were added. No existing membership was updated.

The live audit resource column is varchar(80). The previous long approval reference would generate an 85-character resource. The local wrapper used `stage-e-20261104-admin`, explicitly bound in its execution evidence to the user's exact Admin authorization, yielding a 65-character audit resource. No workflow/model/schema modification or migration was needed. The previous ProgrammingError's raw diagnostic was unavailable; the length mismatch is established, but its historical causality is not independently proven.

| Field | Persisted value |
|---|---|
| Directory tenant | `4ac50105-0c66-404e-a107-7cbd8a9a6442` |
| Entra object ID | `b5d8bfbe-f03a-4132-a13f-ab49aae834b7` |
| Workspace | `demo-appservice-4e2dcce8d618` |
| Actor | `atiya-tabsum-shaik` |
| Role / enabled | Admin / true |
| Membership ID | `cce108dc-72f1-4db2-9aaa-c7128085661c` |
| Audit ID | `5992685e-0f10-44c1-a98a-19e1e4d84137` |

A new SQL connection independently verified the exact six membership fields, one matching row across the identity/actor conflict search, and one corresponding `sso.membership.provisioned` audit with operator `Atiya Tabsum Shaik` and the exact membership/role/enabled/approval resource.

## Application and restrictions

After cleanup, GET /health, GET /ready and GET /api/sso/status all returned HTTP 200. The existing release remains ready on 005 with SSO unavailable, configured=false and demo_login_enabled=true. No new demo login/session writes were needed. Previously verified actual runtime membership INSERT/UPDATE/DELETE permissions remain documented at zero; no permissions changed in this workflow.

No Stage B/C/D suite rerun, unrelated SQL writes, grants, user creation, migration, App Service configuration changes, ENTRA_CLIENT_SECRET configuration, credential rotation, deployment, SSO activation or Stage F execution occurred.

## Evidence

[Final asserted result](evidence/stage-e-execution-2026-11-04/approved-final-result.json), [pre-write reads](evidence/stage-e-execution-2026-11-04/approved-prewrite-verification.json), [guarded transaction](evidence/stage-e-execution-2026-11-04/approved-guarded-provisioning.json), [fresh post-write reads](evidence/stage-e-execution-2026-11-04/approved-postwrite-verification.json), [firewall lifecycle and cleanup](evidence/stage-e-execution-2026-11-04/firewall-approved-execution.json), [post-cleanup App Service checks](evidence/stage-e-execution-2026-11-04/post-cleanup-app-check.json).
