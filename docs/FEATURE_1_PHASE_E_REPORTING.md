# Phase E metadata audit and reporting

All endpoints use the existing authenticated identity, tenant scope, RBAC and cookie-session CSRF dependency. No public v2 generation or validation endpoint is introduced.

| Method | Path | Access |
| --- | --- | --- |
| GET | `/api/v2/audit/executions` | Authenticated |
| GET | `/api/v2/audit/executions/{execution_id}` | Authenticated, same tenant |
| GET | `/api/v2/audit/events` | Authenticated |
| GET | `/api/v2/analytics/overview` | Authenticated |
| GET | `/api/v2/reviews` | Existing review roles |
| GET | `/api/v2/reviews/{review_id}` | Existing review visibility rules |
| PUT | `/api/v2/reviews/{review_id}/assignment` | Admin/Reviewer, existing ownership rules |
| POST | `/api/v2/reviews/{review_id}/approve` | Admin/Reviewer, existing ownership rules |
| POST | `/api/v2/reviews/{review_id}/reject` | Admin/Reviewer, existing ownership rules |
| POST | `/api/v2/reports/export` | Admin/Auditor |
| GET | `/api/v2/reports/exports` | Admin/Auditor |
| POST | `/api/v2/reports/exports/{export_id}/reconcile` | Admin/Auditor |

Lists accept `offset >= 0` and `1 <= limit <= 100`, defaulting to 0 and 50, and return `schema_version:"2.0"`, `items`, `total`, `offset` and `limit`. Execution history, analytics and export accept the existing ISO date window conventions. Detail responses include the entire captured policy set, including sets larger than 100; list pagination limits requests, not policies inside a request.

Execution summaries distinguish historical `execution_mode` from the workspace's current mode. LEGACY records retain `{policy_id, version}` under `legacy`; MULTI records have `legacy:null` and individual published-version evidence. Request summaries expose captured/evidence counts and cardinality completeness. Original records are not rewritten when changing workspace mode.

Analytics separates `request_count` from `policy_evaluation_count`. Each captured policy evidence row counts once, including incomplete/skipped outcomes; a historical LEGACY request counts as one policy evaluation. `requests_by_mode` uses stored historical identity. `active_policy_count` uses current independent assignments in MULTI or the eligible single assignment in LEGACY.

The persistence adapter reconciles every admitted pin against stage evidence. Missing, duplicate or mismatched evidence fails closed and becomes explicit incomplete evidence instead of omitting a captured policy. Stored fields are allowlisted: canonical policy/version IDs, document digest, decisions, control statuses, category names, counts and fixed failure codes. Original prompts, generated content, sanitized content and arbitrary provider fields are excluded.

One execution, one evidence row per captured policy, one governance audit event, optional single metadata-only review and reservation finalization commit atomically. No generated content returns before that commit. Timeout/fencing failures before persistence retain a BLOCK request with all captured evidence and skipped-stage reasons. A failed database persistence transaction is rolled back without automatic retry or content release. Requests rejected before admission have no captured policy set and do not create execution records.

Review details link all captured evidence and identify contributing HUMAN_REVIEW policies. Developer/Policy Owner visibility remains limited to their own requests. Approval requires resubmission and grants no exemption from current policies; original content is never available from review metadata.

Versioned exports accept the existing format/date/idempotency fields plus optional `schema_version:"2.0"`; unknown fields, including tenant selection, are rejected. JSON exports contain `request_count`, `policy_evaluation_count`, window and allowlisted request/evidence objects. CSV exports use explicit `request` and `policy_evidence` row types, so counting rows is not confused with counting requests. Record limits apply to requests; byte limits reject oversized snapshots without truncating evidence.

V2 snapshots use a distinct idempotency namespace and `governance-reports/v2/` paths. Snapshot bytes and SHA-256 are durable before storage. Existing ADLS lease, ownership, bounded digest verification, conditional upload and explicit reconciliation code is reused unchanged. Reconciliation never rebuilds a snapshot from newer history. Historical v1 snapshots and hashes remain untouched; old operator-created jobs are not classified solely by their key prefix.

On schema 005, v2 history/analytics/export use frozen legacy mappings and do not query schema-006-only tables. On schema 006, historical MULTI records remain identifiable after a return to LEGACY. Existing v1 execution/detail/analytics/export-creation guards continue to reject windows or records that cannot be represented faithfully; metadata-only review/export status operations retain their existing semantics.

All acceptance tests are local, using disposable databases, synthetic provider responses and mocked storage. Live SQL Server, ADLS and deployment acceptance are outside this phase.
