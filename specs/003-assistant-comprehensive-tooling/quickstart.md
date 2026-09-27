# Quickstart & Validation Guide: Assistant Comprehensive Tooling & Smart Scheduling

This guide documents runnable validation scenarios that prove all user stories and acceptance criteria from `spec.md` work end-to-end.

---

## Prerequisites & Environment Setup

1. **Activate virtual environment & dependencies**:
   ```bash
   uv sync --extra dev
   ```

2. **Verify test suite health**:
   ```bash
   uv run --extra dev pytest
   ```

---

## Scenario 1: Full Recipe Lifecycle & Semantic Coherence (P1)

**Goal**: Prove the assistant saves a dictated recipe as a structured `Recipe` and never misfiles it as a `Task`.

1. **Run automated test**:
   ```bash
   uv run --extra dev pytest tests/test_assistant_comprehensive_tooling.py -k "test_assistant_recipe_lifecycle"
   ```
2. **What this verifies**:
   - Instruction: *"Enregistre ma recette de Risotto aux champignons : 300g de riz arborio, 250g de champignons..."*
   - Invokes `recipe__add` with structured ingredient objects (name, quantity, unit).
   - Zero `Task` rows created with recipe title.
   - Subsequent search query retrieves the structured recipe card.

---

## Scenario 2: Smart Calendar Conflict Detection & Proactive Resolution (P1)

**Goal**: Prove the assistant detects overlapping timeline events and proactively suggests viable non-overlapping alternative slots.

1. **Run automated test**:
   ```bash
   uv run --extra dev pytest tests/test_assistant_comprehensive_tooling.py -k "test_calendar_conflict_and_alternatives"
   ```
2. **What this verifies**:
   - Existing event from 14:00 to 15:00 UTC.
   - Scheduling attempt from 14:30 to 15:30 UTC with `force=false`.
   - Tool returns `{"conflict": true, "colliding_items": [{"title": "...", ...}], "suggested_slots": [...]}`.
   - Assistant message flags the collision and suggests non-conflicting slots (e.g. 15:00–16:00).
   - Scheduling with `force=true` succeeds and notes overlapping commitment.

---

## Scenario 3: Supermarket Drive Search & Cart Integration (P2)

**Goal**: Search authentic retailer products and manage supermarket drive carts.

1. **Run automated test**:
   ```bash
   uv run --extra dev pytest tests/test_assistant_comprehensive_tooling.py -k "test_supermarket_assistant_tools"
   ```
2. **What this verifies**:
   - Queries `supermarket__search` for "lait demi-écrémé" at Intermarché.
   - Genuine cached retailer products returned with prices and `cache_id`.
   - Adds product to cart via `supermarket__add_cart_item`.
   - Retrieves updated cart total via `supermarket__get_cart`.

---

## Scenario 4: End-to-End Meal Planning & Deficit Restocking (P2)

**Goal**: Schedule a meal, verify pantry stock, and auto-queue only missing ingredients into groceries.

1. **Run automated test**:
   ```bash
   uv run --extra dev pytest tests/test_assistant_comprehensive_tooling.py -k "test_meal_planning_deficit_restock"
   ```
2. **What this verifies**:
   - Recipe requires 500g pasta and 4 eggs.
   - Pantry already contains 500g pasta and 0 eggs.
   - `meal_plan__add` schedules the meal, skips pasta, and creates a grocery item for 4 eggs.

---

## Scenario 5: Reversible Cook Confirmation & Pantry Restock (P3)

**Goal**: Confirm cooked meal decrements pantry stock proportionally; cancellation restores stock.

1. **Run automated test**:
   ```bash
   uv run --extra dev pytest tests/test_assistant_comprehensive_tooling.py -k "test_reversible_cook_confirmation"
   ```
2. **What this verifies**:
   - Pantry starts with 1000g rice.
   - Recipe requires 200g rice.
   - `recipe__confirm_cooked` decrements pantry to 800g rice.
   - `recipe__unconfirm_cooked` restores pantry to exactly 1000g rice.
