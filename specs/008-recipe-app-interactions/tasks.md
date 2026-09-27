# Tasks: Recipe App Interactions (Cooking Confirmation, Groceries Restock, and Smart Calendar Scheduling)

**Branch**: `008-recipe-app-interactions`  
**Input**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [contracts/](contracts/)

---

## Phase 1: Setup & Shared Infrastructure

**Purpose**: Verify dependencies and test harness readiness.

- [x] T001 Verify backend test harness and SQLite isolation in `tests/test_recipe_app_interactions.py`
- [x] T002 [P] Verify `react-native-gesture-handler` and `react-native-reanimated` setup in `app-saas/package.json` and `app-saas/src/app/_layout.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core backend DTOs, batch grocery endpoint, and client API bindings required by all user stories.

**⚠️ CRITICAL**: Must be completed before mobile UI gestures and interactive sheets can be wired up.

- [x] T003 [P] Implement DTOs in `app/schemas/meal_planning.py` (`RecipeAddToGroceriesRequest`, `RecipeAddToGroceriesResult`, `MealPlanConflictResponse`)
- [x] T004 Implement `POST /api/v1/recipes/{recipe_id}/add-to-groceries` in `app/api/recipes.py` supporting ingredient filtering and servings scaling
- [x] T005 [P] Update `app-saas/src/lib/recipes.ts` and `app-saas/src/lib/api.ts` with typed client methods (`confirmRecipeCooked`, `unconfirmRecipeCooked`, `addRecipeToGroceries`, `scheduleMealPlan`)

**Checkpoint**: Backend endpoints and frontend API bindings ready.

---

## Phase 3: User Story 1 - Confirmation de cuisine & décrémentation du garde-manger (Priority: P1) 🎯 MVP

**Goal**: Enable users to confirm cooking a recipe, deducting available ingredients from the pantry down to 0, with tactile shake feedback when ingredients are missing and an immediate 1-tap restock prompt.

**Independent Test**: Perform a short swipe left on a recipe card; verify available pantry stock decrements down to 0; verify shake animation and restock toast appear when ingredients are missing.

### Tests for User Story 1
- [x] T006 [P] [US1] Add unit tests for recipe cooking confirmation, partial stock deduction, clamping at 0, and uncook restoration in `tests/test_recipe_app_interactions.py`

### Implementation for User Story 1
- [x] T007 [US1] Verify `confirm_recipe_cooked_service` in `app/services/cook.py` cleanly outputs `missing_ingredients` and clamps at 0 without raising exceptions on partial stock
- [x] T008 [P] [US1] Implement Reanimated shake animation and vibration feedback in `app-saas/src/components/recipe-card-swipeable.tsx`
- [x] T009 [US1] Wire short left swipe on `RecipeCardSwipeable` in `app-saas/src/app/(tabs)/kitchen.tsx` to trigger `confirmRecipeCooked` with shake feedback and interactive restock toast on deficit
- [x] T010 [US1] Add « Cuisiner » / « J'ai cuisiné cette recette » and « Annuler la cuisson » action buttons on `app-saas/src/app/recipe/[id].tsx`

**Checkpoint**: User Story 1 is independently testable and delivers a complete MVP for cooking confirmation.

---

## Phase 4: User Story 2 - Planification calendrier avec prévention des chevauchements (Priority: P1)

**Goal**: Calculate dynamic cooking duration from `prep_minutes + cook_minutes`, validate timeline collisions, reject conflicts with 409 and alternative slots, and provide a long-swipe modal to schedule.

**Independent Test**: Drag a recipe card far to the left (>160px); select a time slot overlapping an existing appointment; verify collision banner shows conflicting event and suggests 2 alternative slots.

### Tests for User Story 2
- [x] T011 [P] [US2] Add unit tests for dynamic meal duration calculation and calendar collision rejection with alternatives in `tests/test_recipe_app_interactions.py`

### Implementation for User Story 2
- [x] T012 [US2] Update `create_meal_plan` in `app/api/meal_plans.py` to compute duration from `recipe.prep_minutes + recipe.cook_minutes` (default 45 min) and validate timeline collisions via `detect_calendar_conflicts_and_alternatives`
- [x] T013 [US2] Update `app/services/calendar_hub.py` to project `MealPlan` items using the recipe's dynamic duration instead of hardcoded 75 minutes
- [x] T014 [P] [US2] Create `RecipePlanModal` component in `app-saas/src/components/recipe-plan-modal.tsx` with date/time pickers, conflict alert banner, and 1-tap alternative slot adoption
- [x] T015 [US2] Connect long left swipe (>160px) on `RecipeCardSwipeable` in `app-saas/src/app/(tabs)/kitchen.tsx` to open `RecipePlanModal`
- [x] T016 [US2] Add « Planifier la recette » button in `app-saas/src/app/recipe/[id].tsx` opening `RecipePlanModal`

**Checkpoint**: User Stories 1 and 2 work independently and harmoniously.

---

## Phase 5: User Story 3 - Ajout des ingrédients de la recette à la liste de courses (Priority: P2)

**Goal**: Swipe right on a recipe card to open a bottom sheet with selectable checkboxes for all ingredients (missing ingredients pre-checked) and batch-add them to groceries.

**Independent Test**: Swipe right on a recipe card; verify `RecipeGroceriesSheet` opens with deficit items pre-checked; uncheck one item, click confirm; verify only checked items appear in the shopping list.

### Tests for User Story 3
- [x] T017 [P] [US3] Add unit tests for `POST /api/v1/recipes/{id}/add-to-groceries` with selective ingredient IDs and deficit pre-selection in `tests/test_recipe_app_interactions.py`

### Implementation for User Story 3
- [x] T018 [P] [US3] Create `RecipeGroceriesSheet` bottom sheet in `app-saas/src/components/recipe-groceries-sheet.tsx` with ingredient checkboxes (missing items pre-checked), "Tout cocher" toggle, and batch submission
- [x] T019 [US3] Connect right swipe on `RecipeCardSwipeable` in `app-saas/src/app/(tabs)/kitchen.tsx` to open `RecipeGroceriesSheet`
- [x] T020 [US3] Add « Ajouter aux courses » button in `app-saas/src/app/recipe/[id].tsx` opening `RecipeGroceriesSheet`

**Checkpoint**: User Story 3 is complete and verified.

---

## Phase 6: User Story 4 - Ajustement interactif des portions et instructions sur mobile (Priority: P2)

**Goal**: Provide an interactive stepper (+/-) on the recipe detail screen to scale ingredient amounts dynamically, and allow in-place editing of recipe instructions.

**Independent Test**: On `/recipe/[id]`, change portions from 2 to 4; verify ingredient quantities double in real time and cook confirmation uses the scaled quantities; edit instructions and verify save.

### Tests for User Story 4
- [x] T021 [P] [US4] Add tests for servings scaling and instructions updates via `PATCH /api/v1/recipes/{id}` in `tests/test_recipe_app_interactions.py`

### Implementation for User Story 4
- [x] T022 [US4] Implement interactive servings stepper (+/-) in `app-saas/src/app/recipe/[id].tsx` recalculating displayed ingredient quantities dynamically
- [x] T023 [US4] Pass selected `servings_override` to cook confirmation and grocery addition actions in `app-saas/src/app/recipe/[id].tsx`
- [x] T024 [US4] Add inline instructions editor in `app-saas/src/app/recipe/[id].tsx` with save button calling `PATCH /api/v1/recipes/{id}`

---

## Phase 7: Polish, Quality Gates & Verification

**Purpose**: Multi-surface regression checks, type validation, and documentation synchronization.

- [x] T025 [P] Synchronize action catalog and assistant documentation in `adamhub-assistant/SKILL.md` and `adamhub-assistant/recipes/SKILL.md`
- [x] T026 Execute full backend test suite: `uv run --extra dev pytest` (100% pass)
- [x] T027 Execute mobile SaaS typecheck and lint: `cd app-saas && npm run typecheck && npm run lint`
- [x] T028 Execute web build and lint: `cd web && npm run build && npm run lint`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Phase 1 & Phase 2** (Foundational) must be completed before UI gesture and sheet implementations.
- **Phase 3 (US1)** delivers the MVP (immediate cook confirmation + shake deficit feedback).
- **Phase 4 (US2)** delivers smart collision-free calendar planning.
- **Phase 5 (US3)** delivers right-swipe checkable grocery addition.
- **Phase 6 (US4)** delivers portions stepper and instructions editing.
- **Phase 7** runs final quality gates across backend, mobile, and web.

### Parallel Opportunities
- Tasks marked `[P]` operate on distinct files and can be authored concurrently.
- Test suites in Phase 3, Phase 4, Phase 5, and Phase 6 can be developed alongside components.

