# Tasks: Assistant Comprehensive Tooling & Smart Scheduling

**Branch**: `003-assistant-comprehensive-tooling`  
**Input**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [contracts/](contracts/)

---

## Phase 1: Setup & Environment Initialization

**Purpose**: Verify dependencies and test harness readiness.

- [x] T001 Verify backend test harness and SQLite isolation in `tests/conftest.py`
- [x] T002 [P] Create comprehensive test suite scaffold in `tests/test_assistant_comprehensive_tooling.py`

---

## Phase 2: Foundational Tooling Infrastructure

**Purpose**: Core dispatcher and whitelist enhancements required before domain-specific user stories.

- [x] T003 Expand `ASSISTANT_ALLOWED_ACTIONS` whitelist in `app/services/assistant/tool_dispatcher.py` to include `recipe.*`, `supermarket.*`, `meal_plan.*`, `pantry.*`, and enhanced `calendar.*`
- [x] T004 Enhance `dispatch_assistant_tool` in `app/services/assistant/tool_dispatcher.py` to capture and format structured error and conflict responses gracefully
- [x] T005 [P] Update `build_system_context` in `app/services/assistant/context_builder.py` to inject current pantry alerts, active recipes overview, supermarket connectivity status, and multi-action chain guidelines

---

## Phase 3: User Story 1 - Full Recipe Lifecycle & Semantic Coherence (Priority: P1) 🎯 MVP

**Goal**: Enable assistant to create, view, search, edit, and delete culinary recipes without misfiling them as tasks.

**Independent Test**: Instruct assistant to create "Risotto aux champignons" with 300g arborio rice; verify `Recipe` and `RecipeIngredient` rows are created and zero `Task` rows are created.

### Tests for User Story 1
- [x] T006 [P] [US1] Add test for assistant recipe creation vs anti-task misfiling in `tests/test_assistant_comprehensive_tooling.py`
- [x] T007 [P] [US1] Add test for recipe search and update through assistant in `tests/test_assistant_comprehensive_tooling.py`

### Implementation for User Story 1
- [x] T008 [US1] Update `context_builder.py` instructions to strictly mandate `recipe__add` / `recipe__update` for all cooking and meal preparation prompts and explicitly forbid `task__create`
- [x] T009 [US1] Add deterministic mock handling for recipe creation and search in `app/services/assistant/openrouter_client.py`
- [x] T010 [US1] Verify recipe delete flow enforces conversational confirmation before invoking `recipe.delete` in `app/services/assistant/context_builder.py`

---

## Phase 4: User Story 2 - Smart Calendar Conflict Detection & Proactive Resolution (Priority: P1)

**Goal**: Detect calendar collisions, identify conflicting events by title and timeframe, compute and propose non-overlapping alternative slots, and support explicit `force` scheduling.

**Independent Test**: Schedule an event from 14:00 to 15:00, then ask assistant to schedule 14:30 to 15:30; verify structured collision with 14:00–15:00 is returned with alternative slots (e.g. 15:00–16:00).

### Tests for User Story 2
- [x] T011 [P] [US2] Add unit tests for `detect_calendar_conflicts_and_alternatives` in `tests/test_calendar_overlap.py`
- [x] T012 [P] [US2] Add integration test for conversational conflict resolution and forced scheduling in `tests/test_assistant_comprehensive_tooling.py`

### Implementation for User Story 2
- [x] T013 [US2] Implement `detect_calendar_conflicts_and_alternatives` in `app/services/calendar_hub.py` returning `conflict: bool`, `colliding_items: list[dict]`, and `suggested_slots: list[dict]`
- [x] T014 [US2] Update `_handle_calendar_add_item` in `app/skill/actions.py` to support `force: bool = False`, returning structured conflict metadata on collision when `force=False`
- [x] T015 [US2] Add `calendar.check_availability` action in `app/skill/actions.py` and register in `ACTION_CATALOG`
- [x] T016 [US2] Add calendar conflict and alternative slot mock generator in `app/services/assistant/openrouter_client.py`

---

## Phase 5: User Story 3 - Supermarket Drive Search & Cart Integration (Priority: P2)

**Goal**: Search genuine retailer products and manage supermarket shopping carts through conversational instructions.

**Independent Test**: Search for "lait bio" at Intermarché, add the item to cart via `cache_id`, and verify the mirrored cart has the item and updated total.

### Tests for User Story 3
- [x] T017 [P] [US3] Add tests for assistant supermarket search and cart manipulation in `tests/test_assistant_comprehensive_tooling.py`

### Implementation for User Story 3
- [x] T018 [US3] Ensure `supermarket.search`, `supermarket.get_cart`, `supermarket.add_cart_item`, `supermarket.update_cart_item`, and `supermarket.remove_cart_item` handle unauthenticated/expired store connections gracefully with clear instructions in `app/skill/actions.py`
- [x] T019 [US3] Add mock fallback for supermarket search and cart tools in `app/services/assistant/openrouter_client.py`
- [x] T020 [US3] Ensure anti-fabrication: reject cart additions without genuine `cache_id` in `app/services/assistant/tool_dispatcher.py`

---

## Phase 6: User Story 4 - End-to-End Meal Planning & Deficit Restocking (Priority: P2)

**Goal**: Schedule meals, check pantry stock, and auto-add missing ingredients to groceries without double-buying.

**Independent Test**: Create a recipe with 500g pasta and 4 eggs. Pantry has 500g pasta and 0 eggs. Plan meal; verify only 4 eggs are added to `GroceryItem`.

### Tests for User Story 4
- [x] T021 [P] [US4] Add test for end-to-end meal plan scheduling with pantry deficit grocery auto-add in `tests/test_assistant_comprehensive_tooling.py`

### Implementation for User Story 4
- [x] T022 [US4] Update `_handle_meal_plan_add` in `app/skill/actions.py` to return detailed `missing_ingredients` and `groceries_added_count`
- [x] T023 [US4] Update `context_builder.py` to prompt the assistant to summarize missing ingredients queued to groceries

---

## Phase 7: User Story 5 - Reversible Cook Confirmation & Pantry Synchronization (Priority: P3)

**Goal**: Confirm meal/recipe as cooked to decrement pantry inventory proportionally, with exact reversible unconfirmation.

**Independent Test**: Confirm cook of recipe needing 200g rice; verify pantry decremented by 200g. Unconfirm cook; verify pantry restored by 200g.

### Tests for User Story 5
- [x] T024 [P] [US5] Add test for reversible cook confirmation via assistant tools in `tests/test_assistant_comprehensive_tooling.py`

### Implementation for User Story 5
- [x] T025 [US5] Verify `_handle_recipe_confirm_cooked` and `_handle_recipe_unconfirm_cooked` in `app/skill/actions.py` cleanly expose lot restorations and clamp at zero for partial stock
- [x] T026 [US5] Whitelist `meal_plan.confirm_cooked` and `meal_plan.unconfirm_cooked` in `tool_dispatcher.py`

---

## Phase 8: Polish, Skill Sync & Documentation

**Purpose**: Synchronize assistant skill manifests, action catalogs, and verify regression-free execution.

- [x] T027 [P] Synchronize `adamhub-assistant/SKILL.md` and action references with newly whitelisted actions
- [x] T028 [P] Synchronize `app/mcp/server.py` tool registrations
- [x] T029 Execute full test suite `uv run --extra dev pytest` and ensure 100% pass rate
- [x] T030 Execute web and mobile typechecks (`app-saas: npm run typecheck && npm run lint`)

---

## Dependencies & Execution Order

1. **Phase 1 & Phase 2** (Foundational) must be completed first.
2. **Phase 3 (US1)** and **Phase 4 (US2)** deliver the core P1 requirements (Recipe Lifecycle + Calendar Conflicts).
3. **Phase 5 (US3)** and **Phase 6 (US4)** deliver P2 requirements (Supermarket + Meal Plan Deficit).
4. **Phase 7 (US5)** delivers P3 (Reversible Cook Confirmation).
5. **Phase 8** delivers polish, skill documentation sync, and final quality gates.
