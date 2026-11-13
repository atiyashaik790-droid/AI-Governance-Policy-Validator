# Protected original prompts — local Phase 2

Feature default: **off**. No hosted database or Azure configuration was changed.

## Storage and governance

Operator-reviewed additive migration **007 follows 006**. Hosted 005 must first follow the separately reviewed 006 deployment plan; never stamp a revision or auto-upgrade at application startup. Only disposable SQLite fixtures were migrated during verification. 005/006 remain usable with capture disabled. Readiness explicitly checks the selected schema and required runtime permissions.

`review_protected_content` is separate from execution JSON, audit, analytics and export snapshots. Its composite tenant/review foreign key, binary ciphertext, bounded nonce/ciphertext, absolute epoch expiry, seven-day constraint and update-denying database trigger protect pending content. The runtime needs SELECT/INSERT/DELETE on this table, not UPDATE. No plaintext column exists. Rows are created atomically with the final HUMAN_REVIEW execution and case; ALLOW/BLOCK/REDACT never capture. Input and output holds retain the **exact typed input prompt**, including whitespace and Unicode. For PDF/DOCX/TXT, typed input is passed separately; neither files, extracted text, combined model input nor model output are retained in this table. Existing reservation fences and one-dispatch semantics remain intact.

On revision 007 all new assignment/disposition notes accept only the fixed structured reasons shown in the UI (or empty). This deliberately prevents reviewers copying held secrets into ordinary audit notes. Historical immutable notes are not rewritten; existing sanitization still applies. Approval remains APPROVED_RESUBMIT_REQUIRED, never generation or release. Resubmission runs all current policies again.

## Encryption and operator configuration

AES-256-GCM uses a random 12-byte nonce and full authentication tag. Canonical AAD binds tenant, case, execution, content kind, format version and absolute expiry. A unique key/nonce index rejects accidental nonce reuse. Invalid UTF-8, missing keys, authentication failures, unsupported formats and persistence failures fail closed without returning content.

Set `REVIEW_CAPTURE_ENABLED=true`, `REVIEW_CLEANUP_ENABLED=true`, `REVIEW_CONTENT_ACTIVE_KEY_ID` and `REVIEW_CONTENT_KEYS_JSON` in a protected runtime environment. Key JSON is an ID-to-base64 mapping of independently generated 32-byte keys; no production key or generated default is supplied. IDs are versioned and bounded; duplicate IDs and malformed keys are rejected. Never reuse provider/SSO credentials, commit keys, print the environment or put it in diagnostics. Environment access and process dumps require operator protection. No Key Vault or extra service is introduced.

For rotation, deploy a keyring containing both old decryption keys and the new key, then select the new active ID on every worker. Retain old keys until every corresponding row has been purged, including applicable encrypted backup retention. Changing a key's bytes under an existing ID is forbidden operationally. Removing a required old key makes its content unavailable; there is no plaintext fallback. Key compromise requires incident handling and operator rotation; this feature does not provide an external key-management service.

## Cleanup and availability

A bounded cleanup task starts asynchronously with the application and repeats every 15 minutes. Each pass deletes at most 200 expired rows in batches of 50 with a two-second work budget plus bounded database calls. Conditional tenant/review/expiry deletes arbitrate concurrent workers; expiry audits are committed with deletion. Unsuccessful/backlogged passes retry after 30 seconds. Cleanup loads no ciphertext. Startup is nonblocking, but protected capture/readiness are unavailable until a healthy pass completes. A failed/overdue (>960 seconds) heartbeat blocks new governance admission when capture is enabled, before any provider dispatch. Shutdown disables capture and drains the active bounded cleanup pass.

Retrieval is denied at the absolute seven-day timestamp even if physical cleanup has not run. Approval/rejection deletes ciphertext **in the same transaction** as the decision and audit. A failed disposition preserves pending content. Cleanup and access events contain IDs only, never prompts, matches, keys or ciphertext.

**Cleanup is availability-dependent. Prolonged application/database outages can delay physical deletion. There is no guaranteed 24-hour deletion SLA.** Backup/replica copies and forensic storage require the operator's existing restricted-access retention/deletion policy; deleting live rows does not erase backups. A strict outage-independent physical deadline would require infrastructure outside the approved scope.

Application rollback: turn capture off, keep `REVIEW_CLEANUP_ENABLED=true` on a compatible application worker, and retain schema 007 and required decryption keys until content expires/resolves. Schema downgrade intentionally refuses to destroy protected content or relabel a live 007 database as 006. Do not deploy a pre-007 application against a 007 database. Reverting schema requires a separately reviewed data disposal and migration plan.

## Access and interface

POST `/api/reviews/{id}/content` has an empty strict body and a strong `If-Match` case version. It requires a currently enabled authenticated session, Admin/Reviewer role, matching tenant, explicit assignment **including Admin**, pending status and unexpired content. Existing Entra membership verification, same-origin CSRF, User endpoint restrictions and per-user reveal limits remain enforced. Assignment/disposition and reveal serialize through the case lock. A metadata access audit must commit before plaintext is returned. Responses use Cache-Control: no-store. General review/history/export endpoints never join ciphertext or return plaintext; retained published versions supply policy labels.

The case UI provides identity/event-time role (Not recorded historically), retained policy names/versions, safe governance categories, assignment, structured notes and decision history. Revealing requires an explicit click. Text uses a plain preformatted element, without HTML, Markdown or links. It is held only in component memory, clears on close/navigation/selection/signout/tab hiding/local reassignment or disposition, and expires within five minutes or absolute expiry. Metadata is polled every ten seconds while revealed to revoke the view after remote changes; already viewed content cannot be remotely erased from a person's memory or screenshots. Technical metadata is a separate disclosure. Content is never put in local/session storage or console logs. Historical cases show never retained, expired, purged or unavailable; metadata-only histories cannot be reconstructed.

Production rollout, hosted migration, real key provisioning, runtime grants, backup policy review and SQL Server integration verification remain operator tasks outside this local approval. SQL Server DDL is compiled offline in tests; no live SQL Server was contacted.

## Local verification and phase file inventory

Focused verification used disposable migrated SQLite databases, synthetic documents/keys, fixture providers and mocked Entra exchanges. The affected backend regression run passed 275 tests; the final security/reporting/offline SQL Server contract run passed 88 tests (overlapping scopes). Frontend focused runs passed 50 and 46 tests (overlapping review-component scope). Ruff, ESLint, TypeScript build checks and Vite production build passed. Final protected-review migration checks include actual Alembic downgrade refusal with live ciphertext preserved. No hosted schema, production keys, provider transport or deployment was used.

Files changed specifically for this phase (earlier working-tree changes remain separate):

```text
.env.example
backend/app/config.py
backend/app/main.py
backend/app/models_review_content.py
backend/app/protected_reviews.py
backend/app/release.py
backend/app/routers/document_uploads.py
backend/app/routers/protected_reviews.py
backend/app/routers/reviews.py
backend/app/routers/system.py
backend/app/schema_compatibility.py
backend/app/schema_manifests.py
backend/app/services/governance.py
backend/app/services/multi_policy_governance.py
backend/app/services/policy_sets.py
backend/app/services/reporting_v2.py
backend/app/services/reviews.py
backend/migrations/env.py
backend/migrations/versions/007_protected_review_content.py
backend/requirements.txt
backend/tests/test_protected_reviews.py
frontend/src/ReviewContent.tsx
frontend/src/ReviewContent.test.tsx
frontend/src/main.tsx
frontend/src/styles.css
docs/PROTECTED_HUMAN_REVIEW.md
```
