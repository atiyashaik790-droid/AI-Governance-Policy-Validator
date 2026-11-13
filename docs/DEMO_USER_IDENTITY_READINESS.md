# Demo User identity discovery — existing candidates found

9 November 2026. Read-only Microsoft Graph discovery in directory **4ac50105-0c66-404e-a107-7cbd8a9a6442** found two enabled Member accounts distinct from the preserved Admin. No account, password, membership, app assignment, directory permission, SQL permission or hosted configuration changed. No sign-in attempted.

| Existing account | Display name | Verified Entra Object ID | State |
|---|---|---|---|
| **demo-user@Sigmoidanalytics.com** | demo-user citizen | **f4799f3f-703a-42b7-acf7-4cbbf55e7320** | Enabled Member; no active directory-role membership returned |
| demo@Sigmoidanalytics.com | Demo | **03773d13-51ea-4231-97de-26c941e71d48** | Enabled Member; no active directory-role membership returned |

Recommend considering the explicitly named `demo-user` account first, **subject to the owner confirming authority to reuse it and ability to sign in**. Read-only directory metadata does not establish credentials, MFA readiness, exclusive ownership or permission to repurpose an account. No password reset is proposed. Absence of returned active directory-role membership is not a complete audit of PIM eligibility, all group entitlements or other Azure roles.

Current Admin stays unchanged: object ID **b5d8bfbe-f03a-4132-a13f-ab49aae834b7**, actor `atiya-tabsum-shaik`, existing Admin role. **Owner has now explicitly selected demo-user@Sigmoidanalytics.com.** Its verified object ID is f4799f3f-703a-42b7-acf7-4cbbf55e7320. Selection authorizes this proposed identity only, not SQL membership creation or a directory change. The alternative account is not selected.

## Ready-to-review application mappings

The selected mapping and preserved alternative proposal use application tenant **demo-appservice-4e2dcce8d618**, role **User**, enabled=true, and verified directory ID above. Stable actor proposed for `demo-user` is **gpv-demo-user**; alternative `demo` actor is **gpv-demo**.

- [demo-user proposed mapping](../deployment/user-demo-user.PROPOSED.json)
- [demo proposed mapping](../deployment/user-demo.PROPOSED.json)

Both passed the existing operator script's **plan-only** validation with `database_accessed=false`; no SQL connection was made. Only the one owner-selected mapping can later enter an approved bootstrap manifest. The current [runtime/membership review proposal](../deployment/fresh-runtime-and-memberships.REVIEW_ONLY.json) records the owner-selected exact mapping and keeps `sql_apply_authorized=false`. Do not apply both or assume a preferred account is approved.

Existing enterprise app **Governance-Studio-SSO**, app ID **a1a7da0b-ad29-49ec-a9ea-c59219e60df5**, service-principal object ID **e9229aa8-0dca-4959-9eac-179637e3b638**, has **appRoleAssignmentRequired=false**. No separate enterprise-app user assignment is required by that setting. Application authorization still requires the approved server-side SQL membership. It does not trust email claims, browser-supplied roles or a generic successful Entra login. No new registration, directory role or Azure service is needed for either existing candidate.

## Authorization and login routing evidence

**Local verification PASS, actual hosted User sign-in NOT VERIFIED.** Reuse the current68affected backend SSO/bootstrap/profile tests and19User Portal frontend tests from `docs/evidence/final-completion-preparation-2026-11-09/`; source/artifact remain unchanged. No unchanged suite was rerun for this identity-only task.

- Server binds verified directory `tid` and user `oid` to enabled membership, stable actor, tenant and role. A missing/disabled mapping is denied; no JIT role assignment.
- `frontend/src/main.tsx` routes role **User** into a separate router whose `/chat` renders UserPortal and whose other routes redirect to `/chat`. Admin uses the existing Admin Studio router.
- `backend/app/user_access.py` permits User only the defined authentication/session/policy-state and governed-request endpoints. Admin-only APIs return403. This API enforcement is separate from hiding navigation.
- Session/CSRF/revocation and cross-tenant authorization are covered by local tests. Real login must later use separate browser profiles/private windows so cached Admin cookies do not masquerade as User evidence.

After approved membership provisioning and cutover, separately authorized interactive acceptance must confirm: real Admin reaches Studio; the selected distinct account reaches `/chat`; User navigating to Admin pages cannot obtain Admin UI/API access; read-only Admin API attempt returns403; tenant mismatches are denied. Do not mark those hosted checks PASS before real authorized sign-ins. Existing production still uses the old005 database; new008 membership alone does not enable the new hosted portal.

## Only if neither existing account is usable

No new identity is necessary if the owner can appropriately use one of the candidates. If neither is acceptable, prepare a separately approved **GPV Demo User** Member account in the same existing tenant, with no administrative directory role, group assignment, Azure RBAC role or automatic paid license.

Verified tenant domains are **Sigmoidanalytics.com** (default) and **streamvector.onmicrosoft.com** (initial), both verified. Proposed UPN, subject to fresh uniqueness/name validation and owner approval: **gpv-demo-user@streamvector.onmicrosoft.com**. Do not create it now or assign a fabricated object ID.

Minimum owner steps after deciding to create it:

1. Open [Microsoft Entra admin center](https://entra.microsoft.com), select the existing directory, then **Identity → Users → All users → New user → Create new user**. An authorized User Administrator or equivalent must perform creation; no permission elevation is included.
2. Set display name **GPV Demo User**, approved UPN, account enabled, User type **Member**. Leave administrative roles, extra groups and licenses unassigned. Use the tenant's normal password/MFA policies; do not disable Conditional Access or security defaults.
3. Complete creation only after explicit approval. Handle any initial password through an approved private channel or the owner's portal session; never paste it into chat, logs, Git or SQL. Complete required first-sign-in password/MFA setup directly with the identity provider. A successful sign-in is still not verified by account creation alone.
4. Let the agent read back the actual new object ID/enabled state and prepare the exact User membership. Obtain explicit approval before that SQL insertion. No enterprise-app assignment is currently required by its setting.

[Microsoft's user creation guidance](https://learn.microsoft.com/en-us/entra/fundamentals/how-to-create-delete-users). No account creation, password change or permission modification is authorized by this document. Basic account creation does not authorize purchase or assignment of paid products; check any tenant-specific license requirements before provisioning.

## Next action

Owner selected **demo-user@Sigmoidanalytics.com**. The exact selected mapping is now included in the prepared **new008 runtime/Admin/User bootstrap approval**, keeping the same target-only least-privilege scope and one newly approved single-IP SQL window. No existing approval authorizes that window or new membership. Until then, all original approval gates remain; safe release, policy, rollback and demo preparation already completed remains valid.

[Discovery evidence](evidence/demo-user-discovery-2026-11-09/result.json) · [Enterprise-app access setting](evidence/demo-user-discovery-2026-11-09/enterprise-app-access.json).
