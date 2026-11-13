# SQL preflight connectivity diagnosis — 7 November 2026 IST

**BLOCKED — Azure SQL firewall denial reproduced. No cloud change applied.**

## Root cause and precise category

The retry-3 command was `.venv/bin/python -B docs/evidence/phase6b-approval-a-retry3-2026-11-06/source_metadata_readonly.py`. It used the TLS-enforced, pinned-Entra `create_azure_sql_engine()` adapter and failed at `e.connect()`, before source metadata could be read. Its generic `DatabaseConnectionError` used `raise ... from None`, suppressing printed native details. The native exception remains available in-process through `__context__`; the existing allowlisted classifier can inspect it safely. Historical native details were not persisted, so that old traceback alone did not establish a cause.

A single new bounded diagnostic against **sql-governance-validator-dev-atiya.database.windows.net:1433**, database **sqldb-governance-validator-dev**, reproduced:

- Approved subscription: PASS.
- DNS resolution: PASS.
- TCP 1433: PASS.
- Registered Microsoft ODBC Driver 18: PASS.
- Secure ODBC configuration: PASS, Encrypt=yes and TrustServerCertificate=no unchanged.
- Pinned Entra CLI token acquisition: PASS; token contents never logged.
- SQL connection: **BLOCKED — `SQL_FIREWALL_DENIED`, SQLSTATE `42000`, native error `40615`**.

The server rejected this verifier client's network access under its existing firewall policy. This is not a DNS/TCP/driver/token-acquisition failure or evidence of missing database grants. Full database login/permissions cannot be requalified while firewall access is denied. No TLS bypass, alternate target, automatic retry or service/network/identity change was attempted. The current reproduced firewall cause is proven; the exact historical native error remains unavailable.

Per the user's explicit firewall stop condition, cloud checks stopped immediately. No safe local configuration defect was established, so no speculative local connection-string/authentication change was made. The exact failed metadata preflight was **not rerun**: the cloud prerequisite is still denied and no correction has been authorized/applied. The requested one post-correction rerun remains pending.

## Narrow diagnostics and tests

Added `scripts/diagnose_sql_preflight.py`: fixed approved endpoint/subscription, bounded DNS (8s), TCP (5s), CLI token process (15s), existing ODBC connection (10s) and SELECTs only. A 70-second outer process bound was applied; the actual run completed in **2.894 seconds**. It emits only stage/check statuses, allowlisted category/SQLSTATE/native code and public target metadata. No raw exception, token, ODBC string, credential, client IP, application/customer data or certificate details are output. The application/connection adapter was not changed. Diagnosis does not create or mutate any Azure resource.

Added one regression to `backend/tests/test_sql_verifier_diagnostics.py`: exercise the real token-adapter exception boundary with a synthetic credential and denied native handshake, confirm 40615/42000 classification, and confirm IP/host/password/token details are omitted.

- Live diagnostic command: `timeout --signal=TERM --kill-after=5s 70s .venv/bin/python -B scripts/diagnose_sql_preflight.py` — returned blocked, with **40615/42000** as above. No retry.
- Bounded network-denied local runner: `diagnostics-focused backend/tests/test_sql_verifier_diagnostics.py -q` — **16 passed**, zero failed, 0.06 seconds. No unrelated suites repeated.
- Ruff on both changed Python files — PASS.

Evidence: `docs/evidence/phase6b-sql-connectivity-2026-11-06/diagnostic.json`, `diagnostics-focused.log` and JUnit XML. Directory naming retains the UTC evidence date; the report uses IST.

Files added/changed: diagnostic script, one focused diagnostic test, this report and diagnostic evidence/runner files. No application, migration, grant or production configuration was edited. Candidate **1.2-e4d3f0b8116eb37d** remains byte-identical, SHA-256 `09ef12ae3b0a5c11659083bc4e150860d81f1d5714207165e5262e2bd3dc344b`. SQLite remains byte-identical at revision 003, SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. No Git commit/reset/clean/stash/discard.

## Minimum remaining plan / approval boundary

1. Separately review current verifier egress IP and existing firewall rules for the same SQL server, then obtain explicit approval for an exact, minimal single-IP rule if a change is needed, or choose an already authorized execution network. **No rule/IP range change is prepared or applied here; no broad Azure-services bypass is proposed.** The exact client IP/rule must be reviewed before authorizing a mutation.
2. After that separately approved correction, run the exact SELECT-only metadata preflight once with a process timeout and sanitized classification; verify source 005, runtime SID/grant baseline and target absence.
3. Request a new explicit Approval A execution window using unchanged candidate e4d3f0b8116eb37d and the consolidated plan. Reuse completed local/session evidence. Gate 007 on 006 readiness, MULTI and tenant checks; then perform encryption/session/security/failure cycles and independent cleanup under the same S0/10-DTU, four-hour, USD 1, two-incarnation limits.

Remaining blockers: firewall access, post-correction SQL preflight, corrected MULTI Azure execution, all Azure 007/failure qualification and later recovery/fallback/production approvals. Prior retry-3 remains sealed; no rehearsal, resource creation, deployment or B–F is authorized by this diagnosis. STOP after read-only verification.
