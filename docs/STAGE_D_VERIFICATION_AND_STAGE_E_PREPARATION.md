# Stage D verification and Stage E preparation — 4 November 2026

> **Updated after explicit approval: Stage D COMPLETE/PASS.** See [Stage D execution result](STAGE_D_EXECUTION_RESULT.md). Stage E remains proposed and unapplied. The pre-grant BLOCKED findings below are retained historical evidence.

**Stage D: BLOCKED, NOT COMPLETE — seven required data permissions absent.**
**Stage E: PREPARED ONLY — blocked on D and explicit exact membership approval.**

No grants, memberships, configuration changes, credentials, deployments or SSO activation were applied. Existing demo login/configuration were left unchanged. No Stage B/C acceptance suites or unrelated tests were repeated.

## Stage D: actual runtime verification

The reviewed existing main-App-Service shell was used for a short SELECT-only probe under the actual managed identity, reusing the installed application Python environment and `app.database.SessionLocal`. Identity/tenant/database/user/revision 005 and existing role membership were checked. No probe was installed/uploaded, no hosted files were written and no token/environment/SQL exception content was printed. Permission results are actual `HAS_PERMS_BY_NAME` outputs under the runtime identity, not db_owner/operator grants inferred as runtime rights.

| Object | Required operations | Actual result |
|---|---|---|
| dbo.sso_memberships | SELECT | 0: missing |
| dbo.sso_transactions | SELECT, INSERT, UPDATE | all 0: missing |
| dbo.sso_sessions | SELECT, INSERT, UPDATE | all 0: missing |

VIEW DEFINITION on all three objects: **PASS**. Membership INSERT/UPDATE/DELETE and transaction/session DELETE: **all absent**, as intended. Thus Stage C's metadata-only scope is complete, while operational Stage D remains BLOCKED. Do not repeat VIEW DEFINITION or mark D complete from readiness with SSO off.

Target for proposed grants: existing role `governance_validator_web_runtime`, inherited by `app-governance-validator-atiya-1026`. Runtime object ID `600447fe-5fea-4801-9033-ab4aafc474cc`, independently resolved client ID `f7bacace-698a-4968-8add-cba221319a17`.

[Actual runtime evidence](evidence/stage-de-2026-11-04/runtime-permissions.json). Supporting operator catalog inspection independently shows only the three VIEW DEFINITION grants on new SSO tables. No SQL impersonation was used.

## Exact next approval: Stage D only

Prepared [guarded review-only script](../deployment/stage-d-sso-data-permissions.REVIEW_ONLY.sql), SHA-256 `379cdb13d45722129d90c99000e2ca4a435bc3f2d4c4dfdcba48af256001d79a`. The existing MI client-ID placeholder was resolved in this separate proposal, preserving the original review artifact.

```sql
GRANT SELECT ON dbo.sso_memberships TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, UPDATE ON dbo.sso_transactions TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, UPDATE ON dbo.sso_sessions TO [governance_validator_web_runtime];
```

Request approval for just these seven missing object operations to the existing role in one guarded transaction. Before eventual apply, recheck only these rights: if already effective, do not repeat grants; review any unexpected drift. Stop on identity/target/005/membership mismatch or grant failure; no new role/user, role membership, broad schema/database grant, DELETE or runtime membership-write permission. Verify only the changed effective rights through the real runtime SELECT probe, not real Microsoft login or Stage B/C acceptance. Mark D COMPLETE only after all required rights pass and forbidden writes remain absent. Keep SSO off/demo on.

This request does not approve Stage E writes or later configuration/SSO activation. No reviewed script was executed.

## Stage E: exact proposed membership

| Field | Verified fact / proposed value requiring approval |
|---|---|
| Person | Atiya Tabsum Shaik; signed-in directory display name `atiya tabsum` |
| Directory tenant | `4ac50105-0c66-404e-a107-7cbd8a9a6442` |
| User object ID | `b5d8bfbe-f03a-4132-a13f-ab49aae834b7` |
| Directory status | Explicit Graph read: accountEnabled true, userType Member |
| Application workspace (`tenant`) | Proposed existing `demo-appservice-4e2dcce8d618`; source approved demo identity matches this workspace and SQL contains eight existing policies there |
| Stable application actor | Proposed `atiya-tabsum-shaik`, requiring explicit confirmation |
| Role | Proposed **Reviewer**, requiring explicit confirmation; not inferred from Azure or demo roles |
| Enabled | Proposed true, requiring explicit confirmation; SSO remains disabled regardless |
| Existing mapping/conflict | No row for this directory/object or proposed workspace/actor |
| Operator | Existing authorized CLI identity; SELECT/INSERT/UPDATE on memberships and audit INSERT verified effective |
| Approval reference | To be bound to explicit user approval of the exact E mapping; an arbitrary reference is not proof of approval |

[Existing Entra identity](evidence/stage-de-2026-11-04/existing-entra-user-explicit.json), [membership/conflict/operator evidence](evidence/stage-de-2026-11-04/membership-preparation.json), [proposed mapping](../deployment/stage-e-atiya-membership.PROPOSED.json). The proposal passes the existing operator tool's **plan-only validation**, which opens no database. No membership or new actor record was inserted.

No automatic Admin assignment: callback resolves only an enabled explicit `(directory_tenant, object_id)` membership and uses its stored allowed role; unknown identities are denied. It does not import Azure RBAC privileges, trust a browser-provided role, create a first-user Admin or copy the demo `admin` actor. The operator tool accepts an explicitly supplied Admin mapping but does not infer it; workflow authorization must explicitly approve Admin if desired. This proposal is Reviewer. Choosing actor `admin` or another existing application actor would require explicit ownership-mapping approval rather than guessing that historical audit/review records belong to this Entra identity.

## Prepared E execution path — not approved, do not run apply

The existing local ENTRA_TENANT_ID does not currently match the proposed directory. The generic tool also defaults to the local application's database configuration, so **do not run bare `--apply`**. Once D is complete and the exact E mapping is separately approved, bind the operator process explicitly to the reviewed SQL database and tenant. Process-only variables below do not save `.env` or change App Service configuration, and do not enable SSO:

```bash
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" \
DATABASE_URL='mssql+pyodbc://sql-governance-validator-dev-atiya.database.windows.net/sqldb-governance-validator-dev' \
AZURE_SQL_AUTH_MODE=cli \
AZURE_SQL_TENANT_ID=4ac50105-0c66-404e-a107-7cbd8a9a6442 \
AZURE_SQL_USER_OBJECT_ID=b5d8bfbe-f03a-4132-a13f-ab49aae834b7 \
ENTRA_TENANT_ID=4ac50105-0c66-404e-a107-7cbd8a9a6442 \
.venv/bin/python -B scripts/manage_sso_membership.py \
  --mapping deployment/stage-e-atiya-membership.PROPOSED.json \
  --apply --operator 'Atiya Tabsum Shaik' \
  --approval-ref 'stage-e-20261104-atiya-reviewer'
```

That reference and all mapping fields remain proposals until an explicit E approval. Immediately before an approved E write, guard exact DB/revision 005, directory/user, mapping hash and absence of remapping/conflicts. If an identical approved membership already exists, inspect audit history and avoid a duplicate apply. The existing tool writes one membership and its `sso.membership.provisioned` audit in one transaction. Verify the exact persisted six-field mapping plus audit afterwards; no real SSO login or session writes are needed at E. On conflict/failure, rollback and stop; no automatic role escalation, remapping or retries. Disabling/correcting a membership later needs its own reviewed scope; no bulk deletion.

## Shortest safe next action

Approve **Stage D only** for the missing SELECT on memberships and SELECT/INSERT/UPDATE on transactions/sessions to `governance_validator_web_runtime`, then actual-runtime SELECT-only verification. Separately confirm the proposed E workspace, named actor, Reviewer role and enabled=true (or explicitly request another role, including Admin). Stage E provisioning will still require its own exact approval after D passes. No redeploy, configuration save or SSO activation is needed for D/E.
