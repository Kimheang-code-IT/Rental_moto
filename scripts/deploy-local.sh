#!/usr/bin/env bash
# Build HollyWing Motor images locally and start the production stack.
# Uses docker-compose.yml + docker-compose.prod.yml. Nothing is pulled from a registry.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [[ ! -f .env ]]; then
  echo "Missing .env in the repository root. Copy .env.production.example to .env and fill every CHANGE_ME value." >&2
  exit 1
fi

export IMAGE_TAG="${IMAGE_TAG:-local}"

compose=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

echo "Building images locally (tag ${IMAGE_TAG})..."
"${compose[@]}" up -d --build --remove-orphans
"${compose[@]}" ps
echo
echo "Done. Frontend is on port \$FRONTEND_PORT (default 80)."
echo "API is only reachable through nginx /api (not published on :8000)."
