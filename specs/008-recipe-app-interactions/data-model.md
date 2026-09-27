# Data Model: Recipe App Interactions

**Feature**: `008-recipe-app-interactions`  
**Date**: 2026-09-12  
**Status**: Completed  

---

## 1. Domain Entities & Persistence

### 1.1 Recipe
Represents a culinary preparation card owned by a tenant.
```python
class Recipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, nullable=False)
    name: str = Field(nullable=False)
    description: Optional[str] = None
    instructions: Optional[str] = None
    steps: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    utensils: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    prep_minutes: int = Field(default=0)
    cook_minutes: int = Field(default=0)
    servings: int = Field(default=2)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### 1.2 RecipeIngredient
Represents an ingredient associated with a recipe.
```python
class RecipeIngredient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id", index=True, nullable=False)
    name: str = Field(nullable=False)
    quantity: float = Field(default=1.0)
    unit: str = Field(default="item")
    note: Optional[str] = None
```

### 1.3 PantryItem
Represents current inventory in the user's pantry.
```python
class PantryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, nullable=False)
    name: str = Field(nullable=False)
    quantity: float = Field(default=0.0)
    unit: str = Field(default="item")
    category: Optional[str] = None
```

### 1.4 GroceryItem
Represents an item on the active shopping list.
```python
class GroceryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, nullable=False)
    name: str = Field(nullable=False)
    quantity: float = Field(default=1.0)
    unit: str = Field(default="item")
    category: Optional[str] = None
    checked: bool = Field(default=False)
    recipe_id: Optional[int] = Field(default=None, foreign_key="recipe.id", index=True)
```

### 1.5 MealPlan & Calendar Synchronization
Represents a scheduled cooking / eating block projected onto the unified calendar.
```python
class MealPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, nullable=False)
    recipe_id: int = Field(foreign_key="recipe.id", index=True, nullable=False)
    planned_at: datetime = Field(nullable=False)  # UTC
    planned_for: Optional[date] = None
    slot: Optional[MealSlot] = None
    servings_override: Optional[int] = None
    note: Optional[str] = None
    auto_add_missing_ingredients: bool = Field(default=True)
```

---

## 2. Data Transfer Objects (DTOs & API Schemas)

### 2.1 RecipeAddToGroceriesRequest
```python
class RecipeAddToGroceriesRequest(BaseModel):
    ingredient_ids: Optional[list[int]] = None  # None = all ingredients
    servings_override: Optional[int] = None
    missing_only: bool = False
```

### 2.2 RecipeAddToGroceriesResult
```python
class RecipeAddToGroceriesResult(BaseModel):
    recipe_id: int
    added_count: int
    items: list[GroceryItemRead]
```

### 2.3 CalendarConflictDetail
```python
class CalendarConflictDetail(BaseModel):
    title: str
    start_at: datetime
    end_at: datetime
    category: str

class AlternativeSlot(BaseModel):
    start_at: datetime
    end_at: datetime
    label: str

class MealPlanConflictResponse(BaseModel):
    detail: str
    conflict: bool = True
    colliding_items: list[CalendarConflictDetail]
    suggested_slots: list[AlternativeSlot]
```

---

## 3. State Transitions & Invariants

```
[ Recipe in List ]
       │
       ├─ (Swipe Left Short) ──► Confirm Cooked ──► Deduct Pantry (Clamp >= 0)
       │                              │
       │                              └─ (Deficit > 0) ──► Shake Card + Toast Restock Prompt
       │
       ├─ (Swipe Left Long)  ──► Open Plan Modal ──► Check Overlap
       │                              │
       │                              ├─ [Conflict]  ──► Block + Suggest Alternatives
       │                              └─ [Slot Free] ──► Create MealPlan + Calendar MEAL Block
       │
       └─ (Swipe Right)      ──► Open Ingredients Checklist Sheet
                                      │
                                      └─ (Confirm) ──► Batch Add Selected to GroceryItem
```

