# Friendly governance decision messages

AI Playground displays accessible, deterministic guidance for BLOCK,
HUMAN_REVIEW, REDACT and ALLOW. Messages are assembled locally from fixed strings;
no AI provider generates them. They apply equally to prompt-only and document
requests in LEGACY and MULTI modes. Decision codes and enforcement are unchanged.

Messages cover personal information, secrets/API keys, confidential company
information (blocked keywords), unsafe content, custom categories and generic
restrictions. Only findings contributing to the aggregate decision select a
reason. Ties use a stable category order; the contributing published policy
provides any configured next-action template. Names, matched strings, document
text, confidential patterns and original prompts never enter the message.

Provider failures and incomplete inspections use technical guidance rather than
claiming a confirmed policy violation. Intentionally withheld moderation after a
known local hold remains a policy hold. HUMAN_REVIEW always requires a metadata-
only disposition and resubmission under current policies. For an input hold,
messages explicitly state that the request was not sent to the model. If output
inspection requires review, messages accurately state that the model ran and its
response is withheld. Approval never releases the previous output automatically.

REDACT explains removal. The frontend shows a normal response only when the
aggregate decision permits release, output inspection passes, and the result is
not a technical failure. Incomplete/unknown output inspection and unvalidated
output redaction cannot release a response through the Playground.

Admins can optionally choose a next-action template per policy and decision:
`revise`, `public_example` or `contact_admin` for BLOCK, HUMAN_REVIEW or REDACT.
The optional `decision_messages` field lives in existing versioned policy JSON;
old documents default to no overrides. Create, update and rollback enforce Admin
permissions for changes to these settings. Policy Owners can preserve settings
while editing other fields. Immutable published versions retain their own choices.
No database migration is required.

Templates control only next-action wording; they cannot replace protection
reasons, model-invocation facts or mandatory review/resubmission guidance.
Free-form messages, HTML and interpolation are deliberately unsupported. React
renders all message strings as text. Guidance is not persisted as raw content;
existing sanitized audit evidence, tenant scope, SSO, RBAC and CSRF stay intact.
