#!/usr/bin/env bash
set -euo pipefail

project_name="cartographer-it-${RANDOM}-${RANDOM}"
project_root="$(pwd)"
compose=(docker compose --project-name "$project_name" --file "$project_root/docker-compose.integration.yml")
export COMPOSE_PROGRESS=quiet

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT

"${compose[@]}" up --wait neo4j
cd backend
env \
  CARTOGRAPHER_RUN_INTEGRATION=1 \
  NEO4J_URI=bolt://127.0.0.1:7689 \
  NEO4J_USERNAME=neo4j \
  NEO4J_PASSWORD=neo4j-test-password \
  uv run pytest -m integration "$@"
