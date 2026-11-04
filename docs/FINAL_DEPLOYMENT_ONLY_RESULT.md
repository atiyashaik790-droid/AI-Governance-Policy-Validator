# Deployment-only verification result

31 October 2026, Asia/Kolkata. **STOPPED: deployment prerequisites incomplete. No deployment performed.**

URL: https://app-governance-validator-atiya-1026.azurewebsites.net

Target release: 1.1-544cbf32d11a251a. ZIP checksum freshly matches 3d81bdfca85f4df3b4786562283bce4d599d34662993f2c21623eeb6d3286992.

| Check | Fresh actual result | Status |
|---|---|---|
| SQL migration | Sole revision 003; required revision 004 not applied | BLOCKED |
| New schema | All six required 004 tables absent | BLOCKED |
| Runtime permissions | App principal belongs to governance_validator_web_runtime; required new-object grants unavailable because schema is absent; no explicit alembic SELECT grant observed | BLOCKED |
| Existing frontend shell | HTTP 200; unchanged shell hash | PASS for existing deployment only |
| Existing backend health | HTTP 200 | PASS for existing deployment only |
| Existing readiness | HTTP 200; this old release response does not establish revision 004 readiness | PASS for existing deployment only |
| Existing API schema | HTTP 200, API version 1.0.0; new session endpoint absent | PASS for old API; target release NOT VERIFIED |
| Active deployment | 8c2639f4-41d7-4787-bce4-e7253ecbb4b2; active, complete, status 4 | VERIFIED unchanged |
| Actual application build identifier | Not exposed by current public API; do not confuse API version or deployment ID with release fingerprint | UNKNOWN; target 1.1-544cbf32d11a251a not verified hosted |
| Authentication | Not tested; login creates SQL session/audit data and user prohibited data changes in this deployment-only task | NOT TESTED |

Exact prerequisite authorizations: first previously prepared recovery-drill authorization (A), because migration recovery gate remains unverified; then reviewed migration 003→004 (B), conditional on recovery; then reviewed least-privilege grant script (C), conditional on migration. These cannot be executed under deployment-only scope. No schema or permissions were bypassed. Once prerequisites are completed and verified, request/record explicit deployment authorization for the exact release if not already unambiguously approved. This turn did not deploy.

No Web App, plan or hosting infrastructure created; existing architecture/configuration untouched. No paid AI/moderation, ADLS export, synthetic data changes, login, migration, grant, source-code modification or application restart. Frontend asset/browser and authentication acceptance of the candidate remain pending successful rollout and an allowed read-only/authentication verification method.

Evidence: [fresh read-only preflight](evidence/deployment-only-2026-10-31/preflight.json). Prior exact commands/scopes: FINAL_HOSTED_APPROVAL_PLAN.md, FINAL_BOUNDED_RECOVERY_PLAN.md and FINAL_EXECUTION_APPROVAL_CHECKPOINT.md.
