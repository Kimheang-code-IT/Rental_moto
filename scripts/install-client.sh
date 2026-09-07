#!/usr/bin/env bash
# Clone HollyWing Motor from GitHub and build it on this computer (no GHCR image pull).
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Kimheang-code-IT/Rental_moto.git}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "$1 is not installed. Install Git and Docker, then run this script again." >&2
    exit 1
  }
}

need git
need docker

script_dir="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$script_dir/../docker-compose.yml" ]]; then
  root="$(cd "$script_dir/.." && pwd)"
elif [[ -n "${INSTALL_DIR:-}" ]]; then
  root="$INSTALL_DIR"
else
  root="${HOME}/Rental_moto"
fi

if [[ ! -f "$root/docker-compose.yml" ]]; then
  echo "Cloning $REPO_URL -> $root"
  git clone "$REPO_URL" "$root"
elif [[ "$SKIP_GIT_PULL" != "1" ]]; then
  echo "Updating $root"
  git -C "$root" pull --ff-only
fi

cd "$root"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit TELEGRAM_BOT_TOKEN if you need Telegram."
fi

export IMAGE_TAG=local
export PULL_POLICY=build

echo "Building and starting from source (no app image pull)..."
docker compose -f docker-compose.yml up -d --build --pull missing

frontend_port="$(awk -F= '/^FRONTEND_PORT=/{print $2}' .env | tr -d '\r' || true)"
frontend_port="${frontend_port:-80}"

docker compose -f docker-compose.yml ps
echo
echo "HollyWing Motor is starting on this computer."
echo "  App:  http://localhost:${frontend_port}"
echo "  API:  http://localhost:8000/docs"
echo "  Login: admin@gmail.com / 123456  (from .env SEED_ADMIN_*)"
echo
echo "Logs: docker compose logs -f frontend api"
