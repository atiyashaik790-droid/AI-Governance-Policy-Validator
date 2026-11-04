# Live stabilization — 31 October 2026

## Status: PARTIALLY READY — deployment and live acceptance require approval

The local fixes, deterministic regression tests and exact deployment package are ready.
**The new package has not been deployed. No fresh live generation, moderation or export
was executed.** Successful real generation for the reported 31 October failures remains
unverified. Do not describe this work as a completed live AI repair or enterprise production readiness.

## Repository and baseline

Root: `/home/sigmoid/AI governance policy validator`, branch `main`.
The [initial status](evidence/live-stabilization-2026-10-31/git-status-before.txt) records
all preexisting changes. A full initial tracked diff was preserved privately under
`/tmp/governance-live-stabilization-20261031/`. No commit, push, reset or unrelated restore occurred.
Actual entry points are `backend/app/main.py` (local), `backend/app/hosting.py` (App Service),
`frontend/src/main.tsx` and `frontend/src/api.ts`. Policy schema: `backend/app/schemas.py`;
engine: `backend/app/engine.py`; adapters: `backend/app/providers.py`; SQL:
`backend/app/azure_sql.py`, `database.py`; RBAC: `security.py`; package builder:
`scripts/prepare_app_service.py`. Existing acceptance/runbooks are under `docs/reports/`
and `docs/runbooks/`, not the old root-level locations in the request.

Fresh baseline: 312 backend tests and 7 frontend tests passed. Existing user edits,
including contextual secret detection and temporary SQL firewall evidence, were preserved.

## Generation failure: established facts and unresolved cause

Read-only local execution metadata confirms two real failed generation attempts:

| Execution | Duration | Output inspection | Retained error |
| --- | --- | --- | --- |
| `39dff9ad-dea0-4bd0-91d2-e266d15fa429` | 9,185.30 ms | Not invoked | Generic generation unavailable |
| `076db5b3-49bd-4d0e-b104-9b32bf131647` | 10,000.65 ms | Not invoked | Generic generation unavailable |

The old adapter discarded HTTP status, Azure correlation identifier and parse/transport
classification before persisting an execution. Consequently **the exact upstream root
cause of those two failures cannot be recovered from these records**. Their duration
is not evidence of a timeout: the configured default is 20 seconds, not 10.

Read-only Azure management checks confirm endpoint deployment `gpt-5-mini`, underlying
model `gpt-5-mini`, version `2025-08-07`, GlobalStandard capacity 250, provisioning
Succeeded and public network enabled. Local API-key authentication is configured;
hosted configuration uses managed identity. The resource's disableLocalAuth property
was null, not an explicit true. These observations do not validate a key or prove a
successful data-plane generation request.

### Verified defects corrected

1. Every generation failure became the same generic message. The adapter now emits
   fixed safe diagnostic categories for HTTP 400/401/403/404/429/5xx, connect/read/other
   transport failures, authentication acquisition failure and malformed responses.
   Only status and UUID-shaped Azure request IDs are included; response bodies, keys,
   URLs, exception messages and prompt content are never included in diagnostics.
2. Nonempty responses with `finish_reason=length`, `content_filter` or an unfinished
   tool response were accepted as completed candidates. They now fail closed before
   output release, with a specific failure category. Empty/malformed content still fails.
3. The UI displayed an unconditional success icon and ambiguous attempted status.
   It now distinguishes not invoked, generation failed, and generation succeeded;
   generation success explicitly remains subject to output inspection/release.
4. The response lacked active policy name and explicit generation state. It now returns
   `policy_name` from the immutable active document and `generation_status`, preserving
   existing `model_invoked` attempt semantics and tenant/version resolution.

### Bounded GPT-5 compatibility mitigation, not proven live root cause

The old payload capped total reasoning plus visible completion at 700 tokens without
specifying reasoning effort. Original GPT-5 deployments now use `reasoning_effort=minimal`;
other deployment names are left unchanged. The token cap, 20-second timeout default,
URL routes, API-version handling and authentication architecture remain unchanged.
No automatic retries or larger token allowance were introduced.

Microsoft documents that reasoning and visible output share the completion budget and
that minimal effort applies to original GPT-5 models:
[reasoning models](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning),
[completion finish reasons](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/chatgpt).
Budget exhaustion is a plausible cause of the historical empty-content failures, **not
an established explanation**. A separately approved real request must establish the
actual outcome. These settings do not guarantee successful generation for every prompt.

## PII and output governance

Real installed Presidio tests detect synthetic email and `+91 9876543210`, redact them,
reinspect, and dispatch only sanitized input to mocked generation. PII `FAILED` denotes
an observed violation with zero weight for that control; detector outage is `UNKNOWN`.
The original score semantics are preserved. UI explains this distinction.

Output inspection runs after successful generation, using the same immutable policy.
Tests cover output ALLOW release, PII REDACT/reinspection/release, output BLOCK,
HUMAN_REVIEW withholding, redaction reinspection failure and moderation failure.
Generated output is never returned directly; audit commit precedes release. Provider
failure leaves output inspection absent and final BLOCK. No output bypass was added.

Human review remains metadata-only: approval records APPROVED_RESUBMIT_REQUIRED and
never replays/releases the original held content. Revised content must pass the gates.
This is the existing documented contract, not an automatic review-resume implementation.

## Supported policies and limits

| Rule | Configuration and enforcement |
| --- | --- |
| secret_detection | Enabled flag; BLOCK, REDACT or HUMAN_REVIEW for supported patterns |
| pii_detection | Shared email/phone/other installed Presidio entities; same three actions |
| blocked_keywords | Up to 100 literal phrases, 1–100 characters each; same three actions |
| moderation | Any flagged provider category; BLOCK or HUMAN_REVIEW; outage fails closed |

No violation yields ALLOW; ALLOW is rejected as a violation action. Moderation REDACT is
rejected. There are no independent `email_detection`, `phone_detection`, configurable
moderation-category fields or executable natural-language policy fields. Unknown fields
return HTTP 422. Email and phone policies share the PII rule; do not claim independent
entity selection. Combined precedence remains BLOCK > HUMAN_REVIEW > REDACT > ALLOW. A separate future
change could add a validated PII entity allowlist and moderation-category allowlist,
with backward-compatible defaults and entity/category enforcement tests; neither is
implemented or silently accepted in this stabilization.

Draft create/update/save validation, simulation, submit, reviewer/Admin approval, publish,
activate, enable/disable, archive/delete of permitted drafts and immutable version history
are covered. No rollback or policy-rejection endpoint exists. Unpublished draft edits
cannot silently replace the active immutable name/rules. Auditor creation remains 403;
Admin and Policy Owner may create drafts. Cross-tenant access remains denied.
Authentication is opaque local demo bearer tokens, **not JWT**; JWT expiry/signature
verification is not implemented and is not claimed as passed.

## Local/live environments and Azure evidence

The verified project backend on 8002 was gracefully restarted from the documented
process-only live configuration; current PID at startup was 129081. No SQL records were
changed by that restart. Health/readiness/settings/OpenAPI and authenticated policy/export
lists returned 200; database mssql CONNECTED, live mode, Presidio, Admin. The source
schema contains the new status field. Frontend 5175 targets 8002. `.env`, root credentials,
SQL firewall rules, offline launcher and offline data configuration were not modified.
Live policy creation/simulation was not repeated because it would write persistent data
and simulation can invoke moderation. Those workflows passed on isolated fixtures instead.

Hosted health/readiness/OpenAPI returned 200. Hosted index/JavaScript still match the
accepted rollback package; existing deployment ID remains
`eec1e450-11c4-4c0e-939f-f9df9e68999b`, active/complete/status 4. The new schema field is
absent on hosted OpenAPI, confirming these changes are local only.

Azure SQL readiness is freshly live-verified; OpenAI/moderation adapter behavior is mocked;
Presidio is real local detection. ADLS read access was checked earlier on 31 October and
historical successful upload/integrity evidence is retained. All 16 hashes in the prior
real-life evidence manifest still match. No fresh upload was needed or performed.
Settings intentionally remains CONFIGURED_NOT_VERIFIED for providers: it checks presence,
not a durable live-operation ledger. No misleading automatic green status was added.

## Test and package evidence

Final: **345 backend tests, 10 frontend tests, 57 Chrome checks and 8 extracted-package
smoke checks passed**. See [exact results](FINAL_END_TO_END_TEST_RESULTS.md).
Lint, formatting, TypeScript, compile checks, same-origin production build and package
credential/local-host scans passed. The first post-fix full run found a no-argument
ProviderUnavailable compatibility regression; the constructor was corrected, the existing
test retained, focused tests passed and the full final suite passed. A formatting check
also caught the constructor line length; it was formatted and rechecked.

See [deployment approval package](FINAL_AZURE_DEPLOYMENT_VERIFICATION.md) for the exact
ZIP, checksum, target, interruption, rollback and remaining risks.

## Files changed in this task

- `backend/app/providers.py`: safe diagnostics, incomplete-response withholding, original GPT-5 minimal reasoning.
- `backend/app/main.py`: generation state, safe failure metadata and immutable policy name.
- `backend/app/schemas.py`: additive response fields; no database schema change.
- `backend/tests/test_generation_release.py`: 33 synthetic regressions for provider/release/policy behavior.
- `frontend/src/main.tsx`: truthful gateway indicators, provider diagnostics, policy name and PII explanation.
- `frontend/src/App.test.tsx`: three gateway-state rendering regressions; preexisting tests preserved.
- `docs/FINAL_LIVE_STABILIZATION_REPORT.md`, `FINAL_AZURE_DEPLOYMENT_VERIFICATION.md`,
  `FINAL_END_TO_END_TEST_RESULTS.md`: current results and approval boundaries.
- `docs/LOCAL_LIVE_RUN_GUIDE.md`, `docs/runbooks/TECHNICAL_DEMO_RUNBOOK.md`: current guidance appended.
- `docs/evidence/live-stabilization-2026-10-31/`: full inventory/hashes in adjacent manifest.
- `artifacts/live-stabilization-20261031/`: candidate ZIP, accepted rollback ZIP and manifest.

Existing secret-detection improvements in `app/engine.py` are included in the deployment
diff relative to 30 October but were not edited during this task. No application database,
credentials, cloud settings, firewall, dependency lock, auth architecture or unrelated user
file was changed. Build output is ignored and no Git commit/push occurred.
