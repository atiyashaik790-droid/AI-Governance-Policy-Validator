# Integration verification contract

Settings GET is passive: it reads tenant-scoped immutable `audit_events` evidence and performs the existing SQL connectivity query. It never invokes generation, moderation or storage. SQL `CONNECTED` is distinct from provider verification. No new schema, grants or Azure services are required.

| State | Meaning |
| --- | --- |
| NOT_CONFIGURED | Required configuration is absent/blank. Azure generation requires endpoint and deployment; moderation requires its key; ADLS requires account and filesystem. Generation/ADLS may use existing managed identity. |
| CONFIGURED_NOT_VERIFIED | Configuration exists but no matching successful/failed verification evidence is recorded for this tenant. Configuration changes invalidate previous evidence. |
| VERIFIED | Latest matching completed verification performed a successful real provider operation within 24 hours (default). Fixture mode cannot execute verification. |
| FAILED | Latest actual verification attempt failed; only generic `VERIFICATION_FAILED` is exposed. No exception/provider bodies are exposed. |
| STALE | Previously successful evidence is older than the configured freshness window. It is not an assertion of current connectivity. |

`last_verification_at` is UTC and records the most recent completed verification, including a failure. `INTEGRATION_VERIFICATION_FRESHNESS_HOURS` defaults to 24 (allowed 1–168). Latest failure takes precedence over older success. Absent configuration takes precedence over historical evidence. A server-only SHA-256 fingerprint binds evidence to provider/configuration/credential identity inputs; credentials, fingerprints, raw errors and provider responses are not returned by Settings. Audit records remain immutable and tenant-filtered.

Real verification is **disabled by default** (`INTEGRATION_VERIFICATION_ENABLED=false`). Enabling it is a separately approved production configuration change. An authenticated Admin must then deliberately POST `/api/integrations/{azure_generation|moderation|adls}/verify` with `{"confirm_billable_operation":true}`; normal browser CSRF/session checks apply. A shared SQL limit permits one verification operation per actor/tenant per minute. Refresh, login, readiness, scheduled/background work and deployment do not automatically call providers.

Each approved POST performs only its named operation, without automatic application retries:

- Generation: one fixed synthetic prompt through the existing approved wrapper, capped by its existing 700-completion-token limit and provider transport timeout.
- Moderation: one fixed synthetic input through the existing moderation wrapper.
- ADLS: one 28-byte synthetic JSON object at a fresh `governance-reports/integration/<uuid>.json` path and one bounded read-back; matching SHA-256 is required. Upload alone is not VERIFIED. The object path is recorded in a tenant-scoped `integration.adls.OBJECT` audit event before attempting the write, so future separately approved cleanup can identify it. No listing, overwrite, deletion or new service is performed by verification.

Attempt and completion events are committed independently of ordinary governance transactions. A provider success without durable evidence is not reported as a newly verified result. Crashes leave an attempt record; they do not manufacture success. Verification objects are not automatically deleted, and any storage cleanup must be included in the real-provider approval. Operational generation/moderation/export history is not silently promoted into verification evidence, and test mocks do not constitute hosted proof.

Production Settings may therefore continue to display CONFIGURED_NOT_VERIFIED until explicit bounded hosted provider verification is approved and succeeds. The implementation is locally tested; no live provider verification was performed in this preparation.
