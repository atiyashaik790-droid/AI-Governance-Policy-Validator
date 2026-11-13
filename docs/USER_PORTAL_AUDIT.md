# User chatbot portal and audit attribution

## Routing and permissions

The same Microsoft Entra sign-in restores the existing server-managed session.
Only an explicitly provisioned, enabled membership with role `User` opens `/chat`.
Admin, Policy Owner, Developer, Reviewer and Auditor retain the existing Studio
layout and permissions. Unknown/missing roles fail closed. User navigation to a
Studio URL redirects to `/chat`, without rendering the Studio or fetching its
settings, policy data or reports. No memberships are created automatically.

The new role is allowed only the existing session endpoints, workspace readiness
state and governed `generate`/`generate-document` requests. Server authorization
uses an exact method/route allowlist; hiding navigation is not the security
boundary. Policy reads/writes, simulations, validation-only APIs, audit, reviews,
analytics, reports, feedback and session administration are denied. Existing
privileged-role permissions and Entra configuration are unchanged.

The portal supports PDF/DOCX/TXT via the existing upload component and endpoints.
Each turn passes the existing LEGACY/MULTI capture, quota, custom-rule, redaction,
output-inspection and reservation-fencing gates. Friendly notices are reused,
with no link into privileged reviews. Responses for User are explicitly
allowlisted: decisions, safe notices, coarse stage status, validated responses,
request/review references and attachment size/type metadata. Policy documents,
IDs/names, findings, patterns, scores and provider diagnostics are omitted.

Conversation state exists only in the current mounted page. Previous turns are
never sent as model memory. Approved prompt text and validated assistant output
can appear in the conversation; held/redacted prompts are replaced by an
acknowledgement. Extracted document text is never displayed as a chat transcript.
Refresh/sign-out clears the local conversation. Review remains metadata-only and
requires resubmission under current policies after a disposition.

## Execution identity security checkpoint

Existing `validation_executions.metadata_json` is durable SQL text committed with
the tenant-scoped execution, rather than transient response data. LEGACY metadata
is assembled by the server; MULTI uses an explicit metadata allowlist. A new
strict `ExecutionIdentity` value is validated and inserted at persistence in both
paths. It contains actor, tenant, event-time role, and Entra directory/object IDs
when authenticated through SSO. The latter IDs come from the verified membership
selected by authenticated token `tid`/`oid`, never request JSON. Demo sessions
carry no Entra subject. No tokens, credentials or source text enter the snapshot.

Client request schemas still reject actor/role/tenant/metadata overrides. Reads
accept a snapshot only when its bounded fields validate and actor/tenant match
the execution row. Event-time roles never come from current membership lookups.
Execution reads remain tenant-filtered and unavailable to the User role.

Both LEGACY and revision-006 execution mappings now have the same application
append-only update/delete guards used for existing business history. There are
no HTTP execution mutation endpoints; maintenance preserves business history.
These are application-level protections, not new database triggers. Direct
operator/database access remains within the existing trusted database boundary.
No database columns or migrations changed, and historical rows are not backfilled.

## Histories and exports

Policy history shows the stored actor, policy label, event and available metadata.
Policy labels resolve retained published version names first, with source/version
provenance. A never-published surviving policy can use its current name, explicitly
marked as such in details; deleted/missing names display `Not recorded`.
Administrative events show their original server-recorded actor, including SSO
session creation/login and revocation, and `Not applicable` for policy name.
Those event tables have no historical role field, so roles show `Not recorded`.

Governance execution history reads executions, not policy evidence or individual
audit events: one request is one row. It shows actor, recorded role, policy names,
decision and safe violation categories. Details include every retained MULTI pin
and its published version. Historical executions without identity snapshots show
the stored actor where available and `Not recorded` for role/subject. No current
membership is used to fill missing history. Tenant-scoped pagination is retained.

Stored export jobs keep their original content and hashes; recovery/idempotency
does not rebuild them. New versioned JSON snapshots include the enriched read
view. Existing CSV columns remain unchanged. No historical export is rewritten.

## Account configuration

An authorized operator must separately provision/approve a server-side membership
for the intended Entra directory/object with role `User`, tenant and account
label, using the existing membership workflow. This implementation creates no
accounts, memberships or cloud configuration. Only synthetic test accounts were
used locally. Existing missing/disabled memberships continue to be rejected.
