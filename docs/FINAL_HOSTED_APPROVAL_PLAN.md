# Hosted migration and deployment approval plan

31 October 2026, Asia/Kolkata. Prepared only; no hosted writes performed.

## Release and target

- Existing subscription `REPLACE_WITH_AZURE_SUBSCRIPTION_ID`, resource group `REPLACE_WITH_AZURE_RESOURCE_GROUP`.
- SQL server `sql-governance-validator-dev-atiya`, database `sqldb-governance-validator-dev`; fresh SELECT revision 003.
- App Service `app-governance-validator-atiya-1026`, https://app-governance-validator-atiya-1026.azurewebsites.net.
- Candidate `1.1-544cbf32d11a251a`, ZIP `artifacts/final-implementation-20261031/governance-reliability-final.zip`, SHA-256 `3d81bdfca85f4df3b4786562283bce4d599d34662993f2c21623eeb6d3286992`, 240732 bytes. All members and backend source match; rebuilt frontend bytes match all four packaged assets.
- Full deployed file list: [existing manifest](evidence/final-implementation-2026-10-31/package-manifest.json). Includes app modules, locked requirements, startup, release metadata and static assets. Migration scripts are deliberately NOT in runtime ZIP. Migration 004 is a separate reviewed operation, bound by [source/SQL/config hashes](evidence/hosted-preflight-2026-10-31/reviewed-operation-hashes.json). Never claim migration is embedded in the ZIP.
- Current hosted deployment remains `8c2639f4-41d7-4787-bce4-e7253ecbb4b2`; API version 1.0.0 and new session endpoint absent. Candidate API version is 1.1.0. Exact currently hosted backend build identifier is not publicly exposed; it is not inferred from a commit. Public shell hash matches the previous observation.
- Dirty working tree is preserved in [status inventory](evidence/hosted-preflight-2026-10-31/git-status.txt); no commit, push, discard or source change performed.

## A. Migration approval scope and sequence

Approve only revision 003→004, existing database, existing authenticated migration identity. No new resource, data seeding, reset, downgrade or permission grant is included.

1. Immediately before DDL recheck all frozen hashes, identity binding, database name, sole revision 003, metadata, exact counts and PITR window. Abort if changed incompatibly. Current account has effective database CONTROL, CREATE TABLE, ALTER and REFERENCES; use only for the reviewed migration, never runtime. Runtime is the existing managed-identity member of governance_validator_web_runtime. Do not grant extra migration privileges.
2. Coordinate a quiet operator window with no in-flight inference/export/policy mutations. The existing running app remains on old code until schema and approved grants pass. No automatic app shutdown is included. If writes cannot be quiesced, stop for a separately approved maintenance operation. Counts must be compared during that quiet interval; concurrent writes invalidate simple equality evidence.
3. From backend, use the documented Alembic mechanism with a process-scoped DATABASE_URL selecting the existing approved SQL target and AZURE_CONFIG_DIR pointing to the existing organizational cache. Do not print the URL or edit .env. Set auth mode cli and retain pinned tenant/user IDs. Reviewed command: `../.venv/bin/alembic current`, then `../.venv/bin/alembic upgrade 004`, then `../.venv/bin/alembic current`. Do not use an unbounded future head.
4. Creates demo_sessions, inference_rate_buckets, inference_usage, export_jobs, review_assignments, review_notes; all empty. Creates their PKs, tenant/idempotency unique constraint and three FKs into exports/reviews. Creates 11 new-table secondary indexes and ix_execution_tenant_created on the existing validation_executions table. Creates three SQL Server INSTEAD OF UPDATE/DELETE triggers on audit_events, policy_versions, review_notes. Source is authoritative; exact SQL is review-only and must match source. No existing row backfill/update/delete, table drop or type change occurs. Alembic changes its revision row.
5. Verify sole revision 004; six new empty tables; all expected PK/FK/unique/index definitions; three enabled triggers; unchanged eight original application-table counts and accessible policy/version/audit/export records. Perform SELECT-only smoke checks. Do not deliberately update/delete existing audit rows to test triggers. Write smoke tests/authentication require their own approved synthetic record scope.
6. Stop on any failure. Record sanitized error and inspect transaction/revision/object state before deciding recovery. Do not stamp a revision, blindly retry, reset or downgrade.

Fresh count baseline: policies 6; policy_versions 6; active_policy_assignments 4; audit_events 87; validation_executions 20; human_review_cases 3; feedback_records 4; evaluation_exports 7; alembic_version 1. Refresh immediately before execution. [Metadata/count evidence](evidence/hosted-preflight-2026-10-31/sql.json) includes indexes, constraints, triggers, migration rights and role memberships.

## Recovery and compatibility

Azure management reports database Online, seven-day short-term retention, differential backup interval 24 hours and earliest restore time 2026-10-28 15:55:06 UTC (28 October 21:25:06 IST). Record a UTC pre-DDL timestamp and reconfirm it falls inside the restorable window. This is control-plane evidence, not a restore drill or proof of the latest recoverable second. No backup was created and no Azure restore tested.

Migration is additive to core stored data but behavior changes: history triggers prevent UPDATE/DELETE. Downgrade intentionally raises rather than deleting durable records. SQL Server transactional DDL is expected through Alembic; inspect actual state after failure rather than assuming rollback. If cleanly rolled back to 003, preserve evidence and keep old app. If 004 committed, preserve new tables/history and use a reviewed forward repair or compatible old ZIP. If recovery needs Azure PITR, stop for a DBA-reviewed restore target, operator and separate resource/cost approval; restoration normally requires another database and is outside current no-provisioning scope. A named recovery operator and actual restore execution path have not been verified. These must be resolved before executable migration clearance; approval alone does not waive recovery checks.

Application rollback candidate is `artifacts/live-stabilization-20261031/governance-live-stabilized.zip`; rehash before any use (historical SHA-256 `5f22b7d829e79251f58f4b216bcc18d92f500220e28381eee18ad6f251e1d697`). It restores application bytes only, retains schema 004 and all evidence, requires sign-in again and loses new reliability controls. Rehearse old-code compatibility with 004 before rollback clearance. Do not roll back an in-flight generation/export. Current worker archive was not independently downloaded; exact historical backend recovery match remains unverified.

## B. Separate runtime permission approval

After schema 004, apply only [reviewed grant script](../deployment/runtime_004_permissions.REVIEW_ONLY.sql) to existing governance_validator_web_runtime. SELECT on alembic_version; SELECT/INSERT/UPDATE on sessions, rate buckets, usage, export jobs and review assignments; SELECT/INSERT only on review_notes. No DELETE, broad administrator grant, new principal or role membership change. Verify effective permissions under the actual runtime identity; administrator access does not prove runtime access. Existing inheritance must be checked before execution. No OpenAI/Moderation/ADLS privilege change is proposed from configuration presence alone. Provider data-plane success remains unverified.

## C. Separate deployment approval

Only after 004 and approved runtime access pass: rehash the exact ZIP, preserve old artifact, deploy once using the existing Entra-authenticated ZIP method in FINAL_DEPLOYMENT_VERIFICATION.md. Startup remains `python -m uvicorn app.hosting:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log`; it applies no migrations. No infrastructure/configuration/secret change is included. New optional settings use existing code defaults; inspect securely before deploy.

Allow several minutes of single-worker interruption; this is an estimate, not an availability guarantee. Verify management completion, exact frontend asset bytes, release metadata, OpenAPI, health and revision-aware readiness. Public read checks are authorized. Login/session writes, tenant/RBAC and workflow persistence require separate acceptance approval. Abort deployment if schema readiness fails. Rollback deployment requires an explicitly approved compatible recovery ZIP; never automatically downgrade SQL.

## Risks and later approvals

DDL/index locking, history-trigger behavior, partial state after failure, runtime grant omissions, restart downtime, old-session incompatibility, unverified Azure restore and SQL concurrency/load behavior remain risks. Real generation, moderation and ADLS are not proven by local tests or setting names.

Request each independently: (A) migration with recovery prerequisite; (B) runtime grants; (C) deployment; (D) bounded auth/session and synthetic policy lifecycle/audit mutations with existing authorized accounts; (E) exactly one generation for `Explain data governance in two short sentences.` with required input/output moderation budget, no retries; (F) separately bounded real moderation fixtures; (G) exactly one synthetic metadata ADLS object with fixed idempotency key and read-back/hash verification. PII, human-review and policy lifecycle live writes need scoped approval too. Blocked PII should not consume generation calls. Do not infer permission for a second paid call from the first. Preserve separation-of-duties restrictions.

Fresh runtime review: existing role has explicit grants on the eight core application tables and the application identity belongs to that role. No explicit alembic_version grant is present. Hosted setting names for SQL, Azure OpenAI, Moderation, ADLS and demo accounts exist; values and provider connectivity are not certified by name presence. See runtime-readonly.json. Preserved rollback ZIP freshly matches its historical SHA-256; old-code compatibility on 004 remains unverified.
