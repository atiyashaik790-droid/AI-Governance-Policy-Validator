# Expanded real-life end-to-end testing — 30 October 2026

**Result: 648 test/check results passed, 0 failed against the current documented contract.**
This comprises **231 existing automated tests** and **417 additional scenario/assertion
checks**, not 648 independent user journeys. One migration test was deselected and the
historically restricted SQL HTTP driver module excluded. Three exploratory limitation
areas are recorded below; they were not silently converted into passed requirements.
No application source/configuration was changed, no deployment occurred and no Git
commit/push was made. Previous final acceptance remains available separately.

## Fresh results and evidence

| Suite | Passed | Failed | Method / evidence |
| --- | ---: | ---: | --- |
| Existing backend tests | 224 | 0 | Disposable test databases; [JUnit](../evidence/real-life-testing-2026-10-30/backend.xml) |
| Existing frontend tests | 7 | 0 | Includes actual disposable FastAPI HTTP integration |
| Expanded real HTTP scenarios | 263 | 0 | [Case-by-case results](../evidence/real-life-testing-2026-10-30/real-life-http.json) |
| Real Presidio checks | 13 | 0 | Installed spaCy/recognizers; outbound networking blocked; [results](../evidence/real-life-testing-2026-10-30/presidio-checks.json) |
| Disposable real-browser workflows | 50 | 0 | Chrome + real local API; [results](../evidence/real-life-testing-2026-10-30/browser-local-final.json) |
| Hosted real-browser acceptance | 72 | 0 | Nine pages × desktop/tablet/mobile; GET-only; [results](../evidence/real-life-testing-2026-10-30/browser-hosted.json) |
| Hosted security/availability checks | 19 | 0 | GET/CORS OPTIONS only; [results](../evidence/real-life-testing-2026-10-30/hosted-security.json) |
| **Combined test/check results** | **648** | **0** | [Machine-readable summary](../evidence/real-life-testing-2026-10-30/summary.json) |

No executed pytest/Vitest case was skipped. Backend: one deselected test and one entire
excluded module, disclosed rather than counted as passes. The 40 focused ADLS/deployment
cases are already part of 224 backend tests and were not added again. Setup HTTP calls
and the 391-request count were not counted as extra test cases. Browser checks and
backend cases overlap feature coverage; their execution results are reported separately.

## Realistic scenarios exercised

The real-HTTP runner started a new server, temporary SQLite database and six server-controlled
identities: Admin, Policy Owner, Developer, Reviewer, Auditor and a foreign-tenant Admin.
Fixture generation/moderation and regex PII were explicit; all cloud destinations were
disabled. The fixture database and credentials were removed after completion.

- Five-role matrix over existing read APIs, policy create/edit/delete/submit/approve/
  publish/activate/enable/disable/archive, governance operations, feedback, reviews and exports.
- Anonymous/malformed credentials; role denials; foreign policy/version/review/feedback
  attacks and empty foreign listings; no frontend role trust.
- Policy schema errors, invalid actions, moderation-redaction rejection, invalid keywords,
  unsupported export formats, feedback bounds, bad pagination, malformed JSON and 64 KB limits.
- Safe/multilingual/boundary-length text; synthetic OpenAI/AWS-shaped secrets, password
  assignment, private-key header, mixed-case blocked keyword, email/phone/SSN-shaped PII,
  multiple PII values, mixed PII/secret input, moderation flag/outage and unsafe model output.
- Stale approvals, forbidden lifecycle transitions, active archive/published deletion
  protection, disabled-policy fail-closed behavior, immutable versions and review dispositions.
- Redaction/revalidation, output withholding, sanitized audit metadata, numeric feedback
  and failed offline ADLS attempts accurately marked FAILED rather than invented success.
- Bounded concurrency: 20 reads and 20 independent governed writes across eight workers.
  All 40 responses were HTTP 200, all 20 write IDs were unique and all 20 executions committed.

The **391 HTTP requests** include setup, cleanup verification and multi-step workflows;
there are **263 recorded assertions/scenario checks**, not 391 independent test cases.
Concurrent batch timings: median **70.01 ms**, p95 **118.28 ms**,
maximum **180.07 ms**. These are local fixture smoke measurements, not Azure
performance, production load tolerance or capacity guarantees.

## Real Presidio and exploratory limitations

The installed real Presidio/spaCy pipeline detected and revalidated ordinary emails,
plus aliases, mixed-case/multiple emails, contextual phone and a synthetic test credit
card. Original values were withheld. No outbound connection attempt occurred.
Synthetic person recognition also returned PERSON in an exploratory probe.

| Finding | Actual observation | Implication |
| --- | --- | --- |
| Whitespace-only prompt | HTTP 200 for three spaces | Current minimum-length validation does not require non-whitespace text. Usability/input-quality improvement remains possible. |
| Feedback type coercion | `true` and numeric string `"5"` returned HTTP 201 | Current Pydantic integer field coerces these inputs; strict JSON integer validation is not enabled. Values remain bounded, but malformed client input may be accepted. |
| Obfuscated PII coverage | `demo [at] example [dot] com` returned no entity; zero-width email returned URL rather than EMAIL_ADDRESS | Recognizer coverage is not exhaustive. No claim is made that arbitrary obfuscation/Unicode evasion is prevented. |

These are findings from additional exploratory probes, **not proof that every real-world
security requirement passes**. They do not violate the currently specified field-length,
bounded-rating or heuristic-recognizer contracts, so they were kept outside the formal
pass/fail denominator. They should be reviewed before expanding production claims.
No fix was silently deployed or authentication/security scope changed during testing.

## Hosted application and browser findings

Fresh hosted testing used the existing accepted deployment and private role credentials.
All mutating browser API requests were blocked; none were attempted. Login/deep-link
protection, invalid credentials, logout, invalidated-session errors, Developer 403,
policies/search/status filters, immutable versions, record metadata and previous
successful export visibility passed. Nine pages rendered at 1440×1000, 820×1180 and
390×844 without page-level overflow. Wide tables retain their existing inner scrolling.

No unhandled JavaScript exception or failed transport request occurred. Four console
resource messages correspond exactly to the deliberately induced 401/403 responses;
these are expected denials, not undisclosed browser failures. Missing/private files,
encoded traversal, untrusted CORS and pagination bounds were denied correctly. Hosted
health/readiness returned 200; settings confirmed SQL CONNECTED, live provider mode and
Presidio. The previous verified export and four prior failed attempts remain visible.
No new independent ADLS readback or temporary permission grant was performed this turn.

Screenshots: [desktop](../evidence/real-life-testing-2026-10-30/hosted-desktop-_.png), [policies](../evidence/real-life-testing-2026-10-30/hosted-desktop-_policies.png),
[reports](../evidence/real-life-testing-2026-10-30/hosted-desktop-_reports.png), [tablet](../evidence/real-life-testing-2026-10-30/hosted-tablet-_.png),
[mobile](../evidence/real-life-testing-2026-10-30/hosted-mobile-_.png), [mobile form](../evidence/real-life-testing-2026-10-30/local-mobile-_policies_new.png),
[existing successful export](../evidence/real-life-testing-2026-10-30/hosted-successful-export.png).

## Build, dependency and safety checks

Python lint/formatting (39 files), ESLint, TypeScript, Vite production build and whitespace
checks passed. `pip check` found no broken installed requirements. `npm audit` reported
**0 vulnerabilities** across its severities: [raw result](../evidence/real-life-testing-2026-10-30/npm-audit.json).
Existing Starlette/httpx deprecation and >500 kB JavaScript chunk advisories remain.
A dependency audit result is not a penetration-test or production-security certification.

No hosted data write, migration, settings change, role grant, deployment, paid generation,
moderation or export call was made. Cloud transport-failure/SDK/no-overwrite behavior
continues to be covered by the existing mocked/real-wire offline regression suite.
Fresh cloud AI behavior was **not** inferred from fixture responses.

## Limits and verdict

No finite test run can establish “all possible” real-life behavior. This run provides
bounded, reproducible coverage of the current application and preserves prior accepted
evidence. Docker is unavailable; browsers other than Chrome, destructive recovery,
enterprise identity, formal accessibility and Azure stress/capacity testing are not
verified here. No further paid Generate/Moderation/Export allowance was supplied.

**Controlled-demo verdict remains READY.** No new failing documented-contract test or
critical hosted defect was found. The exploratory input/coercion/PII findings above
remain visible, along with the [existing production backlog](PRODUCTION_BACKLOG.md).
Prior live AI/ADLS evidence remains in [final acceptance](FINAL_ACCEPTANCE_REPORT.md)
and is not counted as freshly executed testing in this report.
