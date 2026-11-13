# New database runtime/Admin/User bootstrap — PASS

**9 November 2026, 01:32:23–01:33:40 IST.** Approved firewall rule was created and removed with verified access duration **71.920seconds**, within15minutes. Stopped after bootstrap, read-only verification and cleanup.

| Requested result | Status |
|---|---|
| Bootstrap | **PASS** — one transaction committed on new008 database only |
| Runtime SQL grants | **PASS** — exact catalog and effective SQL permissions verified |
| Admin membership | **PASS** — approved existing subject bound asAdmin |
| Standard User membership | **PASS** — selected distinct subject bound asUser |
| Tenant isolation | **PASS for tenant bindings, negative lookup and backend role guard checks**; actual hosted acceptance not performed |
| Firewall cleanup | **PASS** — exact temporary rule absent; all original rules unchanged |
| Existing production unchanged | **YES** — old005 website/database healthy and unchanged |

## Conditions checked before SQL mutation

Target: subscription `Devops_Azure_SV` / `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, server `sql-governance-validator-dev-atiya`, database **sqldb-gpv-demo-v008-20261108**, UUID `80dd1ba9-74e5-4d26-8463-081572c9c22e`, actual revision **008**. Existing operator database CONTROL confirmed; application tables empty; unexpected existing runtime principal/role rejected. No migration replay.

Reviewed SQL/permit-list/membership manifest checksums matched. Actual permit list had exactly59DML rights over23objects and23object metadata rights, plus CONNECT and the required two execution-mutation denials. Directory read-back confirmed enabled Member identities for Admin **b5d8bfbe-f03a-4132-a13f-ab49aae834b7** and selected User **f4799f3f-703a-42b7-acf7-4cbbf55e7320**, with selected User UPN **demo-user@Sigmoidanalytics.com**. Current Graph confirmed existing MI principal **600447fe-5fea-4801-9033-ab4aafc474cc** / client ID **f7bacace-698a-4968-8add-cba221319a17**. No identity/account/directory role was created or modified.

Azure effective management permissions confirmed firewall read/write/delete before creating the rule. An initial connect-only ODBC observation was insufficient to prove access: a separate SELECT-only reconciliation confirmed actual Azure SQL error40615 for approved **45.127.46.209**. That initial observation and reconciliation are preserved, not silently discarded. No mutation occurred during this diagnosis. Only after exact IP/rule/hash/identity/cleanup checks matched was the bounded window started.

## Applied and verified

- New contained external user **app-governance-validator-atiya-1026**, typeE, SID matching verified MI client ID; custom role **governance_validator_web_runtime**, no broad fixed-role membership.
- **85 explicit permission records**:59objectDML +23objectVIEWDEFINITION +1userCONNECT +2DENYs for UPDATE/DELETE on validation_executions. Exact post-write catalog matched the approved set; there were no extra grants. No schema-wide DML/DDL, sequence permission or membership-provisioning write given to runtime.
- Dedicated SQL context switched to this runtime user and ran the real revision-aware schema verifier **including runtime-permission checks**, with guaranteed REVERT. Full schema008/SSO contract passed. Runtime CONTROL, ALTER, ALTER ANY USER, ALTER ANY ROLE and CREATE TABLE each returned0. This proves effective database rights under SQL impersonation; it does **not** prove a hosted managed-identity token login or real User SSO.
- Permissions and two membership/audit records were committed in **one outer operator transaction**. The reviewed permission SQL guards/declarations/operation order were retained; its internal transaction wrapper was replaced by the enclosing SQLAlchemy transaction so membership insertion was atomic with grants. Existing review-only files were not executed blindly or edited to remove target safeguards. No retry/replay of bootstrap writes.
- Exact committed memberships below were read back on a new connection, and repeating the helper in-transaction added no duplicate membership or audit events. Exactly **two memberships and two normal provisioning audit records** exist; **zero policy records** remain. No policy seed, execution, review content or session record was created.

| Directory/object binding | Actor | Role | Application tenant |
|---|---|---|---|
| b5d8bfbe-f03a-4132-a13f-ab49aae834b7 | atiya-tabsum-shaik | **Admin** | demo-appservice-4e2dcce8d618 |
| f4799f3f-703a-42b7-acf7-4cbbf55e7320 | gpv-demo-user | **User** | demo-appservice-4e2dcce8d618 |

Directory for both: **4ac50105-0c66-404e-a107-7cbd8a9a6442**; both mappingsenabled=true. No record for the unselected `demo@...` candidate was inserted.

Tenant verification checked exact server-side directory/object/actor/tenant/role bindings, absence of either approved subject in a foreign tenant lookup, User denial with403 for Admin policy/audit/review API paths, and allowance of the governed-request route. The shared runtime DB identity is **not** tenant-specific SQL row-level security; application tenant enforcement remains the boundary. Existing local cross-tenant/session/UI-routing evidence was reused. No real browser sign-in, hosted route acceptance or live provider request was performed.

## Cleanup and production preservation

Rule **gpv-runtime-init-20261109**, start=end **45.127.46.209**, was the only firewall mutation. Exact-rule removal occurred immediately after SQL verification; inventory matched the original snapshot, rule absent. Cleanup bypasses the new-operation deadline. No independently verified supervisor exists; automatic expiry after host/process loss is not guaranteed, but this run's removal was actually verified within71.920seconds.

Old production database **sqldb-governance-validator-dev** remains005. SELECT-only before/after comparison confirmed its **51 runtime permission records** and existing Admin membership unchanged, matching the previous saved grant baseline. No source writes occurred. ARM source metadata, backup configuration and App Service configuration matched before/after. Final `/health` and `/ready` returned200, original release **1.2-ca5df7c1dc19e525**, revision **005**.

No application deployment/settings, encryption-key change, new Azure resource, policy seed, real OpenAI/Moderation call or ADLS export. Existing artifacts and prior evidence preserved. New memberships are in the new008 database; the current website still uses old005 and does not yet consume them.

## Exact next approval

Approve **only eight-policy publication/activation on the new008 database in tenant demo-appservice-4e2dcce8d618**, using the complete documents in [demo-policy-seed.REVIEW_ONLY.json](../deployment/demo-policy-seed.REVIEW_ONLY.json), with one fresh bounded single-IP SQL window. See [exact policy-seed approval scope](POLICY_SEED_APPROVAL.md). No memberships/grants/migrations need replaying.

**Deployment is not included and remains NO-GO** until the outstanding mandatory recovery/failure and configuration concurrency/recovery gates are satisfied. Then a separate exact cutover approval must pin candidate **1.2-240cc70e239a595f**, original005 rollback artifact/connection, approved setting changes and bounded acceptance. Real providers, review plaintext access and ADLS still require explicit bounded authorization.

[Sanitized summary](evidence/runtime-user-bootstrap-2026-11-09/summary.json) · [SQL verification](evidence/runtime-user-bootstrap-2026-11-09/sql-result.json) · [Window/cleanup journal](evidence/runtime-user-bootstrap-2026-11-09/result.json). Original/final firewall inventories, approved proposal snapshot and executed controllers are preserved alongside them.
