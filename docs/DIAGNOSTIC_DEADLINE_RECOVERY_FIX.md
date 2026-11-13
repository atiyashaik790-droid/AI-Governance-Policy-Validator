> **Adapter integration follow-up:** [Azure integration result](WEBJOBS_AZURE_INTEGRATION_RESULT.md). Local CLI/ARM/SCM/key-store wiring now exists; actual conditional writes and independent supervision remain blocked. This report retains its earlier local-core evidence.

# Diagnostic deadline and recoverable restoration — local safety core PASS

8 November 2026. No Azure API, restart, WebJobs request, SQL operation, deployment or provider call was performed. Application code, frozen migrations and release artifacts were not changed. Historical execution evidence is preserved.

## Root cause and evidence boundary

The executed controller's `request()` applied `END` during `CLEANUP` and separately rejected monotonic elapsed time above880seconds. Every rollback settings read/PUT passed through this same guard. The original15minute approval expired during a long execution gap; entering `finally` did not grant a cleanup path, so the guard rejected restoration locally. The original full settings map existed only in process memory; the saved journal contained intent/status but not a recoverable baseline. Thus a fresh cleanup process could remove the known flag, but could not independently compare the entire historical secret-valued baseline.

The ledger records17431.155seconds wall time versus175.703seconds monotonic time: an unexplained17255.452second difference. Host suspend/resume, clock changes or execution-environment scheduling are possible; the exact cause is **UNKNOWN**. There are no host/process scheduler traces establishing it. The later cleanup approval-review timeout occurred after this gap and does not explain the original gap. No claim is made that a script sleep or an Azure request caused hours of delay.

[Historical ledger](evidence/webjobs-corrected-final-2026-11-08/execution.json), [preserved controller source](evidence/diagnostic-safety-local-2026-11-08/historical-controller.py.txt).

## Replacement and recovery contract

[Local safety core](../scripts/webjobs_diagnostic.py): diagnostic authorization is an immutable absolute deadline capped at15minutes, also bounded by the initial monotonic allowance. Every diagnostic request is checked immediately before dispatch. The fixed5minute startup/readiness phase inherits both parent deadlines; clock rollback cannot reset them. A response arriving after the health deadline is not counted successful. Existing run state cannot resume diagnostic work or obtain a fresh deadline.

Cleanup has a separate bounded240second work budget, independent of the expired diagnostic grant. It may validate the exact pinned target, read settings, remove only the recorded temporary flag, and verify original-release health. It cannot list WebJobs, enable anything, switch targets or resume the diagnostic. Deadline expiry is durably audited; late cleanup never converts the original run to PASS.

Before mutation, the complete original settings, exact target, approval times, expected health and intent are AES-256-GCM encrypted in an atomic journal, mode0600 under an owned0700 directory outside the repository. Writes and rename are fsynced. Symlink/insecure paths and invalid/tampered/wrong-key journals fail closed. A successful decrypt/read-back is required before mutation. The wrapping key must be recoverable through a separate durable secret store; it must never be stored beside the journal or only in the initiating process. This local run generated no production recovery key and wrote no real settings snapshot.

Mutation intent is persisted **before** a possibly ambiguous write. Listing intent is persisted **before** its sole request. A fresh controller can call `recover()` using the original journal/key, without an unexpired approval. Process locking prevents competing controllers. Recovery is idempotent and preserves unrelated concurrent settings. Drift is reported, not overwritten; an unexpected change to the same flag or identity mismatch blocks automatic restoration. A conditional-write conflict triggers a fresh read rather than replaying stale settings. Missing state/key/credentials or inaccessible Azure remains BLOCKED. Audit-storage failure cannot prevent an already-needed flag restoration, but is explicitly reported as an audit failure.

Health verification requires ordered, top-level events for the new app container: container start, actual startup-probe success, then Site started. Waiting-for-warmup text and historical state Details do not count. Require3consecutive successful /health+/ready pairs10seconds apart, exact approved normalized release/revision, at most10pairs, request timeout bounded by remaining fixed5minute budget. Retryable errors reset the streak and retain sanitized outer/reason types, errno and TLS verification code; raw messages/headers/secrets are not logged. Certificate failures and identity/schema/release/security mismatches stop immediately. No listing occurs until startup and the full health gate pass; listing is never retried, even after an ambiguous timeout or restart.

## Focused mock-only verification

**30 passed in0.37seconds**, Ruff PASS. [JUnit](evidence/diagnostic-safety-local-2026-11-08/tests.xml). No unchanged application suites were rerun.

| Requested case | Verified |
| --- | --- |
| Normal success | Three spaced pairs, one listing, exact restoration |
| Expiry before mutation | No mutation or listing, including expiry between durable intent and dispatch |
| Expiry after mutation | Five-hour simulated wall jump still permits narrow restoration; original run remains BLOCKED |
| Interruption | Actual child `os._exit(42)` after mock mutation bypasses finally; a fresh controller decrypts state and restores |
| Repeated restoration | No additional configuration write; diagnostic resumption refused |
| Configuration drift | Unrelated changes retained; same-flag conflict blocked; conditional-write collision re-read safely |
| Network timeout | Success counter resets; underlying TimeoutError retained without raw secret-bearing text |
| Readiness failure | No listing without actual startup and3pairs; fixed deadline is not reset |
| Overdue restoration | Recovery works after original expiry; overdue audit retained |
| No unauthorized listing | At most one request; ambiguous listing never replayed; recovery makes none |

Additional coverage: journal encryption/key/tamper/permissions, process lock, pre-mutation disk failure, cleanup audit failure, target/certificate denial, backward wall-clock jumps, inherited phase deadlines and rejection of the historical false warmup marker. Tests use synthetic secrets and fake cloud/clock ports only.

## Remaining interruption risks and live boundary

**Local code cannot execute while the process/host is dead or suspended.** Durable recovery enables a later independent process/operator to restore; it is not an independently scheduled cleanup service or a guaranteed15minute rollback. Loss of the journal, wrapping key or platform access prevents restoration. A bounded cleanup attempt can fail; a later explicit `recover()` can retry cleanup only.

The replacement is an offline-tested orchestration library, **not a live Azure CLI replacement**. It intentionally contains no credentials or HTTP adapter. A live adapter must normalize identity/readiness safely, bound every request, and implement real conditional compare-and-swap for settings updates. Mock CAS tests do not prove Azure ARM honors a particular ETag. If atomic conditional updates are unavailable, do not silently substitute whole-map read/PUT with a race; an explicitly reviewed exclusive-writer mechanism is required. Durable secret-store key provisioning/retrieval must also be integrated and reviewed before live wiring. Do not run the historical /tmp controller again.

A new Azure diagnostic could obtain new evidence because the health gate and cleanup design are corrected, but **another unattended15minute live run is not operationally justified yet**. First review the bounded live adapter, durable key custody and an independent recovery operator/executor capable of acting if this session stops. These are not established by local tests. No live approval is requested in this change.

Once those conditions are met, the exact future scope would be one fresh15minute window on app-governance-validator-atiya-1026: original encrypted baseline; only WEBSITE_SKIP_RUNNING_KUDUAGENT=false; genuine warmup plus3pairs within5minutes; at most one listing; exact flag restoration and health verification. Storage/unrelated settings unchanged; no jobs, SQL, providers, deployment or new services. Expect two recycles, approximately1–5minutes each, estimated incremental service capacity costUSD0. Approval must explicitly cover recovery-journal/key custody and cleanup-only recovery after deadline; it must never imply permission to resume expired diagnostic work.
