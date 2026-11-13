# Existing hosted application: 10–15 minute demo

**Status: PARTIAL — public health and release verified; interactive sign-in and fresh governance/provider operations await explicit approval.** The demo uses the existing Web App, release **1.2-ca5df7c1dc19e525**, SQL revision **005**. It does not depend on WebJobs, migrations006–008, new Human Review encryption keys or the newer local release.

Application: https://app-governance-validator-atiya-1026.azurewebsites.net

## Evidence and feature status

| Capability | Status | Evidence and limit |
| --- | --- | --- |
| Hosted health, readiness and revision005 | **VERIFIED** | 8 November 2026 13:16 IST: `/health` and `/ready` returned200; release metadata reports supported revisions004/005 and live provider mode. [Current public checks](evidence/hosted-005-demo-readiness-2026-11-08/public-recheck.json). |
| Hosted login page shell, API contract and auth boundary | **VERIFIED** | On 7 November HTML and all three served assets matched the preserved release byte-for-byte, OpenAPI was available and protected unauthenticated GETs returned401. Four initial network errors passed a targeted recheck. On 8 November `/api/sso/me` returned401 without a session. Browser rendering itself was not inspected. [Release contract](evidence/hosted-005-demo-readiness-2026-11-07/release-and-route-contract.json). |
| Microsoft SSO configuration | **VERIFIED** | Current public status says enabled/configured and demo login disabled. Existing settings indicate a60-minute session; no credentials are disclosed. |
| Admin sign-in and authenticated views | **NOT VERIFIED** | SELECT on 7 November found the operator's enabled Admin membership. Actual Microsoft/MFA sign-in was not performed; it creates session-related records and needs approval. No browser is connected to the assistant. |
| Active policy | **NOT VERIFIED currently** | On 7 November, one enabled published policy had PII REDACT, secret BLOCK, moderation BLOCK and the keyword `internal-only` BLOCK. Current `/ready` passes, but a direct operator SQL recheck on 8 November returned a sanitized connection error; its cause is not established. Confirm active policy and rules in the app after approved sign-in. [Prior inventory](evidence/hosted-005-demo-readiness-2026-11-07/sql-readonly-demo-inventory.json), [current operator check](evidence/hosted-005-demo-readiness-2026-11-08/sql-readonly-demo-inventory.json). |
| Policy management, history, analytics, reviews, reports | **NOT VERIFIED interactively** | Their routes and corresponding code are present in the exact preserved release. On 7 November, read-only SQL counted8 policies,13 versions,58 executions,247 audit events,1 review and2 export metadata records. Counts are historical, not current UI proof; new CRUD and review actions were not run. |
| PII, secret/keyword enforcement, output inspection | **NOT VERIFIED live** | Source and last-observed policy support them; no fresh governance operation was authorized. Expected outcomes below depend on current policy and real service results. |
| Azure OpenAI, Moderation, ADLS | **NOT VERIFIED live** | `gpt-5-mini`, moderation and storage settings are present. Historical metadata includes32 successful generations, but configuration or old records do not prove a new real operation works. No provider call or storage read/write occurred in this preparation. |
| Separate User Chatbot portal / User role | **UNAVAILABLE** | This deployed release has a shared playground and roles Admin, Developer, Reviewer, Auditor and Policy Owner; no dedicated User role or User Chatbot portal. On 7 November the workspace had only one enabled Admin membership; today's non-admin membership could not be refreshed. Do not claim role-isolation acceptance or modify memberships. |
| Multi-policy execution; encrypted review reveal | **UNAVAILABLE** | They require newer undeployed revisions. This release uses one active version per workspace; its basic review detail says original content is not stored. Do not claim encrypted reveal or revision008 database immutability. |

[Full status matrix](evidence/hosted-005-demo-readiness-2026-11-08/feature-status.json). **VERIFIED** always describes the specific evidence stated; route presence is not proof a protected UI workflow was executed.

## Demo script — after the bounded approval below

| Time | Presenter action | Expected outcome / stop condition |
| --- | --- | --- |
| 0–2 min | Open the application. Show the Microsoft sign-in screen and sign in **once** as the existing Admin; complete MFA personally if required. | Sign-in should land in the shared workspace. If login fails, stop; do not create a new account, alter permissions or switch to demo credentials. |
| 2–4 min | Open **Policy management**. Show the active published policy and explain draft → submit → approve → publish → activate. Verify the selected active rules are PII REDACT, secret BLOCK, `internal-only` BLOCK and moderation BLOCK. | Show only existing policy details. Do not save, create, publish or activate anything. Stop live tests if rules or release differ from the approved preflight. Only one version is active per workspace. |
| 4–6 min | In **AI playground**, submit `api_key=DEMO_FAKE_1234567890`, then `This synthetic note is internal-only. Do not distribute it.` | Each input should **BLOCK** with model not invoked. Both are synthetic. Each submission still creates usage, execution and audit records. Stop on an unexpected decision. |
| 6–8 min | In **Policy simulator**, select the same existing policy and simulate `I will hurt you and your family tonight.` Introduce it as a synthetic example. | A successful moderation demonstration shows a moderation category and **BLOCK**. `UNKNOWN`, a provider error or a keyword-only block does not prove real moderation worked. The simulator uses the **draft**, not necessarily the active published version; parity was not verified, so label this as a draft simulation. It creates usage/audit records and can call moderation. |
| 8–10 min | In **AI playground**, submit `Contact the demo team at demo.person@example.com about data governance.` | Input inspection should show **REDACT**. Redacted input can proceed to the model, so this can call both providers. A final REDACT depends on successful moderation, generation and output inspection; failure may instead block safely. |
| 10–12 min | Submit `Explain the purpose of data governance in two short sentences. Use no personal information.` | Expected: **ALLOW**, model invocation succeeds, and output inspection completes before a safe response is displayed. Generated wording is not deterministic. |
| 12–15 min | Show **Validation history**, **Compliance analytics**, and existing **Human review** or **Reports** metadata. Explain that scores are explanatory and decisions enforce release. Sign out once. | Show only authorized metadata; avoid displaying other people's sensitive records. Do not resolve existing reviews, submit feedback, export or reconcile. History/analytics views and logout require the approved session. |

All text is synthetic. The playground's built-in **Fixture moderation** and **Fixture failure** buttons contain fixture markers; the hosted app is in LIVE mode. Do not use those shortcuts as evidence of real moderation or failure behavior.

If the moderation result, policy decision, provider status, model output, health or authorization is unexpected, **stop live tests without retrying**. Do not interpret a provider error, `UNKNOWN`, or a fail-closed BLOCK as a successful moderation or generation test.

## Read-only fallback if providers are unavailable

With an approved Admin session, show existing policy, historical validation/audit metadata, analytics, review metadata and report history without running further simulations, generation or exports. Label historical records as historical; 7 November inventory included24 ALLOW,26 BLOCK,7 REDACT and1 HUMAN_REVIEW decisions and32 generation-success metadata records. They do not prove present provider availability.

Without an approved session or connected browser, show the public sign-in shell, `/health`, `/ready`, OpenAPI and the dated operator inventory in this report. Present it as an evidence walkthrough—not an interactive end-to-end or provider demonstration.

## Troubleshooting

- **SSO fails or the session expires:** do not expose tokens or bypass MFA. Use the public evidence walkthrough. Session creation/retry needs its own bounded authorization if outside the single approved attempt.
- **No active policy or changed rules:** stop before prompt submission. Do not edit or activate a policy under this rehearsal.
- **PII is not redacted / detector unavailable:** stop and report the sanitized status. Configuration alone does not prove the Presidio recognizer works.
- **Moderation returns UNKNOWN or provider unavailable:** stop. A block caused by unavailability is fail-closed, not a verified content-classification success.
- **Generation is unavailable or output is withheld:** stop and use historical metadata. Do not retry or show uninspected output.
- **Another role or the User portal is requested:** the dedicated portal/User role is absent in release005; a separate enabled non-admin identity was not verified today. No automatic role grant is allowed.
- **ADLS export requested:** show existing export metadata only. Upload, reconciliation or read-back needs its own bounded approval and a safe synthetic-data scope; do not export existing production data under this plan.

## Exact next approval

The [review-only rehearsal scope](evidence/hosted-005-demo-readiness-2026-11-08/live-rehearsal-approval.REVIEW_ONLY.json) requests **one Admin SSO login attempt and one logout**, at most **four playground generation requests and one policy simulation** using the listed synthetic prompts, at most **two Azure OpenAI calls** (700 completion tokens each) and **eight moderation calls**, no automatic retries, within15 minutes. The proposed **USD1 maximum estimated incremental provider spend is not a hard billing cap**; verify model pricing and the bound before making provider calls.

This explicitly permits only the new session/usage/rate-limit/execution/audit records caused by those operations, plus at most one unexpected synthetic review case before stopping. It does not permit editing/deleting existing records, policy or membership changes, configuration changes, ADLS calls/exports, WebJobs, temporary SQL, migrations or deployment. Preserve resulting audit records.

A connected browser and the user's interactive Microsoft/MFA authentication are still needed. Approval is required because the user explicitly prohibited real provider calls and production test-data writes without it. No live rehearsal has run.
