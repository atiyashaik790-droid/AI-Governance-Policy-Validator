# Phase 6 — Azure deployment readiness inspection (read-only)

**Overall: PARTIAL. Deployment: BLOCKED pending the prerequisites and approvals below.** Inspection date: 6 November 2026 (Asia/Kolkata). Existing Azure metadata and SQL SELECT access were available. No deployment, migration, configuration save, secret creation/rotation, membership update, permission change, provider call or SSO operation was executed.

Status meanings: **VERIFIED** = observed directly in this inspection (with its stated identity/scope); **CONFIGURED_NOT_VERIFIED** = configuration/role metadata is present but functionality was not exercised; **PENDING** = required preparation/action remains; **BLOCKED** = a deployment gate cannot currently pass; **UNVERIFIED** = evidence is unavailable or the check was intentionally excluded.

## 1. Repository and evidence

Inspected Phase 5/5A reports/evidence, current Git status, deployment/SSO/protected-review documentation and rollback records, migrations 005–007, configuration, SSO/session/review implementations, startup/hosting, packager, schema verifiers and historical read-only probes. All existing working-tree changes were retained. No application source or approved baseline was edited. Phase 5's 1,155 consolidated backend cases, 131 frontend cases and 39 Chrome checks, plus Phase 5A's 74 readiness and 24 backend regression passes, remain **local** evidence; no expensive suite was rerun here.

The Phase 5A frozen probe still intentionally targets revision **004 only**. It must not be used to certify current hosted 005 or future 007; passing its unit tests is not a fresh cloud readiness result. The current revision-aware `verify_schema_compatibility.py --connect` was used instead.

## 2. Targets and observed hosted state

| Item | Result |
|---|---|
| Existing subscription/context | VERIFIED: expected project subscription and tenant, enabled; no login or identity switch |
| Resource group | VERIFIED: `rg_techdemo_Atiya_Tabsum_Shaik` |
| Web App | VERIFIED: `app-governance-validator-atiya-1026`, Running, HTTPS-only, system-assigned managed identity |
| Hosting | VERIFIED metadata: Python 3.13, `sh startup.sh`, Always On, TLS 1.2 minimum, FTPS disabled |
| Current release | VERIFIED public `/ready`: **1.2-ca5df7c1dc19e525**, built 5 November 2026 12:09:33 UTC; backend/frontend hashes match preserved structural-only artifact metadata |
| Public health/readiness | VERIFIED: `/health` and `/ready` HTTP 200; schema versioned, revision 005, SSO available, provider mode live. This does not call providers or establish browser SSO success |
| SQL | VERIFIED: `sql-governance-validator-dev-atiya` / `sqldb-governance-validator-dev`, Online |
| Actual database revision | VERIFIED: **005**, independently from SQL SELECT under executing CLI identity and hosted readiness |
| ADLS Gen2 | VERIFIED resource metadata: `stgovvalidatoratiya1026`, HNS enabled, HTTPS-only; private `governance-reports` filesystem/container exists |
| Azure OpenAI | VERIFIED resource metadata: `aoai-governance-validator-dev`, deployment `gpt-5-mini`, model version `2025-08-07`, provisioning Succeeded |
| Entra registration | VERIFIED metadata: `Governance-Studio-SSO`, single-tenant; callback and root redirect entries match this Web App |

Public release metadata has `git_commit: unavailable`; do not identify this dirty working tree by Git HEAD alone. A future candidate needs a complete source/member hash manifest. Current runtime identity role assignments include **Cognitive Services OpenAI User** on the existing OpenAI account and **Storage Blob Data Contributor** on the existing reports container. These are direct assignment metadata, not effective data-plane test results. An initial scoped role-list attempt was unavailable; a corrected subscription-wide listing filtered to that identity succeeded and supersedes that attempt.

## 3. Database, migrations and compatibility

**005 is already applied; do not rerun it. Required path: 005 → 006 → 007.** No partial 006/007 tables were visible. Snapshot preflight SELECT counts: reserved inference **0**, invalid legacy execution identities **0**, mismatched published-version tenants **0**, mismatched assignment tenants **0**, pending reviews **0**. Recheck immediately before any future mutation; current zeros are not a drain lock or concurrency guarantee.

| Migration | Changes and risk |
|---|---|
| 005 (already applied) | Adds isolated memberships, one-use OIDC transactions and sessions; no historical data conversion; downgrade refuses destruction |
| 006 (PENDING) | Adds workspace state/assignments/events/evidence, tenant composite indexes/FKs, `execution_mode`; **alters existing execution policy/version nullability**, adds a LEGACY/MULTI shape constraint, initializes tenant states/events in LEGACY. It preserves existing records and active legacy assignments by design, but is not purely table-additive: schema locks, constraint validation and initialization writes require a controlled window. It requires dbo default schema and drained/reconciled reservations. SQLite's table rebuild is not the SQL Server path |
| 007 (PENDING) | Adds review tenant/id unique index and encrypted-content table, FK, bounded format/expiry/binary checks, nonce uniqueness/expiry indexes and update-denying trigger. No plaintext backfill and no existing review-content transformation. Index creation/DDL can block; validate actual catalog and transaction behavior |

The currently hosted 004/005 verifier **rejects revision 006/007**. Never migrate underneath the currently serving release and expect continued readiness. Prepare and validate a 005/006/007-compatible application and a compatible fallback first; install/verify the bridge on 005 with capture off, then quiesce traffic for ordered migrations and atomic object visibility/grants. Keep mode LEGACY until a separately approved MULTI activation. Do not stamp Alembic, bypass preflight, disable audit protections or blindly retry partial DDL.

Local SQLite/compiled SQL evidence is not an actual SQL Server migration/recovery rehearsal. A final reviewed SQL Server migration plan, bounded maintenance window, lock/timeout expectations and stop/recovery procedure remain PENDING. No migration SQL was executed or generated in this inspection.

### Runtime and operator permissions

Existing contained Web App user belongs to `governance_validator_web_runtime` (one matching role membership). Catalog SELECT confirms current table grants, including SSO membership SELECT, transaction/session SELECT/INSERT/UPDATE and object-level SSO VIEW DEFINITION. The executing CLI identity passed the full current 005 schema/effective-permission verifier; this is **not** proof of CLI permission to migrate, grant or restore. Hosted `/ready` provides separate current-runtime schema evidence. Future 006/007 effective access is PENDING because the objects do not exist.

Retain these current least-privilege runtime operations:

| Object | Required runtime operations |
|---|---|
| `policies` | SELECT, INSERT, UPDATE, DELETE |
| `policy_versions` | SELECT, INSERT |
| `active_policy_assignments` | SELECT, INSERT, UPDATE |
| `audit_events` | SELECT, INSERT |
| `validation_executions` | SELECT, INSERT |
| `human_review_cases` | SELECT, INSERT, UPDATE |
| `feedback_records` | SELECT, INSERT |
| `evaluation_exports` | SELECT, INSERT, UPDATE |
| `alembic_version` | SELECT |
| `demo_sessions` | SELECT, INSERT, UPDATE |
| `inference_rate_buckets` | SELECT, INSERT, UPDATE |
| `inference_usage` | SELECT, INSERT, UPDATE |
| `export_jobs` | SELECT, INSERT, UPDATE |
| `review_assignments` | SELECT, INSERT, UPDATE |
| `review_notes` | SELECT, INSERT |
| `sso_memberships` | SELECT |
| `sso_transactions` | SELECT, INSERT, UPDATE |
| `sso_sessions` | SELECT, INSERT, UPDATE |
| `workspace_policy_states` | SELECT, INSERT, UPDATE |
| `workspace_policy_assignments` | SELECT, INSERT, UPDATE |
| `workspace_policy_assignment_events` | SELECT, INSERT |
| `execution_policy_evidence` | SELECT, INSERT |
| `review_protected_content` | SELECT, INSERT, DELETE |

The four workspace/evidence rows and protected-content row are new requirements. Coordinate necessary metadata visibility for every reflected table/index/FK/check/trigger with new-object DML grants so no deployed worker sees a new revision but incomplete visibility. Review exact object-level VIEW DEFINITION needs; do not grant broad metadata/DDL rights automatically. Append-only tables retain no runtime UPDATE/DELETE; protected content has DELETE for expiry/disposition and **no UPDATE**. Runtime membership mappings remain read-only.

A separately authorized migration operator needs the specific SELECT integrity checks, schema/table/index/constraint/trigger DDL capabilities, initialization INSERTs and Alembic history writes required by reviewed scripts; a separately authorized grant operator may be needed. Do not give the runtime db_owner, db_ddladmin or broad DDL. Exact migration/grant authority is UNVERIFIED.

## 4. SSO and 120-minute sessions

**SSO configuration: CONFIGURED_NOT_VERIFIED. Hosted 120 minutes: BLOCKED by an explicit 60-minute override.**

Fresh saved settings: `SSO_ENABLED=true`, `DEMO_BROWSER_LOGIN_ENABLED=false`, `ALLOW_LEGACY_API_CREDENTIALS=false`, managed-identity SQL mode, matching `SSO_PUBLIC_ORIGIN`/CORS origin and expected tenant. Tenant/client/secret settings are present. Entra registration has exact Web redirect URIs:

- `https://app-governance-validator-atiya-1026.azurewebsites.net/api/sso/callback`
- `https://app-governance-validator-atiya-1026.azurewebsites.net/`

Registration front-channel `logoutUrl` is null; application logout uses Microsoft's endpoint with the registered root as `post_logout_redirect_uri`. No redirect mismatch was found and no Entra change is currently justified. Credential metadata reports an expiry of 3 May 2027; this does not establish the saved secret's correctness, corresponding credential or successful token exchange. No secret value was printed or saved in evidence.

Exactly **one enabled Admin membership** exists; no User or Reviewer membership was observed. Admin can review when explicitly assigned, including self-assignment. If deployment acceptance must exercise actual User/Reviewer roles, separately approve mapping existing authorized Entra identities to those server-side memberships; do not invent accounts or relax role checks.

Saved `SSO_SESSION_MINUTES=60` overrides the latest default 120. Approval is needed to set 120 after confirming organizational controls permit it. Existing session expiry/cookies are not extended retroactively: test fresh sessions. Current source uses absolute expiry (no sliding refresh), Secure/HttpOnly/SameSite=Lax `__Host-` root cookies, server-stored token hashes, state/nonce/PKCE and five-minute login transactions, same-origin CSRF, fresh-login rotation and logout revocation. Disabled/revoked membership/session is checked on every request. Role changes take effect through live membership resolution. Preserve these protections; shorter upstream controls remain effective. Application replacement alone does not globally invalidate persisted sessions; any mass revocation requires separate approval.

Historical Stage G login failed, with transaction expiry the leading but unproven explanation; later hosted release verification does not prove a successful fresh browser login. Current end-to-end SSO, actual new-session lifetime, logout and revocation remain UNVERIFIED in this read-only phase. No login or token exchange was attempted.

## 5. Secure Human Review

**Full protected-content enablement: BLOCKED.** Migration 007 is absent, capture/cleanup settings are unset, and active-key/keyring settings are absent. Latest defaults leave capture and cleanup **off**; ordinary governance/reviews continue without retaining originals. No production key was generated or read.

To enable the requested feature, separately approve 007, runtime grants, stable protected App Service configuration containing an independently supplied **32-byte AES-256-GCM key**, bounded key ID and base64 keyring JSON, and both capture/cleanup flags. Reuse only the existing hosting/settings architecture; no Key Vault or new service is proposed. The same key bytes/IDs must persist across restarts and every worker; do not generate per-process keys or reuse SSO/provider credentials. Key custody, authorized administrators and restricted backup/retention handling require an operator decision. Availability/persistence cannot be verified because no key is configured.

Capture enabled with missing key/schema or unhealthy cleanup fails readiness/governance admission closed. A successful cleanup heartbeat is required; bounded cleanup runs about every 15 minutes and retries failed/backlogged work, with a two-second work budget and at most 200 deletes per pass. The healthy window is 960 seconds. Seven-day absolute expiry is checked at retrieval even during cleanup outages; physical deletion can lag during outages and backups can outlive live deletion. This is not an outage-independent deletion guarantee.

Keys/AAD bind tenant, review/execution, content kind/version and expiry. Reveal requires current session, Admin/Reviewer, matching tenant, explicit assignment even for Admin, pending status, matching case version, unexpired content and an access audit committed before plaintext returns. Disposition deletes ciphertext atomically; approval never auto-releases content. Existing pending cases (currently zero) remain metadata-only unless content was captured originally; **no original-prompt backfill** is possible/authorized. Structured notes on 007 avoid copying held secrets into ordinary audit notes.

Rollback after 007 must retain the 007 schema, keys and a compatible cleanup-capable worker. Capture/reveal can be disabled; cleanup stays enabled until retained content is gone. Never deploy a pre-007 verifier onto 007 or remove old decryption keys while ciphertext/backups still require them. Downgrades 005, 006 and 007 intentionally refuse destructive reversal.

## 6. Provider readiness

| Component | Status and precise evidence |
|---|---|
| Azure OpenAI | CONFIGURED_NOT_VERIFIED: endpoint/deployment present, deployment Succeeded; API-key setting absent, which is supported by the existing managed-identity credential path; identity has OpenAI User role. No generation/token acquisition/provider request was made |
| OpenAI Moderation | CONFIGURED_NOT_VERIFIED: `OPENAI_API_KEY` present and provider mode live; validity, external access/quota and response are UNVERIFIED |
| Azure SQL | VERIFIED current 005 connection/schema under CLI identity, plus hosted `/ready` 200 and current role metadata. Future 006/007 grants, migration execution and SQL Server load/concurrency remain PENDING |
| ADLS exports | CONFIGURED_NOT_VERIFIED: account/filesystem settings present, HNS/private filesystem and container-scoped Blob Data Contributor role observed. Current data-plane ACLs, actual conditional upload and independent checksum read-back were not exercised |

Provider configuration is not live success. Existing adapters fail closed on missing/invalid inspection, timeouts and unavailable generation; output is inspected before release. Export errors are retained with recovery/idempotency state instead of reported as successful. Diagnostics explicitly use CONFIGURED_NOT_VERIFIED. Historical successful provider runs remain historical only.

## 7. Backup, artifact and rollback readiness

VERIFIED SQL management metadata: seven-day short-term retention, differential interval 24 hours, Local backup redundancy; earliest restore date reported **30 October 2026 08:22:41 UTC**. These facts do not establish the latest restorable point, achievable RPO/RTO, restore authority, a tested restore or the integrity of a restored application. Record the exact pre-change recovery point, operator/access, recovery ownership, downtime/data-loss envelope and validation procedure before authorizing migration. A restore drill/cutover would mutate/create a database and needs explicit separate approval; none was attempted.

A preserved artifact for the **currently hosted** release exists at `artifacts/structural-only-candidate-2026-11-05/production/governance-structural-only.zip`, SHA-256 `6a6a265bc2d27f9965a1a3abb33eaf61a4bd433a1257b241c183a871c12a57db`. Its version/backend/frontend hash metadata match hosted `/ready`; this is not a byte read-back of the hosted filesystem. It is a possible **pre-006** application fallback, supports 004/005 only, and is unsafe after 006/007. A verified 007-compatible fallback package and encrypted-content/key handling runbook are PENDING.

**New local packaging blocker:** `scripts/prepare_app_service.py` still emits `supported_migrations: ["004", "005"]`; `backend/app/release.py` fallback and actual verifier support 004–007. Packaged metadata overrides the fallback. Before producing the latest release, make a separately scoped, tested local metadata correction with evidence for the real supported matrix; do not falsely label compatibility. No fix or package build was performed in this read-only phase. Old readiness/rollout tools also pin historical versions/004 targets; do not execute them as the current deployment plan.

The allowlisted App Service builder excludes secrets, databases, tests and migration operator files. Build same-origin frontend assets, include nested application modules and pinned requirements, preserve full member hashes and release identity, and distribute reviewed migration files separately to the authorized operator. Startup is one worker and runs **no migrations/install commands**. Avoid the old Docker startup migration path.

## 8. Proposed ordered deployment checklist — NOT EXECUTED

1. **Local preparation, PENDING:** resolve package metadata mismatch, review exact dirty-tree source/member manifest and supported 005/006/007 matrix; build/test same-origin frontend, candidate and schema-compatible fallback, inspect extracted imports and pin ZIP hashes. This needs a new implementation/preparation task; no cloud approval is implied.
2. **Recovery gate, PENDING:** refresh SQL revision/schema, catalog counts, backup/PITR metadata, exact recovery point and operator permissions; establish RPO/RTO/cutover validation. **Explicit approval** for any restore rehearsal, copy or resource/cutover change.
3. **Approve exact execution scope, PENDING:** target, artifact hashes, schema 005→006→007, transaction/grant scripts, operators, maintenance interruption, session override, key custody/settings, fallback and acceptance budget. **Explicit user approval required** for cloud changes and live acceptance; historic approvals do not authorize this rollout.
4. **Deploy compatible bridge on 005, PENDING:** after approval, deploy a verified 005/006/007-compatible release with protected capture/cleanup off; verify new worker/release and existing SSO-only behavior. Preserve current identity/provider settings and LEGACY mode. **Deployment/restart approval required.** If verification fails here, restore the pinned current 005 artifact/settings under approved rollback scope.
5. **Quiesce and preflight, PENDING:** block new traffic under the approved maintenance procedure, drain/reconcile reservations, recheck tenant consistency and retained-row baselines immediately before DDL. **Operational interruption and any reconciliation writes require approval.** Do not force-delete reservations/history.
6. **Migrate and grant in order, PENDING:** authorized operator applies reviewed 006, verifies marker/objects/history/row preservation, then 007; coordinate runtime object-level grants/visibility before exposing each boundary. Stop on any partial state; no stamping, downgrade, blind retry or fixed-role escalation. **Separate migration/permission approval required.**
7. **Session/SSO and role settings, PENDING:** approved change to `SSO_SESSION_MINUTES=120` if permitted, preserve SSO=true/demo=false/legacy credentials=false and exact origins; add only explicitly approved existing-identity memberships if User/Reviewer acceptance needs them. No registration change or secret rotation is currently justified. **Settings/membership/restart approval required.**
8. **Protected-content configuration, PENDING:** operator provides stable protected keys/IDs and key retention policy without disclosing values; enable capture and cleanup only after 007/grants and healthy compatible worker. **Key provisioning/settings/restart approval required.** Verify heartbeat before admitting traffic. No additional Azure service.
9. **Post-deployment read-only checks, PENDING:** exact release/member hashes, health/ready, actual 007, supported-migration metadata, actual worker configuration, schema/grants/triggers/FKs, key-presence booleans/cleanup health and unchanged provider destinations. No real provider success inferred from 200/configuration.
10. **Bounded acceptance, PENDING:** separately approved fresh timely SSO login, Admin/User portal/RBAC and 120-minute expiry evidence, refresh/logout/revocation; approved synthetic workflow for LEGACY/MULTI, all decisions, protected review/reveal/audit/disposition, uploads, history/filtering/analytics/usage/sessions. Any real generation/moderation/export has an explicit call/cost/data budget and stop-on-first-unexpected-failure rule. An export is a storage write; independent read-back needs authorized access. Do not exercise these now.
11. **Rollback criteria/procedure, PENDING:** stop on wrong worker/revision, schema/permission drift, failed SSO, unhealthy cleanup, unavailable required keys, tenant/RBAC/audit failure or unacceptable provider/export errors. Before006 use the pinned current 005 artifact only within approved scope. After006/007 retain schema and use a verified compatible fallback; disable capture/reveal if needed while retaining keys and cleanup after007. Never auto-downgrade. Any data restore/switch requires separate approved recovery plan and treatment of post-point audit/data loss. Do not globally revoke sessions or change secrets speculatively.

## 9. Remaining blockers and unverified checks

Deployment is blocked by unapproved migrations/grants/window; stale package compatibility metadata; no verified 007-compatible fallback; unestablished restore authority/drill/RPO/RTO; hosted 60-minute override; absent protected-review key/capture/cleanup setup; and missing exact release/settings/live-acceptance approval. Current 005 SSO settings/redirect metadata are consistent, but successful current-release browser login, effective fresh-cookie lifetime, User/Reviewer memberships and role acceptance, provider/storage data plane, production key persistence/cleanup health, actual SQL Server 006/007 operation and load/failover are unverified. No tests are claimed to have run in Azure.

Only this report and sanitized evidence under `docs/evidence/phase6-readonly-2026-11-06/` were added. Local SQLite remains revision003 with unchanged fingerprint, confirmed read-only. No Git commit/reset/clean/stash/discard, source correction, package build, Azure mutation or production login occurred. STOP: plan prepared, not executed.
