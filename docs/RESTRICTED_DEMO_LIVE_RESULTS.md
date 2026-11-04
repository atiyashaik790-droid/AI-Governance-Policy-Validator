# Restricted demo live release results

1 November 2026. **The corrected application is deployed and healthy, and its hosted functional workflows passed. Complete operational acceptance remains open for independent ADLS checksum read-back and Docker execution.** This is a restricted demo release, not production certification.

## Deployed artifact

- App: [app-governance-validator-atiya-1026](https://app-governance-validator-atiya-1026.azurewebsites.net).
- Release: `1.2-fd9d6fee6af8aa17`; API `1.2.0`; existing schema `004`.
- ZIP: `artifacts/restricted-demo-20261101/governance-restricted-demo-1.2-sql-portable.zip`.
- SHA-256: `390ca1e896a740754e93f7aa7b3881e8ce32912776c2c1b44b2307715c7d88a9`.
- Deployment: `22837d1a-eea5-4d12-89bc-5243c9f232e1`, Azure complete/active. Submitted once despite an uncertain client response. One approved worker refresh activated the correction after a slow container warm-up. Rollback was prepared but not executed.
- Readiness, API metadata, public deep links, security headers and all packaged public asset hashes verified. Transient startup/read failures were resolved by subsequent read-only verification.

## Executed acceptance

All 13 functional checks passed against real hosted Azure SQL, generation/moderation and storage:

1. Four hosted role credentials exchange for expiring sessions backed by Azure SQL.
2. Root credentials cannot directly access protected APIs.
3. Developer mutation restrictions are enforced.
4. Missing/stale policy edit preconditions return 428/412.
5. Secret input blocks before model dispatch.
6. Real safe generation and output moderation succeed.
7. Duplicate feedback is rejected atomically.
8. Human review holds content before model dispatch.
9. Authors can track their own reviews.
10. Assignment ownership is enforced and sensitive review notes are redacted.
11. PII is redacted; linked resubmission and output gating succeed.
12. Analytics retain the input PII violation.
13. ADLS metadata export completes; an identical idempotency key returns the same export.

Hosted Chrome also passed login, all nine navigation routes, logout, desktop/mobile rendering and zero page errors. After responsive charts settled, mobile document width and viewport were both 390 pixels. These navigation checks do not claim every interactive action or formal WCAG certification.

Post-test SELECT-only Azure SQL checks verified zero active inference reservations, export snapshot content matching its stored SHA-256, and all four API test sessions revoked. Both browser sessions logged out successfully. The tenant had no active policy before acceptance, so there was no previous assignment to restore; the first synthetic acceptance policy remains active. Existing business records were preserved.

## Bounds and retained evidence

Used/reserved upper bounds: **6/10 sessions**, **2/2 synthetic policies**, **4/12 executions**, **2/2 generation calls**, **8/8 moderation-call allowances reserved conservatively**, **1 metadata export**, **1 feedback**, **1 review**. No additional paid generation/moderation is authorized by the exhausted allowance. Actual billing was not calculated or independently reconciled; the agreed cost allowances remain USD 1 generation, USD 1 moderation if billed, and USD 0.10 storage.

The two policies/versions, four executions, approved review, feedback, metadata export and corresponding audit/rate/session records are intentionally retained. Identifiers, export path and digest are in [live acceptance evidence](evidence/restricted-demo-2026-11-01/live-acceptance.json). No schema migration, grant, resource creation, account replacement, credential rotation, cleanup, overwrite or deletion was performed.

The verified credential file is `/tmp/governance-approved-deploy-obcsyrz6/demo-credentials.json`; **Admin, Developer, Reviewer and Auditor are all present and successfully authenticated**. Only runbook-documented locations were checked. No credential values are included in evidence. This temporary path is an operator prerequisite, not a durable recovery guarantee.

## Remaining prerequisites

The existing operator Azure CLI identity receives **403 AuthorizationPermissionMismatch** reading the exact exported object. Consequently, independent storage checksum verification is **unverified**. The acceptance runner stopped at that check, then revoked its sessions; its raw `STOPPED` status is preserved rather than rewritten as a full pass. The app's completed export and SQL snapshot hash do not substitute for an independent storage-byte checksum.

A storage owner can use an already-authorized reader to read only the recorded object and compare SHA-256 `68b56d5231edf02f1b4a161d4a0cfa7438fc574759079366f5165ed1f2c19b08`. Alternatively, an owner may separately approve narrowly scoped read access through the organization's normal access process. No grant or identity substitution was attempted. Do not regenerate the export or repeat paid acceptance to recover this check.

Docker is unavailable in this environment. Build/startup validation of the prepared Docker configuration remains required on a Docker-enabled host. Enterprise identity, security assessment, sustained SQL Server load/failover, operational ownership and formal accessibility acceptance remain separate production prerequisites.

## Evidence

- [Consolidated summary](evidence/restricted-demo-2026-11-01/summary.json).
- [Exact hosted release verification](evidence/restricted-demo-2026-11-01/sql-correction/hosted-release-verification.json).
- [Raw bounded live result](evidence/restricted-demo-2026-11-01/live-acceptance.json) and [operation ledger](evidence/restricted-demo-2026-11-01/live-operations.jsonl).
- [Storage read-back diagnostic](evidence/restricted-demo-2026-11-01/storage-independent-readback.json).
- [Post-live SELECT-only verification](evidence/restricted-demo-2026-11-01/post-live-sql-verification.json).
- [Hosted browser result](evidence/restricted-demo-2026-11-01/hosted-browser.json).
- [Local validation](COMPLETION_VALIDATION.md): 434 backend, 16 frontend, 52 fixture browser and 12 exact-package smoke checks passed; npm advisories zero.
