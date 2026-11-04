# Reviewed commit preparation

No files were staged, committed or pushed. Baseline changes are preserved in the initial status inventory. Proposed message:

`Add durable governance recovery, bounded inference and restricted demo sessions`

Review application modules analytics/exports/pii/release/sessions/usage plus changed main/models/schemas/security/providers/config/engine; additive migration 004 and offline migration compilation; frontend main/api/Overview and tests; CI opt-in integration; package builder; schema/API expectation updates; .env.example; deployment runtime review SQL; and current handover documentation/evidence. Existing untracked hosting/web_assets/offline launcher and earlier important fixes are required dependencies and must be reviewed/included, not silently omitted. Existing documentation moves remain intact.

Exclude .env, .demo-tokens.json, .azure-sql-cli, .venv, node_modules, dist, databases, artifacts and private /tmp files. The ZIP is ignored and described by its public manifest. Preserve original evidence; do not replace a failure with a passing result. Review existing versus newly changed files before staging; do not use a blind git add -A. Approval must identify inclusion of earlier uncommitted source/docs; no commit of unrelated changes is assumed.
