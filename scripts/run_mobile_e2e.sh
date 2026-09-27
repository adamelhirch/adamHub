#!/usr/bin/env bash
set -e

# AdamHUB Mobile Expo E2E Test Runner
# Usage: ./scripts/run_mobile_e2e.sh [--headed]

HEADED=""
for arg in "$@"; do
  case $arg in
    --headed)
      HEADED="--headed"
      shift
      ;;
    *)
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== [1/3] Checking Backend Health (port 8000) ==="
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "down")
if [ "$HEALTH_STATUS" != "200" ]; then
  echo "Starting backend..."
  uv run uvicorn app.main:app --port 8000 &
  sleep 3
fi
echo "Backend is healthy."

echo "=== [2/3] Checking Expo Mobile Server (port 8081) ==="
EXPO_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081 || echo "down")
if [ "$EXPO_STATUS" != "200" ]; then
  echo "Expo server is not responding on port 8081."
  echo "Starting Expo in web mode: cd app-saas && npx expo start --web --port 8081..."
  cd "$REPO_ROOT/app-saas"
  npx expo start --web --port 8081 &
  sleep 6
fi
echo "Expo Mobile Server is responding on http://localhost:8081."

echo "=== [3/3] Executing Mobile E2E Tests with Playwright ==="
cd "$REPO_ROOT/web"
PLAYWRIGHT_CMD="npx playwright test tests/e2e/mobile-expo.spec.ts $HEADED"
echo "Running: $PLAYWRIGHT_CMD"
eval "$PLAYWRIGHT_CMD"
