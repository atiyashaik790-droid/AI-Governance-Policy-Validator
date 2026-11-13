> **9 November 2026 recovery update:** Actual hosted main-container managed-identity query to new008 passed (revision008, runtime role, eight policies and eight active assignments). See [recovery gate result](FINAL_RECOVERY_GATE_RESULT.md). Actual PITR, off-host key custody and safe settings restoration remain NO GO; earlier MI-pending statements below are historical.

> **9 November 2026 update:** Corrected seeding is PASS: eight committed active/published policies on new008; temporary firewall rule removed and original inventory restored. See [retry result](POLICY_SEED_RETRY_RESULT.md). Hosted managed-identity new008 authentication, recovery proof and safe cutover approval remain pending. Earlier seed-pending statements below are historical.

# Final cutover command review — NOT AUTHORIZED, NO-GO

**Latest update:** The approved eight-policy attempt rolled back before commit because of a local verifier table-name defect; the firewall was removed and production remained healthy. Local correction passed focused checks. See [policy execution result](POLICY_SEED_EXECUTION_RESULT.md). Earlier zero-policy evidence below remains the latest committed baseline; do not treat attempted policy IDs as committed.

9 November 2026. [Generated exact command arrays](evidence/final-cutover-preflight-2026-11-09/command-review.json) and [network-free generator](../scripts/prepare_final_cutover.py). The generator only hashes local artifacts and prints JSON; it has no executor/apply switch. Neither these files nor the master completion prompt authorize any command below.

## Current decision and evidence

Latest actual new-database SQL receipt is the successful runtime/Admin/User bootstrap: **008, two memberships, two provisioning audit rows, zero policies**. No subsequent seed execution receipt was found. This is the latest verified count, not a new query or proof nobody else changed SQL later. The temporary access window is closed. Do not report eight active/published policies or Azure attribution/lifecycle acceptance without the seed/readback receipt. Local eight-policy precedence/reinspection/attribution and tenant tests remain valid; they are not Azure seeding evidence.

Fresh production health/readiness returned200/ok/ready on **1.2-ca5df7c1dc19e525**, revision005, existing Linux Python3.13/AlwaysOn identity. Both candidate and exact old-release rollback ZIP checksums revalidated locally. No migrations, grant/bootstrap writes, firewall changes, deployment, providers or key regeneration occurred in this final preflight task.

## Exact deployment pair

- Existing Web App **app-governance-validator-atiya-1026** in `rg_techdemo_Atiya_Tabsum_Shaik`, subscription **25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6**.
- Candidate **1.2-240cc70e239a595f**: `artifacts/master-repair-2026-11-07/candidate.zip`, SHA256 **274891fe4ce303d9b05751e1b19cd52e5eb535034ccfedb37eae30fb1c228e22**.
- New database **sqldb-gpv-demo-v008-20261108** on `sql-governance-validator-dev-atiya.database.windows.net`, UUID **80dd1ba9-74e5-4d26-8463-081572c9c22e**, verified008 in latest SQL evidence.
- Exact paired rollback **1.2-ca5df7c1dc19e525**: `artifacts/structural-only-candidate-2026-11-05/production/governance-structural-only.zip`, SHA256 **6a6a265bc2d27f9965a1a3abb33eaf61a4bd433a1257b241c183a871c12a57db**, with original database **sqldb-governance-validator-dev**, revision005. Never start that artifact against008.

## Commands prepared, not run

The generated JSON includes exact absolute artifact paths, subscription/RG/app arguments, main-site stop/start, candidate/rollback deployment, target connection, staged cleanup/capture and baseline flag removal. Use the existing authorized Azure CLI profile; revalidate account, identity, source and exact targets before future execution. No account credentials are embedded.

Deployment command form, with exact pins in the generated file:

```bash
az webapp deploy --subscription 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6 --resource-group rg_techdemo_Atiya_Tabsum_Shaik --name app-governance-validator-atiya-1026 --src-path '/home/sigmoid/AI governance policy validator/artifacts/master-repair-2026-11-07/candidate.zip' --type zip --clean true --restart false --async false --track-status false --enable-kudu-warmup false --timeout 600000 --only-show-errors --output none
```

**Do not run it now.** Clean deployment replaces deployed release files: first prove webroot contains no unrelated persistent business files. Installed CLI source was inspected: default Linux warmup has an exception fallback that can replay the deployment POST. `--enable-kudu-warmup false` avoids that branch; ambiguous deployment status must still be reconciled read-only, not retried. CLI timeout is not proof the remote operation stopped.

Future approved sequence: enforce the exclusive writer/maintenance boundary and recoverable encrypted baseline; stop the main site/writers; deploy exact package with restart=false; prove deployment success and main site still stopped; set only new DATABASE_URL, REVIEW_CLEANUP_ENABLED=true and REVIEW_CAPTURE_ENABLED=false; start; confirm actual warmup and three consecutive successful health/ready pairs10seconds apart within five minutes, plus a real successful cleanup-worker pass; then enable capture only if explicitly approved and repeat readiness after recycle. Preserve existing SSO/provider/key settings. No provider verification flag or real provider call is authorized by these commands.

Main site stop normally leaves SCM available according to [Kudu documentation](https://github.com/projectkudu/kudu/wiki/Full-stopping-a-Web-App), and the [App Service deployment API](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip) supports restart control. That is not live proof this exact Linux instance will remain stopped through deployment: verify state before switching connection, and abort/recover if the platform started it. No stop/deploy rehearsal was run.

**Configuration concurrency remains unresolved.** `az webapp config appsettings set` internally merges into a whole-map update without independently verified CAS here. Printed commands are only a review specification, not a safe unattended settings executor. Do not execute until the approved exclusive writer/change-freeze boundary, immediate drift checks, encrypted original-settings snapshot, restoration mechanism and available recovery operator are established. Never dump settings/key values to logs or a plaintext repo file.

Rollback sequence in generated JSON: stop writers/main site; deploy exact old005 ZIP; restore only original005 connection and original states of the two review flags; verify exact pairing before start; start and verify old005 readiness. Removing the flags is valid **only if fresh original-state evidence still confirms both were absent**. Preserve all encryption key bytes and new008 database/records. New008-only writes remain absent from the restored005 site; no merge/delete/downgrade is authorized. If state differs or rollback cannot be verified, report BLOCKED and use the named recovery operator; do not improvise destructive recovery.

## Completion checklist and cutover gates

| Gate | Current evidence / result |
|---|---|
| Candidate backend/frontend/features | PASS locally;68affected backend tests,19User frontend tests, lint/TypeScript/build; full prior evidence retained; source/static files match artifact |
| Exact candidate/rollback pins | PASS; hashes revalidated by local generator |
| Existing production health | PASS freshly observed; old005 preserved |
| New database008 schema | PASS actual Azure SQL evidence reused; no replay |
| Runtime effective SQL permissions | PASS actual SQL impersonation/schema contract; no excessive CONTROL/ALTER/create-user/create-table rights |
| Actual hosted MI token authentication to new DB | **NOT VERIFIED**. Old host connects to old005; SQL impersonation does not prove a new-target token login. No established safe app-context new-target probe was available in this scope; no remote code/configuration change or credential delegation attempted. Obtain this proof via an explicitly authorized read-only app-context mechanism or approved staged acceptance design; do not silently mark it PASS. |
| Admin/User mappings and SSO config | PASS SQL mappings/Graph enabled identities/registered callback; real new-release browser sign-ins pending |
| Eight published/active policies | **BLOCKED**: latest verified count0; no seed approval/receipt |
| Human Review keys/custody | Existing staged key and synthetic roundtripPASS; backup recovery evidence reused; off-host key recovery unproved. New cleanup/capture still disabled; actual worker/readiness requires approved candidate activation |
| Recovery | **BLOCKED**: actual PITR and remaining controlled migration-failure/recovery evidence unproved; metadata/paired artifact availability are not a substitute. No temporary restore/test DB without approved independent expiry. |
| Configuration concurrency/restoration | **BLOCKED**: strong CAS/unattended restoration unverified; exclusive writer/available owner/secure baseline required |
| Final cutover approval | **NOT REQUESTED** because mandatory gates are not all green |
| Real SSO/provider/reveal/export acceptance | **NOT VERIFIED**; separate explicit bounded authorization required |
| Final hosted demo | **NOT COMPLETE** |

## Smallest safe next action

**Approve the existing [eight-policy seed scope](POLICY_SEED_APPROVAL.md)**: exact new008 tenant/database and eight reviewed documents, one fresh rule `gpv-policy-seed-20261109` for45.127.46.209 only, maximum15minutes with verified cleanup; no deployment, identity/grant change, real provider, reveal or ADLS. Expected website downtime0; additional service capacityUSD0 beyond existing persistent database charges. Abort on target/IP mismatch or unexpected policy state; exact matching seeds must not be duplicated. This removes the immediate gate, not the other recovery/MI/configuration gates.

After policy readback and all mandatory preflight gates pass, present one separately bounded cutover approval using the exact command/pair/setting specification and accepted write-loss conditions above. The existing [demo script, samples, architecture and acceptance budgets](FINAL_TECHNICAL_DEMO_SCRIPT.md) remain prepared. No hosted PASS or new-release completion is inferred.
