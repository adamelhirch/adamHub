# Research & Technical Decisions: Recipe App Interactions

**Feature**: `008-recipe-app-interactions`  
**Date**: 2026-09-12  
**Status**: Completed  

---

## 1. Mobile Swipe Gestures Implementation

### Decision
Utilize `Swipeable` from `react-native-gesture-handler` (already installed in `app-saas`) combined with `react-native-reanimated` for gesture-driven actions directly on recipe list cards:
- **Left swipe**:
  - Threshold 1 (short drag ~80px): Action « Cuisiner » (fond vert émeraude, icône toque/check) triggering immediate cook confirmation (`POST /api/v1/recipes/{id}/confirm-cooked`).
  - Threshold 2 (full drag >160px): Action « Planifier » (fond bleu indigo, icône calendrier) opening the smart calendar planning modal.
- **Right swipe**:
  - Drag right: Action « Courses » (fond ambre/orange, icône panier) opening the `RecipeGroceriesSheet` with selectable ingredient checkboxes.

### Rationale
- `react-native-gesture-handler` is already integrated in `app-saas/package.json` (`~2.32.0`) and provides native 60fps/120fps gesture tracking without JS thread blocking.
- Progressive left swipe allows power users to cook in a single flick while providing immediate access to the planning modal on a longer swipe.

### Alternatives Considered
- `PanResponder` from React Native core: more boilerplate, prone to frame drops on complex lists.
- Context menu (long press only): lacks visual affordance and requires additional taps.

---

## 2. Dynamic Cooking Duration & Strict Calendar Collision Validation

### Decision
Update `POST /api/v1/meal-plans` and `app/services/calendar_hub.py` to enforce dynamic duration calculation and strict non-overlap calendar checks:
1. **Dynamic Duration**:
   - `duration_minutes = (recipe.prep_minutes or 0) + (recipe.cook_minutes or 0)`.
   - If duration is 0, fall back to default of 45 minutes.
   - Projected calendar slot: `start_at = planned_at`, `end_at = start_at + timedelta(minutes=duration_minutes)`.
2. **Strict Timeline Non-Overlap Check**:
   - Call `detect_calendar_conflicts_and_alternatives(session, user_id, start_at, end_at)`.
   - If collision detected: reject with HTTP 409 Conflict returning:
     ```json
     {
       "detail": "Le créneau sélectionné chevauche un événement existant",
       "conflict": true,
       "colliding_items": [{"title": "...", "start_at": "...", "end_at": "...", "category": "..."}],
       "suggested_slots": [{"start_at": "...", "end_at": "...", "label": "..."}]
     }
     ```
3. **Calendar Projection Sync**:
   - In `app/services/calendar_hub.py`, replace the legacy hardcoded `timedelta(minutes=75)` with the actual recipe duration: `timedelta(minutes=duration_minutes)`.

### Rationale
- Enforces Constitution Principle IV (Non-bypassable timeline validation).
- Prevents double-booking user time (e.g. attempting to schedule dinner prep during an existing appointment).
- Providing 2+ alternative slots allows 1-tap resolution without leaving the planning dialog.

---

## 3. Deficit Stock Cook Confirmation & Shake Feedback

### Decision
When confirming cook on a recipe where one or more ingredients have insufficient stock in `PantryItem`:
1. **Pantry Mutation**:
   - Available stock is decremented down to 0 (clamped at 0, strictly preventing negative inventory).
   - Invariant-driven state transitions (Principle III) are strictly maintained.
2. **Client Micro-interaction**:
   - Card executes a Reanimated spring shake sequence (oscillation on the X axis: -10px, +10px, -6px, +6px, 0).
   - Native haptic feedback / vibration (`Vibration.vibrate([0, 50, 50, 50])`).
   - Interactive Toast appears at screen bottom:
     `"2 ingrédients manquants décomptés. Les ajouter aux courses ?"` with a direct action button `[Ajouter aux courses]`.

### Rationale
- Follows Emil Kowalski design polish principles: feedback is immediate, non-modal, tactile, and constructive.
- Does not block the cook action if the user has substitute ingredients off-system, but makes restocking effortless.

---

## 4. Batch Recipe Groceries Restocking Endpoint

### Decision
Introduce a dedicated, atomic endpoint:
`POST /api/v1/recipes/{recipe_id}/add-to-groceries`
Payload:
```json
{
  "ingredient_ids": [12, 15],
  "servings_override": 4
}
```
Behavior:
- Resolves recipe ingredients for the given IDs (scoped to `user_id`).
- Scales quantities by `servings_override / recipe.servings`.
- Inserts corresponding `GroceryItem` records atomically.
- Returns `{ "success": true, "added_count": 2, "items": [...] }`.

### Rationale
- Eliminates multiple sequential HTTP requests from the mobile client.
- Respects multi-tenant isolation (`user_id`).
- Supports the checklist modal where users uncheck ingredients they already have or don't want.

---

## 5. Mobile Portions & Instructions Editing

### Decision
1. **Portions Adjustment**:
   - Recipe detail screen maintains state `servings` with increment/decrement stepper.
   - Ingredient quantities compute client-side in real time: `(base_qty / base_servings) * current_servings`.
   - Passing `servings_override` to cook confirmation or grocery add ensures server-side operations use the exact adjusted quantities.
2. **Instructions Modification**:
   - Existing `PATCH /api/v1/recipes/{id}` endpoint already supports updating `instructions` and `steps`.
   - Mobile UI adds a clean inline or modal edit toggle allowing users to refine recipe steps with instant autosave or explicit save button.

