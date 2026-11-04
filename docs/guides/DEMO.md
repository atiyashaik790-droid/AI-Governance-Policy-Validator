# Technical demonstration and viva guide

## Eight-minute walkthrough

**0:00–0:45 — Problem.** “Enterprise LLMs can expose personal information and secrets or produce disallowed content. This application inserts governance before generation and before response release. The score explains control results; the decision enforces policy. These checks do not certify GDPR or HIPAA compliance.”

**0:45–1:30 — Architecture.** Show the architecture diagram in `ARCHITECTURE.md`. Explain React → authenticated FastAPI → one immutable active policy snapshot → input inspection → model provider → output inspection → audit commit → safe response. Show separate SQL persistence and sanitized ADLS export paths. State that only Azure OpenAI, Azure SQL, ADLS Gen2 and the OpenAI Moderation API are permitted external services; the application is local.

**1:30–2:30 — Policy lifecycle.** Open Policy management. Create or edit a draft. Show the JSON preview and simulator. Submit → Approve → Publish → Activate with an authorized token. Show version history. Editing afterward resets to a draft while the old active version remains intact. Disable the active policy and show the gateway refusing requests; enable it again.

**2:30–4:30 — Playground.** Begin by reading the mode label aloud: “The current model and moderation providers are deterministic local fixtures, not live Azure. PII uses real local Presidio.” Use the safe prompt and inspect both stages. Use the synthetic secret button: BLOCK, model not invoked. Use synthetic PII: initial REDACT, revalidated true, no original email reaches generation. Use fixture moderation and fixture failure markers: FAILED or UNKNOWN moderation, both safely blocked. To show output blocking, enter `[OUTPUT_SECRET]`: input passes, fixture generation produces a synthetic secret internally, output blocks, response withheld. Never imply these markers are behavior of a real moderation model.

**4:30–5:30 — Human review.** Set a blocked-keyword rule to HUMAN_REVIEW in a new draft, then approve/publish/activate it. Submit `internal-only`. Show the hold, no generation, and the review case. Reviewer approval records `APPROVED_RESUBMIT_REQUIRED`. Explain that this implementation does not store/replay held content; revised content must pass the gateway. Approval does not override BLOCK or release an unvalidated response.

**5:30–6:30 — Audit and analytics.** Show persisted executions, control statuses, weighted contributions, policy versions and immutable audit events. Show decision distribution and score trend generated from real local fixture executions. Submit a numeric feedback rating. Attempt JSON/CSV export only when ADLS is configured; otherwise demonstrate its truthful FAILED attempt status, not a fake downloadable cloud report.

**6:30–7:15 — Security and tests.** Explain authenticated tenant predicates, server-controlled roles, bounded request bodies, SQLAlchemy bound parameters, secret-free audit metadata, immutable ORM history and optimistic policy concurrency. State actual test results from READINESS.md. Explain that cloud contract tests use mocked HTTP and SQL Server compilation is not a live migration test.

**7:15–8:00 — Boundaries and next steps.** Show the readiness matrix. Cloud credentials and Docker remain external blockers on this workstation. Production work includes enterprise identity, retention, database privileges, operational resilience and encrypted review replay. Do not call the application production-ready.

## Reproducible scenario evidence

Run `.venv/bin/python scripts/smoke_demo.py` with both local servers running and fixture mode selected. The script reads the private local Admin token without printing it and writes `demo-results.json`. It creates real policies and actual fixture validation executions; it does not insert invented analytics counters. All sample PII and secrets are synthetic.

Ten checks: lifecycle/simulation; safe generation; input secret block; PII redaction and revalidation; moderation flag; moderation outage; output secret block; disable/enable behavior; review disposition with no release; audit/analytics persistence. Cloud verification is a separate future run with approved credentials.

## Presentation outline

1. Business risk and the interception layer.
2. Local architecture and approved services.
3. Versioned policy lifecycle and active snapshot consistency.
4. Deterministic decisions, redaction revalidation and independent scoring.
5. Safe generation and output blocking demonstration.
6. Tenant/RBAC/audit security and metadata-only review scope.
7. Automated test evidence and truthful integration status.
8. Limitations, lessons, and next development priorities.

## Challenges and solutions

- No cloud credentials: isolated real adapters from explicitly labeled deterministic fixtures; never fabricated a live result.
- Detector/provider failures: UNKNOWN control status, no score credit, fail-closed release behavior.
- Sensitive audit persistence: store metadata and counts, omit prompts and matched substrings; export a narrower allowlist.
- Mutable policies during requests: bind both inspection stages to one immutable version; use optimistic concurrency for draft updates.
- Dangerous redaction assumptions: merge spans and run the complete policy again; moderation cannot use span redaction.
- Review bypass risk: record metadata-only dispositions; require resubmission instead of releasing held content.
- Test tooling advisories: upgraded Vitest/Vite and reran build, lint and tests; npm audit reports zero known vulnerabilities at validation time.
- Restricted sandbox: TestClient hangs even for a minimal health app; tests were run with authorized local execution outside that restriction, without altering security gates.

## Five likely solution architect questions

**1. Why use deterministic policy logic if moderation is AI-based?** The detector can be probabilistic, but enforcement must be predictable. Normalized findings and explicit UNKNOWN states feed a deterministic precedence rule. The same configured findings yield the same decision, and scores cannot override blocking.

**2. How do you guarantee blocked prompts never reach generation?** The gateway calls the provider only after input ALLOW or revalidated REDACT. Tests mock the provider and assert it is never called for secrets, holds and moderation failures. The same immutable policy snapshot inspects output before audit commit and release.

**3. Why SQLite if the requirement includes Azure SQL?** SQLite supports a reliable local demonstration while credentials are unavailable. SQLAlchemy separates the database URL from business logic, Alembic provides migrations, and tests separately compile SQL Server DDL. SQLite success does not prove SQL Server success; live driver/connectivity/migration tests remain blocked.

**4. Can an approved reviewer override a critical violation?** No. This reduced implementation records dispositions without releasing content. Revised input must pass all current controls. Full automatic review replay needs encrypted retained content, authorization, expiry, an approval bound to exact content and policy, and mandatory revalidation/output inspection.

**5. Is an 85/100 score evidence of legal compliance?** No. It is an explainable weighted heuristic control score. FAILED and UNKNOWN controls get no credit; disabled controls are not applicable. A 25%-weighted moderation failure can still BLOCK independently of the total. Legal compliance requires organizational processes and context beyond this tool.
