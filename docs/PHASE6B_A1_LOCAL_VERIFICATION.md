# Phase 6B-A1 local session assertion verification — 6 November 2026

**PASS — local session assertion correction fully verified.**

Local verification only. No Approval A retry, Azure command, provider connection, deployment, production mutation, or Git commit/reset/clean/stash was performed. Existing working-tree changes were preserved.

## Cause and correction

The failed historical check was `7100 < lifetime <= 7200`, measuring remaining lifetime after `/api/sso/me`. This permits less than 100 seconds of session age. The recorded request alone took 107.20794 seconds. The deterministic revision-005 reproduction issues exactly 7200 seconds, advances virtual UTC by that request duration, and returns **7092.79206** seconds remaining: the old assertion fails while expiry remains correct. This number is a reproduction, **not a recovered historical value**. The exact historical returned lifetime was never recorded, so the original run cannot independently prove its issued TTL. The cause of the remote SQL latency remains unqualified.

The corrected probes observe the unchanged application expiry function, bracket issuance time, verify the configured duration, and compare the exact issued expiry with fresh persisted database reads and `/me`. They verify cookie Max-Age, second-precision Expires, Secure, HttpOnly, SameSite=lax and Path=/, UTC timestamps, positive remaining lifetime and unchanged expiry after activity. They do not relax runtime authentication or session configuration.

The SSO default is 120 minutes; an explicit 60-minute setting remains honored. Demo sessions independently default to 60 minutes. Tests exercise both durations for SSO and demo sessions. Clock advancement is deterministic; these checks do not wait one or two real hours.

## Recovered evidence and fixture stall

The interrupted run's `focused.log` and `focused.xml` are complete: **38 passed in 3.19 seconds**, with zero failures/errors/skips. Its successful outside-sandbox fixture control and sandbox diagnostic traces were retained.

The continued sandbox run timed out at its 480-second bound while entering Starlette TestClient, before the session assertions. The same focused suite passed outside the sandbox in 3.17 seconds. This isolates the practical test obstruction to the sandbox execution context; the low-level cause of its AnyIO portal stall was not established or patched.

The outside-sandbox runner installs Linux seccomp rules rejecting creation of AF_INET and AF_INET6 sockets, verifies both return PermissionError before testing, and passes that kernel restriction to subprocesses. This also blocks native SQL/provider transport. It supplies a clean environment, `DATABASE_URL=sqlite://`, fixture provider mode and regex PII mode. `sitecustomize.py` blocks dotenv settings files outside `/tmp`, so repository production secrets are not loaded. The first version blocked all dotenv files; it was narrowed after the full regression run exposed interference with a synthetic `/tmp` fixture. No live SQL probe or readiness CLI is invoked; readiness tests mock their external interfaces. Application tests create disposable databases. The guard and commands are preserved in the evidence directory.

## Commands and results

Run from the repository root using `.venv/bin/python docs/evidence/phase6b-a1-local-2026-11-06/run_local.py` followed by:

- `outside-focused backend/tests/test_session_lifetime.py backend/tests/test_phase6b_session_assertion.py -q -s` — **38 passed**, 3.17 seconds.
- `compatibility-readiness backend/tests/test_schema_compatibility.py backend/tests/test_release_transition.py scripts/tests/test_sso_readiness.py scripts/tests/test_phase6a_permissions.py scripts/tests/test_hosted_runtime_probe.py scripts/tests/test_runtime_layout.py -q` — **123 passed**, 41.05 seconds. Includes extracted candidate revision 005 and declared revisions 004/006/007 on disposable SQLite; this is not SQL Server qualification.

- `backend-regression backend/tests -q` — **1196 passed, 1 failed**, 117.49 seconds. The sole failure was runner interference: blanket dotenv suppression hid the test's synthetic environment file. No application failure was identified.
- `database-followup backend/tests/test_application_database.py -q` — **10 passed**, 1.03 seconds, after restricting the dotenv block to files outside `/tmp`. Includes the formerly failing test; no tests or application assertions were changed. The remaining 1196 backend tests passed in the full run. No subsequent full-suite green run is claimed.

Each invocation has a 480-second process timeout and a 45-second traceback diagnostic timer. Existing migration/package subprocess tests also have 60-second timeouts. The focused sandbox attempt (`continued-focused`, same focused arguments) reached the process timeout, exit 124, and is not counted as pass evidence.

Session helper, lifetime tests, assertion regressions and SQLite package probe pass Ruff. An additional lint inspection of the pre-existing SQL package probe reports E731 at its unrelated revision-007 `reveal` lambda; it was left unchanged and is not a session-security defect.

## Configuration and security results

| Check | Result |
|---|---|
| Explicit 60-minute SSO | PASS: 3600 seconds issued; cookie Max-Age 3600; exact DB/API/cookie expiry alignment |
| Default/explicit 120-minute SSO | PASS: 7200 seconds issued; cookie Max-Age 7200; exact DB/API/cookie expiry alignment |
| Demo durations | PASS: independent setting; 60 and 120 minutes; bearer sessions have no SSO cookie |
| Measured-delay reproduction | PASS at both durations; after 107.20794 seconds, 3492.79206 / 7092.79206 seconds remain |
| Absolute expiry | PASS: repeated `/me`, protected reads and a new client/fresh ORM read retain the original expiry |
| Expiry boundary | PASS: valid one microsecond before expiry; rejected exactly at expiry |
| Revocation/logout/rotation | PASS: revoked sessions rejected; logout clears cookie; fresh sign-in rotates and revokes previous session |
| Malformed/naive expiry | PASS: runtime fails closed; offset expiry compares actual UTC instants |
| Assertion negative regressions | PASS: shortened/extended issuance, wrong configured duration, bad cookie, DB mismatch, renewed expiry and non-UTC observations rejected |
| Security configuration | PASS: shorter configured TTLs remain valid and SSO values above 120 minutes are rejected |

## Files and preservation

This continuation added only the local verification report and evidence/runner files beneath `docs/evidence/phase6b-a1-local-2026-11-06/`. It did not edit application code or the existing correction. The correction already present when this continuation began is in:

- `scripts/tests/session_contract.py`
- `scripts/tests/phase6a_package_probe.py`
- `scripts/tests/phase6b_sql_package_probe.py`
- `backend/tests/test_phase6b_session_assertion.py`
- `backend/tests/test_session_lifetime.py`

All 77 available file hashes in the interrupted session's preservation baseline match, including the application hashes and recorded SQLite files. The existing database was inspected with SQLite `mode=ro&immutable=1`: revision **003**, SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. The historical Approval A result and execution evidence remain unchanged.

Evidence: [local test logs, JUnit XML, guard and preservation checks](evidence/phase6b-a1-local-2026-11-06/).

## Decision and remaining limits

The assertion correction is fully verified **for the local session contract** and does not weaken session security. No local blocker remains for that correction. A new, separately authorized Approval A retry is technically justified to qualify the corrected probe against SQL Server and complete the gates left NOT RUN in the original report. This report is not authorization to retry, proof of SQL Server behavior/performance, or approval to deploy.

The exact historical lifetime cannot be recovered, remote guarded SQL latency remains unexplained, actual managed identity authentication and the original outstanding SQL permission/migration/preservation/encrypted-content/fallback/recovery gates remain unqualified. The sandbox TestClient stall remains an environment limitation, bypassed only for local tests with kernel network denial. The unrelated pre-existing SQL-probe E731 lint finding is recorded above. Stop after local verification.
