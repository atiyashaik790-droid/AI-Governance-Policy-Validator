# Approval A retry-4 — PARTIAL / stopped at security gate

Candidate `1.2-e4d3f0b8116eb37d` was exercised only against approved disposable database `sqldb-gpv-mig-20261106-a1`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, server `sql-governance-validator-dev-atiya`. No deployment or production SQL writes occurred.

## Results

- Preflight PASS: exact target, absence, firewall/SQL connectivity, S0 availability, price, candidate SHA-256 and frozen migration hashes. Seven negative target guards passed; 76 harness/source dependencies pinned. Historical 005 session/security and unchanged 006 session evidence reused under existing byte/hash guards.
- 005 → 006 PASS: retained-row hashes unchanged; corrected catalog verifier, extracted-candidate runtime readiness, MULTI transition/execution/v1 fencing and separate tenant-isolation gate passed.
- 006 → 007 migration PASS: retained-row hashes unchanged; operator schema contract/catalog checks and temporary 007 grants passed. This does not establish 007 application runtime readiness.
- Security gate FAILED: `scripts/phase6b_approval_a.py:640`, `UPDATE dbo.validation_executions SET tenant=tenant`, succeeded where the harness required SQL error 51000. Saved `catalog-1-007.json` has no trigger on `validation_executions`. Earlier UPDATE/DELETE negatives for audit_events, policy_versions and review_notes all raised expected 51000. Whether the missing enforcement is a schema defect or the harness expects an unsupported contract requires local investigation; no security assertion was bypassed or changed.
- Stopped immediately. Fresh 007 runtime session/encryption/RBAC probes, compatible-copy retained-ciphertext check and second-incarnation synthetic failure cycles were NOT RUN. No second incarnation was attempted.

## Resource and cleanup evidence

One S0 / 10-DTU database incarnation was created and deleted using finally cleanup; independent watchdog was started before creation. Elapsed harness time 907.62 seconds. Independent ARM GET returned **404 / ResourceNotFound**, and separate server inventory contains only production and master. Production revision 005/schema/runtime mapping/grants match the preflight baseline. Local SQLite revision-003 file hash remains `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`; pinned sources remain unchanged during execution. No real providers or customer data used. Previously approved single-IP firewall rule remains unchanged.

S0 price USD 0.4839/day. Conservative rounded compute estimate **USD 0.040325**, below USD 1 (estimate, not final Azure invoice).

## Local harness changes

Added distinct retry-4 window/token/evidence handling to `scripts/phase6b_approval_a.py`; extended unchanged-session reuse branch in `scripts/tests/phase6b_sql_package_probe.py`; copied target-locked preparation, launcher, tenant and independent cleanup helpers into the new evidence directory. Candidate archive, application source, migrations and SQLite were not changed for this rehearsal. All prior working-tree changes preserved.

Commands: retry-4 harness `--dry-run`; bounded `prepare_readonly.py`; bounded `source_metadata_readonly.py`; `timeout 14400s .venv/bin/python -B .../launch_approved.py` (exit 1 at security gate, finally cleanup passed); bounded `verify_deletion_readonly.py` (PASS); bounded `source_metadata_readonly.py --final` (PASS). No unrelated local suites rerun.

Evidence: [execution](evidence/phase6b-approval-a-retry4-2026-11-06/execution.json), [independent deletion/cost/preservation](evidence/phase6b-approval-a-retry4-2026-11-06/independent-deletion.json), [production comparison](evidence/phase6b-approval-a-retry4-2026-11-06/production-final-readonly.json), [007 catalog](evidence/phase6b-approval-a-retry4-2026-11-06/catalog-1-007.json), [launch trace](evidence/phase6b-approval-a-retry4-2026-11-06/launch.log).

Remaining blocker: resolve the validation_executions append-only contract/security-test mismatch locally, then obtain **fresh Approval A authorization** for any further Azure rehearsal. Approval A is not complete; recovery drill B and production C–F remain unauthorized. STOPPED after retry-4.
