# Phase D internal multi-policy enforcement

This implementation is internal only. No public v2 governance routes are registered. The existing LEGACY engine, provider adapters and public routes remain unchanged.

`app.engine_multi_policy.evaluate_policy_set(text, pins, deadline=...)` evaluates an immutable tuple of Phase B `PublishedPin` snapshots. `app.services.multi_policy_governance.execute(operation, payload, db, authenticated_identity, expected_revision=...)` owns local request orchestration for `generate`, `validate-input` and `validate-output`. Callers must supply the server-authenticated identity; no tenant identity is taken from a payload.

The internal orchestration uses the existing Phase B admission transaction to capture the active published pins and reserve quota. It requires MULTI mode and the existing enforcement roles. It never resolves a newer version implicitly. Input and output use the same admitted tuple, including version IDs, published document hashes and workspace revision.

The evaluator processes the whole tuple without a policy-count cutoff:

1. Validate the snapshot documents and hashes. Inspect every enabled local control in every captured policy. Record disabled controls as NOT_APPLICABLE and failures as UNKNOWN.
2. Apply the global local-hold gate. A local BLOCK, HUMAN_REVIEW or unavailable required detector prevents external moderation and generation. Moderation withheld for privacy is explicitly recorded as WITHHELD_LOCAL_HOLD, not silently marked complete.
3. If there is no hold, combine all requested redaction spans into one sanitized text, merging overlaps through the existing redaction helper.
4. Reinspect that same sanitized text against every captured policy. Any residual redaction requirement fails closed; there is no unbounded redaction loop. Original BLOCK/HUMAN_REVIEW findings are never replaced by another policy's sanitized result.
5. Request moderation for the union of required categories on the common text. A default category selector requires all known categories. The existing provider adapter receives an explicit required-category list and validates coverage before returning flags. Per-policy decisions use only their own selected categories. Missing or malformed evidence fails closed.
6. Aggregate with BLOCK > HUMAN_REVIEW > REDACT > ALLOW. Only complete evidence and an ALLOW/REDACT decision produce safe text. Revalidation is successful only when the final redacted text remains releasable.

Identical local detection work can be shared within one evaluation when text, control and effective detector configuration match. PII entity selectors and detector mode, keyword selectors and secret patterns participate in cache identity; violation action does not affect span detection. Cached findings are interpreted separately under each policy's action. No cache is shared across requests. Moderation work is performed once for a stage's common text and validated category union; each policy retains independent coverage and findings.

Generation is dispatched at most once per internal request execution. The reservation and captured revision are fenced immediately before dispatch. Exceptions, timeouts, malformed content and ambiguous results are withheld without automatic retries. Generated output passes the same captured set. A final fence holds the Phase B workspace/reservation gate through atomic persistence and conditional reservation completion. Expired, reconciled or revised admissions cannot release content.

Persistence uses a MULTI `Execution006` with null legacy policy identity and exactly one immutable `ExecutionPolicyEvidence` row per captured policy. Each evidence row includes the exact version, document digest and independent input/output findings. Metadata excludes input, output, matched substrings and safe text. Audit events, evidence, execution, any metadata-only review case and successful reservation finalization commit together. Failed persistence rolls back these records and finalizes the reservation as failed without resurrecting a reconciled reservation.

HUMAN_REVIEW returns no content and creates only a metadata review case. Pending reviews cannot be linked for resubmission. A resolved review never exempts revised content from current policy admission and all inspection gates.

Focused verification uses synthetic providers and disposable SQLite schema-006 databases, including 1, 6 and 105 active policies. Actual Azure SQL execution, live providers, public v2 governance, frontend, analytics and exports are outside this phase.
