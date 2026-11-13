# Stage C final recovery confirmation — 4 November 2026

> **Executed and accepted 4 November 2026:** [Stage C result](STAGE_C_EXECUTION_RESULT.md). Revision is now 005. Preparation/gate statuses below are historical and superseded by the recorded user approval and successful execution.

**Prepared only. Execution blocked on confirmed ownership, escalation details and explicit approval of the exact C + D-visibility scope.**

## Fresh read-only findings

Recovery checks completed at **21:21:39 IST / 15:51:39 UTC**, 4 November 2026. Existing SQL database remains Online, Standard S0; retention seven days, differential interval 24 hours; CONTINUOUS PITR earliest `2026-10-28T15:55:06Z`. No restore was performed or near-current exact restore second proven.

The signed-in CLI principal resolves to display name **atiya tabsum**, object ID `b5d8bfbe-f03a-4132-a13f-ab49aae834b7`, expected tenant/subscription. Its management allow metadata covers database read/write, restore-point read and backup read. Enumerations returned zero locks and zero deny assignments at subscription, resource group, server and source database scopes. Previous Stage C SQL evidence establishes the same pinned identity's migration permissions; those successful SQL checks were not repeated.

These facts establish an **eligible existing identity**, not an appointment, a claim that the chat user controls that identity, or a guarantee of actual restore/destination capacity. **No designated 005 recovery operator is confirmed. No incident escalation contact/channel is recorded.** Historical volunteering for the 31 October drill is retained but not promoted to current ownership. Shortest resolution: explicitly designate the eligible existing principal's responsible human (or name another existing authorized operator and verify that operator), confirm their availability, and supply one existing DBA/on-call contact/channel with an accountable incident decision-maker. Do not send anyone messages as part of preparation.

Evidence: [fresh recovery metadata/authority](evidence/stage-c-final-2026-11-04/recovery-authority-readonly.json), [signed-in identity](evidence/stage-c-final-2026-11-04/current-cli-identity.json).

## Exact limited grants for approval

Target is the **existing database role** `governance_validator_web_runtime`, inherited by contained runtime user `app-governance-validator-atiya-1026`. It is not the migration operator or Entra SSO application registration.

```sql
GRANT VIEW DEFINITION ON OBJECT::dbo.sso_memberships TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON OBJECT::dbo.sso_transactions TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON OBJECT::dbo.sso_sessions TO [governance_validator_web_runtime];
```

At 005, deployed compatibility release `1.2-6749226f1af65b63` validates all 17 model tables even with SSO off. The runtime currently lacks inherited rights for future-table metadata. These three object-level grants supply definition/index/key visibility as part of the same transaction; they grant no SSO row SELECT/INSERT/UPDATE/DELETE, alter no membership and activate no SSO. Full operational SSO permissions remain outside this request. The release supports 004/005; no redeployment is needed. Stage B evidence was read, not rerun. Real-runtime 005 compatibility remains a required post-migration acceptance check, not an already-passed hosted 005 claim.

## Proposed owner decisions

| Decision | Concrete proposal for approval | Limit |
|---|---|---|
| Recovery owner | Designate the responsible human for existing eligible CLI principal `atiya tabsum` / `b5d8bfbe-f03a-4132-a13f-ab49aae834b7`, if that person accepts responsibility and is available | Not yet appointed; do not presume the chat user is that operator |
| Incident escalation | User supplies one existing DBA/on-call name plus email/team/channel/contact and the incident/cutover decision-maker | No destination is known; no message will be sent without authorization |
| RTO | **120 minutes** from incident declaration to validated service restoration | Target, not measured guarantee; includes approval delays, restore, validation and cutover |
| RPO | **15 minutes** maximum loss of committed writes relative to the incident write-freeze boundary | Requires owner-reviewed exact pre-DDL recovery point and backup-lag assessment; retention length does not prove it |
| Quiet window | **15 minutes today**, starting at T0 when final explicit approval is received, all gates pass and confirmed owner/on-call are available | First 3 minutes pre-DDL gates, up to 5 minutes transaction, remaining 7 minutes verification; no start if owner unavailable or window has elapsed |
| Transaction stop limits | **15-second lock wait**, existing 15-second SQL statement timeout, **five-minute transaction budget** checked before DDL and before commit | Any SQL/guard/grant/assertion failure before commit rolls back both schema and grants; uncertain outcomes require fresh inspection, never retry |
| Incident database recovery route | Same-server PITR into proposed **`sqldb-governance-validator-recovery-005-20261104`**, proposed S0/Local matching source, followed by validated, separately approved cutover | Name is a planning proposal, not existing/reserved/authorized. Incident resource creation, cost/lifetime/cleanup and configuration cutover require separate exact approval before action |

The recovery owner must accept the numeric objectives and assess the historical recovery evidence, backup lag and destination constraints. Record an exact pre-DDL UTC recovery point inside the then-current PITR window. If recoverability within the approved RPO cannot be supported, stop before DDL for a revised decision; do not silently widen RPO or claim metadata proves the exact point. Actual acceptance of a restore timestamp and end-to-end RTO are unproven without a restore. Accepting that uncertainty must be explicit; no new restore drill is automatically demanded or authorized.

For the proposed incident route, record the recovery owner's confirmation of destination tier/quota/cost constraints, existing restore and SQL access authority, source preservation, validation and cutover decision process. If no incident PITR/new-database/configuration exception can ever be approved, provide an already validated alternative meeting the objectives before migration. Merely having an escalation contact is not a database recovery plan. No restore or configuration action occurs under this Stage C request.

## Atomic execution and stop conditions

Use the exact review-only SQL batch [stage-c005-with-separate-visibility-approval.REVIEW_ONLY.sql](../deployment/stage-c005-with-separate-visibility-approval.REVIEW_ONLY.sql), SHA-256 `26b9537cc66fdf7eb4853b177fd5f8fdfd411edcd73949a0f3a0cae9adc02f97`, with the [prepared command](STAGE_C_MIGRATION_APPROVAL.md#exact-prepared-execution-command--review-only-do-not-run-now). Neither has been executed.

1. Before connecting for mutation, require recorded owner/contact, accepted objectives/incident recovery route, active quiet window, fresh recovery boundary and explicit approval of **both C and exactly the three D-visibility grants**. Operator coordinates writers and confirms no inference/export in flight. Preserve settings and artifacts without displaying credentials. Stop if any prerequisite is unavailable.
2. In one existing CLI-identity transaction: guard exact database, clean single 004/no partial 005, default dbo, expected role and independently pinned runtime SID/membership. Record baseline counts and trigger definitions; lock baseline tables during the transaction. No broad permission changes or impersonation.
3. Create exactly three reviewed SSO tables with keys/indexes; apply exactly the three VIEW DEFINITION statements; advance the one Alembic row to 005. All are uncommitted until the final step.
4. Verify the three direct grant records, complete 005 schema, new tables empty, unchanged original table counts and trigger definitions, and transaction deadline. Commit only if every check passes. A failure in either DDL or grants aborts the combined transaction; no intermediate 005-without-visibility state is deliberately committed.
5. After timeout/disconnect, inspect fresh history/partial state before any decision. If clean 004, keep the compatibility app and stop. If 005 committed, retain 005, investigate and escalate. Do not downgrade, stamp history, drop SSO tables, deploy the 004-only original ZIP or automatically retry. Post-commit acceptance failure cannot be repaired by transaction rollback; stop and use the confirmed incident/forward-repair process with its explicit authorization.

The prepared command was strengthened locally to check all three grant records and the transaction budget before commit; no extra SQL permission scope was added and the reviewed SQL hash is unchanged. Python syntax was parsed only. No test suite or cloud mutation was run.

## Bounded post-migration checks

- Fresh SQL connection: exactly one 005 row; three new empty dbo SSO tables; expected columns/nullability, PKs, membership unique keys, session FK, two expiry indexes; trusted/enabled FKs, preserved history triggers and original baseline counts/relationships. Confirm exactly the approved grant additions and unchanged runtime role membership.
- Existing read-only schema verifier without `--require-sso`, explicitly demanding reported revision 005. Operator PASS alone is insufficient runtime evidence.
- Actual hosted `/ready`: HTTP 200, release `1.2-6749226f1af65b63`, revision 005, versioned schema and SSO unavailable. Its real app-managed-identity connection must inspect all new metadata successfully. `/health` succeeds; `/api/sso/status` confirms SSO false/demo true.
- One approved existing demo session: login exchange, authenticated policy GET, restoration and logout/revoked-session denial. Include bounded normal session/audit/rate-limit writes in approval. No new accounts, policy edits, provider/storage calls or repeated Stage B suite. Confirm an already-existing unexpired legitimate demo session if one is available; create no extra fixture to manufacture that evidence.
- Stop after this combined C + D-visibility scope. Credential rotation, operational SSO grants, memberships and SSO activation remain separate and untouched.

## Single consolidated approval request

Confirm **(1)** the responsible recovery operator and availability; **(2)** the actual incident escalation contact/channel and cutover decision-maker; **(3)** RTO 120 minutes, RPO 15 minutes, the 15-minute T0-relative quiet window and acceptance of currently unmeasured restore timing/backup-lag uncertainty; **(4)** the proposed incident-only PITR/cutover planning route and owner review of destination constraints, with separate exact restore/resource/cutover authorization before any incident action; and **(5)** explicitly approve Stage C 004→005 **and separately the three listed D-visibility grants**, as one atomic transaction with bounded post-migration demo acceptance. No execution until all five are recorded. No config change, rotation, SSO activation, restore or later stage is included.
