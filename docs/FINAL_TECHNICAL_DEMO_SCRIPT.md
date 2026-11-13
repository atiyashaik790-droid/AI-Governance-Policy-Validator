# Conditional 10–15-minute technical demo

**Prepared, not hosted-verified.** Run only after candidate `1.2-240cc70e239a595f` is approved/deployed, new008 database/runtime permissions and real Admin/User memberships are verified, policies are approved/seeded, and separately bounded synthetic-data/provider/reveal/export operations are authorized. Today the healthy website still uses the old release005. Do not present this script as evidence it already works on the new hosted release.

## Demo flow

| Minute | Action | Expected evidence / authorization |
|---|---|---|
| 0–1 | Open the existing HTTPS site; sign in as real Admin. Show Settings release008/schema and role, with credentials concealed. | Real Entra sign-in and session creation; Admin Studio visible. Never count a mock login. |
| 1–3 | Overview → Policies. Show eight simultaneously active policies and exact pinned versions. | Correct active count; policy attribution derives from these version IDs. Do not activate/edit without seed/write approval. |
| 3–4 | Create one synthetic draft or edit a separately approved demo-owned draft. Show save, submit/approve/publish and activation; explain disable/archive versus draft deletion. | Real policy/audit writes; lifecycle and version preconditions. Baseline eight pins remain intact unless a named approved edit changes them. |
| 4–5 | Simulator: synthetic email/phone, then secret and confidential examples. | REDACT reinspection; BLOCK for strongest violation. Simulation need not demonstrate Azure generation; moderation-enabled simulation may still call the real moderation provider. |
| 5–6 | Sign out; sign in as the distinct standard User. | Redirect to `/chat`; no Admin navigation. Attempt a read-only Admin API and expect403. Session/CSRF records are real writes. |
| 6–8 | Chat: secret, internal-only and synthetic credit-card prompts. | BLOCK, generation withheld. Some blocked decisions record incomplete moderation because it was intentionally withheld on a local hold; do not claim moderation was called. |
| 8–10 | Chat: synthetic email/phone example, then safe generation prompt. | REDACT with sanitized text sent downstream; ALLOW/generation with governed output. Exact generated prose is nondeterministic. Require separate Azure OpenAI/Moderation approval and current positive evidence. |
| 10–12 | Submit `review-required` synthetic request. Return to Admin; assign, reveal once with the required reason, resolve and show audit. | HUMAN_REVIEW; encrypted SQL content, metadata-only ordinary views, audited authorized reveal; prompt content purged on approved resolution behavior. Reveal is separately approved plaintext access. Approval does not automatically send the held prompt to a model. |
| 12–14 | History, Analytics, Audit/Reports and Feedback. Filter the synthetic tenant and show request IDs and per-policy attribution. | Recorded decisions reflect real executions. Feedback/export are writes. Export one bounded sanitized report/readback only under distinct ADLS approval. |
| 14–15 | Explain safe errors and recovery. Show preserved local/mocked outage evidence rather than deliberately breaking a live provider. | Unknown/failed mandatory controls withhold output; no invented hosted outage PASS. Old005 database and exact old-release artifact remain preserved. |

## Synthetic sample prompts

| Prompt | Expected decision / meaning |
|---|---|
| `Explain why AI governance matters in two short sentences.` | ALLOW input; generation only after all required controls pass. |
| `Explain this synthetic case: email alex@example.test or call +1 202-555-0147.` | REDACT/reinspect input. Output still inspected and may be withheld if a provider/control fails. |
| `Synthetic api_key=DEMO1234567890NOTREAL` | Secret BLOCK; no model generation. This is not an actual credential. |
| `Summarize this internal-only synthetic company note.` | Confidential BLOCK; no model generation. |
| `Synthetic credit card 4111 1111 1111 1111` | Credit-card policy BLOCK. The stronger decision wins even though another policy supports PII redaction. |
| `review-required synthetic request for an exception` | HUMAN_REVIEW; no generation until any separately authorized subsequent flow. |
| A separately approved short non-graphic threatening sentence | Real moderation result must be observed; wording does not guarantee a predetermined provider score. A missed/failed provider test is not PASS. |

`[MODERATION_FLAG]`, `[MODERATION_UNAVAILABLE]` and `[OUTPUT_SECRET]` are **fixture markers**, not reliable live-provider test prompts. Local tests used synthetic moderation evidence; they cannot establish real provider behavior. For output-leakage enforcement reuse the verified mocked-provider output test; do not ask a real model to leak secrets or claim a deterministic real output blocker without observed evidence.

## Backend explanation

Entra callback validates issuer/signature/audience/nonce/PKCE/state; server-side membership binds directory/object ID to tenant, actor and role. A server-side session and CSRF checks protect requests. The User endpoint allowlist blocks privileged APIs.

The gateway captures a deterministic ordered set of published policy versions under tenant revision/concurrency control. It evaluates input, merges PII redactions, reinspects the common sanitized text under every policy and resolves conflicts as **BLOCK > HUMAN_REVIEW > REDACT > ALLOW**. Local holds prevent generation. Eligible requests invoke configured moderation/generation, then govern output before release. Per-policy evidence and execution metadata are recorded without arbitrary original plaintext in reporting. Human Review originals use AES-256-GCM with tenant/review/execution/expiry-bound AAD and audited authorized reveal. Export is a distinct bounded ADLS operation with readback evidence.

Output-safety and baseline documents use the **existing shared input/output rule schema**; there is no output-only selector. CREDIT_CARD is explicitly selected by its dedicated policy. Eight policy documents and deterministic decisions passed local tests.

## Bounded live acceptance proposal — later separate approval

Prepare at most **six generation requests**, each short synthetic input (≤500characters) and existing700-completion-token cap; at most **16 total moderation requests**, including input/output and any standalone verification; no automatic retries beyond an explicitly counted budget. Stop on provider errors/budget exhaustion. A count cap is not a hard monetary cap; current model pricing must be rechecked when requesting live approval. No live call is authorized now.

Plaintext approval should name one synthetic review/request in the approved tenant, one authorized Admin/reviewer, at most one reveal and one resolution. No arbitrary existing content. ADLS approval should name at most one sanitized report object under `demo-acceptance-20261109/` in existing filesystem `governance-reports`, ≤64KiB, with readback/digest verification; no deletion or unrelated enumeration. Existing project/provider charges continue; no new service.

## Troubleshooting and fallback

- `/ready`503: inspect sanitized schema/key/cleanup diagnostics; stop demo writes. Never turn off readiness/security checks. Restore the approved old app **with its old005 connection**, not the old app against008.
- SSO callback/membership errors: verify exact registered callback, tenant/client, enabled mapping and session clock. Never grant Admin to a User to make login succeed or use an email instead of a verified object ID.
- No active policies / revision conflict: use approved publication/pins and refresh the revision; do not overwrite concurrent changes.
- Moderation/generation unavailable: show the recorded safe error and existing local fixture evidence, clearly labelled. Required moderation failure blocks eligible live generation even when Azure OpenAI is configured.
- Review unavailable: confirm key custody, runtime content permissions and a healthy cleanup worker. No manual plaintext SQL inserts or key regeneration. Seven-day logical expiry plus application cleanup is not hard physical erasure through outages/backups.
- ADLS unavailable: show sanitized report preview/local fixture evidence; mark live export NOT VERIFIED. Do not silently save sensitive data elsewhere.

Likely architect questions: Why strongest-decision precedence? How are exact policy versions attributed? How is tenant binding trusted? What happens when moderation fails? How are sessions revoked? What can the runtime identity mutate? How are encryption keys recovered/rotated? What happens to new writes on paired rollback? Answer using the evidence above: server-side identity, pinned snapshots, fail-closed controls, audited reveal, narrow grants, preserved keys and explicit write-loss handling. Actual PITR, hard temporary-resource expiry, off-host key recovery and hosted acceptance remain separate unproved gates.

## Login walkthrough and architect answers

After approved cutover, use two separate browser profiles: Admin **atiya.tabsum@Sigmoidanalytics.com** (objectb5d8bfbe-f03a-4132-a13f-ab49aae834b7) and User **demo-user@Sigmoidanalytics.com** (objectf4799f3f-703a-42b7-acf7-4cbbf55e7320). The owner handles passwords and MFA directly with Microsoft. Admin actoratiya-tabsum-shaik opens Studio; User actorgpv-demo-user routes to/chat. Both are bound server-side to tenantdemo-appservice-4e2dcce8d618. Current old005 website does not yet consume these new008 memberships; a successful current Admin login is not new-release acceptance.

| Architect question | Evidence-based answer |
|---|---|
| Can a User grant itself Admin by changing browser data? | No. Verified Entra tid/oid resolve to an enabled server membership; backend endpoint authorization independently restricts roleUser. Confirm with real403 after deployment. |
| How do multiple policies combine? | Exact published version snapshots are evaluated in deterministic order. Strongest decision wins:BLOCK>HUMAN_REVIEW>REDACT>ALLOW, with shared redaction and per-policy reinspection/attribution. |
| Does policy count multiply provider calls? | Compatible moderation requirements are combined; per-request budgets/deadlines apply. Local holds withhold generation. Actual billable call counts must still be observed and bounded during live acceptance. |
| Is a configured provider proven working? | No. Existing MI RBAC/keys/configuration are readiness inputs; only approved actual calls with observed results establish live verification. |
| Is database tenant isolation SQL RLS? | No. The shared runtime identity has reviewed object rights; application identity binding and tenant-filtered repository/authorization checks enforce tenant boundaries. SQL bindings/local tests passed; real hosted cross-tenant acceptance remains pending. |
| What does Admin/User bootstrap prove? | Actual008 memberships and least-privilege effective SQL rights, not real interactive SSO or a hosted MI token login to that target. |
| Why encrypt review originals separately? | Normal audit/history avoids original plaintext. AES-GCM content uses identity/expiry-bound AAD; explicit assignee/role/session/version checks and audited reveal guard access. |
| Is seven-day retention exact physical erasure? | Logical expiry denies access; application cleanup handles deletion/resume. Outages and retained backups prevent a hard physical erasure guarantee at exactly seven days. |
| What is the rollback boundary? | Restore exact old005 app with old005 connection/settings. Keep new008 and its keys; new008-only writes do not appear on005. Actual PITR/failure-recovery proof remains a separate mandatory gate. |
| Are all features hosted now? | No. Current healthy release is005. The candidate and tests are prepared, new008/bootstrap passed, policy seed/cutover/live acceptance remain unapproved or unverified. |
