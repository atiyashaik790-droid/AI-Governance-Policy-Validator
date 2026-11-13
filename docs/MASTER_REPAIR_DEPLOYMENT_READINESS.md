> **Superseded execution gate, 7 November 2026:** retry-9 is consumed and temporary SQL creation is now blocked before external operations. No approval in this historical preparation permits another run. An independent expiry executor remains unverified; see [current readiness](FINAL_END_TO_END_DEMO_READINESS.md). Do not update pins to bypass this block. Recovery/deployment approvals remain separate.

# Master repair deployment readiness — PARTIAL

7 November 2026, Asia/Kolkata. Read-only local review; no Azure/provider calls or production mutations. Corrected candidate **1.2-240cc70e239a595f**, SHA-256 `274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22`, is packaged and locally tested; see [master repair result](MASTER_REPAIR_RESULT.md). This report authorizes no execution.

## Evidence and limits

[Retry-8](PHASE6B_APPROVAL_A_RETRY8_RESULT.md) passed temporary SQL migrations through 008, assignment, authorized/unauthorized reveal, access audit, encryption and seven-day retention assertions. Expiry cleanup failed; ciphertext preservation and remaining failure cycles were not reached. Independent deletion was confirmed. SQLite and mocked providers cannot establish Azure SQL or hosted acceptance.

[Latest SSO-only report](SSO_ONLY_DEPLOYMENT_ACCEPTANCE.md) records schema 005, SSO enabled, demo/legacy access disabled and 18 hosted denial checks passed. Fresh interactive Admin/User acceptance remains pending. Older revision-003/004 recovery and demo-authentication reports are historical.

## Recovery and independent rollback

Recovery B remains unauthorized. Refresh source revision-005 baseline, actual backup/PITR window, exact restore timestamp, isolated destination, responsible operator/data-plane access, tier, deadline, cost and cleanup scope. After separate approval require actual restore completion, SELECT access, schema/catalog/revision, counts/relationships, retained ciphertext/key checks, source preservation and sanitized evidence. Backup metadata and local ZIP rollback cannot prove database recovery. Production cutover and acceptance of lost post-point writes require explicit scope.

The [independent rollback ZIP](../artifacts/final-demo-readiness-2026-11-07/rollback-1.2-677a11e4b649fa7d.zip) was locally SHA-256 verified: `be1ab97768954fecb5cf26b255bfcecf2a22811848ca910536846b3784174ee9`. Historical [eight rollback tests](evidence/final-demo-readiness-2026-11-07/independent-rollback.log) and [separate-process decrypt test](evidence/final-demo-readiness-2026-11-07/cross-release-ciphertext.log) passed. The preserved release shares the proven slow-cleanup defect and is retained as historical evidence. A [distinct repaired rollback](../artifacts/master-repair-2026-11-07/rollback-cleanup-fixed.zip), **1.2-230d63e0c546e0ba**, SHA-256 `b52287bbf048a66a9f7233753a3fb95730397016f03074d4deb399c1e74c0d29`, uses that older release with only the cleanup correction. [Nineteen compatibility/slow-cleanup tests](evidence/master-repair-2026-11-07/independent-rollback.log) and [two separate-process ciphertext tests](evidence/master-repair-2026-11-07/cross-release-ciphertext.log) passed against original and repaired rollback; database bytes remained unchanged. Shared code limits protection against shared defects. Retain stable keys and cleanup capability; never drop ciphertext or downgrade 007/008 protections.

## Production preparation

Production C–F remain unauthorized. Prepare quiet/drain window, fresh revision/data/catalog/grant baseline, recovery point and approved recovery/cutover procedure. Reconfirm contained managed-identity SID and existing runtime role. Apply frozen 006→007→008 using operator tooling; verify retained hashes and readiness at boundaries. No startup migration or automatic downgrade.

Locally verified artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| [006 migration](../backend/migrations/versions/006_multi_policy.py) | `e9627d8f1b4c1f6385e1573df9bbd9280beef4f7d93bb2b1c3f6ef8a9fbfe9dc` |
| [007 migration](../backend/migrations/versions/007_protected_review_content.py) | `f451e1e83c735b333d5c10b012772cbfa1bf3fd9efe59c1dfbc8c8e2f9f7a8ce` |
| [008 migration](../backend/migrations/versions/008_execution_immutability.py) | `d95c0644a256e7a029e0f43e6fc594391b9846c7a5f469755ae581acc3641eb6` |
| [006 grants, review only](../deployment/phase6a-runtime-006-grants.REVIEW_ONLY.sql) | `28f1a97fffdeb5c268a328a454938ab9deb83ed94c9b2b9187b8039ab150bdc0` |
| [007 grants, review only](../deployment/phase6a-runtime-007-grants.REVIEW_ONLY.sql) | `9d7f4d193154c82c4f60885db0b544c730bd1d9cccab6e379bf406489e9ff2b9` |

Grant proposals default to approval disabled and guard exact database, revision, identity and role. 006 grants required object operations; 007 grants protected-content SELECT/INSERT/DELETE without UPDATE. 008 adds an immutability trigger and needs no new grants file. Verify effective execution UPDATE/DELETE denial, immutable history/audit and actual managed-identity authentication. Temporary EXECUTE AS does not prove runtime authentication. Securely check stable review-key presence/format, Entra/session settings and exact release checksum before existing-Web-App deployment.

## Hosted acceptance matrix

All rows remain pending on the corrected deployed candidate. Execute only within separately approved hosted mutation/provider scopes. Stop on critical failure and retain sanitized evidence.

| Workflow | Required acceptance/evidence | Proof boundary |
| --- | --- | --- |
| Release/runtime | Served release/assets match candidate; 008 health/readiness under actual runtime identity; truthful healthy cleanup execution | Local ZIP/temporary SQL cannot prove hosted runtime |
| Entra Admin/User | Interactive login for approved identities; expected role/tenant/workspace; protected routes enforce both roles | Historical denial probes do not prove interactive login |
| Sessions | Refresh identity, logout/revocation/expiry denial, CSRF/tenant isolation, cookie and absolute-expiry alignment | Local synthetic sessions support but do not replace hosted checks |
| Admin portal | Dashboard, policy lifecycle/MULTI/simulation, history, analytics, audit, critical navigation/buttons | Record sanitized operation/status/durable evidence |
| User portal | Chatbot/uploads, type/size controls, tenant boundaries, Admin-route denial | Hosted synthetic writes need scoped approval |
| Governance | PII REDACT, secret/keyword/moderation BLOCK, allowed generation/output inspection, stored score/policy evidence | Mocks cannot prove real-provider integration |
| Human Review | Assignment, unauthorized/unassigned/stale denial, exact reveal/no-store/access audit, resolution/resubmission and purge | Reuse SQL evidence only under valid code/config comparisons |
| Retention/encryption | Stable-key decryptability, ciphertext preservation, seven-day bound, actual expiry deletion and immutable expiry audit | No exception or uncertain rowcount alone is insufficient |
| Failure/recovery | Missing-grant/schema/audit/provider fail-closed paths; transactional migration rollback; retained data/catalog unchanged | Remaining SQL failure cycles need Azure confirmation |
| Generation/moderation | Bounded synthetic real operations through configured wrappers, output enforcement and sanitized failures | Separate real-provider authorization required |
| ADLS | Approved synthetic export, checksum read-back, durable audit and authorized exact-object cleanup | Upload alone insufficient; cleanup needs explicit scope |
| Settings | NOT_CONFIGURED, CONFIGURED_NOT_VERIFIED, VERIFIED, FAILED, STALE; correct UTC timestamps/tenant/config binding; passive refresh | Mocks prove state logic, not real hosted VERIFIED |

[Verification contract](INTEGRATION_VERIFICATION.md): verification defaults disabled. Explicit Admin confirmation and SQL rate limit precede only the named bounded operation. VERIFIED requires durable matching evidence; latest failure takes precedence; successful evidence becomes stale after the freshness window (default 24 hours). ADLS requires checksum read-back. Include synthetic-object cleanup in real-storage approval. No automatic provider calls from refresh/startup/readiness.

## Next mandatory gate

Complete focused local repair, remaining-assertion review, extracted-candidate checks and release manifest. Request fresh Approval A pinned to the corrected candidate/checksum and bounded temporary target. Retry-8 is consumed; no current approval permits resource creation. Recovery B, production C–F and live providers remain separate. READY requires mandatory Azure and hosted acceptance to pass.
