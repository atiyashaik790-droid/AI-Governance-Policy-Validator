# Phase 6B — Azure SQL and recovery preflight (read-only)

**PARTIAL. GO to approval checkpoint A only; NO-GO to production deployment.** The plans below are proposals, not authorization. No database/resource was created, restored, migrated, deleted or reconfigured. No deployment, live provider call, production SSO login or production-key operation occurred. Existing source/artifacts and working-tree changes were preserved.

## 1. Current state — refreshed evidence

| Check | Observed result |
|---|---|
| Public hosted readiness | VERIFIED: HTTP 200; release **1.2-ca5df7c1dc19e525**, schema005/versioned, SSO available |
| SQL revision/schema | VERIFIED independently by SELECT-only CLI verifier: **005**, current005 schema and required permissions PASS under executing CLI identity |
| SQL target | Existing `sql-governance-validator-dev-atiya` / `sqldb-governance-validator-dev`; Online, westus2, standalone Standard **S0 / 10 DTUs**, 250 GiB maximum, Local backup redundancy |
| Collation | VERIFIED: `SQL_Latin1_General_CP1_CI_AS` |
| Backup policy | VERIFIED: retention **7 days**, differential interval 24 hours |
| Earliest restore point metadata | VERIFIED reported value: **2026-10-30 08:41:52.774878 UTC**; the latest usable point and successful restore are not established |
| Current runtime SQL access | Existing contained Web App user has one matching custom-role membership; 49 direct object grants recorded, including current SSO DML/metadata grants. New006/007 tables absent |
| Operator SQL permissions | VERIFIED metadata includes CONTROL, CREATE TABLE, ALTER, REFERENCES, SELECT/INSERT/UPDATE and VIEW DEFINITION on the current database. This does not authorize using those rights or establish access to a not-yet-created database |
| Preflight counts | RESERVED requests 0; pending reviews 0; invalid legacy execution identities 0; version/assignment tenant mismatches 0. Snapshot only; recheck before future mutation |
| Current settings | SSO=true; demo=false; legacy API credentials=false; explicit session override **60 minutes**. Capture/cleanup flags unset. Production key absence was observed in Phase6; no production key material was read/generated here |
| Existing databases | Only production database and `master` returned. Proposed A/B names absent at inspection |
| Resource locks / deny assignments | Resource-group queries returned none. Parent-level restrictions, conditional policies, quotas and operation-time decisions still require pre-execution review |

Targets: subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, group `rg_techdemo_Atiya_Tabsum_Shaik`. No account login, identity switch or new identity is proposed. The current identity's read access was used only for projected metadata and SELECTs. Current SQL permissions are not proof of new-runtime effective access; test that separately.

**Restore authority:** server/group ARM permission metadata allow database read/write/delete, restore-point read and short-term-retention read; no matching exclusions were found. Thus there is **no identified missing control-plane permission** requiring a new role assignment. Actual create/restore/delete authority is not exercised and may still be limited by policy/quota or inherited restrictions. Recovery readiness is **PENDING approval/drill**, not a verified restore. If rights are absent on recheck, stop: the needed control-plane capability is source/server read plus destination database `Microsoft.Sql/servers/databases/write`, database/operation metadata read, and destination `.../delete` for cleanup. Do not request Owner or alter runtime permissions to solve operator recovery. Microsoft documents Contributor/SQL Server Contributor at the relevant scope as supported restore roles; SQL data-plane CONTROL alone does not confer ARM restore authority. [Microsoft recovery permissions](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql).

Evidence: `azure-current.json`, `database-shape.json`, `sql-readonly.json`, `sql-detail.json` under the Phase6B evidence directory. Historical frozen004 readiness automation is not a valid current005/007 production gate and was not run.

## 2. Artifacts, dependencies and fallback assessment

Both Phase6A ZIPs were rehashed/CRC-checked: candidate and fallback are **1.2-7d572934f2b78aeb**, SHA-256 `a0a53d4899bd5672043420550fdbe01c7beca2a409b710fe180f8f52d516eb28`; they are identical. Local tests remain the Phase6A evidence (1,167 consolidated backend,77 script,131 frontend); they were not rerun or treated as Azure tests.

The preserved currently hosted artifact is `artifacts/structural-only-candidate-2026-11-05/production/governance-structural-only.zip`, SHA-256 `6a6a265bc2d27f9965a1a3abb33eaf61a4bd433a1257b241c183a871c12a57db`, supporting004/005 only. Local ZIP inventory found no independently qualified007-capable older backend. Current007 implementation files are untracked in the existing working tree; no introducing/known-good007 commit is available from their Git history. Rebuilding or renaming the same source is **not fallback independence**.

No safe independent007 fallback can currently be asserted. A separate local qualification task would need a distinct preserved source state/provenance, compatibility/security review and the same007 retained-ciphertext/audit/grant/session tests. Do not port pre006 code or disable security checks to manufacture compatibility. Safe alternative: keep production at005 until recovery is qualified; retain the tested compatible copy for file/configuration recovery, and explicitly approve a forward-fix/PITR strategy with known data-loss/session/key limitations. The same-code fallback cannot repair a shared defect. This limitation must be accepted or resolved before production migration.

Migration hashes (unchanged):

- 005: `325a1fc4e0f7f415d102d340e2b737e1734ecdb119c76f78e61a1e4a4658618a`
- 006: `e9627d8f1b4c1f6385e1573df9bbd9280beef4f7d93bb2b1c3f6ef8a9fbfe9dc`
- 007: `f451e1e83c735b333d5c10b012772cbfa1bf3fd9efe59c1dfbc8c8e2f9f7a8ce`

Dependencies: current pinned backend/Alembic/SQLAlchemy/pyodbc/cryptography environment, ODBC18, existing authorized Entra CLI identity, TLS access to the existing server, complete operator migration chain001–007, `migrations/env.py`, and its current revision-specific models/verifier imports. The application ZIP intentionally excludes migrations; provide separately hash-reviewed operator sources. Empty A must be initialized through005; production already005 must never rerun005. No startup migration or Alembic stamping. Record all operator-source dependency hashes immediately before execution.

## 3. Checkpoint A — synthetic SQL Server rehearsal

**Plan prepared; execution PENDING A approval and a target-locked SQL Server harness.** Existing Phase6A rehearsal utilities hard-code SQLite; do not point them at Azure and claim SQL Server coverage. Under approval A, first adapt a local disposable-target harness, review its diff/deny guards and run dry tests before any database creation. No production application code or security architecture changes are included.

Exact proposed resource:

- Name `sqldb-gpv-mig-20261106-a1`, same subscription/group/server, westus2.
- S0 / 10 DTUs,250 GiB maximum, source-matching collation, Local backup redundancy; no elastic pool, server, firewall, networking, Entra, hosting or Azure-role changes.
- At most **two incarnations** of that exact name for success and deliberate-failure cycles; total wall-clock window **four hours**. If the name exists, stop rather than adopt it. Record owner/purpose/expiry tags and creation resource ID.
- Data: synthetic policies/executions/reviews/audits/sessions only, with synthetic ephemeral test keys and mocked OIDC/providers. No copy/restore of production data in A.
- Temporary SQL contained mappings/custom role may reference the **existing** authorized operator/runtime identity, only inside A. No new Entra identity. Production users/grants remain unchanged.

Future create command (NOT EXECUTED; only after A, name/identity/quota checks and harness review):

```bash
az sql db create --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 \
  --resource-group rg_techdemo_Atiya_Tabsum_Shaik \
  --server sql-governance-validator-dev-atiya \
  --name sqldb-gpv-mig-20261106-a1 --service-objective S0 \
  --max-size 250GB --collation SQL_Latin1_General_CP1_CI_AS \
  --backup-storage-redundancy Local
```

A execution sequence:

1. Reconfirm caller, exact source/destination identities, absence of A, S0 availability/quota, cost and restrictions. Harness refuses production name/ID and `master`, requires exact A name plus approval token, and tests `DB_NAME()` on every new connection. No credentials/connection strings in evidence. Reject a changed artifact or migration hash.
2. Create only A. Use current operator for DDL; confirm dbo default schema. Initialize empty database to005 through the exact chain; seed representative synthetic policies/versions/legacy assignment, execution/review/feedback, immutable audits and persisted sessions. Capture canonical retained-row hashes and schema/object/grant baselines.
3. Apply006. Verify marker and physical VARCHAR/BIGINT/BIT/DATETIME2(7)/NVARCHAR(MAX) shapes, defaults/nullability, tenant composite indexes/FKs, covering INCLUDE columns, trusted/enabled checks/triggers and LEGACY initialization; confirm every prior row/link/session preserved.
4. Apply007. Verify VARBINARY(12)/VARBINARY(MAX), tenant/review FK, unique nonce/key index, expiry index, format/binary/seven-day checks and update-denying trigger. Exercise actual SQL rejected invalid data and audit updates/deletes on synthetic fixtures; no production record is touched.
5. Apply **separately generated temporary-target copies** of Phase6A grant proposals after reviewing only their target/identity substitutions. The existing proposals hard-code production guards and MUST NOT be executed or weakened against another target. Verify exact least-privilege runtime operations; no UPDATE/DELETE on immutable evidence; protected content SELECT/INSERT/DELETE and no UPDATE.
6. Extract pinned candidate/fallback locally, use real SQL Server transport to A, fixture providers/regex and mocked SSO, synthetic keys. Verify ready005/006/007,120-minute sessions, portal/RBAC/tenant negatives, lifecycle, LEGACY/MULTI, all decisions, encrypted capture/reveal/access audit/disposition/expiry/cleanup and retained ciphertext under fallback. No production App Service settings or production login. Local hosting validation remains separate from actual App Service startup.
7. Do not test grants solely as the CONTROL-capable operator. Use a session impersonating the existing runtime mapping **only within A**, verifying `USER_NAME()` and denial cases; explicitly label this as SQL permission-context testing, not MI authentication. If separately included in A approval, use one ephemeral in-memory SELECT-only process via the existing main-container channel to connect **only A** under its actual managed identity and confirm permissions. No hosted files, deployment, restart or provider calls. Stop if A cannot be reached under the existing network/identity—no firewall or new access workaround.
8. For deliberate failure cycle, delete/recreate only A after recording success. At005 seed RESERVED work/invalid identities and confirm006 stops before DDL. Resolve only those synthetic fixtures for the next case. At006 inject a controlled SQL-server THROW after007's first index operation using the test harness (migration files unchanged). Inspect marker/catalog/retained records and actual transactional rollback. Unexpected partial state is a stop, not a blind retry or manual object drop. Record lock/transaction/error behavior; destroy only A afterward.
9. Quiesce harness sessions, delete the exact A database, poll deletion completion/GET404 and confirm server inventory has neither A nor any unexpected test name. Preserve sanitized results and source production release/revision checks. No production/data/backup cleanup. Failed deletion is an open billable resource and blocker; notify with the exact ID, never delete a broader scope.

An operation that fails unexpectedly stops the rehearsal; the second incarnation is for a deliberately planned isolated cycle, not authorization for retrying unexplained failures. No automatic tier increase or extra database name is allowed.

## 4. Costs and permissions for A/B

Public Azure Retail API returned primary **S0 DTUs**, westus2, USD **0.4839/day**, approximately **0.0201625/hour**; secondary meters were excluded from estimates. Saved primary response: `retail-prices.json`. Four hours is approximatelyUSD0.081 per incarnation. Allowing hourly rounding and planned recreations, budget roughlyUSD0.10–0.20 base compute for A. A single four-hour B restore is roughlyUSD0.08–0.10. These are retail planning estimates, excluding taxes/agreement differences, retained backup/storage/egress and abnormal delays. [Retail API documentation](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices), [hourly DTU billing](https://learn.microsoft.com/en-us/azure/azure-sql/database/single-database-scale).

Proposed authorization envelope: **USD 1 for A and a separate USD 1 for B**, each four-hour window, no upsizing. This is an operator stop/escalation budget, not an enforceable billing cap. S0 does not pause when idle. Stop testing before expiry and delete the approved destination; if Azure prevents cleanup, report the continuing charge and seek a narrowly scoped extension. A potential extra synthetic007 recovery leg requires renewed A/B approval, not assumed budget rollover.

Management rights needed: existing server/source read, destination database write and delete, and read access for backup/operation/status/locks/policies. Operator SQL rights are distinct: CREATE TABLE, relevant ALTER/REFERENCES and trigger/index operations, seed INSERTs/Alembic UPDATE plus targeted grant authority in the **test database**. A's impersonation requires test-user IMPERSONATE (or current test-database CONTROL), not a runtime grant. Reconfirm actual database principal SID before mapping the existing runtime identity. Current metadata indicates sufficient broad operator rights at existing scope; **no new cloud role is requested**. Never grant the runtime CONTROL/db_owner/DDL to make tests pass.

## 5. Checkpoint B — isolated PITR drill

**Platform prerequisites indicated; actual recovery PENDING B approval.** The existing Azure SQL service supports same-server PITR to a **new database**, not in-place overwrite. Do not run T-SQL RESTORE, change production retention or route the hosted app to the clone. [Microsoft restore semantics](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql).

Exact destination: `sqldb-gpv-pitr-20261106-b1`, same existing server/group/subscription, S0 / 10 DTUs, Local redundancy, source size ceiling250 GiB. It is absent now; stop on a later collision. This clone **contains production data and persisted session/audit state** from the selected time; B must explicitly authorize that copy and its restricted handling. No application server is pointed at it, no SSO/provider traffic and no additional principal grants. Existing logical-server network rules are shared; this is a separate database/identity access boundary, not a separate network zone. If that boundary is insufficient for data-owner policy, B is BLOCKED without a separately reviewed permitted alternative.

Proposed restore time: **2026-11-06T08:00:00Z**, inside the reported retention window and before this inspection. At execution revalidate this exact point is still inside the window and sufficiently behind the latest available backup. If not, propose a new point for approval; never silently choose current time or an arbitrary fallback. That time intentionally predates deployment and is for a drill, not a future production cutover recommendation.

Future restore (NOT EXECUTED):

```bash
az sql db restore --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 \
  --resource-group rg_techdemo_Atiya_Tabsum_Shaik \
  --server sql-governance-validator-dev-atiya \
  --name sqldb-governance-validator-dev --dest-name sqldb-gpv-pitr-20261106-b1 \
  --time 2026-11-06T08:00:00Z --service-objective S0 \
  --backup-storage-redundancy Local
```

The restore command takes the source name and a distinct destination; the underlying operation creates only the destination. Record exact resource IDs, requested point, start/completion/error categories and operation correlation. Poll until Online; timeout/failure does not authorize a second name, a newer point or production restore. [CLI restore reference](https://learn.microsoft.com/en-us/cli/azure/sql/db?view=azure-cli-latest#az-sql-db-restore).

Validation (only the restored destination):

- Exact `DB_NAME()`, executing identity, collation and single Alembic marker; expected005 at the approved point, subject to retained historical evidence. Inspect actual schema, not only marker.
- Execute reviewed `deployment/phase6b-recovery-validation.REVIEW_ONLY.sql`: aggregate counts/tenant links, trusted/enabled FKs/checks/triggers/indexes, DBCC CHECKDB and CHECKCONSTRAINTS. No prompts, ciphertext, tokens or cookies selected. Any failure blocks recovery qualification.
- Before the drill prepare a small canonical ID/hash manifest of immutable records known to predate the restore point; compare those exact hashes in the clone. Counts alone are insufficient. Current mutable policy rows cannot be assumed equal to historical rows; current source counts also cannot prove exact historical state while the source remains writable. Do not stop production or add markers there under B.
- Record elapsed time to SQL availability and completed validation, selected-point age and source observations. Distinguish measured drill duration from an approved production RTO/RPO and a verified latest-restorable point.
- Inspect roles/users/session expiry/revocation behavior only as sanitized metadata. Do not use restored sessions to authenticate or replay any operation. A real restore/cutover can rewind revocations and lose later audits/data; recovery would require separate explicit session/data-reconciliation approval.
- No migrations or application writes on the production-data clone in B1. Existing protected content is not expected on source005; if unexpected ciphertext or another revision appears, stop and review rather than decrypt with production keys.
- Delete **only B** after collecting aggregate/hash results. Guard the exact destination ID and prohibit production/master. Poll operation completion and confirm GET404/list absence, without changing source backups. Service-retained backups of deleted clones may persist according to policy; resource deletion is not a promise of immediate backup erasure. B approval must accept that data-retention boundary.

If restore fails/permission is denied, preserve sanitized evidence and request only the missing operation at the required scope; do not grant broad roles, alter backups, change firewalls or retry against production. Failed cleanup retains an explicit open-resource/cost blocker. No database rename, endpoint change or production cutover is part of B.

**007 recovery coverage gap:** restoring today's005 production database does not prove recovery of007 encrypted content. Before protected capture is enabled, schedule a separate synthetic007 PITR leg: renew A approval to create/reuse its named synthetic007 source within a new four-hour window; obtain B approval for restoring that source to the same B name after B1 is deleted. Seed synthetic encrypted/pending and expired cases plus immutable audit before a chosen point, wait for a recoverable backup, restore, verify hashes/FKs/constraints and run candidate/fallback with the same synthetic key. Test cleanup only on the synthetic restored clone. Both named resources and their eventual deletion must be approved; if backup availability exceeds the window, stop/clean up and reschedule. No production keys or production-clone writes are needed. Without that leg, declare encrypted007 PITR recovery UNVERIFIED and keep production capture disabled.

## 6. Exact sanitized production configuration proposal

These changes are **E approval only**, never implicit in A/B/C/D:

| Setting/control | Proposed state |
|---|---|
| `SSO_SESSION_MINUTES` | Exact delta `60`→`120`, after confirming upstream policy permits it; new absolute sessions only |
| `SSO_ENABLED` | Preserve `true` |
| `DEMO_BROWSER_LOGIN_ENABLED` | Preserve `false` |
| `ALLOW_LEGACY_API_CREDENTIALS` | Preserve `false` |
| `SSO_PUBLIC_ORIGIN`, CORS | Preserve exact existing HTTPS site origin |
| Entra callback / logout | Preserve `/api/sso/callback` and registered site-root post-logout URI; no registration change or secret rotation justified |
| Cookies | Preserve Secure/HttpOnly/SameSite=Lax/root `__Host-`; state/nonce/PKCE/five-minute transaction and server-side revocation remain enforced |
| Initial bridge/capture | Explicit `REVIEW_CAPTURE_ENABLED=false`; cleanup false on005/006 |
| After007 with capture still disabled | `REVIEW_CLEANUP_ENABLED=true` when approved/healthy; retain every existing required key if content exists |
| Protected capture, later only |007/grants/healthy worker plus approved stable independent32-byte AES-256-GCM key in `REVIEW_CONTENT_KEYS_JSON` and active ID in `REVIEW_CONTENT_ACTIVE_KEY_ID`; then approved capture=true |

No secret values or deployment-ready key placeholder payload is supplied. Authorized custodian must supply keys through the existing protected App Service settings process, retain identical bytes/IDs across workers/restarts and protect configuration recovery independently of database backups. No new Key Vault/service. Never generate a production key in a process startup or reuse SSO/provider credentials. Retain historical keys for live/backup ciphertext; removing them causes permanent decryption loss. No rotation is authorized by enablement.

Verify actual replacement-worker settings, seven-day absolute expiry, cleanup heartbeat (fresh within 960 seconds), metadata-only access audit committed before reveal, explicit reviewer assignment even for Admin, tenant/session/version checks and ciphertext purge on disposition. Keep capture off for missing keys/schema/healthy cleanup. Existing60-minute sessions keep original expiry; do not silently extend or mass-revoke them. Production cookie/SSO persistence and key-restart behavior require E/F-approved evidence; configuration presence alone is not success.

## 7. Separate approval checkpoints and execution order

| Approval | Exact scope/data affected | Risk, rollback and pass evidence |
|---|---|---|
| **A — migration rehearsal** | Only named synthetic S0 database, max 2 incarnations/four hours/USD 1; local target-locked harness; temporary SQL mappings/grants for existing identities;001→005→006→007 and deliberate failure tests; delete A | Cost, shared-server pressure, wrong-target risk; abort/close sessions/delete only A. Pass: physical catalog, retained hashes, least-privilege denials, candidate/fallback behavior and confirmed cleanup. No production copy, restore, deploy or settings |
| **B — recovery drill** | One production005 PITR clone at exact B name/time; maxfour hours/USD 1; aggregate/hash/integrity SELECT/DBCC validation; delete B | Copies sensitive historical data/sessions; shared-server load, cost and retained backup copies. No source writes/cutover. Pass: restore completion, invariants, known-record hashes, measured duration and deletion. Additional synthetic007 leg requires renewed A plus explicit B scope |
| **C — production migrations/grants** | Existing production005→006→007, guarded new-object permissions, approved drain/window and data-preservation baselines; no source changes | Locks, partialDDL, data loss if recovery mishandled; no downgrade/stamp. Requires A/B results, fallback decision and a verified compatible bridge already serving005. Stop/maintenance, reviewed forward repair or separately authorized restore. Pass:007 physical catalog, runtime grants and retained/audit invariants |
| **D — application deployment** | Exact candidate hash to existing Web App, approved recycle and explicit schema-compatible fallback/forward-fix scope; initial capture disabled | Worker outage/shared code defect; old005 artifact usable only before006. After007 same-code copy is file/config recovery, not independent rollback. Pass: actual replacement worker, release/member hashes, appropriate schema readiness; no provider tests |
| **E — settings/key configuration** | Exact120-minute delta; capture-disabled initial flags; later existing-setting key custody/cleanup/capture prerequisites and any individually named existing-identity memberships | Recycle, key loss, encrypted-data unavailability, retention failures; revert capture off but retain keys/cleanup after007. No blanket revocation or speculative SSO-secret rotation. Pass: actual worker config and health, synthetic recovery leg for encrypted007 readiness; values never disclosed |
| **F — bounded live acceptance** | Named approved identities/workspace and synthetic inputs; propose max 2 SSO logins,2 generation calls,8 moderation calls,1≤64KiB ADLS export and1 read-back, no retries; final cost budget approved before F | Billable calls, immutable test/session/audit records and storage writes remain; stop on first unexpected result and preserve evidence. No permission/secret/schema changes. Pass: SSO/session/portals/RBAC, governed decisions/review/audit/filters and exact export checksum within bounds |

**Execution order differs from letters:** A → B/recovery qualification/fallback decision → D's compatible bridge on005 with capture off → C's migrations/grants under maintenance → E's approved settings/healthy cleanup → D post-change read-only checks → F. Protected capture stays disabled until its additional recovery/key gates are satisfied. Approval for C never authorizes D or E, and approval for A never authorizes B. Any restore/cutover after a production failure needs separate exact-point/data-loss/session/reconciliation approval; a drill does not authorize it.

## 8. Remaining blockers and first request

A and B are plans, not executed qualifications. Pending: target-locked SQL Server harness and SQL Server tests; actual restore/cleanup and measured RPO/RTO; synthetic007 ciphertext PITR leg before capture; independent fallback or explicit acceptance of same-code/forward-fix limitations; exact production migration/grant/deploy/settings/acceptance approvals; actual SSO and provider/key/cleanup evidence. Current permission metadata reveals no missing restore allow action, but operation-time quota/policy/identity availability remains a gate. No additional Azure service or broad new permission is proposed.

**First narrowly scoped request:** approve **A only**: prepare/review the target-locked local SQL Server harness, then create `sqldb-gpv-mig-20261106-a1` on the existing logical server as S0 / 10DTUs with 250GiB maximum and matching collation; use only synthetic data/test keys/mocked providers, temporary mappings/grants for existing identities only inside A, at most2 incarnations within 4 hours and a USD 1 budget; run the reviewed migration/compatibility/failure checks and delete that exact test database afterward. This permits no production write/copy, restore drill, deployment, hosted setting/secret change, provider call, production SSO login or approval B–F.

No approval is presumed from the existence of rights, historical deployment approvals or a timeout/no response. **NO-GO for deployment; GO only to deciding checkpoint A.**

## 9. Files and safety record

Added this report, `deployment/phase6b-recovery-validation.REVIEW_ONLY.sql` and sanitized evidence under `docs/evidence/phase6b-readonly-2026-11-06/`; no previous source/report/artifact was changed. `approval-scope.json` records exact destination IDs and current absence/constraints. `fallback-inventory.json` records artifact provenance; `local-artifacts.json` pins packages/migrations. Local SQLite remains revision 003 with unchanged SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. No Git commit/reset/clean/stash/discard or Azure mutation occurred. No expensive suite was repeated: this was read-only inspection and planning.
