# Operations and recovery runbook

Updated 31 October 2026, Asia/Kolkata. **CONDITIONAL DEMO READINESS; NOT PRODUCTION READY.**

## Ownership and configuration
Assign a named application owner, database administrator, security/identity owner and panel-demo operator before production. Owners are not inferred from credentials. Review .env.example for all new limits. Keep actual keys/tokens in existing private process/App Service settings; never paste them into chat. No Key Vault or monitoring service is introduced. Secret rotation requires separate approval.

Defaults: demo sessions 60 minutes, user 30/minute, tenant 100/minute and 500/day, tenant concurrency 4, total governance deadline 90 seconds, threshold 80%, export lease 180 seconds and at most 3 upload attempts. Provider HTTP timeout remains 20 seconds, generated candidate at most 30,000 characters, request text at most 12,000 and body at most 64 KB. Reservations include validations/simulation because they may use moderation; they are not proof that generation was billed. /api/usage reports known tokens and threshold warnings to Admin/Auditor, without billing estimates or external notification.

## Health and diagnosis
/health tests process liveness. /ready tests SQL reachability and, on MSSQL, exact required revision 004. /api/settings shows release fingerprints, required/actual SQL revision, modes and configuration presence. Presence is not provider availability. X-Request-ID correlates completed route/status/duration logs; request content is excluded. Unexpected API errors stay sanitized. For repeated 5xx/UNKNOWN/provider failures stop the panel flow, preserve request IDs and inspect safe diagnostics before any retry. For 429 wait for the indicated window or inspect active reservations. No uncontrolled paid retries.

## Export reconciliation
1. Inspect export history and deterministic path. Do not delete FAILED or UPLOADING records or create a replacement export to hide uncertainty.
2. Wait until the active lease expires. POST /api/reports/exports/{id}/reconcile is an explicit storage operation; obtain live approval first.
3. Reconciler conditionally claims a SQL lease; reads the exact object's bounded ETag-pinned bytes. Matching SHA-256 completes the durable job without re-upload. Missing object may be uploaded conditionally within max attempts. A mismatch records EXPORT_CONTENT_MISMATCH and never overwrites.
4. If storage succeeds but SQL finalization fails, UPLOADING persists. After lease expiry repeat an approved reconciliation, not the original unkeyed export. Final lease ownership checks prevent stale completion.
5. At the attempt limit, missing objects remain failed; reconciliation may still verify an existing matching object. Diagnose permissions/network/destination. Do not reset the counter or force replay.
6. Legacy exports without an export_jobs row are preserved and cannot be replayed through the recovery endpoint; use their historical evidence.

Durable snapshot content contains only request_id/timestamp/decision/policy_id/version. Bounded materialization (default 10,000/5 MB) avoids unbounded memory; it is not an unbounded streaming export. SQL transactions are not held during ADLS I/O. A failed response can still have durable side effects: inspect history first. The UI retains an uncertain request's idempotency key while the screen stays mounted; backend clients should persist their own keys across reloads.

## Database backup and restore
Before hosted DDL, the DBA must verify the existing Azure SQL automated backup/PITR retention, restore window, available safe target and access. Restoring to an Azure target can incur cost/resource creation and needs explicit approval. Validate schema head, core/new table counts, active policy/version relationships, audit history, export checksums and tenant isolation on an approved isolated restore target. Do not replace production blindly. No Azure restore drill was performed. A disposable SQLite backup/restore and integrity/trigger test passed as a local rehearsal only.

## Incident response
Disable or remove a compromised source demo account through an approved configuration change; its sessions then fail authentication. Admin can revoke individual sessions. Preserve audits and request IDs; do not log tokens. Pause operator-triggered inference/export, diagnose source/provider/SQL state, and follow the exact ZIP rollback plan if a verified release regression requires it. Do not stop unrelated processes. No notifications are sent by this application; assign a manual escalation channel outside the app.

## Retention and maintenance
RETENTION_DAYS is a declared retention target (default 365), not an automatic deletion job. No audit, policy, feedback, export, snapshot or usage evidence is purged. Approve the legal retention schedule, archival and any purge separately. Expired session/rate-bucket maintenance and periodic export reconciliation need an owned operational schedule; no new queue/cron/cloud service was introduced. Review database growth, token quotas, data-plane permissions and cost thresholds. Existing single-worker hosting is not HA; App Service plan charges can persist when the app is stopped.
