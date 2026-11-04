# Final Azure integration verification

Updated 31 October 2026, Asia/Kolkata. **CONDITIONAL DEMO READINESS; NOT PRODUCTION READY.**

| Integration | Fresh observation | Remaining requirement |
|---|---|---|
| Existing App Service | Public health/readiness/OpenAPI/index 200; active complete deployment 8c2639f4-41d7-4787-bce4-e7253ecbb4b2, status 4, completed 31 October 2026 19:18:36 IST | New reliability package not deployed |
| Azure SQL | SELECT-only connection succeeded; alembic revision 003; original eight tables present | Approved migration 004, reviewed runtime table permissions, SQL-specific recovery/concurrency acceptance |
| Azure OpenAI | Existing hosted schema now contains generation_status; local adapter completion/error tests pass | Explicitly approved bounded real request with SQL execution/audit evidence; no fresh data-plane call in this task |
| OpenAI Moderation | Adapter and failure semantics tested with mocks/fixtures; installed Presidio tested separately | Bounded real moderation verification; configuration presence is not connectivity |
| ADLS Gen2 | Historical 30 October upload/integrity proof retained; durable recovery now local-tested | One approved new object and explicit read-back/hash check using the new flow; cloud recovery after partial failure not yet established |

The fresh deployment observation supersedes the old report's claim that generation_status was absent on hosted. Previously recorded deployment acceptance did not cover this new session/export/quota schema. Public readiness establishes database reachability on the currently hosted version, not migration 004 or successful model generation.

No provider call, ADLS read/write, migration, grant, firewall change, deployment or data mutation was made by this task. SQL metadata reads and App Service management/public HTTP reads were the only cloud operations. Existing identity, resource IDs, configuration and root .env were preserved. Authentication for application users remains restricted demo credentials/sessions; SQL managed identity is a different identity boundary.

Evidence: [hosted public/management observation](evidence/final-implementation-2026-10-31/hosted-readonly.json), [SQL SELECT](evidence/final-implementation-2026-10-31/sql-readonly.json), [historical ADLS proof](reports/FINAL_ACCEPTANCE_REPORT.md).

Fresh SELECT-only permission review also confirmed the existing external application user and governance_validator_web_runtime role. Explicit grants cover the original core tables, without alembic_version SELECT or new-table permissions. This supports the prepared incremental permission script; inherited roles and broader privileges still require review. Evidence: [runtime permissions](evidence/final-implementation-2026-10-31/sql-runtime-permissions-readonly.json).
