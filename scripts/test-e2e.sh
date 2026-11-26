#!/usr/bin/env bash
set -euo pipefail

server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

(
  cd frontend
  npm run build
  npm run start -- --hostname 127.0.0.1 --port 5183 > /tmp/cartographer-e2e-server.log 2>&1 &
  echo $! > /tmp/cartographer-e2e-server.pid
)
server_pid="$(cat /tmp/cartographer-e2e-server.pid)"

for attempt in {1..30}; do
  if curl --fail --silent http://127.0.0.1:5183/ > /dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:5183/ > /dev/null

cd backend
CARTOGRAPHER_E2E_URL=http://127.0.0.1:5183 uv run python ../frontend/e2e/critical_paths.py
