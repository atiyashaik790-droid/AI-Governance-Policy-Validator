# Stage E operator connection diagnosis

Operator SQL connection: **BLOCKED**. Stage E: **BLOCKED**.

## Confirmed cause

A network-enabled, direct ODBC connection to the approved SQL server/database returned SQLSTATE `42000`, SQL Server error **40615**, with firewall/client-IP-not-allowed diagnostics. Azure SQL is rejecting this client's network route under its firewall rules. Raw error text, tokens and client IP were not logged.

Read-only checks verified:

- Active Azure CLI account type: user.
- Subscription: `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`.
- Tenant: `4ac50105-0c66-404e-a107-7cbd8a9a6442`.
- A fresh Azure CLI SQL access token matches approved object ID `b5d8bfbe-f03a-4132-a13f-ab49aae834b7`, approved tenant and token lifetime requirements.
- Existing authentication method: Entra Azure CLI token, TLS/certificate validation, no SQL password.
- ODBC Driver 18 for SQL Server is installed.
- SQL hostname resolves; TCP port 1433 is reachable.
- Direct driver connection fails with server firewall rejection, independently of the application's sanitized connection exception.

No local driver/authentication/configuration correction was indicated. A permitted network route or separately approved firewall change is required. No firewall, Azure permission, SQL user, credential or App Service change was attempted. Current SQL authorization cannot be checked because the firewall prevents database access; historical operator permissions are not treated as fresh proof.

## Stop state

- Admin membership: **UNKNOWN**.
- Audit event: **NOT VERIFIED**.
- Duplicate membership check: **UNKNOWN**.
- SSO enabled: **NO**, as established by the last actual-runtime read-only verification.
- Demo browser login remains enabled per that same verification; no settings changed.

No SQL write or provisioning retry was attempted. Exact mapping/audit consistency cannot be established, so the requested stop condition applies. No B/C/D tests, migration, deployment, credential rotation, SSO activation or Stage F execution occurred. Existing workspace changes were preserved.

[Sanitized connection diagnosis](evidence/stage-e-execution-2026-11-04/connection-diagnosis.json), [diagnostic command record](evidence/stage-e-execution-2026-11-04/connection-diagnosis-command.RECORD_ONLY.txt), [last actual-runtime verification](evidence/stage-e-execution-2026-11-04/resume-runtime-write-denial.json).
