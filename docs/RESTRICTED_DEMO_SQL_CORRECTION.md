# Narrow SQL Server compatibility correction

1 November 2026. The initially approved 1.2 release deployed successfully as deployment `ade0e12d-9394-4a4e-9b83-c74fad107d98`; one worker refresh activated it. A SELECT-only Azure SQL verification found error 8120 in the new usage statistics query. No authenticated acceptance or paid provider/storage tests were run before this discovery.

## Correction

SQL Server does not treat repeated positional placeholders in a grouped CASE expression as equivalent. The corrected query groups by the stored status column, separately counts expired reservations, and combines those counts in Python. It preserves tenant filtering, quotas, active leases, historical statuses and all existing data. The corrected query has passed actual SELECT-only execution against the existing Azure SQL database, with zero active reserved operations observed.

Only `app/usage.py` and generated `release.json` differ in the ZIP from the first candidate. Frontend assets and all other application files are unchanged. Existing schema remains 004; no migration, grant, resource, setting, secret or account change is included.

Validation: **434 backend tests passed**, **12 corrected exact-ZIP smoke checks passed**, Ruff lint/format passed, and the corrected usage query passed SELECT-only Azure SQL execution. Existing frontend checks remain applicable because frontend bytes are unchanged.

## Exact corrected artifact

- Release: **`1.2-fd9d6fee6af8aa17`**, API 1.2.0.
- Package: `artifacts/restricted-demo-20261101/governance-restricted-demo-1.2-sql-portable.zip`.
- SHA-256: **`390ca1e896a740754e93f7aa7b3881e8ce32912776c2c1b44b2307715c7d88a9`**.
- Size: 246,053 bytes.
- Same existing App Service and preserved 1.1 rollback package as [the approved plan](RESTRICTED_DEMO_RELEASE_PLAN.md).

The deployment/restart may cause several minutes of interruption. The approved live acceptance bounds were unchanged: at most 10 sessions, 2 dedicated policies, 12 executions, 2 generation calls, 8 moderation calls, and one metadata export with the existing stated allowances. No additional paid-call allowance is requested.

The user explicitly approved this exact corrected artifact: “Deploy correction and continue live tests.” It was submitted once under a separate deployment ledger. Azure deployment `22837d1a-eea5-4d12-89bc-5243c9f232e1` completed and is active. The client returned an uncertain result; no second upload was attempted. One approved worker refresh activated the correction after a slow warm-up. API metadata, readiness and all public asset fingerprints match. See [live results](RESTRICTED_DEMO_LIVE_RESULTS.md) for executed acceptance and its remaining storage-read limitation.
