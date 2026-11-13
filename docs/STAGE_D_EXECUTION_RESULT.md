# Stage D execution result — 4 November 2026

**PASS — Stage D COMPLETE. Stopped before Stage E.**

The user's explicit Stage D-only approval authorized the seven reviewed object permissions to existing SQL role `governance_validator_web_runtime`, actual App Service managed-identity verification, and bounded application/demo checks. No other scope was exercised.

## Applied permissions

Existing database `sqldb-governance-validator-dev` on `sql-governance-validator-dev-atiya`, group `rg_techdemo_Atiya_Tabsum_Shaik`, subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`.

| Object | Approved and now effective operations |
|---|---|
| dbo.sso_memberships | SELECT |
| dbo.sso_transactions | SELECT, INSERT, UPDATE |
| dbo.sso_sessions | SELECT, INSERT, UPDATE |

Executed once in a guarded transaction using the existing pinned operator identity. Approved SQL SHA-256: `379cdb13d45722129d90c99000e2ca4a435bc3f2d4c4dfdcba48af256001d79a`. Exact database/revision 005, runtime user SID and role membership were guarded. Existing direct role grants were checked to avoid blindly repeating already-present grants; no duplicate grant was required.

The database-wide permission catalog before/after comparison showed **exactly seven additions**, precisely those approved object/role/permission tuples, and no removals or other changes. Existing VIEW DEFINITION grants were not repeated. Role membership catalog and SSO membership count remained unchanged. Revision stayed 005; no schema migration occurred. Commit: **21:58:43 IST / 16:28:43 UTC**.

## Actual runtime verification

A targeted SELECT-only probe ran through the existing main App Service container using installed `app.database.SessionLocal`, with managed-identity mode, expected tenant/principal/SQL database/user and revision/role guards. It performed no upload, install, hosted file write, DML, token/environment dump or SSO activation.

Actual managed identity `600447fe-5fea-4801-9033-ab4aafc474cc` returned:

- **7/7 required operation permissions = 1 (effective).**
- VIEW DEFINITION on all three objects = 1 (preserved).
- sso_memberships INSERT, UPDATE, DELETE = 0.
- sso_transactions DELETE and sso_sessions DELETE = 0.

The complete permission-catalog delta also confirms no broader or other unnecessary permission was introduced. This is actual application runtime permission evidence, not an operator/db_owner check passed off as runtime proof. No SSO table INSERT/UPDATE exercise or real Microsoft login was run; neither is needed to verify these effective grants while SSO remains disabled.

## Bounded application checks

**10/10 assertions PASS**, using only health/readiness/authentication-status, one existing demo login, one tenant-scoped policy GET, logout and revoked-session denial. The demo session produced only its normal session/audit/rate-limit/logout writes. No policy mutation, provider, moderation, export or storage operation was invoked.

The existing release `1.2-6749226f1af65b63` remains ready on **005**. Actual flags: **SSO disabled, demo login enabled**. Application checks finished **21:59:12 IST / 16:29:12 UTC**; actual-runtime permission probe finished **21:59:32 IST / 16:29:32 UTC**.

These were the expressly approved narrow post-grant checks, not a repeat of the Stage B or Stage C suites. No unrelated tests were run.

## Evidence and stop state

[Grant execution and exact permission delta](evidence/stage-d-execution-2026-11-04/grant-execution.json), [actual runtime permissions](evidence/stage-d-execution-2026-11-04/runtime-permissions.json), [bounded application checks](evidence/stage-d-execution-2026-11-04/bounded-application-checks.json), [executed command record](evidence/stage-d-execution-2026-11-04/executed-grant-command.RECORD_ONLY.txt), [runtime verifier record](evidence/stage-d-execution-2026-11-04/runtime-verification-command.RECORD_ONLY.txt), [result summary](evidence/stage-d-execution-2026-11-04/result.json).

No SSO user/membership was provisioned; the Stage E mapping remains a proposal with no approval to apply it. No Admin membership was assigned. No Azure configuration change, SSO activation, credential rotation, migration, release deployment, restore, new resource or later rollout step occurred. No Stage D blocker remains.
