# Solution architect interview Q&A

Use these answers with the 12-slide demo deck. Describe local tests as local tests. Do not describe the fresh candidate as deployed or hosted-verified.

## 1. What problem does the application solve?

It puts a policy decision point around an LLM request. It inspects an employee prompt before generation and inspects generated output before release. It records the decision, matched policy versions and sanitized evidence so administrators can explain what happened.

## 2. Why a modular monolith?

One FastAPI backend and one React website fit the small approved Azure service set and avoid distributed transaction and deployment overhead. Separate modules still isolate authentication, policy lifecycle, governance, reviews and reporting.

## 3. How does policy precedence work?

The engine captures every active published policy version for the tenant and evaluates each one. Its decision order is BLOCK, HUMAN_REVIEW, REDACT, ALLOW. A permissive policy cannot cancel a blocking match. Redacted text is reinspected before release.

## 4. Can the system support more than eight policies?

Yes. Eight policies are seed examples, not a source-code limit. The evaluator test covers 105 policy snapshots. CRUD and performance acceptance with 20 persisted custom policies still needs a dedicated local workflow test and hosted verification.

## 5. What happens if a detector or provider is unavailable?

Required evidence becomes unknown and the decision fails closed. A blocked or held input does not invoke generation; unsafe output is withheld. The UI should explain the hold without exposing the raw sensitive finding.

## 6. How are tenants and roles enforced?

Entra sign-in establishes a backend-managed session linked to a tenant membership. The backend checks the role and tenant for each protected API, rather than trusting frontend navigation. The fresh database has approved Admin and User mappings, but sign-in against the new release has not yet been hosted-tested.

## 7. Why encrypt Human Review content separately?

Reviewers sometimes need the original held text. Authenticated encryption protects it at rest; the backend controls key access. Reveal requires an authorized role and creates an audit event. Approval does not automatically forward the original prompt to Azure OpenAI.

## 8. What does the compliance score mean?

It is an explanatory control score, not a legal certification or a release gate. Satisfied applicable controls contribute their configured weights: secrets 30, PII 25, moderation 25 and configured rules 20. Failed or unknown controls contribute zero; nonapplicable controls leave the denominator.

## 9. How are audit and exports handled?

Governance and administrative events retain policy and category attribution. Reports export sanitized evidence to the existing ADLS Gen2 account and can reconcile export state. Hosted read-back and current candidate acceptance are still pending.

## 10. What has been tested in this checkpoint?

The full backend suite passed 1,325 tests with fixture providers, the frontend suite passed 133 tests with one skip, and the frontend production build passed. A concurrent frontend run had four timing failures; all passed in isolation and the full suite passed alone. This is local regression evidence, not Azure acceptance.

## 11. Why has the new candidate not been deployed?

The existing App Service still runs the older release and database. The fresh revision-008 database is seeded, and hosted managed-identity read access was recorded. The recorded recovery decision still requires an actual restore proof, off-host review-key custody and a safe settings restoration boundary. A fresh Azure CLI inventory attempt also failed because this environment has no signed-in Azure session. A new release must be pinned and approved before cutover.

## 12. What are the main limitations?

Pattern and model-based detectors have false positives and false negatives. Moderation is not a complete bias or safety certification. Knowledge-grounded hallucination detection is optional and not established here. Production claims also depend on hosted SSO, provider, SQL, review and ADLS acceptance after an approved cutover.
