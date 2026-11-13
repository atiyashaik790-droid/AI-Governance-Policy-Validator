# Approval A retry preparation — 6 November 2026

**PARTIAL — prepared; STOPPED at the new approval gate. No Azure resource changes.**

Reviewed the SQL recovery preflight, stopped Approval A result and completed local assertion verification. No completed local suite was repeated.

Fresh read-only ARM/public-price checks confirmed subscription `25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6`, group `rg_techdemo_Atiya_Tabsum_Shaik`, server `sql-governance-validator-dev-atiya`, westus2; temporary name `sqldb-gpv-mig-20261106-a1` absent; S0 capability returned; no locks/deny assignments returned at subscription/group/server scopes. This does not promise creation-time quota/policy acceptance. Production `sqldb-governance-validator-dev` and `master` are excluded by exact target guards.

Proposed scope: that exact database only, Standard S0 / 10 DTUs maximum, 250 GiB ceiling, source collation, Local redundancy; at most two sequential incarnations of the same name for success and planned isolated failure cycles, within one combined four-hour window and USD 1 estimated-cost budget. No unexplained-failure retry. Current retail S0 meter: USD 0.4839/day; conservative ten billed compute hours across incarnations: USD 0.201625, with headroom under USD 1 for tiny synthetic workload. The budget is an estimate/stop limit, not an enforceable Azure billing cap.

Reuse the existing target-locked harness and corrected issuance/persistence/cookie session contract. Only harness selection of a new evidence directory and distinct token was added: `PHASE6B_APPROVAL_A_WINDOW=retry-1`. The old window remains consumed and its evidence unchanged. Retry dry-run: seven wrong-target negatives PASS; 71 operator dependency hashes captured; artifact/migration pins PASS; Ruff PASS. The old approval token is rejected in the retry window. No execution evidence exists for the new window.

Synthetic fixture inspection found synthetic identities, policies, hashed test credentials, test keys and mocked OIDC; no production data copy. Provider calls use fixture mode before requests. Hosting validation's synthetic placeholder settings are not real provider credentials. Existing Entra/operator identity metadata and CLI authentication are used only for authorized SQL/ARM transport, not seeded as fixture credentials. No production key is used. Runtime SQL permission context uses EXECUTE AS inside the temporary target; actual managed identity authentication is not claimed or included via a hosted process.

After explicit new approval, first refresh exact target absence, source revision/collation and existing runtime SID using SELECT-only metadata; record `live-preflight.json` for this window, recheck pins/cost/restrictions and start the independent watchdog before creating anything. The unchanged execute gate requires the fresh dry-run hashes and price record. No historic runtime mapping will be silently reused as current evidence.

Planned checks: actual frozen migrations through 005 then 006/007; corrected 120-minute session; schema/constraints/indexes/triggers/grants; preserved row hashes and tenant isolation; session/RBAC denials; encrypted capture/reveal/access audit/disposition/expiry/cleanup; retained ciphertext under the same-code fallback; planned 006 preflight rejection and transactional 007 THROW rollback. The identical fallback remains non-independent.

Stop on unexpected behavior or limits. Cleanup is attempted in finally and by the independent three-hour watchdog, reserving one hour for cleanup; independently verify exact ARM GET 404 and inventory absence. An attempt is guaranteed by the procedure, but Azure deletion success cannot be guaranteed; any failure remains an explicit open-resource/cost blocker. No broader deletion, production write, deployment/settings/permission change, customer data, real generation/moderation/ADLS, restore, hosted execution, or Approval B–F is included.

005→006, 006→007, SQL Server security/encryption and migration compatibility remain NOT RUN for this retry. Production blockers remain the original Azure qualification/recovery/PITR, fallback strategy, and separately scoped production approvals. Local SQLite SHA-256 remains `0cad09a35e73ad70bb5ff5e522f783f9b59fdd5b3c31eb5b5dddd4d300795766` (revision 003 per prior immutable inspection).

Evidence: [retry preparation](evidence/phase6b-approval-a-retry1-2026-11-06/). Next required approval: new Approval A retry only, with the exact scope above. No resource creation is authorized by this report.
