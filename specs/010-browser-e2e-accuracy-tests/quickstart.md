# Quickstart Guide: End-to-End Browser Automation & System Accuracy Test Suite

**Feature**: `010-browser-e2e-accuracy-tests`  
**Date**: 2026-09-18  

This guide describes how to run and validate the automated browser test suite in both visual (headed) and headless modes.

---

## 1. Prerequisites & Services

Ensure the backend server is running on `http://localhost:8000`:
```bash
# In repo root:
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 2. Running Browser Tests Visually (Watch Execution on Screen)

To watch the browser navigate, click, fill inputs, and verify pages in real time:

```bash
# Option A: Headed Browser Execution
cd web
npm run test:e2e:headed

# Option B: Interactive Playwright UI Mode (with time-travel timeline & inspector)
npm run test:e2e:ui

# Option C: Using root launcher
./scripts/run_e2e_tests.sh --headed
```

**Expected Outcome**:
- A Chromium browser window opens automatically.
- The test logs into the application using the test tenant account.
- You see the test navigate through Recipes, select "Dahl de lentilles corail", add ingredients to the grocery list, open Drive Cart Staging, and verify products.
- Browser test results output green checkmarks in the console.

---

## 3. Running Rapid Smoke Tests (< 2 minutes)

To quickly verify core navigation, authentication, and critical page rendering:

```bash
cd web
npm run test:e2e:smoke
```

**Expected Outcome**:
- All smoke scenarios pass in under 2 minutes.

---

## 4. Running the Complete Accuracy Benchmark Suite

To run the deep culinary matching accuracy test and invariant verification:

```bash
cd web
npm run test:e2e:accuracy
```

**Expected Outcome**:
- Tests execute benchmark recipe scenarios (Dahl de lentilles corail, Pâtes au saumon).
- Asserts that:
  - 0% butter matched for salt.
  - 0% poultry broth matched for garlic.
  - 0% cow milk matched for coconut milk.
  - 0% processed mock meats matched for dry lentils.
  - 0 duplicate broth boxes.
  - Invariant reversibility holds upon cook unconfirmation.
- Generates `docs/audit/e2e-accuracy-report.md`.

---

## 5. Inspecting the Generated Accuracy Report

Open the generated audit report to review accuracy metrics and any recorded anomalies:

```bash
cat docs/audit/e2e-accuracy-report.md
```

Or open the interactive Playwright HTML report:
```bash
cd web
npx playwright show-report
```
