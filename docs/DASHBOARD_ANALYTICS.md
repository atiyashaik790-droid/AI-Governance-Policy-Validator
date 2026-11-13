# Overview dashboard analytics

The Overview and Compliance analytics pages use the existing overview API. Both
the request counters and chart data use the same tenant and reporting window
(`start_date` inclusive, `end_date` exclusive after date normalization). The
source is persisted validation execution metadata. Policy evidence records and
Validation History are unchanged.

## Compliance score

The percentage measures **evidenced execution of configured controls**, not
regulatory certification, detector accuracy, or the frequency of safe content.
The four weight groups are secrets 30, PII 25, moderation 25, and configured
rules 20. Blocked keywords and custom rules share the configured-rules group.
For each request, disabled controls are excluded. Applicable group weights are
normalized by the sum of applicable weights. A group earns its weight only when
all its persisted input/output policy inspections are known (`SATISFIED` or
`FAILED`). A detected prohibited input can therefore earn its weight even when
the request is blocked. `UNKNOWN` and `WITHHELD_LOCAL_HOLD` earn zero and are
reported separately as incomplete. The dashboard pools earned and applicable
weight across requests before dividing, avoiding an average of policy scores.
When no known inspection exists, the score is unavailable. The trend applies
the same calculation by UTC execution date. It omits dates with no known result.

## Violation categories

A confirmed finding is counted once per **request, inspection stage, category**.
Duplicate detections by several policies within the same stage and category
count once. Input and output are distinct. Secret, PII, moderation, blocked
keyword, and custom findings are separate chart categories. A `BLOCK` decision
alone is never treated as a finding. Unknown, skipped, and unavailable results
are excluded from confirmed findings. Zero bars are shown when persisted stage
evidence is present and no matching finding was recorded; otherwise the page
shows an unavailable state.

These calculations read history only. They do not update enforcement, audit,
session, or policy records and require the existing authenticated tenant scope.
