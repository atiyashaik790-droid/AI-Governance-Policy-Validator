# Phase 5A — readiness contract fingerprint investigation

**PASS — the 13-test readiness blocker is resolved locally.** Complete readiness group: **74 passed**. Connection-free backend regression group: **24 passed**. No new schema-contract baseline was approved or substituted. No deployment, database migration, hosted operation, real provider/SSO operation or production key was used.

## Exact root cause

`scripts/verify_hosted_runtime.py::payload()` used `Path.read_text()` on the evolving `backend/app/schema_compatibility.py`, re-encoded it with `.encode()` and compared its SHA-256 against a literal approved fingerprint. This fingerprints the entire Python source file, including comments/imports and verification logic; it is **not** an OpenAPI digest, a live database digest or a canonicalized schema digest.

The probe was written to stream an already-reviewed 004/005 verifier into an older application container, then explicitly accept **only revision 004**, the pinned target/managed identity and runtime role. The application's verifier subsequently gained intentional local 006/007 capabilities. Its source bytes and dependency closure changed. The fingerprint guard correctly refused to stream that different program. All 13 failures occurred at this same guard in `payload()` before their intended assertions could run; none demonstrated a failed live schema check or remote operation.

The defect is **C: probe input/source-selection defect**. A historical, approval-bound probe was coupled to mutable application source. The safe correction preserves the exact approved program and fingerprint and separates its input from the evolving application helper. No schema differences below were adopted into the historical probe.

## Fingerprints and reference recovery

| Input | SHA-256 |
|---|---|
| Approved literal in `scripts/verify_hosted_runtime.py::payload` | `e3530bb5af9199ee850f54f71984da4643dbd458c791dcd5b2c9a5b4e7612497` |
| Exact archived reference recovered from both Phase 3 and Phase 4 packaging ZIPs | `e3530bb5af9199ee850f54f71984da4643dbd458c791dcd5b2c9a5b4e7612497` |
| Current application helper, unchanged | `b5da9f6e2f593f98be3750fe964260a54802bc375910b2b12312d926d08119e2` |
| New frozen probe-input copy, byte-identical to the archived reference | `e3530bb5af9199ee850f54f71984da4643dbd458c791dcd5b2c9a5b4e7612497` |

No new candidate fingerprint is proposed. `reference-inventory.json` identifies every inspected archive and matching member hash. Reference sources are `artifacts/refactor-phase3-2026-11-05/stages/10-packaging/application.zip` and `artifacts/refactor-phase4-2026-11-05/stages/10-packaging/application.zip`, member `app/schema_compatibility.py`. The baseline source-hash manifests independently record the same hash. Earlier production/rollback packages contain a different `e5d365…` helper and were **not** substituted.

## Human-readable contract differences

The exact source diff is [contract.diff](evidence/phase5a-local-2026-11-06/contract.diff). [Metadata differences](evidence/phase5a-local-2026-11-06/metadata-differences.md) lists added tables/columns and modified execution shape; [metadata-contracts.json](evidence/phase5a-local-2026-11-06/metadata-contracts.json) includes complete static inventories. These comparisons perform no database access or migrations.

| Difference in application helper versus approved probe reference | Meaning and disposition |
|---|---|
| Supported revisions 004/005 → 004/005/006/007 | Intentional application extension for MULTI and protected review; not approved for this legacy probe |
| `Base` import → revision-specific `schema_manifests` imports | Selects frozen metadata per revision; imports MULTI mappings and lazily imports protected-content mappings |
| Four MULTI tables | Adds workspace states, assignments, immutable assignment events and execution policy evidence; includes tenant relationships, indexes, checks, defaults and history protections |
| Execution identity shape | 006 adds `execution_mode`; policy/version become nullable for MULTI, constrained by execution mode; tenant composite indexes support foreign keys |
| Permission verification gains revision argument | 006/007 require SELECT/INSERT/UPDATE for state/assignments, SELECT/INSERT for assignment events/evidence; 007 adds SELECT/INSERT/DELETE for protected content, never UPDATE |
| Unversioned SQLite may infer 006 | Disposable-fixture-only inference; versioned SQL still requires exactly one supported revision |
| SSO accepted on 006/007 | Extends schema availability; does not alter identity, cookie, membership or RBAC implementation |
| Partial-006 guards at older revisions | Rejects MULTI tables or execution-mode columns at legacy markers |
| History selection per revision | Includes append-only assignment/evidence history on 006/007 |
| Strict 006 verification dependency | Adds physical SQL types, defaults, checks, trusted/enabled constraints and covering-index checks |
| Protected-content table and 007 verification | Requires composite tenant/review FK, format version 1, original-prompt content kind, expiry > creation and ≤ seven days, 12-byte nonce, 16–48,016-byte ciphertext, immutable-update trigger; SQL Server binary types and trusted/enabled checks |
| SQLite nonce length special case | Avoids comparing unavailable reflected binary length; explicit 007 byte-length check still enforces 12 bytes |
| Return `sso_schema` recognizes 006/007 | Extends schema result semantics for current application callers; return field names remain unchanged |

**Classification boundary:** These are intentional, established local feature implementations, supported by `docs/FEATURE_1_PHASE_C_API.md`, `docs/FEATURE_1_PHASE_D_ENGINE.md`, `docs/PROTECTED_HUMAN_REVIEW.md`, feature-phase artifacts and the current instruction to preserve LEGACY/MULTI, SSO and migration 007. Those documents do not establish approval to replace the probe's pinned program. No category-A approval for a new probe baseline is claimed. Adoption of these security-relevant differences into that probe would be **D** and require explicit review; no such adoption or edits to those differences were made. No clear category-B application regression was found. The corrected integration mismatch is category **C**, with no change to the approved contract.

The two helper files are untracked in the existing working tree; `git log --all -- <paths>` has no introducing commit to attribute. Phase 3/4 archives preserve the old bytes. Phase B/C preservation manifests identify the later revision-aware verifier and new manifest/verification modules; protected-review documentation and revision-007 code identify the next extension. This traces implementation stages, not a provable commit or an approval transcript.

## Safe correction and security impact

Added `scripts/contracts/schema_compatibility_004_005.py` as an exact byte copy of the recovered reference. Changed only the probe's input path and explanatory comment. The SHA-256 literal, mismatch failure, revision-004 restriction, target/identity/role pins, SELECT-only session behavior, sanitized errors and no-write checks remain in force. No canonicalization, extra accepted hashes, bypass, skip or relaxed assertion was introduced.

This also avoids a second problem with blindly repinning: the current helper imports new modules that an older target package may not contain. The frozen program retains its original dependency on `app.models`; static comparison against the archived model metadata confirms current 004 and 005 inventories are identical to the reference. The legacy probe remains intentionally unsuitable for certifying revisions 005/006/007 as a deployed target; it still requires revision 004. Future target/revision expansion requires separate approval.

Authentication/authorization architecture, tenant isolation, audit records, permissions granted to any identity and all migrations are unchanged. The application keeps its current helper and all 006/007 validation. The frozen reference retains the already-reviewed fail-closed schema/object/permission and append-only checks. No database or API contract was modified.

## Verification and exact commands

Commands were run locally with `DATABASE_URL=sqlite:////tmp/phase5a-unused.db PROVIDER_MODE=fixture PII_MODE=regex`. This URL is a defensive override; the selected tests do not migrate or connect to it.

```bash
.venv/bin/python -m pytest scripts/tests -q \
  --junitxml=docs/evidence/phase5a-local-2026-11-06/readiness.xml
# Before correction: 57 passed, 13 failed

.venv/bin/python -m pytest scripts/tests -q \
  --junitxml=docs/evidence/phase5a-local-2026-11-06/readiness-corrected.xml
# After correction: 74 passed (all original 70 plus 4 new regression cases)

.venv/bin/python -m pytest backend/tests/test_mssql_schema_reflection.py \
  backend/tests/test_sql_verifier_diagnostics.py -q \
  --junitxml=docs/evidence/phase5a-local-2026-11-06/backend-regression.xml
# 24 passed, two existing deprecation warnings
```

All 13 originally failing node IDs and their subsequent passing outcomes are in `verification.json`; the original failure tracebacks show the `require(False, "REVIEWED_SCHEMA_CONTRACT_CHANGED")` assertion. Original failing tests cover payload/session safety, mocked PTY completion, terminal output handling, five error-classifier paths, manual command generation, three pre-Python failures and runtime layout bootstrap. Entire-group rerun includes all 13.

New regressions reject both a deliberately changed contract and even a whitespace-only change; verify only the 004/005 source is embedded without the new dependency imports; and verify application helper drift cannot silently redefine the legacy probe. Independent pre-correction guard experiments accepted the recovered reference for payload construction and rejected current/tampered source. No payload from those experiments was remotely executed. Ruff and `git diff --check` passed.

No frontend/integration rerun was needed: no application or API source changed. Phase 5's saved 131 frontend tests and disposable React/FastAPI integration evidence are retained, not represented as a new run.

## Files changed and remaining boundaries

Source/test changes:

- `scripts/verify_hosted_runtime.py` — frozen probe input path/comment only.
- `scripts/contracts/schema_compatibility_004_005.py` — exact recovered approved reference copy.
- `scripts/tests/test_hosted_runtime_probe.py` — four new regression cases.

Documentation: this report and a superseding note in `docs/PHASE5_LOCAL_ACCEPTANCE.md`. New evidence files are listed in `docs/evidence/phase5a-local-2026-11-06/changed-files.json`.

`backend/governance.db` remains revision **003**, with unchanged SHA-256 `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766`. No existing application source, feature, migration or working-tree change was removed. No long-running application service was started.

**Baseline approval required: no for this correction**, because it restores the original approved program rather than adopting the different application helper. The local Phase 5 readiness-test blocker is resolved. The project may proceed to deployment preparation/review; this is not deployment authorization or evidence of hosted readiness. Real Entra, SQL Server, provider/storage, production-key and hosting checks remain the separately authorized gates documented in Phase 5.
