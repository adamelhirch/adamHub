# Quickstart & Verification Guide: Recipe App Interactions

**Feature**: `008-recipe-app-interactions`  
**Date**: 2026-09-12  
**Status**: Ready  

---

## 1. Automated Backend Verification

Run the targeted test suite covering the new recipe interactions, grocery batching, and calendar non-overlap rules:

```bash
uv run --extra dev pytest tests/test_recipe_app_interactions.py -v
```

### Expected Scenarios Tested
1. **Pantry Cook Deduction**: Confirming cooking decrements `PantryItem` stock down to 0 without negative quantities.
2. **Reversible Uncook**: Calling unconfirm restores initial pantry stock.
3. **Partial Stock Shake Detection**: Cooking with missing ingredients returns `missing_ingredients` without failing.
4. **Batch Add to Groceries**: `POST /api/v1/recipes/{id}/add-to-groceries` scales quantities and creates `GroceryItem` records.
5. **Smart Calendar Overlap Detection**: Attempting to schedule a meal during an existing 17:00–18:00 event returns HTTP 409 with colliding item details and alternative slots.
6. **Multi-Tenant Isolation**: Verifies another tenant cannot cook, restock, or view recipe interactions of the acting user.

---

## 2. Frontend & Mobile Verification

### 2.1 Mobile App SaaS (`app-saas`)
Execute static typing and linting checks:
```bash
cd app-saas && npm run typecheck && npm run lint
```

### 2.2 Web SPA (`web`)
Execute web build and linting checks:
```bash
cd web && npm run build && npm run lint
```

---

## 3. Manual End-to-End Walkthrough

1. **Launch Environment**:
   - Backend: `uv run uvicorn app.main:app --reload`
   - Mobile: `cd app-saas && npx expo start`
2. **Step 1 - Recipe List (Cuisine > Recettes)**:
   - Navigate to the **Cuisine** tab, select the **Recettes** section.
   - Verify all recipe cards display preparation time, portions, and description.
3. **Step 2 - Swipe Left Short (Cuisiné maintenant)**:
   - Perform a short swipe to the left on a recipe card.
   - If ingredients are sufficient: verify instant success and pantry deduction.
   - If ingredients are missing: verify the card shakes, haptic feedback triggers, and the bottom toast prompts to add missing items to groceries.
4. **Step 3 - Swipe Left Long (Planification Calendrier)**:
   - Drag a recipe card far to the left (> 160px).
   - Verify the scheduling modal opens with duration automatically set to `prep_minutes + cook_minutes`.
   - Pick a time slot where another task/event exists (e.g. 17:00).
   - Verify the collision banner shows the conflicting event and offers alternative non-overlapping slots.
   - Tap an alternative slot: verify the meal plan is created and appears on the Home Calendar.
5. **Step 4 - Swipe Right (Courses Checklist)**:
   - Swipe right on a recipe card.
   - Verify the `RecipeGroceriesSheet` opens with all recipe ingredients.
   - Verify missing ingredients are pre-checked.
   - Uncheck/check items and confirm: verify the selected items appear in the **Courses** tab.
6. **Step 5 - Recipe Detail Screen**:
   - Tap a recipe card to view `/recipe/[id]`.
   - Test the portions stepper (+/-) and verify ingredient amounts scale dynamically.
   - Edit the recipe instructions and click Save: verify changes are persisted.
