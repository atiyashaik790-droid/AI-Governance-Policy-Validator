# Independent executor discovery — read-only

7 November 2026, Asia/Kolkata. No cloud resource, permission, workflow, schedule, production configuration or deployment was changed. No test resource, rehearsal or real provider call was performed. Local report only.

## Coverage and findings

- Local Git config has no remote entries; git remote -v is empty. No remote GitHub repository can be identified from this checkout. GitHub CLI/auth configuration was not found at its standard location. This does not prove the user has no GitHub account or repositories elsewhere.
- .github/workflows/ci.yml defines ubuntu-latest hosted-runner jobs for application tests on push/pull_request. It has contents:read permission, no Azure login, no expiry watchdog, no workflow_dispatch and no schedule. A YAML file alone is not an available runner or proof the workflow has ever run.
- No Azure DevOps pipeline, self-hosted agent, Jenkins config, company server address or remote SSH target was identified in project configuration. Existing deployment tools prepare local ZIPs or invoke local operator processes; startup.sh runs only one uvicorn worker. Retry-9 watchdog is a local detached subprocess.
- Read-only Azure DevOps REST profile lookup succeeded. Accounts API for that profile returned count=0 / organizations=[]. No accessible organization/pipeline/agent pool was discoverable under this login. No organizations were created and no pipeline was invoked.
- az account list exposed one Enabled subscription, 25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6. Read-only resource list contains the existing AI accounts/project, SQL server/master/production database, storage account, App Service plan and Web App. No VM, VM scale set, Automation Account, Function App, Logic App or container runner appears in that visible inventory. Visibility is limited to this login; unrelated company infrastructure cannot be ruled out.
- Existing app app-governance-validator-atiya-1026 is Running/enabled, app,linux, PYTHON|3.13, one worker, Always On=true. Existing plan asp-governance-validator-atiya-1026 is Basic B2, capacity=1. This hosting exists outside the laptop's failure domain.
- Both ARM GET continuouswebjobs and triggeredwebjobs returned Conflict: web app is not configured to run the web job; enable running web jobs before calling the API. Thus the background-job facility is not usable as currently configured; do not interpret the response as proof of an empty job list.
- Deployment-source metadata reports isGitHubAction=false and sourceControlType=null. This provides no linked hosted CI executor to inspect.
- Existing system-assigned app identity 600447fe-5fea-4801-9033-ab4aafc474cc has listed Azure roles only Cognitive Services OpenAI User on the existing model account and Storage Blob Data Contributor on the governance-reports container. No Azure SQL control-plane database deletion grant appeared in the subscription-wide role-assignment query. SQL data-plane grants are different and do not authorize ARM deletion. No role assignment was changed; unlisted group/deny/conditional access behavior is not an effective-permission proof.

## Conclusion

No currently configured, authorized and verified independent executor was found. The existing Web App is a plausible host, not an already working cleanup executor. It is independent of laptop sleep but shares the application's restart/deployment/failure domain.

## Fastest candidate without a new Azure service

Prepare a small review-only WebJob watchdog for the existing App Service. Microsoft supports Python WebJobs on compatible Linux Python App Service, WebJobs use existing hosting, and Always On is recommended for reliability. The existing paid B2 plan and Always On are favorable. It would require enabling the facility, uploading code and arranging reviewed cleanup authorization, all of which remain prohibited in this investigation and require separate explicit approval.

Do not grant SQL Server Contributor, Contributor or broad SQL-delete access to the production app identity by default. An exact disposable-target permission design must be reviewed first, including whether ARM permits the required scope before that target exists. Resource-name checks in Python do not replace permission scoping. If an adequately restricted design cannot be established without a new service or unsafe production access, reject this approach and keep resource creation blocked.

The reviewed implementation must bind exact subscription/server/database, ownership and incarnation/creationDate; poll independently from the harness; start cleanup by creation+3h; stop testing without waiting for a hung parent; retry bounded deletion/verification; confirm ARM404 and inventory absence; retain durable UTC evidence; surface missed heartbeats/breaches; and remain safe across restart/redeployment and target reuse. It must not expose an unauthenticated deletion endpoint or touch production data. Do not use expiresUtc tags as if Azure automatically deletes resources.

A hosted job can address laptop sleep. Neither a single WebJob nor a GitHub schedule proves a hard deletion guarantee during executor/control-plane outages. A strict four-hour guarantee has not been established. Creation stays blocked unless the safeguard meets the authorization; do not silently replace a hard limit with best-effort cleanup.

GitHub Actions would first require an identifiable remote repository, enabled Actions, Azure authentication and permissions. Scheduled Actions may be delayed or dropped, so cron alone is unsuitable as the sole strict expiry mechanism. Azure DevOps would require organization/project/pipeline setup because none was discovered. Cloud Shell/browser sessions and another process on this laptop are not substitutes for a verified persistent executor.

## Minimum next step

No technical information or portal operation is needed from the user now. The next useful task is a local review-only WebJob package plus exact configuration, permission, rollback and verification plan for the existing Web App. It must remain disabled/uninstalled. Only after that concrete plan is reviewed should setup authorization be requested. Setup approval must not authorize a temporary database, rehearsal, production application deployment or later provider calls. Any billable rehearsal still needs its own fresh bounded approval. If no safe permission/execution design is possible, stop and report that instead of creating a service or widening permissions.

References checked: [Microsoft WebJobs documentation](https://learn.microsoft.com/en-us/azure/app-service/webjobs-create?tabs=linuxcode), [GitHub schedule limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
