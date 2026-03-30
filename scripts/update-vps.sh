#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

git pull --ff-only
docker compose -f docker-compose.vps.yml up -d --build

echo
echo "AdamHUB updated."
docker compose -f docker-compose.vps.yml ps
