# Stage C migration 005 — prepared 4 November 2026

> **Executed and accepted 4 November 2026:** [Stage C result](STAGE_C_EXECUTION_RESULT.md). Revision is now 005. Preparation/gate statuses below are historical and superseded by the recorded user approval and successful execution.

**BLOCKED pending recovery decisions and separate metadata-permission approval. Nothing executed.**

Latest recovery decisions and numeric proposals: [Stage C final confirmation](STAGE_C_FINAL_CONFIRMATION.md). These remain proposals until explicitly confirmed.

## Confirmed evidence

Stage B result and its 57 acceptance assertions are preserved, not repeated. Its deployed release `1.2-6749226f1af65b63` and checksum-pinned ZIP support 004 and 005 (minimum 004; SSO requires 005). Both the recorded hosted release metadata and packaged schema helper confirm this contract. No redeployment is needed for Stage C.

Current read-only observations:

- Existing subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, group `rg_techdemo_Atiya_Tabsum_Shaik`, server `sql-governance-validator-dev-atiya`, database `sqldb-governance-validator-dev`.
- Database Online, Standard S0, Local backup redundancy; seven-day retention, 24-hour differential interval. Earliest restore time `2026-10-28T15:55:06Z`; REST reports CONTINUOUS recovery. Metadata was queried during this preparation; authority/SQL reports carry UTC observation times.
- Exactly one 004 history row; no three partial-005 tables visible under the migration identity. This is a new migration boundary check, not repeated Stage B acceptance.
- Existing CLI identity: tenant `4ac50105-0c66-404e-a107-7cbd8a9a6442`, object `b5d8bfbe-f03a-4132-a13f-ab49aae834b7`. Existing token provider pins and validates that identity. Actual SQL access: db_owner, default schema dbo; CREATE TABLE, ALTER dbo, REFERENCES dbo, VIEW DEFINITION, SELECT and UPDATE on Alembic history all effective. No new rights are needed or proposed for this operator. It is distinct from the hosted managed identity.
- Current CLI management allow metadata covers SQL database read/write, restore-point read and backup read. Lock/deny lists at subscription, group, server and source database returned empty. These support technical eligibility of this CLI identity; they do not appoint a recovery owner or prove destination policy/capacity or actual restore success.
- Existing source/server inventory contains only master and the application database. No incident destination is authorized or provisioned.

Evidence: [migration/artifact review](evidence/stage-c-2026-11-04/migration-review.json), [SQL identity/permissions](evidence/stage-c-2026-11-04/sql-migration-prerequisites.json), [backup retention](evidence/stage-c-2026-11-04/backup-retention.json), [database/PITR metadata](evidence/stage-c-2026-11-04/database-metadata.json), [management recovery review](evidence/stage-c-2026-11-04/recovery-authority-readonly.json), [runtime identity](evidence/stage-c-2026-11-04/runtime-service-principal.json).

## Exact migration and expected effects

`backend/migrations/versions/005_entra_sso.py`, SHA-256 `325a1fc4e0f7f415d102d340e2b737e1734ecdb119c76f78e61a1e4a4658618a`, has revision 005, parent 004. The reviewed SQL SHA-256 is `4bbaf5c8a0db69bf52efa9be5d5d824a60856a2a292abde8fedb8a6456b9e29d`. A fresh **offline** Alembic compile of only `004:005` matches that SQL byte-for-byte. No test suite or hosted migration was run.

Every column below is NOT NULL. Varchar lengths are exact; no server defaults or seed records are introduced.

| New dbo table | Columns | Constraints/indexes |
|---|---|---|
| sso_memberships | id varchar(36); directory_tenant varchar(36); object_id varchar(36); tenant varchar(80); actor varchar(80); role varchar(30); enabled int | PK(id); UNIQUE(directory_tenant,object_id); UNIQUE(tenant,actor) |
| sso_transactions | id varchar(64); binding_hash varchar(64); nonce varchar(100); verifier varchar(128); return_path varchar(500); expires varchar(40); consumed int | PK(id); ix_sso_transactions_expires(expires) |
| sso_sessions | id varchar(64); membership_id varchar(36); expires varchar(40); revoked int | PK(id); FK membership_id → sso_memberships.id, default NO ACTION; ix_sso_sessions_expires(expires) |

The migration updates the single Alembic row 004→005. Existing 14 application/history tables, their records/columns/indexes/triggers and account settings are preserved. New SSO tables start empty. There is no registration, membership provisioning, credential rotation, SSO activation or SSO data grant in migration 005. Its downgrade deliberately raises; do not drop tables or stamp 004.

## Confirmed atomic-visibility blocker

The existing runtime principal belongs only to `governance_validator_web_runtime`; inherited database/schema permission inspection shows CONNECT only, no dbo ownership or database/schema-wide metadata/data grant. Existing object-scoped baseline grants do not cover future objects. Therefore runtime visibility of the three new SSO tables will not be supplied by its present inherited permissions. At 005 the bridge inspects all 17 tables even with SSO disabled; migration-only execution would cause readiness failure.

Shortest least-privilege resolution: **separately approve Stage D-visibility only**, granting VIEW DEFINITION on the three new objects to the existing runtime role **inside the migration transaction before 005 commits**. No SELECT/INSERT/UPDATE/DELETE on SSO objects is needed at this SSO-off stage. Operational SSO data grants remain a later, separate Stage D scope.

A review-only combined batch is prepared at `deployment/stage-c005-with-separate-visibility-approval.REVIEW_ONLY.sql`, SHA-256 `26b9537cc66fdf7eb4853b177fd5f8fdfd411edcd73949a0f3a0cae9adc02f97`. It contains exactly the compiled 005 DDL, fail-closed database/revision/partial-state/identity/role guards, three explicitly marked VIEW DEFINITION grants, and one guarded revision update. It requires an existing outer transaction. It binds runtime SQL SID to independently resolved managed-identity client ID `f7bacace-698a-4968-8add-cba221319a17` (object ID `600447fe-5fea-4801-9033-ab4aafc474cc`). The existing contained-user SID was also independently checked against that client ID: match PASS ([binding evidence](evidence/stage-c-2026-11-04/runtime-sid-binding.json)). No role/user creation, membership change or grant has been executed.

**Stage C approval alone does not authorize this combined batch.** Both C and the exact D-visibility statements need separate explicit approval. Do not run plain `alembic upgrade 005` and then grant visibility afterward. The existing broader SSO grant script has an unresolved placeholder and separate transaction; it is not the command proposed here.

## Recovery prerequisites and shortest resolution

| Item | Current state | Required resolution before execution |
|---|---|---|
| Recovery owner | The user historically volunteered for the 31 October drill, conditional on rights; no current 005 incident assignment is recorded | Confirm the user/current pinned identity as accountable recovery owner, or designate an existing authorized operator and verify that operator's rights |
| Restore authority | Current CLI allow metadata and empty lock/deny lists support eligibility; actual restore/target policy/capacity is unproven | Bind the designated owner to this evidence, confirm destination constraints and SQL access path; grant no new rights |
| RTO and RPO | No numeric 005 incident objectives are recorded | Supply maximum outage and acceptable committed-write loss in minutes; do not infer RPO from seven-day retention |
| Current exact recovery point | Earliest continuous window known; no exact pre-DDL recovery second validated | Immediately before approved DDL, record UTC boundary, latest available recoverability/backup lag and the owner's accepted point inside the window; stop if it cannot meet RPO |
| Restore destination/cost/cutover | No exact destination or source-switch authorization; new resources and config changes currently prohibited | Approve a specific incident-only PITR destination/tier/cost and separate cutover scope, or supply an already validated authorized alternative meeting objectives. No resource is created by this preparation or by C alone |
| Quiet window | No current schedule/coordination or no-in-flight-work confirmation | Owner confirms no inference/export in flight, controls writers and accepts brief lock/readiness interruption; transaction below bounds lock waits to 15 seconds |

PITR creates another database; it cannot overwrite the source. Seven-day metadata and historical drill success do not guarantee a near-current point or measured RTO. A fresh restore drill is not automatically required: the owner must review historical evidence and decide whether a current rehearsal is necessary for these objectives. Any new drill/restore/resource has its own explicit approval. [Microsoft recovery documentation](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql).

## Exact prepared execution command — REVIEW ONLY, DO NOT RUN NOW

This is the concrete combined C + separately approved D-visibility transaction, not an approval bypass. Run only after all recovery/quiet-window gates above are recorded and both scopes approved. No hosted executor has been enabled or run. The SQL is frozen by hash. Recheck that current source/package hashes still match this document before eventual execution.

From the repository root:

```bash
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/backend" \
  .venv/bin/python -B - <<'PY'
import hashlib
from time import monotonic
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from app.config import settings
from app.azure_sql import create_azure_sql_engine
from app.models import Base
from app.schema_compatibility import inspect_schema

assert settings.azure_sql_tenant_id == '4ac50105-0c66-404e-a107-7cbd8a9a6442'
assert settings.azure_sql_user_object_id == 'b5d8bfbe-f03a-4132-a13f-ab49aae834b7'
source = Path('backend/migrations/versions/005_entra_sso.py').read_bytes()
assert hashlib.sha256(source).hexdigest() == '325a1fc4e0f7f415d102d340e2b737e1734ecdb119c76f78e61a1e4a4658618a'
batch = Path('deployment/stage-c005-with-separate-visibility-approval.REVIEW_ONLY.sql').read_bytes()
assert hashlib.sha256(batch).hexdigest() == '26b9537cc66fdf7eb4853b177fd5f8fdfd411edcd73949a0f3a0cae9adc02f97'
engine = create_azure_sql_engine(
    URL.create('mssql+pyodbc', host='sql-governance-validator-dev-atiya.database.windows.net',
               database='sqldb-governance-validator-dev'),
    settings.azure_sql_tenant_id, settings.azure_sql_user_object_id, auth_mode='cli')
new = {'sso_memberships', 'sso_transactions', 'sso_sessions'}
baseline = sorted(set(Base.metadata.tables) - new)
assert len(baseline) == 14
try:
    with engine.begin() as connection:
        transaction_started = monotonic()
        connection.exec_driver_sql('SET XACT_ABORT ON; SET LOCK_TIMEOUT 15000;')
        assert connection.scalar(text('SELECT DB_NAME()')) == 'sqldb-governance-validator-dev'
        assert list(connection.execute(text('SELECT version_num FROM dbo.alembic_version')).scalars()) == ['004']
        with Session(bind=connection) as db:
            assert inspect_schema(db, require_sso=False)['revision'] == '004'
        # Approved quiet window: lock baseline tables until commit to hold counts stable.
        before = {n: connection.scalar(text(f'SELECT COUNT_BIG(*) FROM dbo.[{n}] WITH (TABLOCKX,HOLDLOCK)'))
                  for n in baseline}
        trigger_sql = text("SELECT name,is_disabled,OBJECT_DEFINITION(object_id) FROM sys.triggers WHERE parent_class=1 ORDER BY name")
        triggers_before = list(connection.execute(trigger_sql))
        assert monotonic() - transaction_started < 300, 'Transaction budget exceeded'
        connection.exec_driver_sql('SET NOCOUNT ON;\n' + batch.decode()).close()
        visible_grants = set(connection.execute(text("""
            SELECT OBJECT_NAME(p.major_id)
            FROM sys.database_permissions p
            JOIN sys.database_principals r ON r.principal_id=p.grantee_principal_id
            WHERE r.name='governance_validator_web_runtime' AND p.class=1
              AND p.permission_name='VIEW DEFINITION' AND p.state='G'
              AND p.major_id IN (OBJECT_ID('dbo.sso_memberships'),
                                OBJECT_ID('dbo.sso_transactions'), OBJECT_ID('dbo.sso_sessions'))
        """)).scalars())
        assert visible_grants == new
        assert list(connection.execute(text('SELECT version_num FROM dbo.alembic_version')).scalars()) == ['005']
        assert all(connection.scalar(text(f'SELECT COUNT_BIG(*) FROM dbo.[{n}]')) == before[n]
                   for n in baseline)
        assert all(connection.scalar(text(f'SELECT COUNT_BIG(*) FROM dbo.[{n}]')) == 0 for n in new)
        assert list(connection.execute(trigger_sql)) == triggers_before
        with Session(bind=connection) as db:
            assert inspect_schema(db, require_sso=False)['revision'] == '005'
        assert monotonic() - transaction_started < 300, 'Transaction budget exceeded'
        # Outer transaction commits only after every in-transaction assertion passes.
    print('COMMITTED_005_WITH_SEPARATELY_APPROVED_METADATA_VISIBILITY')
except Exception:
    # No raw database errors, secrets, or automatic retries.
    print('STOP_AND_INSPECT_ACTUAL_REVISION_AND_PARTIAL_STATE_NO_RETRY')
    raise SystemExit(1)
finally:
    engine.dispose()
PY
```

The review command now explicitly checks all three grant records before commit and checks a five-minute transaction budget before DDL and before commit. The SQL batch hash is unchanged. SET NOCOUNT suppresses intermediate rowcount results; no new permission scope is added. Operator timing controls still stop on an elapsed quiet window.

All baseline count values remain in memory and no row content/credentials are printed. Existing data counts and trigger definitions are compared inside the same transaction. The single Alembic row count stays one. The in-transaction schema contract is operator-identity evidence only, not actual-runtime permission proof. A local process/network failure can leave commit outcome uncertain: always inspect actual revision/objects from a fresh connection before deciding recovery; never automatically rerun this command. Metadata mismatch, lock timeout or failed assertion before commit causes transaction rollback; independently confirm that rollback actually left clean 004.

## Post-migration verification — prepare now, execute only under approval

1. Fresh operator connection: exactly one history row 005; three new empty tables, lengths/nullability/PKs/two unique constraints/FK/two expiry indexes; trusted/enabled FKs and unchanged history triggers. Check original data/count/relationship inventory against the immediately pre-change baseline. Preserve sanitized output and transaction outcome; do not manually stamp success.
2. Verify exactly the three VIEW DEFINITION grants on the existing role and unchanged role membership. No operational SSO data grants. Reuse the SELECT-only schema verifier with `--connect` **without `--require-sso`**, because SSO remains disabled. An expected-revision check must explicitly demand 005; its generic success alone also accepts 004.

   ```bash
   AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" .venv/bin/python -B scripts/verify_schema_compatibility.py \
     --server sql-governance-validator-dev-atiya.database.windows.net \
     --database sqldb-governance-validator-dev --connect
   ```

3. Hosted `/ready`: HTTP 200, release `1.2-6749226f1af65b63`, `database_revision=005`, `schema_versioned=true`, `sso_available=false`. This uses the real managed-identity app connection and demonstrates runtime inspection of all 005 objects, unlike an operator-only success. `/health` succeeds; `/api/sso/status` reports SSO false/demo true. No repeated pre-change Stage B suite.
4. With a current approved private demo credential: one bounded session, authenticated policy GET, session restoration and logout/revoked-session denial; verify a pre-existing unexpired legitimate demo session if available. These post-schema-change checks and normal session/audit writes need explicit C acceptance scope; no policy edits, SSO login, provider/moderation or storage operations.
5. Stop after C plus its explicitly coordinated D-visibility only. Full SSO permissions, memberships and activation are separate later approvals.

## Failure and recovery

- **Before commit:** connection-managed rollback, then independent exact-history/partial-object inspection. If clean 004, keep the deployed bridge and demo login. Do not retry after an unknown outcome.
- **After successful 005:** keep schema/data 005 and the deployed compatibility bridge. Original Stage B rollback release `1.2-5e8064f901573795` is 004-only and forbidden against 005. No downgrade, table drop, revision stamping or broader permission workaround. The same corrected bridge is the application recovery artifact; since it is already deployed, do not redeploy gratuitously. Any package/configuration change needs its own approved recovery scope.
- **If metadata/readiness fails:** record actual objects/grants/runtime status, stop and request a targeted reviewed forward repair. Do not enable SSO or grant broad access to hide the failure.
- **Database damage:** named recovery owner selects the approved pre-DDL point, preserves the source and evidence, and obtains the exact incident restore/cutover authorization. Restore to a separately approved new database, validate schema, original row/relationship inventory, SQL identity access and application-runtime access, then perform separately approved application cutover with the pre-agreed write-loss/reconciliation decision. Current no-new-resource/no-configuration-change scope forbids performing that restore/cutover now.

A future incident command cannot be made executable until target and timestamp are fixed. The exact Azure CLI shape, deliberately blocked by required variables, is:

```bash
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az sql db restore \
  --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 \
  --resource-group rg_techdemo_Atiya_Tabsum_Shaik \
  --server sql-governance-validator-dev-atiya --name sqldb-governance-validator-dev \
  --dest-name "${STAGE_C_APPROVED_RECOVERY_DATABASE:?separate incident destination approval required}" \
  --time "${STAGE_C_APPROVED_RESTORE_UTC:?owner-approved recoverable pre-DDL UTC point required}" \
  --edition Standard --service-objective S0 --backup-storage-redundancy Local \
  --zone-redundant false --no-wait --output none --only-show-errors
```

No restore, cutover, cleanup, new resource or billable recovery action is authorized by this preparation or C approval alone.

## Exposed demo credentials — separate narrow rotation plan

All five exposed roles are affected: Admin, Policy Owner, Developer, Reviewer and Auditor. No values are reproduced. No credentials have been generated, rotated, disabled or changed during this preparation. Keep credential rotation separate from the schema transaction so its application restarts and session effects do not obscure migration acceptance.

Proposed pre-migration incident remediation, requiring its own explicit approval:

1. User/current authorized custodian generates fresh random credentials locally into an existing private mode-0600 store, never tool output/chat/command arguments/source. Keep the exact existing five user/tenant/role/enabled/expiry mappings; only token hashes change. Deliver each new credential privately to its authorized owner before cutover. Verify hashes privately, not by displaying tokens. Reuse existing approved secure delivery; no new service/resource.
2. Review one narrow `DEMO_ACCOUNTS_JSON` change adding a replacement hash entry for each identical identity while retaining the original hash temporarily. Existing authentication supports both entries and keeps existing sessions working during this brief overlap. Save **only this setting**, outside any portal form holding pending Entra settings; SSO remains false/demo true and database selection is unchanged. The save causes an approved app restart, so uninterrupted availability is not promised.
3. Immediately verify a fresh replacement Admin session and Developer session/role/tenant/policy read/logout, plus replacement credential exchange for the other three roles with logout. Bound overlap to an owner-approved few minutes, because exposed credentials remain usable until removal. Preserve a verified new Admin credential before the next step.
4. Second narrow save removes **all five original hashes** from `DEMO_ACCOUNTS_JSON`; retain only new entries with original identity mappings. Existing code invalidates sessions derived from removed hashes on the next request; no SQL session deletion, permissions change or migration is necessary. New sessions remain valid. Verify old credentials and old sessions deny access and replacement demo login/restoration/logout succeed. Do not print tokens or audit resource contents.
5. If replacement login fails during overlap, stop cutover while the still-working login remains available; correct the replacement privately within the approved overlap window. After originals are removed, never restore exposed hashes as rollback: use a privately preserved verified replacement Admin credential or obtain separate incident authorization for a fresh replacement hash. There is no silent credential-rotation rollback to compromised values.

This plan entails exactly two narrowly scoped settings saves/restarts plus bounded session/audit writes. It requires approval **separate from C**; no Azure configuration change or credential rotation is included in C migration approval. Custodian, secure recipient delivery and overlap window must be confirmed. [Incident record](evidence/stage-b-2026-11-04/credential-output-incident.json).

## One approval request, conditional on blockers

Approve **Stage C only, once the listed recovery/quiet-window prerequisites are recorded and the three object-level Stage D-visibility grants have separate explicit approval**, for the pinned 004→005 batch and bounded post-migration demo acceptance; keep release `1.2-6749226f1af65b63`, SSO off/demo on. Confirm the recovery owner, numeric RTO/RPO and authorized incident destination/cutover path. This does not authorize full SSO data grants, memberships, credential rotation, Azure configuration changes, restore/new resources or SSO activation. Until those prerequisites are resolved, remain at 004.
