#!/usr/bin/env bash
# Preparation controller only; there are deliberately no hosted write handlers.
set -euo pipefail
set +x
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec "$project_root/.venv/bin/python" "$project_root/scripts/prepare_sso_rollout.py" "$@"
