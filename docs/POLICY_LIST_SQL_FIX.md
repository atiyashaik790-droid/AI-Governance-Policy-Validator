# Policy list database error — 1 November 2026

The hosted `/api/policies` returned HTTP 503 while `/ready` and authenticated settings returned 200. Both policy management and the simulator load this endpoint.

The list query projected two bare `EXISTS` predicates for `has_published_versions` and `is_active`. SQL Server requires a scalar expression in the SELECT list. Both now use `CASE WHEN EXISTS (...) THEN 1 ELSE 0 END`; response booleans, tenant scope, filtering and pagination remain intact.

Validation: 16 pagination tests, including SQL Server compilation for both pagination modes, and 27 governance/acceptance regressions passed. Ruff lint/format passed. The corrected SELECT passed actual read-only Azure SQL execution for the first page, second page and search.

Package: `artifacts/restricted-demo-20261101/governance-policy-list-fix.zip`, SHA-256 `6d54ac74740dfacde4e55c284996a06d3b3c465d2a86afa63d99d3e5f05efb85`, release `1.2-37d875d722719d8a`. Relative to deployed `1.2-fd9d6fee6af8aa17`, only `app/main.py` and `release.json` change. No schema or permission change is needed. The previous ZIP remains available for rollback.

## Hosted verification — 2 November 2026

Deployment `e9431c40-3974-4e53-8ee0-9efb558bf257` is complete, active, status 4. Hosted readiness reports the expected release `1.2-37d875d722719d8a`.

Authenticated policy listing, pagination, search, enabled filtering and published-status filtering all returned HTTP 200; boolean flags passed response checks. Both `/policies` and `/simulator` page routes returned HTTP 200. The temporary diagnostic session was revoked. No generation, moderation or export was invoked. Exact results: [hosted evidence](evidence/policy-list-fix-hosted.json).
