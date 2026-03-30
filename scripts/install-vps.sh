#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.vps.example .env
  echo ".env created from .env.vps.example"
  echo "Edit .env before re-running this script."
  exit 1
fi

docker compose -f docker-compose.vps.yml up -d --build

echo
echo "AdamHUB is starting."
echo "Health: ${ADAMHUB_PUBLIC_BASE_URL:-http://localhost:${ADAMHUB_PORT:-8000}}/health"
echo "Frontend: ${ADAMHUB_PUBLIC_BASE_URL:-http://localhost:${ADAMHUB_PORT:-8000}}/"
echo "Skill manifest: ${ADAMHUB_PUBLIC_BASE_URL:-http://localhost:${ADAMHUB_PORT:-8000}}/api/v1/skill/manifest"
