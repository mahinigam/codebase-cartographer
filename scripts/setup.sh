#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_example="$repo_root/.env.example"
env_file="$repo_root/.env"

if [[ ! -f "$env_file" ]]; then
  cp "$env_example" "$env_file"
  echo "Created $env_file from .env.example."
fi

if grep -qE '^NEO4J_PASSWORD=[^[:space:]]+' "$env_file"; then
  echo "NEO4J_PASSWORD is already configured in $env_file; leaving untouched."
  exit 0
fi

if command -v openssl >/dev/null 2>&1; then
  neo4j_password="$(openssl rand -hex 24)"
else
  neo4j_password="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
fi

if grep -qE '^NEO4J_PASSWORD=' "$env_file"; then
  tmp_file="$(mktemp)"
  trap 'rm -f "$tmp_file"' EXIT
  awk -v pw="$neo4j_password" '
    /^NEO4J_PASSWORD=/ { print "NEO4J_PASSWORD=" pw; next }
    { print }
  ' "$env_file" > "$tmp_file"
  mv "$tmp_file" "$env_file"
  trap - EXIT
else
  printf '\nNEO4J_PASSWORD=%s\n' "$neo4j_password" >> "$env_file"
fi

echo "Generated NEO4J_PASSWORD in $env_file."
