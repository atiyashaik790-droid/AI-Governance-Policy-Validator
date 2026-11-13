#!/usr/bin/env bash
set -euo pipefail
set +x
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export AZURE_CONFIG_DIR="$project_root/.azure-sql-cli"
export PYTHONDONTWRITEBYTECODE=1
exec "$project_root/.venv/bin/python" "$project_root/scripts/verify_hosted_runtime.py" "$@"
