# Phase 6A — pre-deployment hardening and recovery plan

**PARTIAL. GO for the next approval/preparation review; NO-GO for Azure deployment.** Safely addressable local packaging work, compatibility/rehearsal tests, grant proposals and configuration/recovery procedures are complete. No security architecture, application feature, schema migration, approved fingerprint, Azure resource, hosted data/configuration or production key was changed. Mocked/SQLite success is not Azure SQL or production readiness.

## 1. Baseline, scope and corrected causes

Phase 6 verified hosted release `1.2-ca5df7c1dc19e525`, database **005**, explicit session override **60**, missing protected-review configuration and seven-day backup retention. Those are prior read-only observations, **not refreshed cloud checks in Phase 6A**. Local revision003 is preserved. Existing working-tree edits were retained.

The package builder carried forward the historical `[004,005]` declaration even though the current revision-specific verifier, mappings and application support 006/007. Packaged `release.json` takes precedence over the runtime fallback, so a correct unpackaged default did not correct packaged metadata. `scripts/prepare_app_service.py` now declares **004/005/006/007**, keeps minimum004 and SSO minimum005, and includes the schema declaration in the deterministic build-version digest together with the complete file-hash map. A different compatibility contract cannot silently reuse the same file-derived version. Existing nested-module discovery, secret/database/migration exclusion, exclusive-create packaging and same-origin checks were preserved.

The initial new rehearsal fixture incorrectly inserted a nonexistent `inference_usage.day`; that test-only mistake was corrected. It exposed no application defect. No application implementation or migration correction was required by the completed tests.

## 2. Candidate and fallback artifacts

| Property | Candidate | 007 recovery/fallback |
|---|---|---|
| Artifact | `artifacts/phase6a-2026-11-06/candidate.zip` | `artifacts/phase6a-2026-11-06/fallback007.zip` |
| Version | `1.2-7d572934f2b78aeb` | `1.2-7d572934f2b78aeb` |
| SHA-256 | `a0a53d4899bd5672043420550fdbe01c7beca2a409b710fe180f8f52d516eb28` | `a0a53d4899bd5672043420550fdbe01c7beca2a409b710fe180f8f52d516eb28` |
| Intended settings | Capture off before007; controlled enablement only after approval | Capture/reveal off, cleanup on, existing keys preserved |

**Fallback limitation:** these are intentionally byte-identical frozen copies of the locally tested current code. No independently qualified earlier 007-compatible implementation exists in the inspected baseline. This fallback can recover damaged deployment files or revert protected-capture configuration while retaining 007 support; it cannot undo a defect shared by candidate and fallback code. Do not describe it as an independent previous-code rollback. Before rollout, either explicitly accept that limitation with an approved forward-fix/restore strategy or qualify a genuinely independent 007-compatible fallback. The old hosted 004/005 release remains unsafe after006.

`candidate-manifest.json` records every included member/hash and release metadata. Both ZIPs passed CRC, exact allowlist and member-hash verification. The production frontend was freshly built; no source maps, environment files, databases, tests, migration files or production secrets were included. All nested application modules are present. Build identity is deterministic for identical files/contract; `built_utc` and ZIP timestamps remain build-specific, so pin and retain the actual ZIP checksum rather than assuming reproducible ZIP bytes. Git HEAD alone does not identify this dirty working-tree release.

The actual production ZIPs—not only synthetic package fixtures—were extracted into temporary directories and tested. Their hosted entry point performed real hosting-configuration validation; SQL transport alone was replaced with local SQLite, then fixture providers/regex PII and synthetic OIDC/keys were used for functional checks. This does not verify native ODBC, managed-identity token acquisition, Presidio production startup or Azure networking.

## 3. Bridge compatibility and transition boundaries

| Revision | Local extracted-package evidence | Boundary |
|---|---|---|
| 004 | Hosted import, readiness, release contract, SPA/auth boundary, policy lifecycle, LEGACY ALLOW/HUMAN_REVIEW, integrity/FKs | SSO and MULTI unavailable; capture off. Included for the existing supported legacy contract |
| 005 | Above plus mocked SSO callback from `/chat`, secure cookie and 120-minute session | Actual hosted starting point; LEGACY only, capture off |
| 006 | Above plus MULTI activation/execution and v1 bypass rejection | Capture off; new grants/visibility required |
| 007 | Above plus encrypted original-prompt capture, seven-day expiry and audit | Capture requires stable keys and healthy cleanup |
| 007 fallback | Mock SSO, lifecycle, LEGACY/MULTI with capture disabled and cleanup healthy; a separate fallback process decrypts retained synthetic content internally without changing ciphertext/audit | No database downgrade; keep keys and cleanup. No plaintext output or reveal API bypass |

A separate running-process rehearsal retains a persisted synthetic application session and policy while applying quiescent005→006→007 migrations; the same application process resumes readiness and LEGACY generation at each boundary. This is **not concurrent migration traffic safety**. Production must stop admission, drain requests and reconcile reservations before DDL. The bridge should be deployed and verified on005 before either migration; it then remains installed through006/007. Enable MULTI separately and explicitly, after all checks. Do not migrate under the old hosted verifier.

## 4. Migration and failure rehearsals

All migrations ran only on temporary SQLite files. A representative005 database was populated through the extracted package with policies, versions, active assignments, executions, a pending Human Review case, audit events, memberships and server-side sessions. After006 and007 every original column/row in every005 table matched its retained snapshot; execution mode became LEGACY, foreign keys remained valid and original reviews were not backfilled with plaintext. Separate rehearsal checks retained audit records and append-only rejection at both boundaries.

006 preflight refuses RESERVED work **before** workspace objects appear; marker005 and the reservation remain intact. Existing regression coverage also rejects invalid legacy identities and tenant links. Injected007 table-creation failure leaves marker006 and audit intact; SQLite may retain the index created before failure. **Marker preservation is not proof of atomic rollback.** Stop and inspect catalog, constraints, triggers and retained data; never stamp, blindly retry or auto-drop partial objects. Existing tests verify007's downgrade refusal with ciphertext retained, tenant FKs, immutable ciphertext, failed audit commit denying reveal, transactional disposition, cleanup failure/backlog gates, missing/wrong-key failure, expiry and role/tenant/assignment restrictions.

SQL Server-specific DDL, physical types/checks/indexes and query contracts were compiled/reflected under existing mocks. Actual SQL Server005→006→007 execution, lock duration, collation/catalog differences, transaction/DDL failure semantics, runtime effective permissions and post-restore behavior remain **UNVERIFIED**. No claim of a successful Azure SQL rehearsal is made. Migration006 alters existing execution nullability and initializes workspace/event rows; it is not purely additive and needs an approved maintenance window.

## 5. SQL permission proposals

Prepared but never executed:

- `deployment/phase6a-runtime-006-grants.REVIEW_ONLY.sql`
- `deployment/phase6a-runtime-007-grants.REVIEW_ONLY.sql`
- `deployment/phase6a-runtime-permissions.READ_ONLY.sql`

| New object | Proposed runtime DML |
|---|---|
| `workspace_policy_states` | SELECT, INSERT, UPDATE |
| `workspace_policy_assignments` | SELECT, INSERT, UPDATE |
| `workspace_policy_assignment_events` | SELECT, INSERT |
| `execution_policy_evidence` | SELECT, INSERT |
| `review_protected_content` | SELECT, INSERT, DELETE; **no UPDATE** |

Object-level VIEW DEFINITION is proposed on those new tables for required reflection. Existing parent-object access/grants and append-only protections are retained; no broad schema/database permissions or runtime DDL are proposed. No identity or role is created. Existing current permissions are enumerated in Phase6 and its evidence.

Each grant proposal defaults to an approval guard of zero, checks the exact database and migration boundary, requires a freshly reconfirmed contained managed-identity client-ID/SID match and existing custom-role membership, and applies grants in a transaction. The identity confirmation placeholder intentionally prevents unattended execution. Do not substitute the SSO application client ID or assume object/principal ID equals contained-user SID.

Apply006's proposal at006 and007's at007 under the approved migration/grant boundary, with traffic quiesced. The SELECT-only verification must run as the actual application runtime identity and confirm DB/user/revision and each effective permission; an operator's HAS_PERMS result does not establish runtime privileges. Static tests enforce exact grant sets, approval/identity guards and absence of broad grants or mutating verification SQL.

Record pre-change grants and DENY/inheritance metadata before applying anything. No automatic REVOKE rollback is provided: revoking protected-content DELETE/SELECT or audit INSERT could break cleanup, retention and access auditing. Any rollback of grants requires separate object-by-object review, after proving retained workloads no longer need them.

## 6. SSO and session configuration checklist

1. Preserve SSO=true, demo-browser-login=false, legacy API credentials=false, existing tenant/client/server-side secret and matching public/CORS origin. No Entra secret or registration change is justified by local evidence.
2. Confirm exact Web callback `https://app-governance-validator-atiya-1026.azurewebsites.net/api/sso/callback` and registered root post-logout redirect. Keep state/nonce/PKCE, five-minute transaction limit and secure `__Host-` cookies (Secure/HttpOnly/SameSite=Lax/root path).
3. Review `deployment/phase6a-session120.REVIEW_ONLY.json`. The **only proposed session-setting delta** is `SSO_SESSION_MINUTES: "60" → "120"`. Confirm organizational/upstream controls allow it. This setting save/recycle requires explicit approval; it was not executed.
4. New sessions receive an absolute120-minute expiry; refresh/activity does not extend it. Existing persisted sessions keep their original expiry and are not mass-revoked or silently lengthened. Deployment is not a blanket sign-out. Membership disable/role changes and revocation remain checked on each request.
5. After approval, verify actual replacement-worker settings and one fresh synthetic-safe bounded login completed within five minutes, database expiry and Secure cookie lifetime without logging cookie/token values. Verify refresh, portal roles, logout local revocation before Microsoft logout and denied old session.
6. The Phase6 snapshot contained one enabled Admin and no User/Reviewer mapping. Any additional server-side membership for existing authorized Entra identities needs separate approval. Admin reveal still requires explicit assignment, including self-assignment.

Local tests prove mocked session/SSO contracts, not current Entra login, secret correctness or external session policy. Historical login failure remains unresolved live evidence; no real login was retried.

## 7. Human Review encryption/cleanup checklist

- Keep defaults capture=false/cleanup=false while on005/006. Before enablement require007, exact runtime grants/visibility, approved deployment and a healthy compatible cleanup worker.
- An authorized operator must supply an independent, stable32-byte AES-256-GCM key through the existing protected App Service settings process. Required names: `REVIEW_CONTENT_ACTIVE_KEY_ID`, `REVIEW_CONTENT_KEYS_JSON`; identifiers and base64 JSON must pass existing validation. No production key was generated, printed, copied, uploaded or embedded here. No Key Vault/new service is proposed.
- Preserve identical key bytes/IDs across workers/restarts/redeployments and recoverable configuration. Never generate keys at startup, change bytes under an existing ID or reuse provider/SSO credentials. Limit settings access/process dumps and retain a protected independent configuration recovery procedure: a SQL database restore does **not** restore these external keys.
- Enable `REVIEW_CLEANUP_ENABLED=true` and then approved capture only when schema/key/worker prerequisites are satisfied; both settings require approval. Capture enabled with invalid/missing key/schema or unhealthy cleanup fails closed. Verify only presence/health/shape booleans and audit metadata, never key bytes or plaintext in logs.
- Cleanup is bounded (at most200 rows, two-second work budget, roughly15-minute interval with failed/backlog retries); health must be fresh within960 seconds. Retrieval denies at seven-day absolute expiry, irrespective of deletion lag. Outages can delay physical deletion; backups can retain ciphertext longer.
- Reveal requires current session, Admin/Reviewer, matching tenant, explicit assignment, pending case, matching version, unexpired content and a committed access audit. Disposition deletes ciphertext atomically and never automatically releases/generates held content. Old metadata-only cases are not backfilled.
- For eventual approved rotation, add a new key ID while retaining old decryption entries, then select the new active ID consistently. Retain old keys through live content and restricted backup-recovery obligations. This phase performs **no rotation**. Losing a required key permanently prevents decryption; there is no plaintext fallback.
- Fallback profile `artifacts/phase6a-2026-11-06/fallback007-settings.REVIEW_ONLY.json` disables capture/reveal, retains cleanup and every required key. Confirm cleanup continues; do not remove schema/keys while retained content exists. Local two-process synthetic-key tests preserve ciphertext/audit; production key persistence is UNVERIFIED.

## 8. Ordered recovery and deployment plan — proposal only

1. **Before approval:** freeze candidate/fallback hashes and the complete dirty-tree manifest; review the fallback's identical-code limitation. Qualify an independent007-compatible fallback or explicitly accept a forward-fix/restore strategy. Define operators, window, stop criteria, RPO/RTO and exact rollback authorization.
2. **Recovery gate:** refresh actual source revision, backup retention, latest usable restore point and source/destination access. Phase6 observed seven-day retention, not tested recovery. Verify the designated operator's effective management authority, scope, deny policies and data-plane access; SQL DDL rights alone do not grant cloud restore. Microsoft documents Contributor/SQL Server Contributor at the relevant subscription/resource-group scope as supported management roles; this is a requirement reference, not proof this operator has them. [Azure SQL backup recovery documentation](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql).
3. **Proposed drill, separately approved only:** restore a chosen pre-change point to an explicitly named temporary database on the existing logical server; isolate all provider traffic and use synthetic/mocked application adapters. Validate schema, retained counts/checksums, tenant links, audit triggers, membership/session treatment and key availability; measure recovery time and cleanup behavior. PITR creates a new database rather than replacing the original, so destination creation/cost, any endpoint/config cutover and cleanup require explicit approval. No new service architecture is proposed and no drill was run. [Microsoft recovery behavior](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql).
4. **Approved bridge deployment:** install exact candidate on005 with capture/cleanup off and preserved SSO/provider configuration. Verify replacement worker/version/member hashes and005 readiness. If deployment fails before migration, the pinned currently hosted005-compatible artifact can be restored under explicit rollback approval. Keep the database unchanged.
5. **Maintenance/drain:** stop new admissions, wait for in-flight inspections/generation/exports to finish, reconcile reservations under separately approved write scope, and record a fresh pre-DDL recovery point/retained baselines. Zero RESERVED at an earlier inspection is not a concurrency guarantee. Never delete history/reservations as a shortcut.
6. **006 then007:** approved operator applies the reviewed migration and matching grant proposal at each boundary, inspecting exact physical objects, trusted/enabled constraints, immutability and retained data before continuing. Keep traffic quiesced and LEGACY mode; no automatic migration at application startup. No Alembic stamping or automatic downgrade.
7. **Session/encryption enablement:** approved120-minute setting and any approved memberships; operator-supplied stable keys; approved cleanup/capture flags only after007 and healthy worker. Recheck actual worker configuration after any recycle. Do not speculate by rotating/re-entering SSO secrets.
8. **Post-change read-only gates:** exact release hashes,007 marker plus actual catalog, runtime effective grants/visibility, health/readiness and cleanup heartbeat, original-row preservation and configuration alignment. Stop before live traffic if any fail.
9. **Bounded live acceptance, separate approval:** timely fresh Microsoft login, Admin/User portals/RBAC/tenant negatives and absolute-session evidence; synthetic review assignment/reveal/audit/disposition, uploads, filters/history/analytics/usage; explicitly approved MULTI activation and reversibility checks. Any real generation/moderation/export requires a call/cost/data budget; export is a storage write and needs independent read-back authorization. No live acceptance is authorized or executed here.

### Failure-specific actions

| Failure | Required response |
|---|---|
| During006 | Keep maintenance active; inspect marker **and catalog**, retained identities/FKs/constraints/triggers/initialization. Do not retry partially applied DDL or run old code against a completed006. Choose separately reviewed forward repair or authorized restore |
| During007 | Preserve every created object, marker and key; stop capture. Inspect partial indexes/table/checks/trigger and actual transaction outcome. Do not drop ciphertext, relabel as006 or call downgrade. Forward repair/restore needs approval |
| Deployment/startup before006 | Restore exact pinned prior005 artifact/settings under approval; verify correct replacement worker and005 health. No DB rollback necessary |
| Deployment/startup after006/007 | Never restore pre006 code. Use qualified compatible code/configuration or approved forward repair. On007 retain keys/cleanup, capture off. Identical-code fallback cannot fix a shared application bug |
| Failed acceptance | Stop on first unexpected result; keep admission blocked when security/retention is uncertain. Preserve sanitized evidence. No broad account revocation, secret rotation or schema rollback by inference |
| Database restore/cutover | Treat post-point writes/audits as potentially lost and session revocations as potentially rewound. Preserve original DB/evidence, obtain data-owner decisions for reconciliation/cutover, and separately approve targeted session invalidation if needed. Do not blindly merge/replay governance history or revive revoked sessions. Keys must match restored ciphertext; expired content remains inaccessible and cleanup resumes before capture |

Application rollback never rolls back the database. All005/006/007 downgrades intentionally refuse destructive reversal. SQL restore cannot recover lost external encryption keys, and a pre-change restore can discard immutable audit events written after the selected point. Recovery is **not verified** until an authorized drill and validation succeed.

## 9. Verification results and commands

- Fresh full backend: **1,164 passed**, no failures/skips,107.04 seconds. This includes the initial nine new package/rehearsal cases.
- Follow-up: **88 passed** = expanded11-case transition group plus **77 readiness/script cases** (74 existing and3 new permission-proposal cases). No failures/skips.
- Final transition group: **12 passed**, no failures/skips, including same-process continuity; see `transition-final.xml`. Unique backend coverage is1,167 after all follow-ups; do not sum overlapping runs.
- Frontend: **131 passed /14 files**, including disposable React/FastAPI integration; no failures/skips.
- Actual pinned ZIP verification: **six successful extracted-package probes**,004–007 candidate and two007 fallback scenarios; both artifact allowlists/member hashes passed and retained ciphertext/audit matched across separate processes.
- Ruff across `backend scripts`: PASS. Frontend ESLint: PASS. TypeScript and production Vite build: PASS. Git whitespace check: PASS. Existing Starlette/Authlib deprecations and an Alembic path-separator deprecation were reported, not suppressed.
- Initial development-only transition run:8 passed,1 failed due to the incorrect fixture column; corrected and superseded by passing runs. No application failures remain in the executed local checks. Browser acceptance was not repeated; frontend source is unchanged and prior Phase5 browser evidence is retained.

Reproduction (local fixtures only; replace output paths to preserve saved evidence):

```bash
DATABASE_URL=sqlite:////tmp/phase6a-unused.db PROVIDER_MODE=fixture PII_MODE=regex \
  .venv/bin/python -m pytest backend/tests -q
DATABASE_URL=sqlite:////tmp/phase6a-unused.db PROVIDER_MODE=fixture PII_MODE=regex \
  .venv/bin/python -m pytest backend/tests/test_release_transition.py scripts/tests -q
DATABASE_URL=sqlite:////tmp/phase6a-unused.db PROVIDER_MODE=fixture PII_MODE=regex \
  .venv/bin/python scripts/tests/verify_phase6a_artifacts.py
.venv/bin/ruff check backend scripts
# From frontend/, run npm run lint; npm run build; and tests with
# GOVERNANCE_TEST_PYTHON pointing to ../.venv/bin/python.
```

The approved frozen probe fingerprint remains `e3530bb5af9199ee850f54f71984da4643dbd458c791dcd5b2c9a5b4e7612497`; application schema-helper fingerprint remains `b5da9f6e2f593f98be3750fe964260a54802bc375910b2b12312d926d08119e2`. Deliberate mismatch rejection and application-helper separation tests passed. The frozen historical probe still only certifies004; do not repurpose it for007 without review.

## 10. Exact files changed

Modified existing source: **`scripts/prepare_app_service.py` only** (the earlier recursive packaging changes were preserved).

New test/probe files:

- `backend/tests/test_release_transition.py`
- `scripts/tests/phase6a_package_probe.py`
- `scripts/tests/verify_phase6a_artifacts.py`
- `scripts/tests/test_phase6a_permissions.py`

New proposals: the three SQL files and session-setting JSON listed above. New deliverable: this report. Five artifact/profile/manifest files are under `artifacts/phase6a-2026-11-06/`; exact artifact/evidence file lists are in `docs/evidence/phase6a-local-2026-11-06/changed-files.json`. Ignored frontend production assets/incremental build output were regenerated. No frontend/backend application source, migration or prior report was edited.

Local SQLite remains revision **003**, SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`, unchanged. No Git commit/reset/clean/stash/discard was performed.

## 11. Remaining Azure-only gates and exact approvals

UNVERIFIED: actual SQL Server migration/failure/locking behavior; effective new runtime grants and physical catalog; Entra end-to-end login/secret correctness; replacement-worker120-minute configuration; production key custody/persistence/recovery and cleanup; provider generation/moderation/export/read-back; recoverable backup point, restore authority/drill/RPO/RTO and live load/failover. Existing metadata is not functional verification.

Before any execution require explicit approval of:

1. Exact candidate/compatible fallback hashes and the identical-code recovery limitation, or a newly qualified independent fallback.
2. Existing Azure target, execution window, operator identities, maintenance/admission drain and any reconciliation writes.
3. Reviewed005→006→007 migration steps, runtime object grants/metadata visibility and failure-stop/repair scope.
4. Existing App Service deployment/recycle and separately scoped post006/007 rollback/forward-repair actions; never an automatic schema downgrade.
5. The sole60→120 session setting delta and any named existing-identity membership changes.
6. Operator-controlled production key provisioning/storage/retention and capture/cleanup settings—no production keys are included here.
7. Any temporary-database restore drill, cost/retention/cleanup and cutover/reconciliation/session-invalidation plan.
8. Bounded real SSO/provider/storage acceptance with explicit data/call/cost limits.

**Recommendation:** GO to approval and recovery qualification; NO-GO to deployment until these gates are satisfied. Stop after this local verification. No Azure operation, production secret operation, deployment or live SSO/provider test was performed in Phase6A.
