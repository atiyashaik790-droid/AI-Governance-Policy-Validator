> Historical release report. For the current implementation and deployment boundary, see [CURRENT_STATUS.md](CURRENT_STATUS.md).

# Azure deployment verification / approval gate — 31 October 2026

## NOT DEPLOYED — explicit approval required

Target is the **existing** App Service:

- Name: `app-governance-validator-atiya-1026`
- Resource group: `REPLACE_WITH_AZURE_RESOURCE_GROUP`
- Subscription: `REPLACE_WITH_AZURE_SUBSCRIPTION_ID`
- URL: <https://app-governance-validator-atiya-1026.azurewebsites.net>

No new resource, setting, identity grant, firewall change or migration is proposed.

## Exact candidate package

Location:

`/home/sigmoid/AI governance policy validator/artifacts/live-stabilization-20261031/governance-live-stabilized.zip`

SHA-256:

```text
5f22b7d829e79251f58f4b216bcc18d92f500220e28381eee18ad6f251e1d697
```

Size: 223,735 bytes. Entries: 17. The adjacent `package-manifest.json` records the
allowlist and rollback fingerprint. The ZIP was byte-compared to current source/build;
no configured credentials, environment files, databases, migrations, tests or CLI caches
are included. JavaScript contains no localhost/127.0.0.1 API target. Frontend uses
`VITE_API_URL=/`. ZIP integrity and eight extracted-package hosted route/auth checks passed.

Changed members relative to the accepted rollback ZIP:

- `app/engine.py`: previously authorized contextual secret/keyword whitespace fix.
- `app/main.py`: explicit generation state, immutable policy name, safe failure diagnostics.
- `app/providers.py`: safe error categories, incomplete-response withholding, minimal GPT-5 reasoning.
- `app/schemas.py`: additive API response fields; no DB schema changes.
- `static/index.html` and new `static/assets/index-6kIrc9QN.js`.
- Previous `static/assets/index-Dt2dI4nI.js` is replaced; CSS is unchanged.

The source includes existing accepted Azure SQL/ADLS/hosting work. Unrelated uncommitted
files, docs and private artifacts are not packaged. All changed application members
were included in the tested source and inspected package.

## Validation before requesting approval

- 345 backend tests; 10 frontend tests; 57 real-Chrome fixture checks: PASS.
- Eight exact-package smoke checks with network prohibited: PASS.
- Ruff lint/format, compile checks, ESLint, TypeScript, same-origin Vite build: PASS.
- Existing local-live backend restarted and SQL/readiness/auth/read-only routes checked.
- No fresh generation/moderation/export calls made.
- Existing hosted configuration is live/Presidio/managed SQL identity, Python 3.13,
  startup `sh startup.sh`, HTTPS only, same-origin CORS, expected GPT-5-mini deployment.
- Required hosted settings are present. Values of credentials were not printed.

## Current hosted version (before deployment)

Read-only server-side deployment listing reports:

`eec1e450-11c4-4c0e-939f-f9df9e68999b`, active true, complete true, status 4,
finished 30 October 2026 at 14:14:14 UTC.

Public health, readiness and OpenAPI return 200. Hosted index/JavaScript exactly match
the accepted package. The new generation-status OpenAPI property is absent on hosted
and present locally. There is **no new deployment ID** for this candidate.

## Expected effects / interruption

Use the existing ZIP deployment mechanism and existing Oryx build setting. Dependencies
and resource SKU remain unchanged. Build and worker restart can cause several minutes
of degraded/unavailable service; zero downtime is not promised on this single-worker
setup. Existing deployment artifacts/logs will be created by App Service. No service
provisioning, SQL schema/data command, firewall change, provider call or export is part
of deployment. Existing users' in-flight requests may be interrupted; do not redeploy
while a live inference/export is in progress.

Approval must cover this exact checksum/target and the rollback below if startup fails.
The agent must verify the checksum again immediately before upload and use a single
submission ledger; do not blindly retry an uncertain deployment result.

Reviewed command, **not executed**:

```bash
cd "/home/sigmoid/AI governance policy validator"
AZURE_CONFIG_DIR="$PWD/.azure-sql-cli" az webapp deploy \
  --subscription REPLACE_WITH_AZURE_SUBSCRIPTION_ID \
  --resource-group REPLACE_WITH_AZURE_RESOURCE_GROUP \
  --name app-governance-validator-atiya-1026 \
  --type zip \
  --src-path artifacts/live-stabilization-20261031/governance-live-stabilized.zip \
  --async true --track-status false
```

## Preserved rollback

Location:

`/home/sigmoid/AI governance policy validator/artifacts/live-stabilization-20261031/rollback-known-good-b1a3dc0f.zip`

SHA-256:

```text
b1a3dc0f3d53e98c4ce8c133cbd81d29146299530c42622a11cd384b492d46e1
```

This is an exact copy of the ZIP associated with accepted deployment eec1e450, verified
against the historical checksum. If deployment/startup fails after approval, deploy
this rollback ZIP to the same target using the reviewed command with only `--src-path`
changed. Then verify server-side completion, health/readiness, exact old assets, auth,
policy/history/export read-only metadata. Rollback does not reset or delete SQL data.

## Postdeployment read-only acceptance plan

1. Poll the actual server-side deployment to complete/active success; inspect worker errors.
2. Verify the intended package with hosted index/asset byte equality and new API schema.
3. Check health/readiness, SPA deep links, protected API authentication, RBAC and CORS.
4. Use approved existing hosted credentials privately to inspect settings, policies,
   review/history/audit and export metadata without mutations.
5. Confirm no historical export/audit records changed; preserve predeployment snapshots.
6. Stop before generation/moderation/export and request a separate bounded allowance.

Proposed later AI allowance: at most two generation calls and eight moderation calls for
one safe and one synthetic PII workflow, no retries and **zero ADLS exports**. Policy/tenant
selection and exact retained SQL write scope must also be agreed before those tests.
Existing deterministic output-sensitive-data tests need no live model injection endpoint.
Do not exceed the approved count or describe mocked responses as real Azure output.

## Remaining risks and acceptance limits

The historical 9–10 second failures discarded upstream details. The new diagnostic
categories and GPT-5 reasoning mitigation are deterministic-tested, not proof of a
live upstream fix. The separately approved live result must establish that. Token cap
and timeouts are unchanged. Existing SDK/model/permission/network problems can still
cause fail-closed results, now with useful safe classification. Managed identity is
mock-tested in this package but must be confirmed by an actual approved hosted request.
The known bundle-size and TestClient warnings remain. Human review still requires
resubmission; authentication remains opaque demo bearer tokens, not enterprise JWT/SSO.

**Required next action: user approval of this exact package, target and rollback.**
