# Workspace policy management API v2

These endpoints use the existing authenticated identity, RBAC and cookie-session CSRF checks. Request bodies reject extra fields, including tenant, actor and role. Tenant scope always comes from the authenticated identity.

| Method | Path | Access |
| --- | --- | --- |
| GET | `/api/v2/workspace/policy-state` | Authenticated |
| PUT | `/api/v2/workspace/policy-mode` | Admin |
| GET | `/api/v2/workspace/policy-assignments` | Authenticated |
| PUT | `/api/v2/workspace/policy-assignments/{policy_id}` | Admin |
| GET | `/api/v2/workspace/policy-assignment-events` | Authenticated |

Read policy-state first. On schema 006, the response includes a strong workspace `ETag`, such as `"1"`, and a body with `mode`, `set_revision`, `active_policy_count`, and `multi_policy_available`. Reads do not initialize workspace state or append events. The initial mode is LEGACY.

Every PUT requires the exact strong workspace ETag in `If-Match`. Missing headers return 428. Stale, malformed, weak, wildcard or multiple validators return 412. Mutation responses contain `set_revision` and the resulting ETag. A no-op retains the revision and emits no new assignment or audit events. ETag is exposed to clients through the existing CORS configuration.

Select MULTI explicitly:

```json
{"mode":"MULTI","seed_legacy_assignment":false}
```

Set `seed_legacy_assignment` to true only to explicitly carry over the currently assigned eligible legacy published version. Returning to LEGACY requires an explicit published version:

```json
{"mode":"LEGACY","legacy_version_id":"published-version-id"}
```

Outstanding reservations block mode transitions, including expired reservations that have not been reconciled. Returning to LEGACY requires at most one active multi-policy assignment, matching the supplied legacy version. Returning later to MULTI never silently restores old assignments.

Activate or repin an eligible published version of the policy named in the path:

```json
{"active":true,"version_id":"published-version-id"}
```

Deactivate the policy independently:

```json
{"active":false}
```

Activation requires an explicit version ID belonging to the same policy and tenant. Deactivation must omit version ID or supply null. Publishing a newer version does not change existing pins. Disabled, archived, deleted or unknown published pins cannot be activated. Assignment mutations require MULTI mode; existing v1 activation cannot bypass that boundary.

Both listing endpoints accept `offset` (default 0, minimum 0) and `limit` (default 50, range 1–100). Responses include `items`, `total`, `offset`, `limit`, `set_revision`, `mode`, and `active_policy_count`, plus the workspace ETag. Assignment rows are ordered by policy ID; immutable events are ordered by descending workspace revision and event ordinal. Pagination totals count the entire tenant-scoped listing, not just the page. Tenant fields are omitted from returned rows.

Active counts describe the effective workspace mode: active independent pins in MULTI, or the eligible legacy assignment in LEGACY. Stored inactive pins remain visible after returning to LEGACY. A listing response reads state, count and page in one database transaction; SQL Server holds a state range lock and SQLite uses an explicit read transaction.

On schema 005, policy-state reports LEGACY with `multi_policy_available:false`, `set_revision:null`, and no ETag. V2 assignment listings and mutations return 503 `SCHEMA_006_REQUIRED` with valid authorization/preconditions. These handlers never query schema-006 tables on schema 005. Existing legacy endpoints remain available.

This phase adds management endpoints only. Existing v1 governance rejects MULTI requests with `USE_API_V2`; no v2 enforcement engine is included here.
