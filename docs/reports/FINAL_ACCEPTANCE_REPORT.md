# Final acceptance and handover report

Updated 30 October 2026, Asia/Kolkata. **COMPLETE — CONTROLLED TECHNICAL DEMO READY.**
This report supersedes earlier approval-pending and ADLS-failure verdicts for the agreed
controlled demonstration. Historical evidence is retained unchanged. No production-readiness claim.

## Project and architecture

The existing React/TypeScript/Vite interface and FastAPI/SQLAlchemy backend run together
in the existing Python 3.13 Azure App Service. Same-origin `/api` requests use scoped,
server-validated hashed bearer identities and roles. Azure SQL persists eight application
tables. Immutable policy snapshots govern input, Azure OpenAI generation and output.
OpenAI Moderation and Presidio contribute controls; sanitized export metadata goes to ADLS.
No new service, architecture, schema, dependency in the project, enterprise SSO or durable
recovery feature was introduced. Local SQLite remains the persistent development default.

## Repository baseline and actual changes

Repository: `/home/sigmoid/AI governance policy validator`; branch `main`; commit
`8d12cc4caf78ad2b38c0d81fa297d27ace7aca9a`. Existing tracked and untracked changes were
preserved; no commit/push occurred. The prepared provider correction was present and its
package matched working-tree provider bytes. This turn changed one stale mock expectation
in `backend/tests/test_providers.py`, deployment state in Azure, and handover documentation.
No additional application-code or UI change was necessary. See [repository state](../evidence/final-acceptance-2026-10-30/repository-baseline.json).

Initial broad regression: 223 passed, 1 failed. The old mock required `overwrite=False`.
It now requires `overwrite=True, match_condition=MatchConditions.IfMissing`, matching
the tested conditional-create contract. Real SDK wire regressions continue to require
`If-None-Match: *` on create, ETag-conditioned flush, and rejection of existing files
without append/flush. The initial failed browser assertions were test-locator mistakes;
corrected selectors passed without application changes. Earlier aborted/sandbox runs
are not counted as successful tests.

## Deployment verification

Target: https://app-governance-validator-atiya-1026.azurewebsites.net

Deployment: **`eec1e450-11c4-4c0e-939f-f9df9e68999b`**.
Prepared ZIP: `/tmp/governance-adls-final-bqcipv0q/governance-adls-create-only.zip`.
ZIP SHA256: `b1a3dc0f3d53e98c4ce8c133cbd81d29146299530c42622a11cd384b492d46e1`.
Provider SHA256: `0da32cb68c09068a107025de001f7f766bde65ee1c09bb51f821ee24df95ecc1`.
Only `app/providers.py` differs from the prior package. The provider checksum was read
from the deployed Oryx archive and matches the tested source. Azure's platform event
confirms this deployment serving at **19:46:57 IST** (14:16:57 UTC).

The client command timed out after 300 seconds; it was **not resubmitted**. Server-side
build status became complete/active/status 4. No critical new startup errors appeared in
the inspected startup logs. Postdeployment HTTP smoke: **21 passed, 0 failed**.
Hosted configuration/foreign-policy denial: **6 passed, 0 failed**. Health/readiness
returned 200; readiness/settings executed non-destructive SQL checks; SQL/live/Presidio
configuration was confirmed. Authenticated existing routes, invalid-token rejection,
Developer export denial, exact frontend asset bytes, private-path denial and CORS passed.
Evidence: [worker](../evidence/final-acceptance-2026-10-30/serving-verification.json), [smoke](../evidence/final-acceptance-2026-10-30/postdeploy-verification.json),
[configuration](../evidence/final-acceptance-2026-10-30/configuration-verification.json).

Recovery remains the existing ZIP deployment mechanism: preserve SQL/storage records
and settings, diagnose first, and redeploy the preserved prior
`/tmp/governance-adls-final-bqcipv0q/governance-adls-final.zip` if a verified regression
requires rollback. Its SHA256 is `f54ab2adc143a0abcf8014e92d0f9f0a9badeace51d33da1ed484bd4220b0a64`.
That prior package contains the known export defect, so rollback restores prior behavior,
not ADLS acceptance. No rollback, resource deletion, migration or data reset was needed.

## ADLS export and independent integrity verification

The user explicitly approved the exact package deployment, exactly one fresh export,
and conditional temporary reader access. The exclusive fsync checkpoint was written
before POST; automatic HTTP retries were disabled. New generation/moderation calls: **0/0**.

| Field | Verified value |
| --- | --- |
| Client request identifier | `8ac75d1a-62ab-4e75-81d7-f077299e41b2` |
| Export ID | `eae2ead0-2a52-4a34-a5dd-bcfb071a7df5` |
| Created | 30 October 2026, 19:48:36 IST |
| Response | HTTP 201; SUCCEEDED |
| Account / filesystem | stgovvalidatoratiya1026 / governance-reports |
| Object path | `governance-reports/2026/10/30/eae2ead0-2a52-4a34-a5dd-bcfb071a7df5.json` |
| Format | JSON, UTF-8 |
| Record count | 9 |
| Expected/downloaded/storage size | 1745 bytes |
| Expected SHA256 | `d561b2df77cee461bdf3a78d9e039ca1d4179dd267202f6d03941075b48e3cfb` |
| Downloaded SHA256 | `d561b2df77cee461bdf3a78d9e039ca1d4179dd267202f6d03941075b48e3cfb` |
| Exact byte/content comparison | PASS |
| Temporary reader cleanup | PASS; pre-existing assignments preserved |

Independent SQL rows supplied the expected values. The export query has no ORDER BY,
so the verifier first proved a unique-ID bijection for all nine downloaded records, then
serialized the independently sourced SQL rows in that observed order using the actual
contract key order and `json.dumps` defaults. It did not assume a different arbitrary
ordering must produce identical bytes. The only keys were request_id, timestamp,
decision, policy_id and version; no prompts, responses, credentials or user content.

The first exact-path read was 403. Only then was the approved filesystem-scoped reader
created for the existing operator identity. After download/comparison it was removed;
independent role inventory confirmed removal and preservation of all prior assignments.
Downloaded bytes were processed in memory and discarded; no downloaded payload copy
was retained. Private SQL snapshots/checkpoints remain in `/tmp/governance-final-stabilization` for evidence,
not public documentation. [Export evidence](../evidence/final-acceptance-2026-10-30/export-verification.json): **41 passed, 0 failed**.

All four prior FAILED exports and all earlier rows in all eight approved-tenant tables
remain unchanged. The separately existing synthetic foreign tenant was **not empty** at
this turn's baseline; all of its actual rows were compared and remained unchanged.
The old empty-tenant assumption was rejected rather than clearing that data or claiming
isolation failure. A hosted request for a foreign policy ID returned 404.
Only one export and one audit event were added. Final approved-tenant counts:
`{"policies":2,"policy_versions":2,"active_policy_assignments":1,"audit_events":32,"validation_executions":9,"human_review_cases":1,"feedback_records":2,"evaluation_exports":5}`.
Audit event `07725b12-9a0e-46fd-a820-df039138f70f` records `report.SUCCEEDED` for this export.

## Browser acceptance

Real headless Google Chrome through temporary Playwright Core tooling was used. It was
installed under /tmp; no project dependency/lockfile changed. **72 hosted checks passed,
0 failed**; **50 disposable local checks passed, 0 failed**.

Hosted pages: overview, policies, simulator, playground, validation history, reviews,
compliance analytics, audit/reports and settings at **1440×1000**, **820×1180** and
**390×844**. Login/deep-link protection, invalid credentials, sign-out, invalidated-token
errors, role denial, policy search/status filters, immutable history, metadata details,
and the exact successful export's visible history passed. No hosted mutating requests
were sent. No unhandled exceptions, missing assets or failed transport requests occurred.
Four resource console errors corresponded exactly to intentional 401/403 denial tests;
no unexpected critical console error was observed.

Disposable SQLite + fixture generation/moderation + regex PII verified UI author/edit/save,
simulation, submit/approve/publish/activate/enable/disable, immutable history, unused-draft
archive/delete, ALLOW/REDACT/BLOCK/HUMAN_REVIEW, secret/moderation failure and unsafe-output
withholding, numeric feedback, review approval/rejection/details and navigation. These
are real browser tests, **not fresh cloud-provider verification**. Prior live provider
results are cited separately. Browser tests never altered hosted policies or review cases.

Screenshots were visually inspected for desktop layout, mobile forms, policy tables,
spacing and overflow. Wide tables intentionally scroll horizontally; a separate browser
check confirmed action buttons remain reachable on mobile. Four positive-height chart
bars were confirmed after scrolling them into view and settling animation. Offscreen
animation can make a full-page screenshot capture a chart before its bars appear.
No demo-blocking UI defect was established; no broad redesign occurred.

Scope limits: there is no token time-expiry mechanism in demo auth; invalid-token error
handling was tested, and time-based expiration is NOT APPLICABLE. There is no supported
policy-reject endpoint; human review has approve/reject. Policy validation is backend
schema validation on save plus simulation. Audit pagination and policy filters were
verified; no new audit search feature or feedback aggregate panel was invented. This is
Chrome/demo visual acceptance, not a formal WCAG, load or cross-browser certification.

Evidence: [hosted](../evidence/final-acceptance-2026-10-30/browser-hosted.json), [local](../evidence/final-acceptance-2026-10-30/browser-local-final.json),
[mobile actions](../evidence/final-acceptance-2026-10-30/mobile-table-verification.json).
Screenshots: [dashboard](../evidence/final-acceptance-2026-10-30/hosted-desktop-_.png), [policies](../evidence/final-acceptance-2026-10-30/hosted-desktop-_policies.png),
[successful export](../evidence/final-acceptance-2026-10-30/hosted-successful-export.png), [tablet](../evidence/final-acceptance-2026-10-30/hosted-tablet-_.png),
[mobile](../evidence/final-acceptance-2026-10-30/hosted-mobile-_.png), [mobile form](../evidence/final-acceptance-2026-10-30/local-mobile-_policies_new.png),
[mobile actions](../evidence/final-acceptance-2026-10-30/hosted-mobile-policy-actions.png).

## Regression and security summary

- Backend: **224 passed, 0 failed, 0 skipped, 1 deselected**, 8.38 s.
- Focused ADLS/deployment/combined workflows: **40 passed, 0 failed, 0 skipped**; subset,
  not 40 additional unique backend tests.
- Frontend with opt-in real disposable HTTP integration: **7 passed, 0 failed, 0 skipped**.
- Python lint and formatting: PASS, 39 files. Frontend ESLint: PASS. TypeScript/Vite: PASS.
- Existing warnings: Starlette/httpx deprecation; production JS chunk >500 kB advisory.
- Historical SQL HTTP driver test module excluded; fresh migration test deselected to
  preserve saved boundaries. No existing database or cloud was used as a local fixture.

Auth/RBAC, tenant isolation, lifecycle, append-only history, audit-before-release and
export contracts remain covered by the executed suite. Live denied-role/foreign-ID
checks and independent before/after SQL comparisons support continued enforcement.
Credentials stayed in memory/private existing files; no tokens/settings/connection
strings were printed or included in documentation. No destructive migration, cloud
service dependency, permission widening retained, auth weakening or failed-record deletion
occurred. This is bounded verification, not proof that every historical external log
has been audited for secrets. [Exact test summary](../evidence/final-acceptance-2026-10-30/regression-summary.json).

## Final acceptance matrix

PASS means the stated method/scope passed; prior live evidence is labeled and does not
claim fresh paid calls. All 22 required components are represented.

| Component | Expected behavior | Verification method | Evidence reference | Result | Remaining issue |
| --- | --- | --- | --- | --- | --- |
| Frontend startup | Hosted React and assets load | Live HTTP byte equality + Chrome | [postdeploy-verification.json](../evidence/final-acceptance-2026-10-30/postdeploy-verification.json) | PASS | None |
| Backend startup | Correct worker starts; health/readiness 200 | Platform worker event + live HTTP | [serving-verification.json](../evidence/final-acceptance-2026-10-30/serving-verification.json) | PASS | None |
| Authentication | Valid credential accepted; invalid denied; logout works | Hosted Chrome + API | [browser-hosted.json](../evidence/final-acceptance-2026-10-30/browser-hosted.json) | PASS | Demo tokens have no time expiry |
| Authorization | Server rejects forbidden role operations | Developer 403 + backend regressions | [browser-hosted.json](../evidence/final-acceptance-2026-10-30/browser-hosted.json) | PASS | Enterprise identity deferred |
| Azure SQL | Connected; persist export/audit; preserve prior rows | Independent SELECT snapshots across eight tables | [export-verification.json](../evidence/final-acceptance-2026-10-30/export-verification.json) | PASS | No migrations rerun |
| Azure OpenAI | Governed generation only after input approval | Prior live ALLOW/REDACT evidence + current mocked regressions | [FINAL_LIVE_VERIFICATION_RESULTS_2026_10_30.json](../FINAL_LIVE_VERIFICATION_RESULTS_2026_10_30.json) | PASS | Prior live evidence; zero fresh generation calls |
| OpenAI Moderation | Inspect input/revalidation/output; fail closed | Prior live evidence + fixture failures/regressions | [FINAL_LIVE_VERIFICATION_RESULTS_2026_10_30.json](../FINAL_LIVE_VERIFICATION_RESULTS_2026_10_30.json) | PASS | Prior live evidence; zero fresh moderation calls |
| Presidio | Detect PII before safe release | Prior live REDACT evidence + hosted mode check | [configuration-verification.json](../evidence/final-acceptance-2026-10-30/configuration-verification.json) | PASS | Local browser uses limited regex fixtures |
| Policy CRUD | Create/edit drafts; supported delete/archive | Disposable real Chrome + backend tests | [browser-local-final.json](../evidence/final-acceptance-2026-10-30/browser-local-final.json) | PASS | No hosted policy mutations |
| Policy lifecycle | Submit/approve/publish/activate/disable/enable/history | Disposable Chrome + hosted immutable history | [browser-local-final.json](../evidence/final-acceptance-2026-10-30/browser-local-final.json) | PASS | Policy rejection is not a supported lifecycle action |
| Input governance | ALLOW/REDACT/BLOCK/HUMAN_REVIEW | Fixture Chrome and prior live evidence | [browser-local-final.json](../evidence/final-acceptance-2026-10-30/browser-local-final.json) | PASS | Fixtures clearly distinguished |
| Output governance | Inspect output and withhold unsafe content | Fixture output secret + prior live output inspection | [browser-local-final.json](../evidence/final-acceptance-2026-10-30/browser-local-final.json) | PASS | No new live model invocation |
| Simulation | Validate draft rules without generation | Disposable Chrome + backend schema tests | [browser-local-final.json](../evidence/final-acceptance-2026-10-30/browser-local-final.json) | PASS | Live moderation may still incur a call; not repeated |
| Human review | Queue/details/approve/reject preserve held content | Disposable Chrome + hosted recorded metadata | [browser-local-final.json](../evidence/final-acceptance-2026-10-30/browser-local-final.json) | PASS | Approval requires revised resubmission |
| Feedback | Save numeric rating; aggregate via existing API | Disposable Chrome + live read-only summary + tests | [browser-local-final.json](../evidence/final-acceptance-2026-10-30/browser-local-final.json) | PASS | No dedicated aggregate UI panel |
| Compliance scoring | Show persisted heuristic scores and contributions | Hosted charts + existing engine regressions | [browser-hosted.json](../evidence/final-acceptance-2026-10-30/browser-hosted.json) | PASS | Not regulatory certification |
| Audit logging | Committed export event; historical records unchanged | Independent SQL comparison + hosted listing | [export-verification.json](../evidence/final-acceptance-2026-10-30/export-verification.json) | PASS | ORM immutability is not tamper-proof storage |
| ADLS export | One fresh export succeeds on deployed correction | Exactly one POST; SQL/audit + object read | [export-verification.json](../evidence/final-acceptance-2026-10-30/export-verification.json) | PASS | Allowance consumed; no automatic retry |
| ADLS file integrity | Exact object contains expected sanitized records | Independent download, row bijection, bytes, size, SHA256 | [export-verification.json](../evidence/final-acceptance-2026-10-30/export-verification.json) | PASS | Temporary reader removed |
| Browser acceptance | Nine hosted pages render at three viewports | 72 hosted + 50 disposable Chrome checks | [browser-hosted.json](../evidence/final-acceptance-2026-10-30/browser-hosted.json) | PASS | No formal WCAG/cross-browser certification |
| Regression testing | Relevant existing suites and build pass | 224 backend; 40 focused subset; 7 frontend; lint/build | [regression-summary.json](../evidence/final-acceptance-2026-10-30/regression-summary.json) | PASS | One migration test deselected; historical driver module excluded |
| Documentation | Current status, evidence, demo and backlog agree | Handover links and evidence validation | [documentation-verification.json](../evidence/final-acceptance-2026-10-30/documentation-verification.json) | PASS | Historical checkpoints intentionally preserved |

## Known limitations and next use

No mandatory controlled-demo blocker remains. See [production backlog](PRODUCTION_BACKLOG.md)
for enterprise SSO, token lifecycle/security hardening, durable export recovery and
operational limitations. Docker and production certification are outside this acceptance.
The one new export allowance is consumed. Use existing recorded live history and the
verified export in the hosted demo. Use the disposable fixture rehearsal for interactive
mutations/Generate/Export demonstrations; offline exports correctly fail because ADLS is
disabled. A further live Generate or Export requires a separate allowance.

Use [technical demo runbook](../runbooks/TECHNICAL_DEMO_RUNBOOK.md), final section 17, for the panel.
**Final verdict: COMPLETE — CONTROLLED TECHNICAL DEMO READY.**
