> **9 November 2026 update:** Corrected seeding is PASS: eight committed active/published policies on new008; temporary firewall rule removed and original inventory restored. See [retry result](POLICY_SEED_RETRY_RESULT.md). Hosted managed-identity new008 authentication, recovery proof and safe cutover approval remain pending. Earlier seed-pending statements below are historical.

# Next approval — eight synthetic policies on the isolated008 database

**Execution update, 9 November 2026:** The user approved one seed window. The attempt rolled back before commit; cleanup passed. See [execution result](POLICY_SEED_EXECUTION_RESULT.md). A fresh bounded access approval is required for a corrected retry. Runtime/Admin/User bootstrap remains complete; do not repeat it.

Exact write target: subscription **Devops_Azure_SV** / `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, resource group `rg_techdemo_Atiya_Tabsum_Shaik`, server **sql-governance-validator-dev-atiya**, database **sqldb-gpv-demo-v008-20261108**, UUID **80dd1ba9-74e5-4d26-8463-081572c9c22e**, revision008; tenant **demo-appservice-4e2dcce8d618**. Preserve old production and the installed Admin/User/runtime grants.

Proposed fresh firewall rule **gpv-policy-seed-20261109**, start=end **45.127.46.209**, maximum15minutes, expected5–10minutes. Freshly verify exact current blocked IP, target identity/revision, original rule snapshot and absence of this rule; abort on mismatch. Remove only the new rule immediately on success/failure, restore even after deadline, verify absence and exact original-rule preservation. No independent host-failure expiry guarantee is claimed.

Approve creation of exactly these **eight synthetic policy documents**, using the existing lifecycle and version/concurrency checks, then pin their published versions simultaneously under **MULTI** mode:

1. Customer Personal Data Protection — email/phoneREDACT.
2. API Key and Secret Leakage Prevention — secretBLOCK.
3. Credit Card Data Protection — CREDIT_CARD detection withBLOCK.
4. Confidential Company Information Protection — internal-only/confidential-demo keywordBLOCK.
5. Unsafe Content Prevention — moderationBLOCK when observed; seeding itself does not invoke moderation.
6. Human Approval for Sensitive Requests — review-required synthetic marker routesHUMAN_REVIEW.
7. AI Output Data Leakage Prevention — PII/secret inspection, using existing shared input/output rules.
8. Enterprise AI Safety Baseline — required PII/secret/moderation/keyword protections.

Exact documents are in [deployment/demo-policy-seed.REVIEW_ONLY.json](../deployment/demo-policy-seed.REVIEW_ONLY.json), profile **gpv-clean-demo-v2**. All eight and their deterministic conflict decisions passed local tests. There is no output-only selector; do not invent one. No synthetic directory identity from the local-only profile may be applied to SQL.

Operator uses approved existing Admin actor **atiya-tabsum-shaik** in the exact tenant. Use deterministic seed-owned IDs, audit creation/publication/activation, and perform draft→submit→approve→publish through existing reviewed lifecycle. Exact reruns must skip matching published documents/pins without duplicate versions or audit writes. Reject unexpected/edited existing policy data, changed memberships/grants or concurrent revision drift; do not overwrite it. Do not alter frozen migrations or stamp schema.

Verify after commit: exactly8seed-owned published policies and8pinned active versions, enabled states, matching canonical documents, MULTI mode, valid per-policy attribution structures, ordinary audit records, installed Admin/User mappings and runtime grants unchanged, no execution/review/plaintext/export/session data seeded, old website/source005 healthy, and access rule absent. No new membership or grant is included.

Risk: accidental activation/conflicts or duplicate seed state; target/tenant guards, exact documents, lifecycle checks and idempotence address it. The existing website still points to old005, so expected production downtime **0**; additional service capacity cost **USD0** beyond continuing persistent S0 billing. No provider call is required or approved.

Rollback/failure: abort the current transaction, preserve earlier committed stage evidence and stop rather than retry blindly. Only under this explicitly approved rollback scope, deactivate seed-owned pins created here and archive only these newly created policies using lifecycle/revision guards. Preserve immutable published versions/audit; never wipe schema/history, remove memberships/grants or delete a database. Stop for review if intervening changes make exact reversal unsafe. Always clean up the access rule.

**Excluded:** deployment/App Service changes, migrations, identity/grant changes, real generation/moderation, review capture/reveal, ADLS, recovery/failure injections, new resources and all production database writes. Deploy only under a later exact cutover approval after outstanding recovery and configuration-safety gates pass; no blanket deployment approval is requested now.
