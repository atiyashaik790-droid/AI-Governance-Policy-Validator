> Current policy edits require `If-Match` with the last observed `row_version` (428 missing, 412 stale). Provisioned credentials exchange for sessions at `/api/auth/session`; direct API use is disabled by default. New endpoints: authenticated `/api/capabilities`, Admin-only read-only `/api/maintenance`. Developers and Policy Owners may read only their own review cases; ratings are unique per actor/execution. See [current status](CURRENT_STATUS.md).

# API integration guide

The running contract is at http://localhost:8000/docs and `/openapi.json`. All `/api/*` endpoints require `Authorization: Bearer <locally-provisioned-token>`. Never pass a tenant or trusted role from the browser. The backend resolves both from the authenticated account. The gateway returns typed Pydantic inspection and generation results; policy request/response contracts are also typed.

## Minimal integration

```python
import os
import httpx

# Integrate another local LLM application through the protected gateway.
def ask_governed_model(prompt: str) -> str | None:
    with httpx.Client(timeout=60) as client:
        response = client.post(
            'http://localhost:8000/api/governance/generate',
            headers={'Authorization': f'Bearer {os.environ["GOVERNANCE_TOKEN"]}'},
            json={'text': prompt},
        )
        response.raise_for_status()
        result = response.json()
        # Only this field contains released output. A hold or block returns None.
        return result['safe_response']
```

Do not independently call Azure with the original prompt after validation. Use `/generate` so the same immutable policy snapshot gates input and output and the audit transaction commits before release. The standalone input/output endpoints support integrations, but the caller must preserve those same invariants if orchestrating its own model.

## Routes

| Group | Routes | Behavior |
|---|---|---|
| System | GET `/health`, GET `/ready` | process liveness; live database SELECT |
| Policies | GET/POST `/api/policies` | tenant list; strict JSON policy creation |
| Policy | GET/PUT/DELETE `/api/policies/{id}` | view; edit draft; delete a never-published draft or remove a disabled inactive published policy from the workspace while retaining history |
| Simulation | POST `/api/policies/{id}/simulate` | inspect draft without model generation |
| Lifecycle | POST `/api/policies/{id}/submit`, `/approve`, `/publish`, `/activate`, `/enable`, `/disable`, `/archive` | backend-authorized state transitions |
| Versions | GET `/api/policies/{id}/versions` | immutable snapshot history |
| Governance | POST `/api/governance/validate-input`, `/validate-output`, `/generate` | enabled active policy required |
| Audit | GET `/api/audit/events`, `/executions`, `/summary` | sanitized actual records and aggregates |
| Reviews | GET `/api/reviews`, GET `/api/reviews/{id}` | authorized metadata-only case access |
| Review disposition | POST `/api/reviews/{id}/approve`, `/reject` | immutable audit event; no content release |
| Analytics | GET `/api/analytics/overview`, `/violations`, `/compliance` | common aggregate payload for consistent analytics views |
| Feedback | POST `/api/feedback`, GET `/api/feedback/summary` | 1–5 rating referencing a tenant-owned execution |
| Reports | POST `/api/reports/export`, GET `/api/reports/exports` | existing ADLS filesystem upload; accurate attempt status |
| Diagnostics | GET `/api/settings` | database connectivity and configuration presence without secrets |

List policies, audit records, reviews, and export attempts accept `offset >= 0` and `limit` from 1 to 100. The UI paginates execution/review/audit records. Analytics compute from persisted rows, not seeded time series; current implementation loads the tenant's execution metadata in memory and needs database aggregation for production scale.

## Request contracts

Policy POST/PUT:

```json
{
  "schema_version": "1.0",
  "name": "Enterprise Data Protection",
  "description": "Protect sensitive information",
  "rules": {
    "secret_detection": {"enabled": true, "action": "BLOCK"},
    "pii_detection": {"enabled": true, "action": "REDACT"},
    "moderation": {"enabled": true, "action": "BLOCK"},
    "blocked_keywords": {"enabled": true, "values": ["internal-only"], "action": "BLOCK"}
  }
}
```

Text endpoints accept `{"text":"<bounded input>"}`. Feedback accepts `{"execution_id":"<id>","rating":4}`. Report export accepts `{"format":"json"}` or `{"format":"csv"}`. Unknown fields are rejected. Policy names are bounded and restricted to words, spaces, dots and hyphens. Keyword values are literal, bounded, and non-empty. Supported violation actions are BLOCK, HUMAN_REVIEW and (except moderation) REDACT; ALLOW is only an outcome, not an action on a detected violation.

Generation response includes input/output inspection, decision, safe_response, model_invoked (attempted invocation), provider_mode, immutable policy ID/version, duration, request ID, and optional review ID/provider error. Each inspection includes decision, score, per-control statuses/contributions, non-content findings, redaction revalidation status, and safe text only where release is approved. The original unvalidated output is never returned.

## Errors and statuses

201: created policy, feedback or export-attempt record. A created export attempt can truthfully have FAILED status; inspect `status`, not just HTTP 201. 401: missing/invalid token. 403: forbidden role. 404: missing or foreign-tenant resource. 409: invalid lifecycle transition, stale concurrent update, no effective policy, or already-resolved review. 413: request body limit exceeded. 422: invalid schema; errors exclude submitted values. 503: database unavailable or audit persistence failed.

Governance BLOCK and HUMAN_REVIEW are successful inspections returning HTTP 200 with explicit decisions and withheld content; they are not transport failures. Provider failures also produce a non-releasing BLOCK plus sanitized failure metadata. Callers must use the decision and safe_response fields and never treat an HTTP 200 alone as permission to release model output.


## Reliability API additions — local candidate 1.1, SQL head 004 required

- `POST /api/auth/session`: exchange a provisioned bearer credential for an expiring opaque demo session; returns access_token/expires. `POST /api/auth/logout` revokes that session. Admin-only `GET /api/auth/sessions` and `POST /api/auth/sessions/{id}/revoke` are tenant-scoped. No JWT/SSO/password service is claimed.
- `GET /api/policies`: server-side search (literal name substring), status and enabled filters plus offset/limit; stable ID sorting. Computed has_published_versions/is_active flags support UI restrictions.
- `POST /api/policies/{id}/reject`: Admin/Reviewer, SUBMITTED→DRAFT. `POST /api/policies/{id}/rollback` with `{"version":1}` restores an eligible immutable snapshot into DRAFT, retaining history/current activation and requiring reapproval/publication/activation.
- Policies remain schema_version 1.0. Optional `rules.pii_detection.entities` and `rules.moderation.categories` preserve old all-entities/categories behavior when null/missing. Lists must be nonempty when supplied; unknown values are rejected. Requested unavailable detectors fail closed.
- Text requests reject blank content, retain original legitimate whitespace and optionally accept `source_review_id` for a resolved same-tenant case. Linked resubmission never bypasses current gates. All governance and simulation routes reserve SQL request quotas; exhaustion returns 429, total deadline 504.
- `PUT /api/reviews/{id}/assignment` accepts assigned_reviewer/reason; the reviewer must be an enabled same-tenant approved role. Reassignment advances review concurrency version. Approve/reject accept optional reason and preserve notes in decision_history from `GET /api/reviews/{id}`. Held original content is not retained/released.
- `GET /api/usage`: Admin/Auditor reservation counts, configured limits, warning and actual supplied token totals; no invented billing.
- `POST /api/reports/export`: format plus optional idempotency_key/start_date/end_date. Same tenant/key/request returns the original job; changed request with the same key returns 409. Default date window is 90 days, maximum explicit window 366 days; default bounds 10,000 records/5 MB. Job states are PENDING/UPLOADING/COMPLETED/FAILED; legacy success status remains SUCCEEDED. SQL snapshot/claim commits precede storage I/O.
- `POST /api/reports/exports/{id}/reconcile`: Admin/Auditor, explicit bounded storage read/recovery. Live use needs approval. An active lease returns 409; matching bytes finalize without upload; mismatch never overwrites; missing object can be conditionally uploaded within the attempt bound. Historical exports without jobs remain preserved. No automatic HTTP mutation retry.
- Analytics accepts start_date/end_date with the same bounded date window and SQL aggregation. Trends return at most 100 latest chronological samples.
- Settings/readiness expose release metadata from the exact ZIP; MSSQL readiness requires head 004. Configured provider settings still do not prove data-plane availability.

All additions retain server-owned tenant/RBAC enforcement, sanitized diagnostics and audit-before-content-release. See FINAL_DEPLOYMENT_VERIFICATION.md before using new source against the current SQL 003 database.

### Separate audit histories

`GET /api/audit/events?category=policy|governance|administration|all&offset=0&limit=20`

The optional category defaults to `all` for existing API clients. Policy history includes `policy.*` actions; governance execution history includes `governance.*` actions (including ALLOW/BLOCK/REDACT outcomes); administrative history contains all other actions, such as sessions and reviews. Filtering occurs within the authenticated tenant before stable ordering and pagination. Invalid categories return 422. Audit & reports defaults to Policy history and provides separate category controls. Switching categories resets the page and closes the old metadata panel. Export scope remains all audit categories within the selected export window.

### Delete from Policies while retaining history

`DELETE /api/policies/{id}` remains available to Admin and Policy Owner. A never-published DRAFT retains the previous physical-delete behavior and append-only deletion audit event. For policies with published versions, the request requires `If-Match: <row_version>`, a disabled policy and no active assignment. Missing/stale preconditions return 428/412; enabled or assigned policies return 409.

Published deletion marks the policy `DELETED` and records `policy.removed` in the same transaction. The policy is omitted from all policy list/search/filter results, the simulator selector and workspace policy counts. Published versions, execution records and audit history remain intact. Tenant-scoped GET-by-ID and version history remain readable; edits, activation, simulation, rollback and further lifecycle changes return 404. Audit & reports → Policy history offers **View retained versions** for removal events, with read-only pagination. Activation now advances the policy's row version to prevent an activation based on a stale read from racing a disable/deletion. No migration or additional grants are required.
