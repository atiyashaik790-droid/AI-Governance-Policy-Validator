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
| Draft | GET/PUT/DELETE `/api/policies/{id}` | view; edit new draft; delete never-published draft only |
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
