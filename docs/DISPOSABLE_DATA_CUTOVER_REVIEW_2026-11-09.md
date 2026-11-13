# Disposable-data cutover review — 9 November 2026

## Decision

**NO GO for deployment today.** The operator accepts loss of old005 history and disposable demo-generated rows. This narrows the recovery *data objective*; it does not make new008's eight policies, active assignments, Admin/User memberships, or review-key configuration disposable. No Azure mutation was performed for this review.

## Verified compatibility and limits

- Candidate `1.2-240cc70e239a595f` ZIP SHA256 `274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22` embeds a release manifest supporting migrations 004–008. Its paired old005 rollback ZIP SHA256 is `6a6a265bc2d27f9965a1a3abb33eaf61a4bd433a1257b241c183a871c12a57db`.
- Prior actual hosted-main-container read-only managed-identity probe reached `sqldb-gpv-demo-v008-20261108`, revision008, runtime role, eight policies and eight active assignments. The approved seed readback also verified eight published versions, MULTI mode and tenant binding. Admin/User membership readback passed in the bootstrap evidence. These establish schema/identity/data compatibility, not actual candidate startup or interactive acceptance.
- Fresh public `/health` and `/ready` both returned 200 on old release `1.2-ca5df7c1dc19e525`, revision005. The healthy site was not changed.

## Formal recovery scope

1. **Can simplify:** Do not require restoration or reconciliation of old005 historical rows, disposable Playground executions, reviews, audit/analytics records generated during the demo, or cross-database merging. Rollback may return service to the original old005 database while preserving new008 unchanged; new008-only writes need not appear in old005.
2. **Cannot simplify:** Preserve new008's eight policies, versions, active pins and two memberships, plus the protected-review key bytes and all unrelated App Service settings. A rollback ZIP alone cannot recover a corrupted/deleted new008 database; backup metadata is not a demonstrated restore. Actual new008 recovery proof remains a gate unless a separately reviewed, verified method protects these mandatory records.
3. **Cannot simplify:** Off-host encrypted key and wrapping-secret recovery, a recoverable encrypted settings baseline, a named available restoration operator, and an exclusive or conditional settings-writer boundary. Same-workstation key backup and an unguarded whole-map settings update do not meet these controls. Do not store the key backup in the existing `governance-reports` container accessible to the application identity.
4. **Can narrow qualification:** Any approved restore drill need verify only revision008, required schema/permissions, the eight policy/version/pin relationships, memberships and decryptability of retained encrypted review content (if present). It need not prove restoration of discarded demo data. A billed isolated restore still requires exact target, cost/lifetime cap, independent expiry/cleanup and explicit authorization. Remaining controlled SQL failure checks may be limited to failure modes that threaten the mandatory records and fail-closed security behavior; no blanket waiver is justified by disposable data.

## Minimal cutover after all gates and explicit approval

1. Recheck subscription/app/database identity, candidate and rollback hashes, old-site health, new008 revision/counts/role/memberships, key custody, settings baseline, and writer boundary. Keep the current setting names and all secret values in protected memory only. Designate the sole operator as supervised cutover and rollback owner if available.
2. Freeze other Web App configuration writers and drain/stop the main site. Confirm it remains stopped. Deploy only the pinned candidate ZIP with restart/warmup disabled; reconcile ambiguous deployment status read-only before any retry.
3. Guard the whole settings map against drift, then change only `DATABASE_URL` to new008, set `REVIEW_CLEANUP_ENABLED=true`, and keep `REVIEW_CAPTURE_ENABLED=false`. Preserve SSO, provider, managed identity and both review-key settings byte-for-byte. Start the site and require three health/readiness pairs plus an actual successful cleanup-worker pass. Enable capture only after the separate approved security gate and recheck readiness.
4. Perform bounded hosted Admin/User sign-ins, role separation, eight-policy readback/enforcement, Playground, Human Review, history, analytics, audit and API checks. Live generation, moderation, ADLS export, reveal and hosted data mutation require explicitly bounded authorization and cost/data limits in the final acceptance approval.

## Paired rollback

Stop the main site/writers. Deploy only the pinned old005 ZIP, restore the exact original old005 `DATABASE_URL` and original absence of the two review flags from the guarded encrypted baseline, and preserve both review-key settings and every unrelated setting. Verify old ZIP + old005 revision005 pairing before start, then require health/readiness. Leave new008 and its mandatory records intact. If settings drift, recovery or pairing checks fail, halt and use the designated operator; do not improvise a downgrade, merge, deletion or key regeneration.

## Approval sequence still needed

1. Authorize an exact off-host encrypted key/settings custody destination and recovery test, with the wrapping secret independently recoverable. Establish the exclusive/conditional writer boundary and supervised settings restoration proof.
2. Provide a verified independent exact-target cleanup executor, then separately approve one bounded isolated new008 PITR drill (target, timestamp, tier, cost ceiling and deletion scope). If proposing a different recovery method, review and prove it before cutover.
3. After those gates pass, request final explicit approval for the pinned deployment, the three-field cutover, rollback pairing, limited accepted data loss, and each bounded live acceptance operation. No prior rehearsal or seed approval authorizes these steps.
