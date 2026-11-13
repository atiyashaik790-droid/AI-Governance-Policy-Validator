# Stage C execution result — 4 November 2026

**COMPLETE — migration and bounded post-migration acceptance PASS. Stop after Stage C.**

## Authorization and ownership

The user explicitly approved 004→005 and exactly three reviewed object-level VIEW DEFINITION grants applied atomically, with bounded post-migration acceptance. The user then confirmed Atiya Tabsum Shaik as recovery operator, reachable escalation contact and incident/cutover decision-maker for this independently managed demo project. The reviewed documents do not require a second or independent contact; that gate was satisfied without inventing an organizational policy. Existing CLI identity/authority verification is retained. The supplied phone number is not copied into repository evidence. RTO 120 minutes/RPO 15 minutes are accepted targets, not a claimed restore guarantee.

## Applied change and evidence

The exact approved database is `sqldb-governance-validator-dev` on `sql-governance-validator-dev-atiya`, existing group `rg_techdemo_Atiya_Tabsum_Shaik`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`. Existing pinned CLI identity executed one guarded transaction; no identity, configuration or membership change was needed.

- Created `dbo.sso_memberships`, `dbo.sso_transactions`, `dbo.sso_sessions` and exactly the reviewed constraints/indexes.
- Granted VIEW DEFINITION on each of those three objects to existing role `governance_validator_web_runtime`. No SSO SELECT/INSERT/UPDATE/DELETE or other operational SSO permissions were granted.
- Advanced the single Alembic row 004→005 in that same transaction.
- Verified original 14 model-table row counts and history-trigger definitions unchanged before commit; all three new tables empty; exact three grant records present; complete operator-identity 005 schema contract passed before commit.

Approved SQL SHA-256 remains `26b9537cc66fdf7eb4853b177fd5f8fdfd411edcd73949a0f3a0cae9adc02f97`; migration source hash remained pinned. Commit: **21:47:06 IST / 16:17:06 UTC**. Transaction duration **174.469 seconds**, below the approved five-minute budget.

## Pre-DDL recovery and quiet gates

Current continuous recovery window was refreshed. A completed retained log backup at `2026-11-04T16:11:04Z` supported candidate pre-DDL recovery point `2026-11-04T16:11:03Z`, inside the published window and **265.525 seconds** before the final pre-DDL boundary. This supports the accepted 15-minute target; no restore was performed or exact-point acceptance guaranteed. Backup history is read-only evidence, not a restore rehearsal. [Microsoft backup-history DMV](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-database-backups-azure-sql-database).

The first read-only snapshot observed one open user transaction; follow-up metadata found no remaining transaction or write lock. The final in-transaction gates independently required zero other active user requests, user transactions, write locks, active inference reservations and active export jobs. All passed before the atomic batch. The migration attempt itself was submitted once; there was no failed-migration retry.

Quiet window: **21:45:28–22:00:28 IST / 16:15:28–16:30:28 UTC**. Baseline tables were locked during the transaction as reviewed to hold counts stable; no session was terminated. Migration and acceptance completed inside the approved window.

## Post-migration acceptance

A fresh SELECT-only operator connection independently verified exactly one 005 row, complete schema/keys/indexes/FKs/history protections, all new SSO tables empty, exactly three metadata grants and existing runtime role membership unchanged. Operator schema success is separate from actual runtime proof.

Hosted acceptance passed **18 bounded assertions**:

- `/health` and `/ready` return success; release remains `1.2-6749226f1af65b63`, actual revision 005, versioned schema, SSO unavailable. `/ready` successfully inspects 005 objects through the actual application managed identity.
- `/api/sso/status` confirms SSO disabled and demo login enabled.
- Existing approved Admin credential exchanges successfully for one demo session; expected role/tenant and SQL revision 005 are preserved; tenant-scoped policy GET and fresh-client session restoration succeed.
- Logout succeeds and the revoked session is denied afterward.

Hosted acceptance finished **21:47:32 IST / 16:17:32 UTC**. Writes beyond the approved schema/grants were limited to one demo session and normal audit/rate-limit/logout activity. No prior session token was available for continuity testing, so no additional fixture/session was manufactured. Stage B suite and unrelated tests were not rerun.

Evidence: [authorization](evidence/stage-c-execution-2026-11-04/authorization.json), [pre-DDL boundary](evidence/stage-c-execution-2026-11-04/boundary-readonly.json), [quiet diagnostic](evidence/stage-c-execution-2026-11-04/transaction-detail-readonly.json), [recovery window](evidence/stage-c-execution-2026-11-04/recovery-window.json), [atomic execution](evidence/stage-c-execution-2026-11-04/migration-execution.json), [exact executed command record](evidence/stage-c-execution-2026-11-04/executed-command.RECORD_ONLY.txt), [fresh SQL verification](evidence/stage-c-execution-2026-11-04/postmigration-sql.json), [hosted acceptance](evidence/stage-c-execution-2026-11-04/hosted-acceptance.json), [result summary](evidence/stage-c-execution-2026-11-04/result.json).

## Stop state and recovery applicability

No Azure configuration change, SQL membership change, credential rotation, SSO activation, restore, new resource, paid provider/storage operation or later rollout step occurred. Only the separately approved metadata-only D-visibility scope accompanied C; full operational SSO grants remain unapproved and unapplied.

**The old original ZIP `1.2-5e8064f901573795` is 004-only and must not be deployed against 005.** Keep schema/data 005 and compatibility release `1.2-6749226f1af65b63` with SSO off/demo on. No downgrade, dropping tables or history stamping. Any incident restore/new resource/configuration cutover or further repair requires separate explicit scope.

No Stage C acceptance blocker remains. The known exposed-credential rotation plan remains separate and unexecuted, as instructed. No broader SSO readiness or successful Microsoft authentication is claimed.
