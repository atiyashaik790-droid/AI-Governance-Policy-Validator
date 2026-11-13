# Conditional 10–15 minute technical demonstration

**Status: prepared, not hosted accepted.** Use https://app-governance-validator-atiya-1026.azurewebsites.net/ only after `final-hosted-demo-acceptance.md` records a successful candidate cutover and hosted checks. Use separate Admin and User browser profiles; the account owners enter their own credentials and MFA.

| Time | Navigation and click | Synthetic input / expected result | Explain to mentor |
|---|---|---|---|
| 0–1 min | Open site → Sign in as Admin → Overview | Admin Studio, correct release and revision008 | Entra validates identity; server-side membership binds tenant and role. |
| 1–3 | Policies → active list | Eight pinned, published policies; count 8 | Exact policy versions are captured for each execution. |
| 3–4 | Policies → New draft → Save → Submit → Approve → Publish, only with approved demo-owned draft | Lifecycle and audit entries; restore baseline eight pins afterward | Revision checks prevent silent concurrent edits. |
| 4–5 | Simulator → Run each sample below | BLOCK, REDACT, HUMAN_REVIEW, ALLOW as specified | Strongest decision wins; redacted text is reinspected. |
| 5–6 | Sign out → Sign in as User | Redirect `/chat`; no Admin navigation; Admin API returns 403 | UI and backend both enforce role boundaries. |
| 6–8 | Chat → Send blocked samples | No model generation; decision and attribution visible | Local holds avoid unnecessary provider calls. |
| 8–10 | Chat → Send safe sample, only within the approved one-generation/five-moderation budget | ALLOW and governed answer if providers succeed; record actual call IDs | Input moderation, generation and output governance are separate checks. |
| 10–12 | Chat → review sample; Admin → Human Review → Assign → Reveal with reason → Resolve | HUMAN_REVIEW, encrypted content, one audited authorized reveal | Plaintext is withheld from ordinary history; reveal is separately authorized. |
| 12–14 | Admin → Governance Execution History → Validation History → Compliance Analytics → Audit & Reports | Filter synthetic request IDs; inspect decision, policy versions, totals and audit. Export/read back one sanitized report only if approved | Evidence joins decisions to policies, actor and tenant. |
| 14–15 | Overview → Settings/status | Show actual integration outcomes and rollback evidence | Paired old005 app/database rollback; new008-only writes stay in new008. |

## Eight policy demonstrations

Use the eight exact policy names and rules shown in the active list. These synthetic examples exercise their combined behavior; confirm each displayed attribution before narrating it.

| Input to Simulator or Chat | Expected result |
|---|---|
| `Explain why AI governance matters in two short sentences.` | ALLOW when mandatory controls pass. |
| `Email alex@example.test or call +1 202-555-0147.` | REDACT, then reinspection. |
| `Synthetic api_key=DEMO1234567890NOTREAL` | Secret BLOCK. |
| `Summarize this internal-only synthetic company note.` | Confidential BLOCK. |
| `Synthetic credit card 4111 1111 1111 1111` | Credit-card BLOCK even where PII redaction also matches. |
| `review-required synthetic request for an exception` | HUMAN_REVIEW, no generation. |
| A short, separately approved non-graphic safety sample | Observe actual Moderation result; never promise a specific score. |
| Safe generated answer | Inspect output governance and recorded policy attribution; response wording varies. |

Architecture: Entra OIDC login uses server-side tenant/role membership and sessions. The gateway evaluates ordered published policy snapshots, merges redactions, reinspects sanitized content, and resolves `BLOCK > HUMAN_REVIEW > REDACT > ALLOW`. Eligible requests invoke configured Moderation and Azure OpenAI; output is governed before release. SQL holds decisions, versions, history and audit. AES-GCM protects review originals with bound metadata and audited reveal. ADLS receives only an authorized sanitized export.

## Fifteen architect questions and answers

1. **Why strongest-decision precedence?** A permissive match cannot override a stronger safety hold.
2. **How do you know which policies ran?** Execution evidence records pinned published versions and per-policy attribution.
3. **Can browser role data grant Admin?** No; backend checks server-side Entra object membership and role.
4. **How is tenant isolation enforced?** Verified identity binds to tenant; repositories and authorization filter by that tenant. Real hosted negative checks are still required.
5. **Is SQL row-level security used?** No; the current design uses application tenant controls and narrow runtime grants.
6. **What if Moderation fails?** Mandatory control failure withholds output; show recorded safe error, not a fabricated live outage test.
7. **Do eight policies make eight provider calls?** Compatible moderation requirements are combined; inspect actual call receipts.
8. **What happens to blocked prompts?** Local holds prevent model generation; metadata and decisions may be audited.
9. **How is output governed?** Model output is evaluated before release under the captured policy set.
10. **Why encrypt review originals?** Ordinary history excludes original plaintext; AES-GCM content requires authorized audited reveal.
11. **How are keys recovered?** The existing key ID and bytes must be preserved; off-host recovery proof remains a cutover gate.
12. **Can a User reveal reviews?** Only authorized role, assignment, session and reason checks permit it; verify hosted denial.
13. **Does seven-day retention mean physical erasure at that instant?** No; expiry denies access, while cleanup and backups have separate timing.
14. **What does rollback restore?** Exact old005 release with old005 connection/settings; new008 records remain in new008.
15. **Does configured Azure access prove integrations work?** No; bounded actual provider receipts and ADLS readback are needed.

If any hosted check fails, present the corresponding BLOCKED result and local fixture evidence explicitly as local. Do not describe this script as a successful hosted run until the acceptance report is updated.
