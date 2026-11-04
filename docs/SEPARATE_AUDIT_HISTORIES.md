# Separate audit histories — 2 November 2026

Audit & reports now presents three independent views:

- Policy history: creation, edits, simulation and lifecycle actions (`policy.*`).
- Governance execution history: generation and validation outcomes (`governance.*`), including ALLOW, BLOCK, REDACT and HUMAN_REVIEW.
- Administrative history: remaining events, including session, review and export administration.

The browser defaults to Policy history. Each category is filtered on the server within the authenticated tenant before ordering/pagination. Switching categories resets the page to one and closes previously inspected metadata. The API's omitted category still means all events for backward compatibility. Existing rows are preserved. Exports continue to include all audit categories within their export window, as the UI explains. The existing Validation history page continues to show execution metadata.

Validation: 440 backend tests and 17 frontend tests passed; frontend tests include actual local backend integration. Backend tests cover category separation, filtering before pagination, tenant isolation, unfiltered compatibility and invalid categories. Frontend tests cover switching between all three histories. Lint, formatting, TypeScript and production build passed. Actual SELECT-only Azure SQL checks passed for all three category queries.

Artifact and fingerprint: [package evidence](evidence/separate-audit-history-package.json). Deployment verification is recorded separately when the hosted release activates. No schema, grant, credential or business-history mutation is required. Previous release ZIP is retained for rollback.

Hosted release `1.2-bcba8e97a8b84793` is verified active after deployment `313cc865-e189-45e0-97ef-b4e4720134e5` and one worker restart. Warm-up initially caused read timeouts; subsequent readiness and all three authenticated category endpoints returned HTTP 200 with no mixed-category rows. Served frontend assets contain all three category controls. The diagnostic session was revoked. See [hosted evidence](evidence/separate-audit-history-hosted.json).
