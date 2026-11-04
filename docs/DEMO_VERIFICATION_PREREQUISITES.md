# Remaining verification prerequisites — 2 November 2026

No storage access, packages, services or Linux privileges were changed.

## ADLS diagnosis

The exact target is storage account `REPLACE_WITH_ADLS_STORAGE_ACCOUNT`, filesystem `governance-reports`, and object `governance-reports/2026/11/01/REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_05.json` within that filesystem. The repeated `governance-reports` component is the actual recorded object prefix, not a typo. Expected SHA-256 is `68b56d5231edf02f1b4a161d4a0cfa7438fc574759079366f5165ed1f2c19b08`.

Confirmed: account provisioning succeeded, hierarchical namespace is enabled, filesystem exists with anonymous public access disabled, network default action is Allow, and the reader's token has the correct tenant and storage audience. Azure returns HTTP 403 `AuthorizationPermissionMismatch` for the exact object. The reader's effective inherited assignments are Contributor, User Access Administrator and Foundry User, with no storage data-reader role. Management-plane access does not itself authorize reading file contents.

Reader object ID: `REPLACE_WITH_ADLS_READER_OBJECT_ID`; tenant: `REPLACE_WITH_AZURE_TENANT_ID`. Its ACL lookup is also denied, so the exact deficient ACL entry or ancestor mask cannot be inspected with this reader. The confirmed cause is lack of effective data-plane authorization; it is not evidence that the file is missing or that the digest mismatches.

The existing app managed identity `REPLACE_WITH_WEB_APP_PRINCIPAL_ID` has Storage Blob Data Contributor on this filesystem. A read-only attempt to reuse that identity in the existing SCM diagnostic environment found no managed-identity endpoint/header. No token or file bytes were obtained. That identity is already authorized, but is not currently usable from this diagnostic environment and would not be a separate reader identity. Only one operator account was found in the selected Azure CLI cache; no identity switch was performed.

### Exact minimum read-only access request (not applied)

Identity: reader object ID above, or an existing approved reader group containing it.

Resource scope:

```text
/subscriptions/REPLACE_WITH_AZURE_SUBSCRIPTION_ID/resourceGroups/REPLACE_WITH_AZURE_RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/REPLACE_WITH_ADLS_STORAGE_ACCOUNT/blobServices/default/containers/governance-reports
```

Use access ACLs scoped to this exact export, rather than a container/account-wide role:

| Object within filesystem | Named reader access needed |
| --- | --- |
| `/` | `--x` traversal |
| `governance-reports` | `--x` traversal |
| `governance-reports/2026` | `--x` traversal |
| `governance-reports/2026/11` | `--x` traversal |
| `governance-reports/2026/11/01` | `--x` traversal |
| `governance-reports/2026/11/01/REPLACE_WITH_RECORDED_CLOUD_OBJECT_ID_05.json` | `r--` file read |

An authorized ACL owner must first inspect existing access ACLs, group membership and masks, preserve unrelated entries, and ensure the reader's required bits are effective through the mask. Do not set default ACLs, recurse over the filesystem, or change masks blindly. No directory list, write, delete or permission-administration access is required. Microsoft documents [file read and ancestor traversal](https://learn.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-access-control). This is a proposed access request requiring explicit approval before any change.

After authorized access is available, run the exact read-only command in [final verification](DEMO_FINAL_VERIFICATION.md). No need to regenerate the export.

Evidence: [authorization](evidence/final-storage-authorization.json), [existing identity attempt](evidence/final-existing-identity-readback.json), [operator read result](evidence/export-storage-verification.json).

## Docker on this Ubuntu machine

Verified Ubuntu 25.10 (Questing), x86_64, user `sigmoid`. Docker/Podman binaries, Docker packages, daemon socket and rootless UID/GID mapping helpers are absent; Docker service/socket are inactive. `sudo -n true` requires interactive authentication. No installation attempted.

The local Ubuntu package index offers `docker.io`, `docker-compose-v2` and `docker-buildx`. An administrator can run the following commands **after approval**. These use the configured Ubuntu repositories, rather than adding an upstream repository for another Ubuntu release.

```bash
sudo apt-get update
sudo apt-get install docker.io docker-compose-v2 docker-buildx
sudo systemctl start docker
sudo docker version
sudo docker compose version
sudo docker run --rm hello-world
```

Run the verifier with per-command sudo, without adding the user to any privileged group:

```bash
cd '/home/sigmoid/AI governance policy validator'
sudo /usr/bin/python3 scripts/verify_docker_demo.py --output /tmp/governance-docker-verification.json
cat /tmp/governance-docker-verification.json
```

These commands require administrator authorization/password to install packages, start the daemon and use its root-owned socket. The script builds images and manages only its uniquely named fixture project. Do not change socket permissions to world-writable. Permanent `docker` group membership is unnecessary for this path; [Docker documents that the group grants root-level privileges](https://docs.docker.com/engine/install/linux-postinstall/). The daemon may create Docker networking/firewall rules as part of normal startup. No persistent boot-time service enablement is requested.

## Completed checks without Docker

- Full backend: **439 passed**.
- Frontend including actual disposable-backend integration: **16 passed**, zero skipped on the final run.
- Frontend ESLint, TypeScript compilation and production build passed.
- Backend/scripts Ruff lint, formatting (58 files) and Python compilation passed.
- Integrity verifier coverage includes matching bytes, corrupt bytes and denied reads.

These results do not substitute for a successful ADLS byte read-back or actual container build/startup. Both remain open; full acceptance is not passed.
