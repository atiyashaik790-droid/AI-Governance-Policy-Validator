#!/usr/bin/env bash
# Read-only: never login, select an account, fetch secrets, or mutate hosted state.
set -euo pipefail
set +x
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$project_root/.venv/bin/python" ]]; then
  printf '%s\n' '{"status":"UNKNOWN","category":"PROJECT_VENV_UNAVAILABLE"}'
  exit 2
fi
export AZURE_CONFIG_DIR="$project_root/.azure-sql-cli"
export PYTHONDONTWRITEBYTECODE=1
exec "$project_root/.venv/bin/python" "$project_root/scripts/sso_deployment_readiness.py" "$@"
