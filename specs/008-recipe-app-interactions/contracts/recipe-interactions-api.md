# API & UI Contracts: Recipe App Interactions

**Feature**: `008-recipe-app-interactions`  
**Date**: 2026-09-12  
**Status**: Completed  

---

## 1. HTTP Endpoints

### 1.1 `POST /api/v1/recipes/{recipe_id}/confirm-cooked`
Confirms the preparation of a recipe and decrements available pantry stock.

- **Headers**: `Authorization: Bearer <token>`
- **Path Parameter**: `recipe_id: int`
- **Request Body** (Optional):
  ```json
  {
    "servings_override": 4,
    "note": "Cuisiné pour les invités"
  }
  ```
- **Response 200 OK**:
  ```json
  {
    "recipe_id": 1,
    "recipe_name": "Saumon teriyaki avec riz",
    "cooked_at": "2026-09-12T20:30:00Z",
    "note": "Cuisiné pour les invités",
    "missing_ingredients": [
      {
        "name": "Sauce teriyaki",
        "required": 50.0,
        "available": 0.0,
        "deficit": 50.0,
        "unit": "ml"
      }
    ],
    "pantry_consumption": [
      {
        "pantry_item_id": 4,
        "name": "Pavé de saumon",
        "consumed": 400.0,
        "unit": "g"
      }
    ],
    "meal_plan_id": null,
    "already_confirmed": false
  }
  ```

---

### 1.2 `POST /api/v1/recipes/{recipe_id}/add-to-groceries`
Transfers selected or all ingredients from a recipe directly to the user's shopping list.

- **Headers**: `Authorization: Bearer <token>`
- **Path Parameter**: `recipe_id: int`
- **Request Body**:
  ```json
  {
    "ingredient_ids": [2, 5],
    "servings_override": 4,
    "missing_only": false
  }
  ```
- **Response 200 OK**:
  ```json
  {
    "recipe_id": 1,
    "added_count": 2,
    "items": [
      {
        "id": 12,
        "name": "Sauce teriyaki",
        "quantity": 50.0,
        "unit": "ml",
        "category": "Condiments",
        "checked": false,
        "recipe_id": 1
      },
      {
        "id": 13,
        "name": "Riz basmati",
        "quantity": 300.0,
        "unit": "g",
        "category": "Féculents",
        "checked": false,
        "recipe_id": 1
      }
    ]
  }
  ```

---

### 1.3 `POST /api/v1/meal-plans`
Schedules a recipe meal on the calendar with duration calculation and collision checks.

- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "recipe_id": 1,
    "planned_at": "2026-09-13T17:00:00Z",
    "servings_override": 2,
    "note": "Dîner du dimanche",
    "auto_add_missing_ingredients": true
  }
  ```
- **Response 200 OK (Success)**:
  ```json
  {
    "id": 14,
    "recipe_id": 1,
    "recipe_name": "Saumon teriyaki avec riz",
    "planned_at": "2026-09-13T17:00:00Z",
    "duration_minutes": 45,
    "slot": "dinner",
    "servings_override": 2,
    "note": "Dîner du dimanche",
    "auto_add_missing_ingredients": true
  }
  ```
- **Response 409 Conflict (Collision with Existing Calendar Event)**:
  ```json
  {
    "detail": "Le créneau sélectionné chevauche un événement existant",
    "conflict": true,
    "colliding_items": [
      {
        "title": "Séance de sport",
        "start_at": "2026-09-13T17:00:00Z",
        "end_at": "2026-09-13T18:00:00Z",
        "category": "fitness"
      }
    ],
    "suggested_slots": [
      {
        "start_at": "2026-09-13T18:00:00Z",
        "end_at": "2026-09-13T18:45:00Z",
        "label": "Immédiatement après (18:00 - 18:45)"
      },
      {
        "start_at": "2026-09-13T16:15:00Z",
        "end_at": "2026-09-13T17:00:00Z",
        "label": "Avant l'événement (16:15 - 17:00)"
      }
    ]
  }
  ```

---

## 2. Mobile UI Contracts (`app-saas`)

### 2.1 `RecipeCardSwipeable`
Props:
```typescript
interface RecipeCardSwipeableProps {
  recipe: RecipeRead;
  onCookShort: (recipe: RecipeRead) => Promise<void>;
  onPlanLong: (recipe: RecipeRead) => void;
  onGroceriesSwipe: (recipe: RecipeRead) => void;
  onPressCard: (recipeId: number) => void;
  isShaking?: boolean;
}
```

### 2.2 `RecipeGroceriesSheet`
Props:
```typescript
interface RecipeGroceriesSheetProps {
  visible: boolean;
  recipe: RecipeRead | null;
  pantryItems: PantryItemRead[];
  onClose: () => void;
  onConfirmAdd: (ingredientIds: number[], servings: number) => Promise<void>;
}
```

### 2.3 `RecipePlanModal`
Props:
```typescript
interface RecipePlanModalProps {
  visible: boolean;
  recipe: RecipeRead | null;
  onClose: () => void;
  onSchedule: (plannedAt: string, autoAddMissing: boolean) => Promise<void>;
}
```
