# Feature Specification: End-to-End Browser Automation & System Accuracy Test Suite

**Feature Branch**: `010-browser-e2e-accuracy-tests`

**Created**: 2026-09-18

**Status**: Ready for Planning

**Input**: User description: "Je veux créer une série de tests pour voir l'accuracy et le bon fonctionnement du tout. Ce serait pas mal via browser, et voilà, permettre de voir l'automatisation des tests. Pour le lancement, on va permettre de tester l'application et son fonctionnement pour vérifier que ça ne fait pas n'importe quoi. Si tu repères des choses qui manquent, tu pourras les noter aussi."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visual & Interactive Browser Test Automation (Priority: P1)

As a product owner and developer, I want to trigger an automated test suite that launches a real browser, allowing me to visually observe the automated interactions step-by-step (or run headless in the background) across the web application, so that I can see the system operating smoothly in authentic conditions without manual repetitive clicking.

**Why this priority**: Visual browser automation provides immediate, undeniable proof that the entire application stack (UI, APIs, database, external scrapers) functions cohesively in real user conditions. It allows observing UI responsiveness, dialog flows, and actual user journeys in real-time.

**Independent Test**: Can be tested independently by running the test launcher command with a visible browser flag, observing the automated browser launch, navigate across the application pages (Recipes, Groceries, Pantry, Calendar, Assistant), perform user actions, and generate an execution report with screenshots and video artifacts.

**Acceptance Scenarios**:

1. **Given** the test automation command executed in visual mode, **When** launched, **Then** a visible browser window opens, automatically executes defined user journeys at observable speed, and highlights interacting elements.
2. **Given** the test automation executed in headless mode (e.g. background/CI), **When** completed, **Then** all steps execute without error, capturing final snapshots and performance traces for every executed flow.
3. **Given** any unexpected UI failure or assertion error during execution, **When** the error occurs, **Then** the test suite automatically captures a full-page screenshot, DOM dump, and error details without crashing the test runner.

---

### User Story 2 - Supermarket Matching & Culinary Accuracy Audit (Priority: P1)

As a home cook relying on automated grocery shopping, I want the browser test suite to rigorously audit the accuracy of supermarket product matching (from recipe ingredients to drive cart items), verifying that the system never selects absurd products (e.g. butter for salt, poultry broth for garlic, cow milk for coconut milk, duplicate broth cubes, or processed vegan cold cuts for dry lentils), so that my grocery basket contains strictly accurate, cost-optimized, and genuine ingredients.

**Why this priority**: Inaccurate product matching directly harms user trust, creates monetary waste, and degrades the primary value proposition of the grocery synchronization engine. Automated accuracy verification guarantees culinary fidelity across all supported stores (Carrefour, Intermarché, Leclerc, Auchan).

**Independent Test**: Can be tested independently by navigating to a recipe (e.g. Dahl de lentilles corail), adding all ingredients to the grocery list, generating a draft cart job under Budget, MDD, and Bio strategies, and asserting that 100% of matched items correspond to valid culinary categories with zero duplicates and zero incompatible substitutes.

**Acceptance Scenarios**:

1. **Given** a recipe requiring "Lentilles corail", "Lait de coco", "Ail", "Concentré de tomate", and "Sel", **When** the browser automation generates a drive cart under the Budget strategy, **Then** the cart contains genuine dry coral lentils, genuine coconut milk, fresh garlic, tomato concentrate, and table salt (no butter, no cow milk, no duplicate broth, no veggie slices).
2. **Given** multiple optimization strategies (Budget, MDD, Bio), **When** each strategy is tested against the same recipe ingredients, **Then** the system assigns the appropriate product tiers (lowest price among valid items for Budget, store brand for MDD, certified organic for Bio) while maintaining 100% culinary fidelity.
3. **Given** missing or uncached catalog items, **When** the draft job is created, **Then** the system triggers catalog search enrichment without blocking or timing out, accurately resolving previously unseen products.

---

### User Story 3 - Pantry Inventory Invariants & Cook Deduction End-to-End Verification (Priority: P2)

As a household manager, I want the test suite to verify the complete lifecycle of pantry stock (intake via barcode/Open Food Facts, manual stock adjustments, restock upon grocery item check, and depletion upon recipe cook confirmation), so that the mathematical inventory invariants remain strictly consistent across state transitions.

**Why this priority**: Inventory tracking requires absolute mathematical precision. Silent over-deductions, missing sync links, or failure to reverse deductions upon unchecking shopping items breaks inventory reliability.

**Independent Test**: Can be tested independently by running an automated scenario that adds an item to the pantry (e.g. 500 g lentils), schedules and confirms a recipe consuming 150 g as cooked, verifies stock drops to 350 g, cancels the cook confirmation, and verifies stock returns to 500 g.

**Acceptance Scenarios**:

1. **Given** an empty pantry, **When** an item is scanned or entered with a known barcode via Open Food Facts, **Then** the browser verifies that commercial marketing noise is stripped, culinary variety is preserved, and the item appears in the pantry with the correct metric quantity and unit.
2. **Given** a pantry with 500 g of an ingredient, **When** a recipe consuming 200 g is marked as cooked in the UI, **Then** the pantry item displays exactly 300 g remaining.
3. **Given** a cook confirmation marked in error, **When** the user toggles unconfirm in the UI, **Then** the pantry inventory strictly recovers the deducted 200 g, restoring the original balance.
4. **Given** a shopping list item checked as purchased, **When** toggled, **Then** the pantry stock increases by the purchased quantity, and unchecking immediately reverses that increase.

---

### User Story 4 - Gap Detection, Anomaly Logging & Automated Accuracy Report (Priority: P2)

As a project stakeholder, I want the test execution to produce a structured accuracy report that logs the overall system accuracy score, highlights detected anomalies or product mismatch edge cases, and explicitly flags missing features or usability gaps, so that quality bottlenecks can be reviewed and addressed systematically.

**Why this priority**: Testing should not merely return a binary pass/fail; it must quantify accuracy, track regressions over time, and catalogue product gaps or missing UI affordances discovered during live browser exploration.

**Independent Test**: Can be tested independently by running the test suite and inspecting the generated report artifact (`docs/audit/e2e-accuracy-report.md` / HTML report), verifying that it provides accuracy percentages, breakdown by domain module, and an explicit list of identified gaps.

**Acceptance Scenarios**:

1. **Given** a completed test execution, **When** the suite finishes, **Then** an accuracy score (percentage of valid culinary matches and flawless user journeys) is calculated and saved to a persistent audit report.
2. **Given** an edge case where a product match is suboptimal or a UI element lacks responsive feedback, **When** encountered during automated testing, **Then** the anomaly is recorded in the "Identified Gaps & Recommendations" section of the report.
3. **Given** the generated report, **When** viewed by a user, **Then** it clearly lists executed journeys, pass/fail status, execution duration, and screenshots for any flagged anomalies.

---

### User Story 5 - AI Assistant Conversations & Guardrails Verification (Priority: P3)

As a user interacting with the AI assistant through the web chat interface, I want the automated suite to verify that assistant responses adhere to system constitution guardrails (metric units, disambiguated ingredients, valid tool calls, no arbitrary cut units), so that conversational interactions remain dependable.

**Why this priority**: Conversational AI can hallucinate or drift from system rules. Automated browser verification of chat interactions ensures the assistant remains compliant with metric and culinary standards.

**Independent Test**: Can be tested independently by submitting prompts to the assistant UI (e.g. asking for recipe creation or grocery additions), inspecting the rendered assistant message and tool cards, and asserting adherence to metric and culinary rules.

**Acceptance Scenarios**:

1. **Given** a user chatting with the assistant to plan a meal, **When** the assistant suggests recipes or generates shopping items, **Then** all ingredients use standardized metric units (`g`, `kg`, `ml`, `cl`, `l`, `item`) and cuts remain strictly in notes.
2. **Given** an assistant tool execution, **When** performed through the browser interface, **Then** the corresponding UI state (e.g. new grocery item or recipe card) updates dynamically without requiring a page refresh.

---

### Edge Cases

- What happens if the backend API or an external retailer scraper is unreachable or slow during browser testing? The suite implements configurable timeouts, retry policies, and clear error diagnostics to distinguish between infrastructure outages and functional regressions.
- What happens if the test database is dirty or contains prior state? The test suite provides an isolated test runner environment or seed/cleanup fixture ensuring tests run deterministically without corrupting production or owner data.
- What happens if a supermarket search query returns no results? The suite verifies that the UI displays a clean "unmatched item" state rather than hanging or selecting an arbitrary cheap product.
- What happens if the browser viewport is resized? The test suite verifies responsive behavior across standard desktop (1280x800) and mobile/tablet viewport emulation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an automated End-to-End browser test suite capable of executing across all primary user workflows in the web application.
- **FR-002**: Test suite MUST support both headed mode (visual execution in a real browser window) and headless mode (unattended execution with minimal resource consumption).
- **FR-003**: System MUST provide a unified command line launcher (e.g. `npm run test:e2e` or python/bash runner script) that can launch backend and frontend services or connect to running services.
- **FR-004**: Test suite MUST execute a full Recipe-to-Cart workflow: selecting or creating a recipe, adding items to groceries, generating a supermarket cart job, and verifying the staging output.
- **FR-005**: Test suite MUST compute and enforce a Retail Accuracy Score: 100% of staged cart items for benchmark recipes MUST match compatible culinary categories with zero incompatible product types (e.g. no butter for salt, no poultry broth for garlic, no cow milk for coconut milk).
- **FR-006**: Test suite MUST verify that no duplicate product items are generated in the staged cart for distinct ingredient requests.
- **FR-007**: Test suite MUST audit strategy selection (Budget, MDD, Bio) and verify that items match the chosen optimization criterion within the valid culinary category.
- **FR-008**: Test suite MUST verify the pantry lifecycle: adding items via barcode / Open Food Facts lookup, direct stock quantity adjustments, restock on grocery check, and stock deduction on recipe cook confirmation.
- **FR-009**: Test suite MUST verify mathematical inventory reversibility: unmarking a grocery item or unconfirming a recipe cook action MUST strictly restore prior pantry inventory levels.
- **FR-010**: Test suite MUST verify timeline scheduling: scheduling tasks, meals, and fitness sessions without overlapping time slot collisions.
- **FR-011**: Test suite MUST verify AI assistant interactions: submitting conversational prompts in the chat UI and asserting that generated ingredients and items obey metric unit standards and culinary disambiguation.
- **FR-012**: Test suite MUST generate an automated accuracy and gap report (`docs/audit/e2e-accuracy-report.md` and HTML summary) containing pass/fail metrics, execution timings, accuracy percentages, and recorded anomalies or missing features.
- **FR-013**: Test runner MUST capture full-page screenshots and DOM snapshots upon any test failure or detected gap, linking them directly in the generated audit report.
- **FR-014**: Test suite MUST be idempotent and self-contained, using dedicated test tenant credentials or test database seeding without mutating production data.
- **FR-015**: Test suite MUST include smoke and sanity checks that can complete in under 2 minutes for rapid developer validation before full regression runs.

### Key Entities

- **E2E Test Run**: Represents a single execution of the browser test suite, including timestamp, duration, mode (headed/headless), total scenarios, passed scenarios, failed scenarios, and overall accuracy score.
- **Accuracy Benchmark**: A predefined set of canonical recipes and culinary scenarios (e.g. Dahl de lentilles corail, Pâtes au saumon) with known expected product categories and price thresholds.
- **Audit Anomaly Record**: A structured record of any identified defect, product mismatch, or missing feature discovered during automated exploration, including severity, description, reproduction journey, and screenshot link.
- **E2E Report**: The generated summary artifact synthesizing test run results, accuracy metrics, and prioritized recommendations for application improvements.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers and users can launch the visual browser test suite with a single command and observe automated workflows executing in real time.
- **SC-002**: 100% of benchmark recipe ingredients in the automated cart staging scenario match genuine, compatible retail products (0% false positive category mismatches, 0% duplicate items).
- **SC-003**: 100% of pantry inventory state transitions (restock on check, depletion on cook, reversal on uncheck/unconfirm) maintain exact arithmetic consistency without data drift.
- **SC-004**: Automated smoke test suite completes execution in under 2 minutes, providing rapid feedback on core system health.
- **SC-005**: Every test run produces a complete, readable audit report detailing pass rates, accuracy percentages, and an explicit list of identified gaps or recommended enhancements.
- **SC-006**: Zero regressions across existing backend tests (`uv run --extra dev pytest`) and frontend builds (`npm run build`).

## Assumptions

- Test suite targets the Vite React web application (`web/`) communicating with the local FastAPI backend (`localhost:8000`).
- Playwright is the browser automation engine for executing cross-browser flows (Chromium, WebKit, Firefox) with native support for headless, headed, screenshot capture, and video recording.
- The local backend can run against the development PostgreSQL or SQLite test database with pre-seeded fixtures for reliable, repeatable test assertions.
- External supermarket scrapers utilize cached responses in `SupermarketSearchCache` or proxy-routed requests during test execution to prevent rate limiting or external network flakes.
