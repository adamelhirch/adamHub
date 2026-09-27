# Research: Assistant Comprehensive Tooling & Smart Scheduling

**Feature**: `003-assistant-comprehensive-tooling`
**Date**: 2026-09-12
**Status**: Complete

---

## 1. Calendar Conflict Detection & Alternative Slot Proposal

### Context & Problem
Currently, `validate_calendar_slot_free` in `app/services/calendar_hub.py` verifies interval overlaps against manual `CalendarItem` entries and projected generated items from tasks, habits, and sessions. If any overlap is found, it unconditionally raises a `ValueError(f"Calendar slot overlaps with...")`. When exposed to conversational agents, this causes a hard error in `dispatch_assistant_tool`, leaving the LLM to either crash the conversation or echo a technical error string without actionable alternatives.

### Decisions & Implementation Approach
1. **New Conflict Detection Engine in `calendar_hub.py`**:
   - Introduce `detect_calendar_conflicts_and_alternatives(session, start_at, end_at, user_id, max_alternatives=2)`:
     - Scans for colliding manual items and generated timeline items within `[start_at, end_at]`.
     - Collects collision metadata: `title`, `start_at`, `end_at`, `source`, `category`.
     - Computes non-overlapping alternative slots:
       - **Slot A (Immediate After)**: Searches starting from the end of the latest colliding item, respecting reasonable operating hours (07:00–22:00 local/UTC).
       - **Slot B (Same-Day Prior or Closest Available)**: Checks backwards before the earliest colliding item, or looks for the next open gap on the same day.
       - **Slot C (Next-Day Morning Fallback)**: If the target day is fully booked, proposes 09:00–10:00 on the subsequent day.
       - Each candidate alternative is verified with `validate_calendar_slot_free` to ensure zero collision.
2. **Action Updates in `app/skill/actions.py`**:
   - Update `calendar.add_item` schema: add optional `"force": "bool?"` (default: `False`).
   - If `force=False` and collisions exist:
     - Return structured conflict payload:
       ```json
       {
         "conflict": true,
         "message": "Créneau occupé par un ou plusieurs événements existants.",
         "colliding_items": [{"title": "Dentiste", "start_at": "...", "end_at": "..."}],
         "suggested_slots": [{"start_at": "...", "end_at": "..."}]
       }
       ```
     - Do NOT persist the item. The assistant reads this structure and converses with the user, proposing the alternative slots or asking if the user wants to force scheduling.
   - If `force=True` or no collision exists:
     - Persist the `CalendarItem` as normal and return the saved item.
   - Add `calendar.check_availability` to `ACTION_CATALOG` allowing proactive slot checks.

### Alternatives Considered
- *Rejecting with 409 Conflict HTTPException*: Hard exceptions interrupt the multi-step agent flow and require complex try/catch translation. Returning structured `{conflict: true, ...}` keeps the tool calling cycle fluid and enables the LLM to provide natural conversational alternatives.
- *Silent Overwrite*: Silently moving or erasing colliding events violates user intent and Principle IV. Explicit resolution paths (accept slot, change time, or force overlap) are strictly required.

---

## 2. Recipe Lifecycle Tooling & Semantic Coherence

### Context & Problem
`ACTION_CATALOG` in `app/skill/actions.py` already includes robust recipe handlers: `recipe.add`, `recipe.list`, `recipe.get`, `recipe.update`, `recipe.confirm_cooked`, `recipe.unconfirm_cooked`, `recipe.delete`. However, `ASSISTANT_ALLOWED_ACTIONS` in `app/services/assistant/tool_dispatcher.py` omitted all `recipe.*` actions. As a consequence, conversational recipe requests either triggered `task.create` (misfiling recipes as to-do tasks) or failed with "Action 'recipe.add' is not authorized".

### Decisions & Implementation Approach
1. **Whitelist Recipe Actions in `tool_dispatcher.py`**:
   - Add to `ASSISTANT_ALLOWED_ACTIONS`:
     - `recipe.add`
     - `recipe.list`
     - `recipe.get`
     - `recipe.update`
     - `recipe.confirm_cooked`
     - `recipe.unconfirm_cooked`
     - `recipe.delete`
2. **Semantic Distinction in System Prompt (`context_builder.py`)**:
   - Explicitly instruct the assistant:
     - Culinary recipes, meal preparation, cooking steps, and ingredient lists MUST be stored via `recipe__add` or `recipe__update`.
     - NEVER invoke `task__create` or note tools for culinary recipes.
     - For recipe deletion, ask for explicit user confirmation before calling `recipe__delete`.
3. **Deterministic Mock Handling in `openrouter_client.py`**:
   - For dev/test execution without an OpenRouter key, recognize recipe dictations (e.g. "enregistre ma recette", "recette de", "salade césar", "risotto") and generate structured `recipe__add` mock tool calls with ingredients and instructions.

### Alternatives Considered
- *Merging recipes into tasks with a "cooking" tag*: Strongly rejected. Recipes require structured servings, prep/cook times, discrete ingredient lines with units and supermarket linkages, and meal plan integration. Tasks do not support these domain attributes.

---

## 3. Supermarket Drive Search & Cart Integration

### Context & Problem
AdamHUB has high-fidelity scrapers and cart synchronizers for Intermarché, Carrefour, Leclerc, and Auchan (`app/services/scrapers/`, `app/services/cart_mirror.py`). While `app/skill/actions.py` contains `supermarket.*` actions, none were whitelisted in `ASSISTANT_ALLOWED_ACTIONS`.

### Decisions & Implementation Approach
1. **Whitelist Supermarket Actions in `tool_dispatcher.py`**:
   - `supermarket.search`: Catalog search yielding authentic `cache_id` entries.
   - `supermarket.get_cart`: Real-time cart contents, counts, and prices.
   - `supermarket.list_carts`: Overview across connected retailers.
   - `supermarket.add_cart_item`: Adding authentic items by `cache_id`.
   - `supermarket.update_cart_item`: Updating quantities.
   - `supermarket.remove_cart_item`: Line deletion.
   - `supermarket.clear_cart`: Emptying cart.
   - `supermarket.list_stores` & `supermarket.list_connections`: Checking store connectivity.
2. **Truth-in-Store Anti-Fabrication Enforcement**:
   - Enforce Principle II: The assistant must never invent mock IDs or fake prices. Cart additions must validate `cache_id` in `SupermarketSearchCache`.
   - If a retailer connection is absent or expired (401 from scraper), catch `CartException` or `ValueError` and return a user-friendly instruction: "Votre connexion au drive [Magasin] nécessite une reconnexion via l'extension AdamHUB Connect."

### Alternatives Considered
- *Direct scraper execution in assistant tools*: Rejected. Scraper logic is cleanly abstracted behind `app/services/cart_mirror.py` and `app/skill/actions.py`. Assistant tools must route through the unified action layer to preserve tenant scoping and proxy management.

---

## 4. End-to-End Meal Planning & Deficit Restocking

### Context & Problem
Users expect to plan a meal, check what is currently in stock in their pantry, and add only the missing ingredients to their shopping list or drive cart without double-buying.

### Decisions & Implementation Approach
1. **Leverage `compute_missing_ingredients` & `add_missing_to_grocery`**:
   - `app/services/cook.py` and `app/services/meal_planning.py` already implement unit-aware pantry stock comparison and deficit calculation.
   - Whitelist `meal_plan.add`, `meal_plan.list`, `meal_plan.confirm_cooked`, `meal_plan.unconfirm_cooked`, `meal_plan.delete` in `ASSISTANT_ALLOWED_ACTIONS`.
   - Enhance `_handle_meal_plan_add` return dictionary to include:
     - `missing_ingredients`: list of missing ingredient items.
     - `groceries_added_count`: count of items newly queued for shopping.
2. **Expose `pantry.overview`**:
   - Add `pantry.overview` to `ASSISTANT_ALLOWED_ACTIONS` so the assistant can query low-stock and expiring items during proactive meal suggestions.

---

## 5. Reversible Cook Confirmation

### Context & Problem
Confirming a meal or recipe as cooked decrements pantry stock. If confirmed accidentally, users need a one-click or conversational rollback without manual reconciliation.

### Decisions & Implementation Approach
1. `app/services/cook.py` maintains `MealPlanCookConfirmation.pantry_consumption` lots, tracking the exact row IDs and deducted quantities.
2. Calling `recipe.unconfirm_cooked` or `meal_plan.unconfirm_cooked` restores the exact decremented quantities back into the pantry item.
3. If pantry items were deleted in the interim, unconfirmation recreates them cleanly with the restored quantity.
4. If pantry stock was insufficient at the time of cooking, stock is clamped at 0.0 without negative inventory, and the shortfall is reported.
