# Remaining demo acceptance checks — 2 November 2026

The hosted policy fix is deployed. The two remaining checks are implemented as reproducible commands but remain **BLOCKED**, not passed. No further generation, moderation, export creation, cloud permission mutation or Docker installation was performed.

## Independent export bytes

`scripts/verify_export_storage.py` uses only an explicit Azure CLI reader. It reads one known object with an ETag condition, caps downloaded bytes, hashes the storage bytes, compares the retained expected digest and exits nonzero unless they match. It never lists, uploads, overwrites, deletes, grants permissions or falls back to the application writer identity.

The current reader still receives HTTP 403. An already-authorized reader must run this command after signing in through the organization's approved process. If an owner grants access instead, the required ADLS ACL permissions are read on this exact file and traversal on its ancestor directories; do not broaden the application runtime role solely for independent acceptance.

```bash
.venv/bin/python scripts/verify_export_storage.py \
  --account-url https://stgovvalidatoratiya1026.dfs.core.windows.net \
  --filesystem governance-reports \
  --path governance-reports/2026/11/01/bf230ad9-cef4-4a24-aeea-83ca0c590edd.json \
  --sha256 68b56d5231edf02f1b4a161d4a0cfa7438fc574759079366f5165ed1f2c19b08 \
  --tenant REPLACE_WITH_AZURE_TENANT_ID \
  --output docs/evidence/export-storage-verification.json
```

Current result: [export storage evidence](evidence/export-storage-verification.json). Three deterministic integrity tests pass for matching bytes, corruption and denied access. These tests do not substitute for a real successful read-back.

## Docker build and startup

Run on a machine with Docker Engine and Compose v2:

```bash
python3 scripts/verify_docker_demo.py --output docs/evidence/docker-demo-verification.json
```

This builds both existing production Dockerfiles, starts a uniquely named isolated Compose project with a new SQLite volume and temporary demo credential, waits for readiness, verifies frontend assets/deep links and API proxying, checks login, policy creation/listing/lifecycle, fixture generation/output gates, installed Presidio redaction and session revocation, then removes only this test project's containers/network/volume. It never loads the operator's `.env`, connects to Azure, or uses paid providers. The images remain in the local build cache. Allow up to 30 minutes for builds.

The `docker-demo` CI job runs the same command and uploads its JSON result. The job is present locally; it has not been pushed or executed remotely in this session. The host has no Docker/Podman binary, daemon/socket, passwordless sudo, or rootless UID/GID mapping helpers. Installing only a Docker CLI would not meet the runtime requirements. See [Docker rootless prerequisites](https://docs.docker.com/engine/security/rootless/).

Current result: [Docker evidence](evidence/docker-demo-verification.json). YAML parsing, script compilation and lint/format checks pass. Actual image build/startup remains unverified.

## Completion criteria

Both commands must exit zero and retain `status: PASS`, with Docker cleanup confirmed. Only then can these two acceptance items be closed. Hosted restricted-demo readiness is separate from enterprise production certification.
