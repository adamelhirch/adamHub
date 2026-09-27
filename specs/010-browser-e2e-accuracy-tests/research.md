# Research & Technical Decisions: End-to-End Browser Automation & System Accuracy Test Suite

**Feature**: `010-browser-e2e-accuracy-tests`  
**Date**: 2026-09-18  
**Status**: Completed  

---

## 1. Browser Automation Engine & Framework

### Decision
Adopt **Playwright (`@playwright/test`)** in the `web/` package as the primary browser automation framework, configured with both headless execution and interactive visual runners (`--headed` and `--ui`).

### Rationale
- **Visual Observability**: Playwright provides first-class `--headed` mode and Playwright UI Mode (`--ui`), allowing the user to watch browser interactions in real-time on their screen with time-travel inspection.
- **Native Vite Integration**: Playwright's `webServer` configuration natively coordinates starting Vite (`npm run dev`) or re-using the running frontend server (`http://localhost:5173` or `http://localhost:8000`).
- **Resilience**: Playwright features automatic waiting, locator-based resilience (avoiding fragile arbitrary sleep timers), and built-in artifact capture (screenshots, full video recordings, and trace viewer).
- **Multi-Viewport Testing**: Allows running tests in desktop viewports (1280x800) and emulated mobile devices (iPhone/Pixel) to verify responsiveness across the SPA.

### Alternatives Considered
- **Cypress**: Slower execution, heavier memory footprint, and more cumbersome multi-tab / network proxy inspection.
- **Selenium / WebDriver**: Requires separate driver binaries, brittle element locators, lacks native trace viewer and modern video recording.
- **Python `pytest-playwright`**: Viable, but collocating frontend E2E specs in `web/tests/e2e/` allows sharing TypeScript types from `web/src/types/` and integrating directly into standard web npm lifecycle scripts.

---

## 2. Test User Authentication & State Isolation

### Decision
Implement an automated authentication fixture (`web/tests/e2e/fixtures/auth.ts`) that signs in using a designated dedicated test account (`e2e-tester@adamelhirch.com`) or utilizes a pre-authenticated browser context state (`storageState: 'playwright/.auth/user.json'`).

### Rationale
- **Constitution Compliance (Principle I - Tenant Isolation)**: Using a dedicated test user guarantees that test mutations (recipes, shopping items, pantry stocks) are strictly contained within `user_id = test_user_id` and never mutate or pollute the owner's personal operational data.
- **Speed & Idempotency**: Authentic authentication via JWT ensures all backend API calls made by the browser pass through standard `CurrentOrOwnerUser` dependency resolution without mocks.

### Alternatives Considered
- **Testing with the Owner Account**: Rejected because test runs would create and delete real user data, conflicting with active household groceries and pantry stock.
- **Mocking Backend API Responses**: Rejected because the user specifically requested testing real system accuracy ("vérifier que ça ne fait pas n'importe quoi"). Mocking would defeat the entire purpose of detecting real backend matching errors.

---

## 3. Retail Product Matching Accuracy Benchmark Suite

### Decision
Define a canonical set of benchmark recipes and test scenarios in `web/tests/e2e/benchmarks/accuracy-cases.ts`:
1. **Dahl de lentilles corail** (validates dry legumes, coconut milk, garlic, tomato paste, salt; rejects poultry broth for garlic, cow milk for coconut milk, butter for salt, processed slices for lentils).
2. **Pâtes au saumon** (validates fresh salmon fillets in grams, fresh pasta, cream; rejects smoked salmon ambiguity, non-metric cut units).
3. **Poulet curry coco** (validates chicken breasts, spices, coconut milk; verifies zero duplicate spices or broths).

For each benchmark, the test asserts:
- **Zero Category Mismatches**: e.g., head noun compatibility is strictly verified.
- **Zero Unwanted Duplicates**: no product appears multiple times for distinct recipe ingredients.
- **Essential Qualifiers Respected**: e.g., `coco` for coconut milk, `concentré` for tomato paste.
- **Strategy Compliance**: Budget strategy selects the lowest price among valid items; MDD selects store brands.

### Rationale
- Standardizes regression testing against the exact real-world failures encountered previously.
- Provides a quantitative Accuracy Metric:
  $$\text{Accuracy Rate} = \frac{\text{Valid Culinary Matches}}{\text{Total Requested Ingredients}} \times 100\%$$
  The test passes if and only if $\text{Accuracy Rate} = 100\%$.

### Alternatives Considered
- **Only testing happy path UI clicks**: Insufficient because a test could click "Generate Cart" and succeed in UI while adding 5€ of butter for salt. Accuracy requires semantic validation of the cart contents.

---

## 4. Pantry & Invariant Verification Flow

### Decision
Create an end-to-end invariant test suite (`web/tests/e2e/pantry-invariants.spec.ts`) testing the complete cycle:
1. Intake via barcode EAN lookup (Open Food Facts integration).
2. Direct stock quantity edit in UI.
3. Cook confirmation deduction (`recipe.confirm_cooked`) and verification of exact remaining weight.
4. Cook unconfirmation (reversal) and verification of stock recovery.
5. Grocery checklist restock and reversal on uncheck.

### Rationale
- Directly enforces **Constitution Principle III (Invariant-Driven Pantry State Transitions)**.
- Validates that UI state, client store (`zustand`), and backend persistence remain 100% in sync without drift.

---

## 5. Anomaly Logging & Automated Audit Report Generation

### Decision
Implement a custom Playwright reporter / post-test generator (`web/tests/e2e/reporters/accuracy-reporter.ts`) that compiles results into `docs/audit/e2e-accuracy-report.md`:
- Total scenarios run, execution duration, pass/fail status.
- Global Accuracy Score (%).
- Detailed breakdown by domain: Recipes, Groceries, Drive Staging, Pantry, Assistant.
- **Identified Gaps & Anomalies**: Automatically catalogs any assertions that failed, slow responses (>3s), or missing UI affordances.
- Links to failure screenshots and trace recordings in `output/playwright/`.

### Rationale
- Satisfies the user requirement: *"Si tu repères des choses qui manquent, tu pourras les noter aussi"*.
- Creates a permanent, human-readable audit trail that tracks quality across iterations.

---

## 6. Execution Modes & CLI Entrypoints

### Decision
Expose clean scripts in `web/package.json`:
- `npm run test:e2e`: standard headless run.
- `npm run test:e2e:headed`: visible browser execution for visual observation.
- `npm run test:e2e:ui`: interactive Playwright UI mode with live timeline and DOM inspection.
- `npm run test:e2e:smoke`: fast sub-2-minute sanity check of critical paths.
- `npm run test:e2e:accuracy`: full retail matching and invariant benchmark run.

And a root bash launcher: `scripts/run_e2e_tests.sh` that checks backend health, ensures test database readiness, runs the suite, and outputs the report link.
