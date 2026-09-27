# Tasks: Pantry Stock Management, Ingredient Normalization & Open Food Facts Scanner

**Branch**: `009-pantry-stock-openfoodfacts`  
**Input**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [contracts/](contracts/), [research.md](research.md), [quickstart.md](quickstart.md)

---

## Phase 1: Setup & Shared Infrastructure

**Purpose**: Verify dependencies and test harness readiness across backend, mobile, and web.

- [X] T001 Setup test harness and fixtures in `tests/test_pantry_editing.py` and `tests/test_openfoodfacts_pantry.py`
- [X] T002 [P] Install `expo-camera` dependency in `app-saas/package.json` for camera barcode scanning

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schemas, models, services, and backend endpoints required by all user stories.

**⚠️ CRITICAL**: Must be completed before user stories can be implemented and wired up.

- [X] T003 [P] Add `OpenFoodFactsCache` table model to `app/models/entities.py` and `OpenFoodFactsProductDraft` schema to `app/schemas/pantry.py`
- [X] T004 [P] Update `PantryItemUpdate` in `app/schemas/pantry.py` to support all editable fields (`name`, `quantity`, `unit`, `category`, `location`, `expires_at`, `note`, `min_quantity`)
- [X] T005 Implement Open Food Facts HTTP client with custom User-Agent, 30-day cache, and error handling in `app/services/openfoodfacts.py`
- [X] T006 Implement `GET /api/v1/pantry/barcode/{barcode}` endpoint in `app/api/pantry.py`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - User Pantry Stock Modification & Full Editing (Priority: P1) 🎯 MVP

**Goal**: Enable users to view and directly edit all fields of any existing pantry item (especially exact numeric quantity input, unit, category, location, and expiration date) on both mobile and web.

**Independent Test**: Open any pantry item (e.g. "Saumon frais"), type `300` directly with the numeric keypad, change unit, category, and expiration date, tap save, and verify changes persist immediately.

### Tests for User Story 1 ⚠️
- [X] T007 [P] [US1] Add integration tests for `PATCH /api/v1/pantry/items/{id}` testing all fields and non-negative validation in `tests/test_pantry_editing.py`

### Implementation for User Story 1
- [X] T008 [US1] Verify `update_pantry_item` in `app/api/pantry.py` applies all `PantryItemUpdate` fields and enforces `quantity >= 0`
- [X] T009 [P] [US1] Create `PantryEditSheet` modal component with numeric keyboard input, unit picker, and date selector in `app-saas/src/components/pantry-edit-sheet.tsx`
- [X] T010 [US1] Integrate `PantryEditSheet` into `app-saas/src/app/(tabs)/pantry.tsx` to open on tapping any pantry item card or quantity display
- [X] T011 [P] [US1] Implement direct pantry item editing modal and store action in `web/src/pages/GroceriesPage.tsx` and `web/src/store/groceryStore.ts`

**Checkpoint**: User Story 1 is fully functional and delivers a complete MVP for direct pantry stock management.

---

## Phase 4: User Story 2 - Correction and Disambiguation of Existing Recipes & Pantry Items (Priority: P1)

**Goal**: Correct existing user database entries where "Saumon" is ambiguous and units are inconsistent: update "Saumon teriyaki avec riz", "Pâtes crémeuses au saumon", and the pantry item to "Saumon frais" with metric weights (`g`) and piece notes.

**Independent Test**: Execute the fix script, query the database, and verify that both recipes and the pantry item have `name: "Saumon frais"`, units in `g`, and accurate piece notes.

### Tests for User Story 2 ⚠️
- [X] T012 [P] [US2] Add unit test in `tests/test_fix_user_recipes_and_pantry.py` verifying data fix idempotency and record correctness

### Implementation for User Story 2
- [X] T013 [US2] Create and run database fix script `scripts/fix_user_recipes_and_pantry_saumon.py` updating Recipe 1, Recipe 12, and PantryItem 7
- [X] T014 [US2] Verify that recipe cook confirmation (`recipe.confirm_cooked`) against "Saumon teriyaki avec riz" and "Pâtes crémeuses au saumon" decrements "Saumon frais" stock without unit mismatch errors in `tests/test_recipe_app_interactions.py`

**Checkpoint**: Existing user recipes and pantry items are clean, unambiguous, and consistent.

---

## Phase 5: User Story 3 - AI Directives & Guardrails for Physical Measurability and Disambiguation (Priority: P2)

**Goal**: Enforce physical measurability (`g`/`kg`/`ml`/`l` for measurable foods, `item` strictly for natural whole pieces), culinary disambiguation (`Saumon frais` vs `Saumon fumé`), and prohibition of cuts-as-units across AI assistant prompts, skills, and backend normalization.

**Independent Test**: Call `canonical_ingredient()` with cut-units ("pavés") or ambiguous proteins, and assert normalization to metric units with cuts placed in notes.

### Tests for User Story 3 ⚠️
- [X] T015 [P] [US3] Add unit tests for physical measurability rules and cut-unit normalization in `tests/test_ingredient_normalization.py`

### Implementation for User Story 3
- [X] T016 [US3] Update `canonical_ingredient()` in `app/services/units.py` to enforce metric units on measurable proteins and relocate cuts to `note`
- [X] T017 [US3] Update AI assistant system prompt Section 8 in `app/services/assistant/context_builder.py` with physical measurability rules, culinary disambiguation, and prohibited units
- [X] T018 [P] [US3] Update skill documentation in `adamhub-assistant/recipes/SKILL.md` and `adamhub-assistant/pantry/SKILL.md`

**Checkpoint**: AI assistant guardrails and backend normalization strictly prevent future unit or naming regressions.

---

## Phase 6: User Story 4 - Barcode Scanning & Open Food Facts Ingestion with Culinary Specificity (Priority: P2)

**Goal**: Provide barcode scanning (mobile camera + manual entry) with Open Food Facts lookup, cleaning brand noise while preserving culinary varieties (e.g. "Pâtes penne"), and an interactive review/completion sheet before saving to stock.

**Independent Test**: Scan or enter barcode `3560070557451`, verify cleaned proposal "Pâtes penne", 500g, category "Épicerie", fill in expiration date, tap save, and verify item appears in the pantry.

### Tests for User Story 4 ⚠️
- [X] T019 [P] [US4] Add unit tests for Open Food Facts parsing, caching, and cleaning algorithm in `tests/test_openfoodfacts_pantry.py`

### Implementation for User Story 4
- [X] T020 [US4] Implement `clean_openfoodfacts_product()` in `app/services/openfoodfacts.py` stripping brand noise while preserving culinary varieties and extracting metric quantities
- [X] T021 [P] [US4] Register `pantry.lookup_barcode` in `app/skill/actions.py` and implement action handler in `app/skill/handlers/pantry.py`
- [X] T022 [P] [US4] Create camera barcode scanner screen `app-saas/src/app/barcode-scanner.tsx` with camera permissions, viewfinder, and manual EAN fallback
- [X] T023 [US4] Create `OpenFoodFactsReviewSheet` component in `app-saas/src/components/openfoodfacts-review-sheet.tsx` for validating, editing, and completing scanned product attributes
- [X] T024 [US4] Wire scan button in `app-saas/src/app/(tabs)/pantry.tsx` and `app-saas/src/app/new-pantry.tsx` to navigate to barcode scanner and open review sheet
- [X] T025 [P] [US4] Add manual barcode lookup input dialog and review modal in `web/src/pages/GroceriesPage.tsx`

**Checkpoint**: Barcode scanning pipeline with Open Food Facts is fully operational across mobile and web.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, test suite execution, and code quality verification across all surfaces.

- [X] T026 [P] Execute end-to-end quickstart validation scenarios in `specs/009-pantry-stock-openfoodfacts/quickstart.md`
- [X] T027 Run backend test suite via `uv run --extra dev pytest`
- [X] T028 Run mobile app typecheck and lint via `cd app-saas && npm run typecheck && npm run lint`
- [X] T029 Run web app build and lint via `cd web && npm run build && npm run lint`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational - delivers standalone MVP for stock editing.
- **User Story 2 (Phase 4)**: Depends on Foundational - can run in parallel with US1.
- **User Story 3 (Phase 5)**: Depends on Foundational - can run in parallel with US1/US2.
- **User Story 4 (Phase 6)**: Depends on Foundational (T005, T006) and US1 editing components.
- **Polish (Phase 7)**: Depends on all user stories being complete.

### User Story Dependencies
- **US1 (Stock Modification)**: Independent (delivers core UI and API for stock edits).
- **US2 (Data Correction)**: Independent (fixes specific DB rows for the user).
- **US3 (AI Guardrails)**: Independent (enhances prompt and unit normalization).
- **US4 (Open Food Facts Scanner)**: Uses `PantryItem` creation from US1 foundational models.

### Parallel Opportunities
- T001, T002 can run in parallel.
- T003, T004 can run in parallel in Phase 2.
- Once Phase 2 is complete, US1 (T007-T011), US2 (T012-T014), and US3 (T015-T018) can proceed in parallel.
- Frontends: Mobile (`app-saas`) tasks (T009, T022, T023) and Web (`web`) tasks (T011, T025) are completely decoupled and can be implemented in parallel.

---

## Parallel Example: User Story 1
```bash
# Launch backend test and frontend component in parallel:
Task: "T007 [P] [US1] Add integration tests for PATCH /api/v1/pantry/items/{id} in tests/test_pantry_editing.py"
Task: "T009 [P] [US1] Create PantryEditSheet modal component in app-saas/src/components/pantry-edit-sheet.tsx"
Task: "T011 [P] [US1] Implement direct pantry item editing modal in web/src/pages/GroceriesPage.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup (`tests`, `expo-camera`).
2. Complete Phase 2: Foundational (`PantryItemUpdate`, Open Food Facts service).
3. Complete Phase 3: User Story 1 (Pantry stock direct editing on mobile & web).
4. **STOP and VALIDATE**: Verify users can edit stock quantities with numeric keypad.

### Incremental Delivery
1. Add User Story 2: Run data fix script to correct existing recipes and pantry salmon items.
2. Add User Story 3: Upgrade AI assistant guardrails and unit normalization.
3. Add User Story 4: Deploy barcode scanner and Open Food Facts review pipeline.
4. Run Phase 7 validation gates.
