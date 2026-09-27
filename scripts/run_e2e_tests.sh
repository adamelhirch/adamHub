#!/usr/bin/env bash
set -e

# AdamHUB E2E & Accuracy Test Runner
# Usage: ./scripts/run_e2e_tests.sh [--headed] [--ui] [--smoke] [--accuracy] [--report]

HEADED=""
UI=""
SPEC_FILTER=""
OPEN_REPORT=false

for arg in "$@"; do
  case $arg in
    --headed)
      HEADED="--headed"
      shift
      ;;
    --ui)
      UI="--ui"
      shift
      ;;
    --smoke)
      SPEC_FILTER="tests/e2e/smoke.spec.ts"
      shift
      ;;
    --accuracy)
      SPEC_FILTER="tests/e2e/supermarket-accuracy.spec.ts"
      shift
      ;;
    --report)
      OPEN_REPORT=true
      shift
      ;;
    --help)
      echo "AdamHUB E2E & Accuracy Test Runner"
      echo ""
      echo "Options:"
      echo "  --headed     Launch visible browser window for observation"
      echo "  --ui         Open Playwright interactive UI runner"
      echo "  --smoke      Run only rapid smoke tests (< 2 minutes)"
      echo "  --accuracy   Run deep retail accuracy benchmarks"
      echo "  --report     Open the generated HTML/Markdown accuracy report after completion"
      echo "  --help       Show this help message"
      exit 0
      ;;
    *)
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== [1/3] Checking Backend Health ==="
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "down")
if [ "$HEALTH_STATUS" != "200" ]; then
  echo "Backend is not running on port 8000 (status: $HEALTH_STATUS)."
  echo "Starting backend with 'uv run uvicorn app.main:app --port 8000'..."
  uv run uvicorn app.main:app --port 8000 &
  BACKEND_PID=$!
  sleep 3
  HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "down")
  if [ "$HEALTH_STATUS" != "200" ]; then
    echo "ERROR: Failed to start backend on port 8000."
    exit 2
  fi
fi
echo "Backend is healthy (status 200)."

echo "=== [2/3] Seeding Test Tenant & Canonical Benchmarks ==="
uv run python "$REPO_ROOT/scripts/seed_e2e_tenant.py"

echo "=== [3/3] Executing Playwright Tests ==="
cd "$REPO_ROOT/web"

PLAYWRIGHT_CMD="npx playwright test"
if [ -n "$SPEC_FILTER" ]; then
  PLAYWRIGHT_CMD="$PLAYWRIGHT_CMD $SPEC_FILTER"
fi
if [ -n "$HEADED" ]; then
  PLAYWRIGHT_CMD="$PLAYWRIGHT_CMD $HEADED"
fi
if [ -n "$UI" ]; then
  PLAYWRIGHT_CMD="$PLAYWRIGHT_CMD $UI"
fi

echo "Running: $PLAYWRIGHT_CMD"
eval "$PLAYWRIGHT_CMD" || TEST_EXIT=$?

REPORT_PATH="$REPO_ROOT/docs/audit/e2e-accuracy-report.md"
HTML_REPORT="$REPO_ROOT/web/playwright-report/index.html"

echo ""
echo "=========================================================="
echo "🎯 E2E Automation & Accuracy Test Run Finished"
echo "=========================================================="
if [ -f "$REPORT_PATH" ]; then
  echo "✔ Markdown Audit Report: $REPORT_PATH"
fi
if [ -f "$HTML_REPORT" ]; then
  echo "✔ HTML Test Report:     $HTML_REPORT"
fi
echo "=========================================================="

if [ "$OPEN_REPORT" = true ]; then
  echo "Opening Playwright HTML Report in browser..."
  npx playwright show-report playwright-report || true
fi

exit ${TEST_EXIT:-0}
