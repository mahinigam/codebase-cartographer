#!/usr/bin/env bash
set -euo pipefail

server_log="$(mktemp "${TMPDIR:-/tmp}/cartographer-e2e.XXXXXX.log")"
server_pid=""
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  if [[ "$status" -ne 0 && -f "$server_log" ]]; then
    cat "$server_log" >&2
  fi
  rm -f -- "$server_log"
  exit "$status"
}
trap cleanup EXIT

if curl --fail --silent --max-time 2 http://127.0.0.1:5183/ > /dev/null; then
  echo "Port 5183 is already serving a response; stop it before running browser E2E." >&2
  exit 1
fi

export NEXT_TELEMETRY_DISABLED=1
(cd frontend && npm run build)

cd frontend
./node_modules/.bin/next start --hostname 127.0.0.1 --port 5183 >"$server_log" 2>&1 &
server_pid=$!
cd ..

ready=0
for attempt in {1..30}; do
  if curl --fail --silent --max-time 2 http://127.0.0.1:5183/ > /dev/null; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "$ready" -ne 1 ]] || ! curl --fail --silent --max-time 2 http://127.0.0.1:5183/ > /dev/null; then
  echo "Frontend server failed its readiness probe." >&2
  exit 1
fi

cd backend
CARTOGRAPHER_E2E_URL=http://127.0.0.1:5183 uv run python ../frontend/e2e/critical_paths.py
