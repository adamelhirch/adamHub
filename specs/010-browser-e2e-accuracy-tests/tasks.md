# Tasks: End-to-End Browser Automation & System Accuracy Test Suite

**Feature**: `010-browser-e2e-accuracy-tests`  
**Date**: 2026-09-18  
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)  

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize Playwright dependencies, configuration, and directory structure in `web/`.

- [X] T001 Install `@playwright/test` in `web/package.json` and configure NPM test scripts (`test:e2e`, `test:e2e:headed`, `test:e2e:ui`, `test:e2e:smoke`, `test:e2e:accuracy`).
- [X] T002 Create Playwright configuration file in `web/playwright.config.ts` configuring webServer, viewports, artifact capture, and reporter.
- [X] T003 [P] Create output directory structure in `output/playwright/` and `docs/audit/` for test artifacts, traces, and reports.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core authentication fixtures, benchmark assertions, and reporting framework required by all user stories.

**⚠️ CRITICAL**: Must be completed before user story execution.

- [X] T004 Implement test tenant authentication fixture in `web/tests/e2e/fixtures/auth.ts` providing authenticated sessions for `e2e-tester@adamelhirch.com`.
- [X] T005 [P] Create base Playwright test environment fixture in `web/tests/e2e/fixtures/test-env.ts` providing authenticated page, test user context, and database state reset helpers.
- [X] T006 [P] Implement benchmark definition models and assertions in `web/tests/e2e/benchmarks/accuracy-cases.ts` (Dahl de lentilles corail, Pâtes au saumon, with required qualifiers and prohibited terms).
- [X] T007 Implement custom accuracy reporter in `web/tests/e2e/reporters/accuracy-reporter.ts` conforming to `specs/010-browser-e2e-accuracy-tests/contracts/accuracy-report-schema.json`.

**Checkpoint**: Foundational test infrastructure ready - user stories can proceed.

---

## Phase 3: User Story 1 - Visual & Interactive Browser Test Automation (Priority: P1) 🎯 MVP

**Goal**: Enable launching visual (headed), interactive (UI mode), and headless browser automation to observe real user journeys across the web application.

**Independent Test**: Run `npm run test:e2e:smoke` with visible browser flag, observing automated login and navigation through main pages with green checkmarks.

- [X] T008 [P] [US1] Create rapid smoke test spec in `web/tests/e2e/smoke.spec.ts` verifying primary navigation (Dashboard, Recipes, Groceries, Pantry, Calendar, Assistant) in < 2 minutes.
- [X] T009 [US1] Implement root launcher shell script `scripts/run_e2e_tests.sh` with `--headed`, `--ui`, `--smoke`, `--accuracy`, and `--report` flags, checking backend health before running.
- [X] T010 [US1] Configure visual slow-motion and action highlights for headed mode in `web/playwright.config.ts` so the user can easily observe browser actions on screen.
- [X] T011 [US1] Validate User Story 1 by running `npm run test:e2e:smoke` in headed mode and verifying the browser window opens and navigates cleanly.

**Checkpoint**: Visual browser runner operational and validated.

---

## Phase 4: User Story 2 - Supermarket Matching & Culinary Accuracy Audit (Priority: P1)

**Goal**: Audit supermarket product matching from recipe ingredients to drive cart staging, enforcing 100% culinary fidelity and zero duplicates or absurd items.

**Independent Test**: Run `npm run test:e2e:accuracy`, selecting "Dahl de lentilles corail", adding ingredients to cart, and asserting that all matched items are authentic (no butter for salt, no poultry broth for garlic, no cow milk for coconut milk).

- [X] T012 [P] [US2] Create supermarket accuracy E2E spec in `web/tests/e2e/supermarket-accuracy.spec.ts` testing the complete flow: selecting recipe (Dahl de lentilles corail), adding to groceries, and staging drive cart.
- [X] T013 [US2] Implement negative assertion checks in `web/tests/e2e/supermarket-accuracy.spec.ts` verifying: 0% butter for salt, 0% poultry broth for garlic, 0% cow milk for coconut milk, 0% veggie slices for lentils, and zero duplicate broth cubes.
- [X] T014 [US2] Implement strategy switching tests in `web/tests/e2e/supermarket-accuracy.spec.ts` asserting that Budget, MDD, and Bio strategies select valid products matching the strategy criteria while preserving 100% culinary fidelity.
- [X] T015 [US2] Validate User Story 2 by executing `npm run test:e2e:accuracy` and verifying 100% retail accuracy score.

**Checkpoint**: Retail accuracy benchmark passing with 100% valid product categories.

---

## Phase 5: User Story 3 - Pantry Inventory Invariants & Cook Deduction End-to-End Verification (Priority: P2)

**Goal**: Verify pantry inventory lifecycle, barcode intake, cook confirmation deductions, and mathematical recovery on unconfirm.

**Independent Test**: Add 500 g lentils, confirm a recipe consuming 150 g as cooked, verify stock drops to 350 g, toggle unconfirm, and verify stock strictly recovers to 500 g.

- [X] T016 [P] [US3] Create pantry invariant E2E spec in `web/tests/e2e/pantry-invariants.spec.ts` testing OpenFoodFacts barcode intake, direct quantity edit, and grocery restock.
- [X] T017 [US3] Implement cook confirmation and unconfirmation invariant checks in `web/tests/e2e/pantry-invariants.spec.ts` asserting exact stock decrement and exact mathematical recovery on unconfirm.
- [X] T018 [US3] Implement grocery check/uncheck invariant checks in `web/tests/e2e/pantry-invariants.spec.ts` asserting stock increases on check and strictly reverts on uncheck.

**Checkpoint**: Inventory invariants verified and reversible without data drift.

---

## Phase 6: User Story 4 - Gap Detection, Anomaly Logging & Automated Accuracy Report (Priority: P2)

**Goal**: Automatically catalogue detected UI gaps, anomalies, and accuracy metrics into a structured markdown and HTML audit report.

**Independent Test**: Execute test suite and inspect `docs/audit/e2e-accuracy-report.md`, verifying presence of global accuracy %, domain breakdown, and recorded gap recommendations.

- [X] T019 [P] [US4] Implement markdown audit report generator in `web/tests/e2e/reporters/accuracy-reporter.ts` formatting execution metrics, accuracy percentages, and anomaly logs into `docs/audit/e2e-accuracy-report.md`.
- [X] T020 [US4] Implement anomaly detection listener in `web/tests/e2e/fixtures/test-env.ts` capturing console errors, slow network requests (>3s), and UI element missing states as structured `AuditAnomalyRecord`.
- [X] T021 [US4] Add HTML report link and summary printout in `scripts/run_e2e_tests.sh` after test completion.

**Checkpoint**: Audit report automatically generated after each test run.

---

## Phase 7: User Story 5 - AI Assistant Conversations & Guardrails Verification (Priority: P3)

**Goal**: Verify that AI assistant chat interactions in the browser adhere to metric units and culinary disambiguation standards.

**Independent Test**: Prompt assistant for a salmon pasta recipe, assert rendered message uses `g` for salmon and puts cut in notes, and verify grocery item creation.

- [X] T022 [P] [US5] Create assistant guardrail E2E spec in `web/tests/e2e/assistant-guardrails.spec.ts` sending recipe and grocery prompts through the chat interface.
- [X] T023 [US5] Implement assertion helpers in `web/tests/e2e/assistant-guardrails.spec.ts` verifying that generated assistant responses use standard metric units (`g`, `kg`, `ml`, `l`, `item`), contain no prohibited units (`pavés`, `tranches`), and disambiguate culinary states.

**Checkpoint**: AI assistant guardrails verified end-to-end in the browser UI.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, full test validation, and final integration.

- [X] T024 [P] Update `README.md` and `docs/agents/plan.md` with instructions on running E2E tests and viewing reports.
- [X] T025 Verify that full backend test suite (`uv run --extra dev pytest`) and web build (`npm run build`) pass with zero errors.
- [X] T026 Execute full end-to-end audit run via `./scripts/run_e2e_tests.sh --accuracy` and verify the generated `docs/audit/e2e-accuracy-report.md`.

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion; blocks User Stories.
- **User Story 1 (Phase 3 - MVP)**: Depends on Foundational completion.
- **User Story 2 (Phase 4)**: Depends on Foundational & US1 runner.
- **User Story 3 (Phase 5)**: Depends on Foundational & US1 runner.
- **User Story 4 (Phase 6)**: Integrates with reporter across US1-US3.
- **User Story 5 (Phase 7)**: Depends on Foundational & Assistant UI.
- **Polish (Phase 8)**: Depends on completed user stories.

### Parallel Execution Opportunities
- T003 (directories) in parallel with T001/T002.
- T005, T006, T007 in parallel within Phase 2.
- T008 (smoke spec) in parallel with T009/T010.
- T012, T016, T019, T022 can be drafted in parallel across story modules.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (US1 - Visual Browser Runner & Smoke Test).
3. Validate: launch `npm run test:e2e:smoke` in headed mode.
4. User can immediately see the browser navigating the app on screen.

### Incremental Delivery
1. Add Phase 4 (US2 - Supermarket Accuracy Audit) -> Guarantees 0% absurd matches.
2. Add Phase 5 (US3 - Pantry Invariants) -> Guarantees inventory mathematical integrity.
3. Add Phase 6 (US4 - Anomaly & Gap Report) -> Generates structured audit markdown.
4. Add Phase 7 (US5 - Assistant Chat Guardrails) -> Guarantees conversational compliance.
5. Final Polish & full audit run.
