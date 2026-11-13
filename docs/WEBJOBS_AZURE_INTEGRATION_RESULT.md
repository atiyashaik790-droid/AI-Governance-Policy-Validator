# WebJobs Azure adapter — local wiring complete; live integration BLOCKED

8 November2026.28new focused adapter tests PASS (0.08seconds); Ruff PASS. Reuse the previously passed30controller tests. No application suites, SQL checks, encryption staging or WebJobs operations repeated. One new read-only concurrency-metadata query was performed; no configuration or production-data mutation.

[Azure CLI/ARM/SCM adapter and entry point](../scripts/webjobs_diagnostic_azure.py) now wires the existing controller to:

- Existing CLI account/token workflow, exact subscription/tenant/operator/audience/expiry validation; no account switching or interactive login. Credentials remain in captured process memory.
- Exact App Service resource/identity, built-in Python3.13/AlwaysOn/single-worker validation; explicit management/public/SCM endpoint allowlist; TLS validation, redirects disabled and no credential forwarding to public health routes.
- Settings snapshots, strong ETag precondition, fresh snapshot comparison, If-Match writes,409/412 drift handling and read-back. Only the single diagnostic flag may differ; no unconditional write fallback or automatic mutation retry.
- Lazy existing desktop libsecret integration for a separate per-operation journal-wrapping key. Keys are not printed or placed in arguments/files; lookup-only recovery never regenerates a missing key. Use system Python with GI/libsecret for eventual operation; unavailable/locked stores fail closed. No actual key-store operation occurred here.
- Existing encrypted, atomic recovery journal outside the repository; original state/intent before mutation; idempotent cleanup-only recovery after expiry, preserving unrelated concurrent settings. The adapter does not convert an overdue diagnostic into success.
- Reliable startup log sequences, normalized readiness with pinned005release/frontend/backend hashes, bounded subrequest budgets using both wall and monotonic clocks, and at most one listing request without retries. Raw settings, tokens, response/error bodies and network exception strings are not emitted. Snapshot/HTTP response representations hide secret-bearing values.

## Why real conditional writes remain blocked

A new read-only ARM2024-11-01 settings-list response returnedHTTP200 with **no ETag header and no body etag**. [Sanitized metadata](evidence/diagnostic-azure-integration-2026-11-08/concurrency-metadata.json). No actual setting value or token was persisted.

Microsoft's exact-version [update operation](https://learn.microsoft.com/en-us/rest/api/appservice/web-apps/update-application-settings?view=rest-appservice-2024-11-01) replaces the complete settings map and does not document If-Match. The [list response contract](https://learn.microsoft.com/en-us/rest/api/appservice/web-apps/list-application-settings?view=rest-appservice-2024-11-01) likewise provides no ETag field. Absence from these references is not proof that every App Service version ignores preconditions; **server enforcement on this target is unverified**, and this observed response lacks the metadata required by the implemented guarded path. A client-side hash/read-compare is not atomic concurrency protection. A parent-resource ETag cannot be assumed to cover child settings.

The adapter therefore refuses writes before any PUT without both independently reviewed exact-target/API conditional capability evidence and a strong ETag. [Default conditional gate](../deployment/webjobs-diagnostic-conditional.REVIEW_ONLY.json) isfalse. Do not edit it totrue merely to bypass the block. Mock conditional response tests are not evidence of Azure semantics. An alternate documented atomic mechanism or explicitly enforced exclusive-writer design must be reviewed before any different write strategy is implemented/approved.

## Independent recovery and command boundaries

No independent supervisor was verified in the existing discovery evidence; no discovery scan or resource creation was repeated. A detached local process, finally block, local lock and manually restartable recovery command do not survive initiating-host unavailability. The current desktop keyring and journal also depend on that host. Another host must independently have verified journal/key custody, appropriate Azure restoration access and observable termination/host-loss recovery evidence; none currently does.

[Supervisor gate](../deployment/webjobs-diagnostic-supervisor.REVIEW_ONLY.json) defaultsfalse. The `run` entry point requires explicit original approval timestamps/scope, unexpired<=15minute authorization, positive independently reviewed supervisor evidence and conditional capability proof before key access or Azure execution. Local JSON evidence is an operator-reviewed prerequisite record, not an implemented supervisor or cryptographic proof of remote liveness. No positive evidence file or execution approval was generated.

The `recover` entry point does not require an unexpired diagnostic approval or supervisor certificate; it only restores the journal-bound flag. It still needs the original recoverable wrapping key, exact target identity, credentials and safe write capability. It cannot resume the diagnostic or list WebJobs. Missing state/key/platform access, same-flag drift or unavailable conditional writes reportsBLOCKED. No live command is presented as executable while these gates fail.

For eventual reviewed wiring, use system Python to invoke `scripts/webjobs_diagnostic_azure.py run` with explicit `--operation-id`, protected `--journal`, `--approval`, `--conditional-evidence`, and `--supervisor-evidence` paths. Cleanup-only invocation uses `recover` with the same operation/journal/key lookup and conditional proof, without a new diagnostic grant. These descriptions are not authority to run either mode. No executable live approval file was created.

## Focused local validation

[JUnit](evidence/diagnostic-azure-integration-2026-11-08/adapter-tests.xml):28passed. Fake CLI/HTTP/libsecret backends only; real connection/DNS/CLI paths blocked in these tests. Coverage: exact account/token checks, wrong/expired identity, CLI timeout secrecy, complete mocked enable/list/restore flow, strong/missing/weak/injectable ETags, pre-write and mid-write concurrency, applied-but-unacknowledged mutation, expired cleanup with a fresh adapter, forbidden URLs/unrelated mutations, non-replayed listing timeout, response normalization, durable key lookup without rotation, missing/locked keys, host-loss supervisor gating, expired CLI approval and wall-jump detection inside an adapter operation. The30prior core tests cover actual abrupt child termination bypassing finally; they are reused, not represented as newly executed Azure tests.

**Decision:** Azure integrationBLOCKED for live writes; local adapter testsPASS; independent supervisorBLOCKED; unattended live diagnosticNO-GO. No safe new mutation approval is actionable yet. First establish supported concurrency protection and an existing independently verified recovery supervisor/custody path. Only then prepare a fresh exact15minute flag-only/one-listing/restore approval. No production deployment or database authorization is implied.
