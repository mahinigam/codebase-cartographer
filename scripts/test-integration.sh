#!/usr/bin/env bash
set -euo pipefail

project_name="cartographer-it-${RANDOM}-${RANDOM}"
compose=(docker compose --project-name "$project_name" --file docker-compose.integration.yml)

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT

"${compose[@]}" up --build --wait neo4j
"${compose[@]}" run --rm tests "$@"
