# Stage C — exact remaining confirmation

> **Executed and accepted 4 November 2026:** [Stage C result](STAGE_C_EXECUTION_RESULT.md). Revision is now 005. Preparation/gate statuses below are historical and superseded by the recorded user approval and successful execution.

Prepared 4 November 2026; no migration, grants, restore, credential rotation or configuration changes. No completed tests repeated. Existing reviewed execution plan and all three VIEW DEFINITION statements remain unchanged; atomic SQL hash `26b9537cc66fdf7eb4853b177fd5f8fdfd411edcd73949a0f3a0cae9adc02f97`.

## Verified current authority

Read-only inspection completed at 21:33:11 IST / 16:03:11 UTC. Actual signed-in Azure principal is `atiya tabsum`, object ID `b5d8bfbe-f03a-4132-a13f-ab49aae834b7`, in the expected tenant/subscription. The principal has inherited **Contributor** on existing resource group `rg_techdemo_Atiya_Tabsum_Shaik`; management permission metadata allows source read, database write (same-server PITR destination creation), restore-point read and backup read. No locks/deny assignments were returned at the inspected subscription/group/server/source scopes. Therefore this identity's **Azure management-plane restore authority is verified at the inspected scopes**. User Access Administrator and Foundry User are also assigned, but are not the basis for restore authority and will not be exercised.

This does not appoint a recovery operator, establish that the chat user controls that identity, prove destination quota/policy/cost readiness or guarantee a successful restore/timepoint/RTO. Previous read-only SQL evidence verifies the pinned identity's existing SQL access; no SQL permission test was repeated. Evidence: [current authority](evidence/stage-c-final-2026-11-04/user-restore-authority-confirmation.json). [Microsoft PITR permissions and new-database behavior](https://learn.microsoft.com/en-us/azure/azure-sql/database/recovery-using-backups?view=azuresql).

## Shortest confirmation procedure

1. If the verified Azure identity is yours, explicitly accept recovery ownership and availability. Otherwise identify the responsible human who controls that identity and confirm they accept; an alternative operator needs that operator's authority verified before execution.
2. Supply one actual existing DBA/on-call contact/channel and identify the incident/cutover decision-maker. No new channel/tool/resource or automatic outbound message is needed. The contact must be reachable during the window; an invented or placeholder contact does not clear this gate.
3. Finalize the provisionally accepted targets and the reviewed incident recovery route, then explicitly approve both C and the three unchanged metadata grants with bounded acceptance. The responsible owner confirms source/destination constraints and SQL access path. Restore/new-database/cost/cleanup/configuration-cutover execution still requires a separate exact incident approval.

The user has provisionally accepted RTO 120 minutes, RPO 15 minutes and a 15-minute quiet window. These are not final execution authorization. Exact pre-DDL UTC point/backup-lag assessment and no-in-flight-work confirmation are boundary checks once the owner/window is fixed; do not rerun Stage B tests. If a recoverable point meeting the agreed RPO cannot be supported, or owner/contact is unavailable, stop before DDL. Timing and exact point acceptance remain unmeasured by a live restore; owner must explicitly accept the reviewed uncertainty or request a separately authorized rehearsal.

## Reply template — complete all bracketed fields

> Recovery operator: [confirmed responsible name]. The verified Azure identity atiya tabsum (`b5d8bfbe-f03a-4132-a13f-ab49aae834b7`) is [mine / controlled by the named operator, who has accepted responsibility]. The operator is available for the window.
>
> Incident escalation: [actual existing DBA/on-call name and reachable email/channel/phone]. Incident/cutover decision-maker: [name]. I confirm these contacts are reachable during the window.
>
> I finally accept RTO 120 minutes, RPO 15 minutes and a 15-minute quiet window starting immediately after all pre-DDL gates pass and the confirmed owner/contact are ready. No inference/export or concurrent writer will be in flight. I accept that end-to-end restore time and the exact recovery point remain untested by a fresh restore; stop if the boundary assessment cannot support the approved RPO.
>
> The named recovery owner accepts the reviewed same-server S0/Local incident PITR planning route, proposed destination `sqldb-governance-validator-recovery-005-20261104`, source preservation/validation and separate approved cutover process, and has reviewed destination constraints and existing access. This does not authorize a restore, new resource, cost or configuration cutover now; obtain separate exact incident approval before such action. [Confirm this route, or provide the already validated authorized alternative.]
>
> I explicitly approve Stage C 004→005 AND separately the three unchanged object-level VIEW DEFINITION grants to `governance_validator_web_runtime`, executed atomically under the reviewed hash and stop conditions, plus bounded post-migration demo acceptance. Keep SSO off and demo on. No credential rotation, other permissions/memberships, configuration changes, restore or later stage is authorized. Stop after this scope.

No execution until this confirmation is complete. The [atomic command, verification and recovery procedure](STAGE_C_MIGRATION_APPROVAL.md) and [final recovery plan](STAGE_C_FINAL_CONFIRMATION.md) remain the reviewed operational documents.
