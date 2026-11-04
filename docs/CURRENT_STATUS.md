# Current project status — restricted demo release

Updated 2 November 2026 (Asia/Kolkata). This is the authoritative status entry point; older “FINAL” reports and evidence describe historical releases and approvals.

Latest hosted release: **1.2-38d43c3690160556** adds searchable multi-select dropdowns for PII entities and moderation categories. All 20 frontend tests passed, and hosted Chrome verified selection/search and mobile layout with zero page errors and no saved policy changes. Backend fingerprint and enforcement behavior are unchanged. See [dropdown verification](POLICY_SELECTION_DROPDOWNS.md). This supersedes earlier fingerprints below.

Current hosted release: **1.2-bcba8e97a8b84793**. Audit & reports now has separate Policy history, Governance execution history and Administrative history views, backed by tenant-scoped filtering before pagination. Hosted category checks returned 200 and verified separation; 440 backend and 17 frontend tests passed. See [audit history release verification](SEPARATE_AUDIT_HISTORIES.md). Earlier fingerprints below are historical.

The policy list SQL Server compatibility fix is deployed as **1.2-37d875d722719d8a**. Authenticated policy listing, pagination, search and status/enabled filters now return HTTP 200; policy management and simulator page routes also return 200. See [fix and hosted verification](POLICY_LIST_SQL_FIX.md). This supersedes the release fingerprint below; the earlier bounded acceptance results remain historical evidence.

The selected scope is **restricted demonstration login**, as requested. Enterprise SSO/MFA and production certification are outside this release. The code now requires provisioned credentials to be exchanged for expiring sessions by default. Operator compatibility can be enabled explicitly with `ALLOW_LEGACY_API_CREDENTIALS=true`; leave it false for browser demos. Session logout/revocation does not disable a provisioned credential's ability to create a new session; operators must disable/rotate its account for that.

## Implemented changes

- Required `If-Match` row-version preconditions for policy edits; missing headers return 428 and stale headers return 412. The browser preserves the loaded version and cancels obsolete loads.
- Analytics preserve violations from either input/output, use the lowest inspected stage score, and show the reporting window and trend sample limit.
- Reviewers cannot take another reviewer's assigned case. Developers/Policy Owners can track their own cases, and revised submissions still pass every current gate.
- Blocking detection runs off the event loop with bounded active capacity. Request deadlines withhold content, and SQL statements/lock waits have bounded configuration.
- Position-preserving normalization for secret/keyword matching; stronger moderation schema/category checks; review-note sensitive-data redaction.
- Atomic duplicate-feedback protection per actor/execution, persisted alongside feedback using existing rate-bucket infrastructure.
- SQL-backed session/export/reconciliation rate limits; expiring-session administration UI; independent pagination for policy selection, version history, exports and sessions.
- Offline logout clears local authentication and truthfully reports unconfirmed server revocation; read-only fields are disabled; route state is isolated; a render error boundary and accessibility improvements are included.
- PII capability discovery, all schema entity options visible, unsupported entity selections rejected before lifecycle advancement.
- Explicit read-only maintenance planning and operator-only expired-bookkeeping cleanup. No business history, export snapshot, storage object or permanent feedback marker is automatically deleted.
- Current runtime permission probe covers all 14 application tables and Alembic SELECT. Old revision-003 mutation protocols fail safely as retired tools.
- Frontend Docker serves built same-origin assets through unprivileged NGINX instead of Vite's development server. Docker execution still requires validation where Docker is available.
- Updated development-only ESLint/minimatch tooling: fresh npm advisory lookup reports zero vulnerabilities.

No new schema migration is required by this release: the existing revision-004 tables support these controls. New operational controls use `inference_rate_buckets` and its existing runtime grants. Local implementation changed no existing cloud data, permission or setting. The user subsequently approved rollout: the corrected release **1.2-fd9d6fee6af8aa17** is deployed and ready on the existing Azure app. Its SQL Server usage query passed actual Azure SQL verification. Bounded live acceptance passed 13 functional checks, including real AI/moderation and an ADLS export. Independent storage checksum read-back remains unverified because the existing operator identity receives **403 AuthorizationPermissionMismatch**. See [live release results](RESTRICTED_DEMO_LIVE_RESULTS.md).

## Validation and release

See [completion validation](COMPLETION_VALIDATION.md) for executed checks, release fingerprints and limitations. The exact user-approved corrected package is deployed; API version, release fingerprint and all public asset hashes match. Hosted Chrome navigation passed all nine routes with no page errors, login/logout and a mobile width of 390/390 pixels. The release is usable for the selected restricted demo, but complete operational acceptance is not claimed while independent storage read-back and Docker execution remain open.

## Remaining operational boundaries

The final two acceptance checks now have reproducible verification scripts and a Docker CI job. They remain blocked on an authorized storage reader (current attempt: HTTP 403) and a Docker-enabled host; neither has been recorded as passed. See [final verification commands and evidence](DEMO_FINAL_VERIFICATION.md).

The 2 November follow-up verified the operator's exact identity and management-only roles, confirmed the app's existing container-scoped data role, and retried read-only identity reuse without acquiring a usable managed-identity credential. No access or system privileges changed. Full backend (439) and frontend including real local integration (16) passed. See [exact minimum access request and Ubuntu commands](DEMO_VERIFICATION_PREREQUISITES.md).

- Complete independent exact-object ADLS checksum verification using an already-authorized storage reader. Export creation/idempotency passed; the operator identity lacks read permission. No grants were changed.
- Paid acceptance has consumed its two-generation/eight-moderation reserved bounds. Do not run further paid tests under this approval.
- Complete Docker build/startup validation on a Docker-enabled machine.
- For production use, separately require approved enterprise identity, threat/penetration assessment, tenant/database integrity strategy, alerting/incident ownership, sustained SQL Server load/failover testing, and formal accessibility acceptance.
- Pattern/PII/moderation detection is heuristic; it does not certify all secrets, prompt injection, factual correctness or legal compliance. A mismatched/partial ADLS object is preserved for operator inspection rather than overwritten automatically.

## Running locally

Use the existing `.venv` and frontend dependencies:

```bash
.venv/bin/python scripts/run_offline_demo.py --port 8010 --frontend-origin http://localhost:5174
```

The launcher prints only the path to a private temporary credential file. Retrieve the desired role privately from that file; never paste tokens into logs or chat. In a second terminal:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8010 npm run dev -- --port 5174
```

The temporary SQLite database and credentials are removed on graceful shutdown. No Azure provider calls are made by fixture generation/moderation. Export attempts correctly fail with a durable record when storage is not configured.

## Maintenance

`python scripts/maintain_demo.py` is a read-only plan against the configured database. `--apply` is an explicit operator transaction removing only expired sessions older than the retention target and expired non-gate rate buckets, and marking stale inference leases EXPIRED. It does not run on startup or via HTTP. The runtime role deliberately has no DELETE grants on those tables; a separately approved operator must execute cleanup. Do not grant broader runtime access just to schedule it. Inspect/reconcile incomplete exports through the existing bounded UI/API workflow; never blindly retry or overwrite mismatched storage evidence.

## Current API edit contract

1. `GET /api/policies/{id}` and retain `row_version`.
2. `PUT /api/policies/{id}` with the policy document and `If-Match: <row_version>` (quoted strong ETags also accepted).
3. On 412, reload and compare your edits before resubmitting. Never fetch the new version and blindly replay stale content.

The old mutation scripts are retained for historical safety-contract tests, but their revision-003 preflight now refuses execution against current releases. Use current read-only inventory/permission checks and the tested browser workflow for demo acceptance.
