#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
docker compose up -d --build
FRONTEND_PORT="${FRONTEND_PORT:-80}"
printf '\nHollyWing Motor is starting.\n'
printf '  Frontend (nginx): http://localhost:%s\n' "$FRONTEND_PORT"
printf '  API:              http://localhost:8000/docs\n\n'
printf 'Check status: docker compose ps\n'
printf 'View logs:    docker compose logs -f frontend api\n'
