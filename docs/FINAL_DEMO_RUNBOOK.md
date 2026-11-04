# Final panel demo runbook

Updated 31 October 2026, Asia/Kolkata. **CONDITIONAL DEMO READINESS; NOT PRODUCTION READY.**

## Safe reproducible local rehearsal
From repository root, Terminal 1:
```bash
.venv/bin/python -B scripts/run_offline_demo.py --port 8010 --frontend-origin http://localhost:5174
```
Terminal 2:
```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8010 npm run dev -- --host 127.0.0.1 --port 5174
```
Open **http://localhost:5174**. The launcher creates a new disposable database with all current tables, fixture generation/moderation, limited regex PII and ADLS disabled. It does not migrate/open the existing database. Open the printed credential-file path privately; copy the Admin value into Access token. Never paste credentials into chat. The browser exchanges it for an expiring demo session. Sign out revokes that session server-side. Stop only these terminals; disposable files are removed on graceful exit.

Fresh installation: Python 3.12/3.13, Node 24, `python3 -m venv .venv`, `.venv/bin/pip install -r backend/requirements.lock.txt`, `cd frontend && npm ci`. Fresh backend lockfile installation and all 415 tests passed in a temporary Python 3.13 environment. A temporary npm ci --ignore-scripts installation passed lint and production build; OS libraries were reused. For an existing persistent local database, inspect and approve its migration plan before running migration commands; use the disposable launcher for rehearsal.

## Panel workflow
1. Login and Settings: explain fixture/live mode, PII mode, release provenance and role; Admin/Auditor can view actual reservation quotas and available provider token counts. These are not billing estimates.
2. Policies → Create policy. Name `Panel Protection`. Set secret BLOCK, PII REDACT, moderation BLOCK and keyword `internal-only`. Optional entity/category selections are real controls. In regex rehearsal select EMAIL_ADDRESS/PHONE_NUMBER/CREDIT_CARD/US_SSN only; PERSON needs installed Presidio. Save draft. Name search/status/enabled filters query the server.
3. Submit → optionally demonstrate reviewer rejection back to DRAFT → Submit → Approve → Publish → Activate. Enable if disabled. History shows immutable versions. Restoring a version only creates a draft; repeat all approval/publication gates before activation. Active policy cannot be archived; published history cannot be deleted.
4. Simulator: choose policy and inspect `person [at] example [dot] com`. Expected REDACT and revalidated safe text. Simulation never generates, but live mode can invoke moderation and consumes request allowance.
5. Playground safe example: `Explain the benefits of data governance briefly.` Expect input ALLOW, fixture generation, output ALLOW, safe response and persisted execution/audit metadata.
6. Synthetic PII: `Contact person [at] example [dot] com or +91 9876543210`. Expect REDACT/reinspection for the configured entities. No real personal information.
7. Secret: `api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345`. Expect BLOCK before generation. Keyword `internal-only` enforces its configured action.
8. Fixture moderation: `[MODERATION_FLAG]` → BLOCK; `[MODERATION_UNAVAILABLE]` → fail-closed BLOCK/UNKNOWN. These markers are deterministic fixtures and do not establish actual Moderation API behavior. A real live moderation fixture needs separately approved wording and allowance.
9. Unsafe output fixture: `[OUTPUT_SECRET]` → generation succeeds but output inspection blocks; no model content is released. Score is explanatory weighted control evidence, not legal certification.
10. Edit keyword action to HUMAN_REVIEW, save, republish and activate. Submit `internal-only`. Review → Inspect metadata → assign an enabled same-tenant reviewer username (offline reviewer is `offline-reviewer`), enter a nonsensitive note, approve/reject. Original prompt/output is not stored. Approval never releases content. Use Submit revised text for reinspection, change the text, and resubmit through current input/model/output gates. The new execution records its source review.
11. Rate a decision; Validation history shows aggregate feedback. Inspect history and audit events; raw prompt/response text is excluded.
12. Audit & reports: default 90-day window, at most 366 days; default maximum 10,000 metadata records/5 MB. Offline Export JSON/CSV correctly records FAILED because ADLS is disabled. It demonstrates durable failure, not successful cloud storage. Reconcile/recover performs explicit bounded storage verification/retry when configured. Do not demonstrate successful ADLS on fixtures.
13. Disable the active policy; a new request must receive 409/no enabled active policy. Re-enable. Logout; the prior session must be rejected. Auditor can view policies but cannot create/edit them.

## Live demonstration boundary
The same real workflows need SQL 004, approved runtime permissions and the new hosted package. Do not point new local source at the existing SQL 003 database. Follow FINAL_DEPLOYMENT_VERIFICATION.md first. Proposed safe live request: `Explain data governance in two short sentences.` Proposed PII request uses only the synthetic contact above. A maximum of two generation calls/eight moderation calls, no retries, is proposed—not approved. The exact tenant, existing active policy, session/audit/execution/usage write scope and expected PII action must be agreed first. An ADLS demonstration needs one separately approved new object plus exact read-back/hash verification. Never silently create a hosted policy or change activation to make a live test pass.

Evidence: local Chrome and HTTP test reports establish these fixture workflows. They do not replace fresh paid provider acceptance. Full cloud demo readiness remains conditional.


## Fresh hosted acceptance checkpoint — 31 October 2026

Use FINAL_HOSTED_APPROVAL_PLAN.md and FINAL_HOSTED_DEMO_ACCEPTANCE.md for the newly refreshed evidence. The hosted service is still the previous deployment and SQL revision 003. Fresh local Chrome has 49 passing checks; this does not authorize or prove cloud workflows. Do not present fixture screenshots as live Azure results.

Panel architecture narration: React sends same-origin authenticated requests to FastAPI. The backend resolves the tenant's enabled active policy, inspects input with configured PII/secrets/Moderation controls, calls existing Azure OpenAI only when permitted, reinspects output, and stores metadata decisions/audit in Azure SQL. Human review holds content and requires revised resubmission. SQL export jobs persist an idempotent metadata snapshot before existing ADLS upload; reconciliation checks object bytes before completion. SQL sessions and quota reservations are durable. No extra Azure service is involved.

After separate live approvals, demonstrate in this order:

1. Login/dashboard: existing provisioned authorized account; session created, real stored counts displayed, no invented activity. Capture dashboard and release Settings; hide credentials.
2. Dedicated synthetic policy `Panel Protection`: draft, validate, submit, authorized approval, publish, activate, enable; screenshot lifecycle/history. Honor any distinct-reviewer requirement. Record prior active assignment and obtain approval for activation/restoration; never silently replace a business policy. Disable/re-enable and verify effective-policy behavior, then inspect rejection and restore-as-draft where supported.
3. Safe generation: exact `Explain data governance in two short sentences.` One approved generation only, no automatic retry; show input decision, actual generated response, output decision and execution/audit IDs. A provider error is a failed live check; stop and capture sanitized correlation evidence.
4. PII: exact `Please contact demo.user@example.com`, `Contact demo.user [at] example [dot] com`, documented synthetic phone `+91 9876543210`, and mixed `Please contact demo.user@example.com or +91 9876543210`. Match expected BLOCK/REDACT to the actual active policy, inspect entity labels/redaction/reinspection. If blocked before generation, verify generation was not called. Each live request may invoke paid moderation and must fit separately approved allowance; do not silently generate four more responses.
5. Moderation: approve a non-graphic fixture and exact allowance before provider calls. Capture real category mapping and policy decision. `[MODERATION_FLAG]` is exclusively a fixture-mode demonstration, never evidence of real provider invocation.
6. Human Review: synthetic `internal-only` under approved HUMAN_REVIEW rule; show held execution, authorized assignment and decision, then revised safe resubmission. Approval does not directly release held content. Resubmission may incur generation/moderation and needs remaining approved budget.
7. Compliance/audit: open the generated execution; show applicable, passed, failed, unknown and not-applicable controls, weighted-score inputs/result and matching stored audit IDs. Unknown must not be narrated as passed. Capture metadata-only views.
8. ADLS: approve one synthetic-only record scope and fixed idempotency key. Show PENDING/UPLOADING→COMPLETED job, deterministic object metadata and independent content hash read-back. Existing tenant exports can include existing records; verify snapshot contains only approved synthetic records before upload, otherwise stop. Do not export arbitrary business history to satisfy the demo.
9. Failures: show invalid input/auth and authorized role denial safely; explain timeout/failure, quota and durable export recovery using isolated fixture evidence. Do not induce a production outage or corrupt sessions/exports. Run duplicate export acceptance only within approved no-extra-object scope.
10. Final UI: login, dashboard, policies, validation, generation/output gate, review, compliance, audit, feedback, analytics, export history, settings; capture desktop/mobile loading and errors, console results and candidate asset fingerprints. Every screenshot must be labeled with environment/date/release. Current fresh screenshots are local fixtures under evidence/hosted-preflight-2026-10-31/.

A full live panel sequence needs more paid requests than the single safe generation approval; request those bounds explicitly before running it. Final readiness remains blocked until every required cloud workflow has direct evidence.
