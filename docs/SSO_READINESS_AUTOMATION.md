# One-command SSO readiness and staged approval preparation

This is a read-only automation workflow, not an authorized production release.
The corrected candidate remains `1.2-6749226f1af65b63`. Existing demo login is untouched.

## Run from Ubuntu

From the repository directory:

```bash
bash scripts/verify_sso_deployment_readiness.sh
```

Equivalent controller default: `bash scripts/prepare_sso_rollout.sh`.
Both run Stage A only using the existing `.azure-sql-cli` context and `.venv/bin/python`.
Neither logs in, switches accounts, retrieves secrets, installs dependencies, or changes Azure configuration.
The wrapper sets the context for its own process, not your saved settings.
Python 3.11+ is required (the current project virtual environment uses Python 3.13).

The existing candidate ZIP must remain available at
`/tmp/governance-sso-compatibility-fixed-004-20261104.zip` and the preserved original
ZIP at `artifacts/restricted-demo-20261101/governance-workspace-policy-delete.zip`.
`/tmp` is temporary: preserve the candidate using your existing local artifact procedure.
If it is already stored elsewhere, run:

```bash
bash scripts/verify_sso_deployment_readiness.sh --package /absolute/path/to/existing-candidate.zip
```

The same pinned SHA-256 is required regardless of path; no automatic rebuild/download occurs.
The original 004-only ZIP is valid only before migration. After 005 use the corrected
004/005-compatible ZIP with SSO off and demo on; retain schema/data 005.

## Checks and interpretation

1. Validate both pinned ZIP checksums and candidate release/004–005 manifest contract.
2. Require the existing project-local CLI directory and its currently selected subscription
   `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, tenant
   `4ac50105-0c66-404e-a107-7cbd8a9a6442`. No account selection occurs.
3. Discover exactly one `app-governance-validator-atiya-1026` and
   `sql-governance-validator-dev-atiya` in that subscription, validate their ARM IDs,
   and discover existing resource groups. Require Running app and Online exact database
   `sqldb-governance-validator-dev`.
4. Report the existing system-assigned managed identity's immutable principal object ID
   and tenant ID. This is not the SSO registration's ID.
5. Reuse the reviewed `verify_schema_compatibility.py --connect` SELECT-only contract:
   exact DB, single revision 004, required columns/keys/indexes/triggers/FKs,
   no visible partial 005 schema, effective baseline SQL permissions and metadata visibility.
   Its permission subject is **executing_cli_identity**, never App Service identity.
6. Read existing short-term retention and earliest PITR timestamp. Require positive
   retention (1–35 days) and a past, timezone-aware restore timestamp. Read current CLI
   management permission metadata at the existing SQL server scope with ARM GET only.
   Policy/earliest-date evidence does not prove the latest usable recovery point, an
   actual restore, destination authorization, deny/lock checks, or cutover readiness.
7. Report runtime/recovery gaps explicitly. Stop on command failures, missing prerequisites,
   mismatched targets or schema drift. Later checks remain NOT_ATTEMPTED.

Output is allowlisted JSON on stdout; no raw Azure response, CLI stderr, SQL errors,
connection string, token, secret, environment dump, or database row content is forwarded.
No report file is automatically created. Do not enable shell tracing.
Exit **1** means a checked prerequisite failed; exit **2** means evidence is incomplete
or access unavailable. Per-check PASS means only that check passed.
The workflow cannot currently return overall PASS because the runtime channel and
recovery review remain unimplemented/unverified, even when all CLI checks pass.

## Actual hosted runtime permissions: precise blocker

There is no existing reviewed read-only runtime attestation endpoint or noninteractive
remote probe in this repository. `az webapp ssh` is interactive; obtaining publishing
credentials or installing/uploading a probe is outside this workflow. Consequently it
**does not attempt remote execution** and reports `ACTUAL_RUNTIME_CHANNEL_UNAVAILABLE`
if it reaches that check. It never replaces runtime evidence with operator access,
SQL catalog grants, a wildcard management permission, or a hand-authored attestation file.

The existing approved procedure in
[FINAL_SSO_DEPLOYMENT_APPROVAL.md](FINAL_SSO_DEPLOYMENT_APPROVAL.md#exact-managed-identity-and-required-verification)
requires an already-authorized existing App Service console/session using its installed
Python environment and `app.database.SessionLocal`. Run only the reviewed SELECT
contract in `deployment/verify_sso_compatibility.READ_ONLY.sql` and supporting principal
inspection in `deployment/verify_managed_identity.READ_ONLY.sql`; confirm the connection
uses managed identity and the confirmed principal/tenant pins without displaying settings.
Compare DB_NAME/USER_NAME, existing contained user mapping and effective HAS_PERMS_BY_NAME
under that actual connection. The old hosted package lacks the new schema helper: do not
upload it or install dependencies. Catalog inspection as the CLI operator alone is not proof.
If that existing channel is unavailable, retain UNKNOWN and stop. No alternate identity,
new endpoint, elevated privileges or deployment is authorized.

Recovery readiness also needs an existing designated operator, restore/target permission
review (including denies/locks), agreed RTO/RPO, a current usable pre-change point and
cutover ownership. An actual restore/new database needs separate approval and is never
performed here. A recovery drill is UNKNOWN, not automatically demanded or claimed.

## Staged controller

Later commands **prepare and print approval plans only**:

```bash
bash scripts/prepare_sso_rollout.sh --stage B --plan  # Compatibility deployment
bash scripts/prepare_sso_rollout.sh --stage C --plan  # Migration 005
bash scripts/prepare_sso_rollout.sh --stage D --plan  # Minimum runtime grants
bash scripts/prepare_sso_rollout.sh --stage E --plan  # Exact approved memberships
bash scripts/prepare_sso_rollout.sh --stage F --plan  # SSO settings/release
bash scripts/prepare_sso_rollout.sh --stage G --plan  # Real Microsoft acceptance
```

There are deliberately **no hosted mutation executors**, approval bypass flags, arbitrary
shell hooks or stage chains. B–G without `--plan` are BLOCKED. Printed plans do not
authorize any action. Separate stage approval must bind the exact stage, targets,
artifact hash, fresh prerequisite evidence, operator/reference, window and rollback.
These are preparation commands, not deploy/migrate/grant commands. Implementing or
executing a future mutation executor requires separate review and the stage's explicit
approval; this delivery does not provide unattended production deployment automation.

C and D require special coordination: 005 readiness needs metadata visibility of all
three SSO tables immediately. Separate C and D approvals and a reviewed atomic visibility/
grant boundary must be obtained **before** any combined transaction. Do not commit 005
then discover runtime cannot see its objects. The existing REVIEW_ONLY grant file's
managed-identity client-ID placeholder must be confirmed independently first.
No automatic Admin or runtime membership-write permission is introduced.

F keeps demo enabled. The pinned compatibility package already includes SSO: no second
code deploy is needed unless approved code/artifact changes. G includes real login/MFA,
callback, intended tenant/workspace/role, safe policy reads, refresh, CSRF rejection,
logout and unknown-user denial, with separately approved bounded session/audit writes.
No paid provider/storage calls. Demo retirement is another separately approved operation.

## Latest local execution and tests

4 November 2026: package and rollback integrity PASS; local CLI context PASS;
currently selected approved subscription/tenant PASS. App Service lookup UNKNOWN,
`AZURE_NETWORK_OR_DNS_UNAVAILABLE`. The script stopped there; live MI/SQL/backup/runtime
checks were NOT_ATTEMPTED. Earlier user-run SQL revision 004 PASS remains separately
recorded in `docs/evidence/sso-compatibility/operator-verified004.json`.

29 focused mock-based tests PASS: target guards, no identity switching, missing context,
artifact tampering, revision/partial-005 contract, backup failures, sanitized stderr,
timeouts, read-only CLI/SQL orchestration and nonexecuting independent stage plans.
Both shell scripts pass `bash -n`; all three new Python files pass Ruff lint/format.
No unrelated suites were run. Live hosted verification is incomplete, not production-ready.

Next hosted approval, only after outstanding runtime/backup/target checks are accepted:
**Approve Stage B only: deploy compatibility release `1.2-6749226f1af65b63`, SHA-256
`9d81fa9b7700557eac2cb41edd5ab861d19a6b8c4f9052e55068e5eab784df80`, to the
confirmed existing App Service/resource group in the approved subscription, SSO disabled,
demo enabled; enumerate any approved settings/restart and bounded demo acceptance writes.
No migration, grants, membership writes, SSO activation, restore or later stage is authorized.**
Do not execute that request while prerequisite evidence remains UNKNOWN.

## Update: check only the remaining blockers

The runtime-channel limitation above describes the first automation version. It was a
placeholder rather than an observed authorization denial. A separate, bounded probe
now uses the existing main-app shell via `az webapp exec`; the default full preflight
says `ACTUAL_RUNTIME_PROBE_NOT_RUN` instead of claiming a channel is unavailable.

```bash
bash scripts/verify_sso_deployment_readiness.sh --remaining-only
```

This reuses the existing context and confirms fresh target/identity pins, reads current
CLI management permission metadata and streams the pinned reviewed SELECT contract
in memory through the existing main-app runtime connection. It performs no upload,
install, deployment, restart, grants or persistent configuration changes. No full
schema/backup/artifact check under CLI identity is repeated. CLI shell capability and
existing SCM authorization are prerequisites, not automatically enabled or granted.
Runtime PASS is scoped to the runtime 004 contract; recovery status remains separate.
If the app's existing interpreter/environment or channel is unavailable, stop at
UNKNOWN. See the latest section of [the approval report](FINAL_SSO_DEPLOYMENT_APPROVAL.md#remaining-blockers-update--confirmed-operator-evidence-4-november-2026)
for exact boundaries and the Stage B versus migration recovery requirements.
