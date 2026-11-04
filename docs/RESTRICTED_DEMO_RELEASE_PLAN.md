# Restricted demo 1.2 — concrete deployment and acceptance plan

Prepared 1 November 2026 (Asia/Kolkata). **Prepared and locally validated; not deployed.**

## Exact candidate and target

- Existing App Service: `app-governance-validator-atiya-1026`.
- Existing resource group: `REPLACE_WITH_AZURE_RESOURCE_GROUP`.
- Existing subscription: `REPLACE_WITH_AZURE_SUBSCRIPTION_ID`.
- URL: `https://app-governance-validator-atiya-1026.azurewebsites.net`.
- Release: **`1.2-b67467d215710f03`**, API 1.2.0.
- Package: `artifacts/restricted-demo-20261101/governance-restricted-demo-1.2.zip`.
- SHA-256: **`92fcea24b8ab87c1879d7ec0ae22947d1eacf3755f4d80d4c1ae23e80c221805`**.
- Size: 245,908 bytes; 26 allowlisted files. No credentials, environment files, databases, migrations or tests are packaged. All packaged application source bytes match the current workspace.
- Existing required SQL schema remains **004**. No migration, resource provisioning, firewall change, permission grant, or secret rotation is part of this plan.

## Completed validation

433 backend tests, 16 frontend tests, 52 Chrome acceptance checks, 12 exact-package checks, backend/script Ruff lint+format, frontend lint+types+same-origin build, and an isolated clean frontend install/lint/build passed. npm reports zero vulnerabilities. The exact package smoke uses disposable SQLite and fixture services; it does not certify live cloud access.

## Proposed operational scope

1. Recheck existing target, current ready release/schema, required configuration presence and rollback checksum without printing secrets.
2. Upload this exact ZIP **once** to the existing App Service using the existing deployment method. Record submission intent and the server-side deployment ID. Poll its status; never blindly resubmit an uncertain operation.
3. Verify actual release/API/static assets, health/readiness, deep links, security headers, and root-credential/session behavior. Use existing provisioned accounts privately. No credentials or raw prompts/responses are printed.
4. Authenticated acceptance may create at most **10 expiring sessions**, **2 dedicated synthetic policies**, **2 published versions**, **12 execution/usage records**, **2 review cases**, **2 feedback records**, and corresponding bounded audit/rate-bucket records. Preserve existing business policies, history and exports. Activate a dedicated policy only in an identified disposable/demo tenant; if no such existing tenant can safely be used, stop before modifying active assignments. No cloud user/principal is created.
5. Provider acceptance: at most **2 generation calls** and **8 moderation calls**, using one harmless and one synthetic PII prompt, with no retries and a **USD 1 allowance for generation and USD 1 for moderation if billed**. These are agreed test bounds, not an enforced Azure spending cap. Stop on unexpected results or exhausted allowance.
6. Storage acceptance: **one new metadata-only JSON export**, fixed idempotency key, exact known-path read-back/checksum and a duplicate-key check that creates no second object. Allow **USD 0.10** for storage operations. Preserve the object as evidence. Never overwrite or delete existing storage data, add permissions, or retry an uncertain export blindly.
7. Record results and retained synthetic record IDs. Do not claim production certification. No commit or push is included.

## Expected interruption and compatibility

The single-worker deployment can interrupt the demo for several minutes and can interrupt in-flight operations. Use a quiet window. Existing revision-004 data remains intact. Root credentials now exchange for sessions by default, and policy-edit clients must send If-Match; unupdated external demo clients will need the documented migration. Existing valid opaque sessions remain compatible with the stored schema and identity mapping.

## Rollback

Preserved previous candidate: `artifacts/final-implementation-20261031/governance-reliability-final.zip`.

Verified local SHA-256: **`3d81bdfca85f4df3b4786562283bce4d599d34662993f2c21623eeb6d3286992`**.

Reconfirm it matches the currently serving 1.1 release before deployment. If the new release fails startup/readiness, deploy that exact preserved package to the same existing target, then verify old readiness/assets and read-only API behavior. Do not change SQL schema/data or replay uncertain inference/exports. Rollback removes these new application protections; preserve new audit/session/export records.

## Prepared command — not executed

```bash
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az webapp deploy \
  --subscription REPLACE_WITH_AZURE_SUBSCRIPTION_ID \
  --resource-group REPLACE_WITH_AZURE_RESOURCE_GROUP \
  --name app-governance-validator-atiya-1026 \
  --type zip \
  --src-path artifacts/restricted-demo-20261101/governance-restricted-demo-1.2.zip \
  --async true --track-status false
```

Deployment and live acceptance need authorization for this exact release and operational scope. The implementation request authorized code changes; it did not specify a new production deployment interruption, paid-call allowance or retained hosted test data.
