#!/usr/bin/env bash
# Start the preferred local stack: live-provider backend on 8012 (persistent DB, Microsoft SSO)
# and the HTTPS Vite frontend on https://localhost:5176. Ctrl+C stops both gracefully;
# the persistent database in private/live-local-chat/ is never deleted.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HTTPS_DIR="$ROOT/private/local-https"
LOGS="$ROOT/private/logs"

for port in 8012 5176; do
  if ss -ltn "sport = :$port" | grep -q LISTEN; then
    echo "Port $port is already in use; stop the running server first (nothing was started)." >&2
    exit 1
  fi
done
for file in "$ROOT/private/live-local-chat/offline.db" "$HTTPS_DIR/localhost.pem" "$HTTPS_DIR/localhost-key.pem"; do
  [[ -f "$file" ]] || { echo "Missing $file; see docs/PROGRESS.md (Port 5176 section)." >&2; exit 1; }
done
mkdir -p -m 700 "$LOGS"

"$ROOT/.venv/bin/python" -B "$ROOT/scripts/run_live_local_demo.py" --persistent-local --sso \
  --port 8012 --frontend-origin http://localhost:5176 >> "$LOGS/live-8012-sso.log" 2>&1 &
backend=$!
(
  cd "$ROOT/frontend"
  exec env VITE_LOCAL_DEMO=false VITE_API_URL=https://localhost:5176 \
    GPV_DEV_HTTPS_CERT="$HTTPS_DIR/localhost.pem" GPV_DEV_HTTPS_KEY="$HTTPS_DIR/localhost-key.pem" \
    GPV_DEV_API_TARGET=http://127.0.0.1:8012 node_modules/.bin/vite --host 127.0.0.1 --port 5176
) >> "$LOGS/vite-5176-https.log" 2>&1 &
frontend=$!

stop() {
  trap - INT TERM
  echo "Stopping frontend and backend…"
  kill -TERM "$frontend" "$backend" 2>/dev/null || true
  wait "$frontend" "$backend" 2>/dev/null || true
  echo "Stopped. Data in private/live-local-chat/ is kept."
}
trap stop INT TERM

echo "Backend pid $backend (log private/logs/live-8012-sso.log)"
echo "Frontend pid $frontend (log private/logs/vite-5176-https.log)"
echo "Open https://localhost:5176 — press Ctrl+C here to stop both."
wait -n "$backend" "$frontend" || true
stop
