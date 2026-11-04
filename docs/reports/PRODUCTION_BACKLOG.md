# Production backlog — current local implementation status

Updated 31 October 2026. [FINAL_IMPLEMENTATION_REPORT](../FINAL_IMPLEMENTATION_REPORT.md) and [FINAL_PRODUCTION_READINESS](../FINAL_PRODUCTION_READINESS.md) supersede the implementation status below. Durable export recovery, demo session expiry/revocation, SQL quotas, strict input validation, configurable PII/moderation, server search, review annotations, bounded analytics, API resilience and route splitting are implemented and locally tested. Their SQL 004 migration, hosted rollout and cloud acceptance remain approval-gated. Enterprise identity, live operational recovery/security certification, dependency-tooling advisories and broad accessibility/browser/load acceptance remain open. The original 30 October backlog follows as historical context.

# Production backlog and accepted demo limitations

Updated 30 October 2026. These items are outside the completed controlled technical demo.
See [final acceptance](FINAL_ACCEPTANCE_REPORT.md) for verified scope and evidence.

| Area | Future work / current limitation |
| --- | --- |
| Enterprise SSO | Replace locally provisioned hashed bearer mappings with approved enterprise identity. Demo tokens have no automatic expiry, enterprise revocation or account-management workflow. |
| Production security | Review token lifecycle, secret rotation, tenant-level database enforcement, least privilege, tamper-evident audit retention, threat model and independent security assessment. Existing server RBAC and tenant checks remain active. No Key Vault or new service was introduced. |
| Durable export recovery | Upload happens before the SQL export/audit transaction completes. A storage write followed by database failure can leave uncertainty. Design durable recovery/idempotency separately; never blindly replay a failed or uncertain export. Conditional creation protects existing files. |
| Review workflow | Approval records metadata disposition and requires revised resubmission through all gates. It never releases stored content automatically. |
| Explainability | Scores are weighted heuristic control results, not legal compliance certification. Presidio/regex and moderation have distinct detection limits. |
| UI capabilities | Feedback aggregate is an API, without a dedicated aggregate panel. Existing audit controls provide listing/metadata/pagination; no new full-text audit search was added. Wide mobile tables scroll horizontally. |
| Operations | Define ownership, monitoring, backup/restore drills, retention and cost controls before production. App Service B1 remains one worker. Stopping the Web App alone does not stop App Service Plan charges. No resource deletion or tier change was performed. |
| Export scope | One bounded fresh JSON export was verified. CSV and error/no-overwrite contracts have local coverage; no fresh live CSV export was authorized. Further live Generate/Export operations need an agreed allowance. |
| Certification and performance | Chrome at desktop/tablet/mobile sizes was accepted for the demo. Formal WCAG, broad cross-browser, load, failover and Docker acceptance remain unverified and are not demo gates. |
| Input strictness | Expanded testing found whitespace-only prompts accepted and feedback booleans/numeric strings coerced to integers. Consider nonblank text and strict integer validation if required; no application change was made during testing. |
| PII evasion coverage | Real Presidio did not recognize an obfuscated `name [at] example [dot] com` address; a zero-width address was classified as URL rather than EMAIL_ADDRESS. Assess normalization/recognizers and false positives separately before claiming comprehensive PII protection. See [expanded test report](REAL_LIFE_TEST_REPORT_2026_10_30.md). |
| Maintenance | Existing Starlette/httpx deprecation and large frontend chunk advisory are non-blocking. Dependency upgrades/code splitting require separate scoped work. |

No out-of-scope production feature was implemented. No mandatory controlled-demo blocker
remains at the recorded acceptance time. Previously successful Azure OpenAI/moderation/
Presidio evidence was reused; completion does not claim a new paid availability probe.
