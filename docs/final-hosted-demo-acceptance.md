# Final hosted demo acceptance — BLOCKED

9 November 2026 (Asia/Kolkata). This is a factual checkpoint, not a hosted sign-off. Website: https://app-governance-validator-atiya-1026.azurewebsites.net/ . Fresh read-only checks found the Web App Running, `/health` returning `ok`, and `/ready` returning `ready` with release `1.2-ca5df7c1dc19e525` on database revision005. The new database is Online; Azure backup metadata does not demonstrate an actual restore. The requested `1.2-240cc70e239a595f` on revision008 has **not** been deployed.

Local SHA256 recheck passed: candidate `274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22`; paired old005 rollback `6a6a265bc2d27f9965a1a3abb33eaf61a4bd433a1257b241c183a871c12a57db`; reviewed seed manifest `b5b1aea3889a8a42193f7a5058a427cf8da7ed09fdd41fb0437aa5944c72104b`. Azure inventory confirmed managed identity object ID `600447fe-5fea-4801-9033-ab4aafc474cc` and absence of the prior `gpv-policy-seed-20261109` firewall rule. The subsequent main-container probe did prove hosted new008 authentication.

The approved corrected seed subsequently committed eight new008 policies. The firewall rule was independently confirmed absent again after cleanup. Read-only App Service settings inspection confirms managed-identity SQL mode, the expected identity, the old005 database target and presence of review-key settings; capture and cleanup flags are absent. No setting value containing a key was printed. A read-only main-container managed-identity query confirmed new008, revision008, runtime role membership and eight active assignments. The hosted frontend active-policy count cannot match the new008 backend count until the approved cutover.

| Critical feature | Status | Actual evidence / missing proof |
|---|---|---|
| Revision008 schema and SQL grants | PASS for prior Azure SQL qualification | Recorded migrations001–008 and effective rights; main-container hosted MI query confirmed revision008. |
| Eight published active policies | PASS — 8/8 in new008 SQL | `POLICY_SEED_RETRY_RESULT.md`: committed transaction and separate post-commit readback; old005 website does not yet display them. |
| Candidate deployment, health, readiness, frontend/backend | BLOCKED | Current old005 health/readiness PASS; candidate not deployed or exercised. |
| Actual hosted managed identity → new008 | PASS | Main App Service container authenticated with its MI and read DB/user/role/revision/policy counts; `FINAL_RECOVERY_GATE_RESULT.md`. |
| Admin/User Entra sign-in and routing | BLOCKED | Memberships recorded; real candidate sign-ins and `/chat` routing untested. |
| Admin API restriction, tenant isolation, RBAC | BLOCKED | Local tests exist; real hosted negative tests pending. |
| Policy lifecycle, simulation and four decisions | BLOCKED | Local candidate tests exist; hosted policy set absent. |
| AI input/output governance and chatbot | BLOCKED | Hosted candidate and provider tests pending. |
| Encrypted Human Review and authorized reveal | BLOCKED | Key staged and local tests exist; hosted capture/cleanup/reveal untested. |
| Governance/validation history, dashboard, analytics, audit | BLOCKED | Hosted synthetic records and UI acceptance pending. |
| Azure OpenAI, Moderation, ADLS | BLOCKED | No real calls, export or readback in this run. |
| Recovery and rollback | BLOCKED | Exact paired artifact exists; actual PITR, off-host key custody, controlled failure recovery and safe settings restoration remain unproved. See `RECOVERY_SAFEGUARDS_CHECKPOINT.md`. |
| Final demo | NOT READY | Hosted acceptance cannot be signed off. |

The approved eight-policy seed changed only new008 policy/lifecycle records and was separately verified. The subsequent hosted MI and recovery checks were read-only. No App Service setting, deployed release, recovery resource, provider call or hosted test data was changed. See `final-blockers.md` for the remaining gates and `final-demo-script.md` for the conditional walkthrough.
