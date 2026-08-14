from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import MealSlot, SupermarketStore


class RecipeIngredientIn(BaseModel):
    name: str
    quantity: float = 1
    unit: str = "item"
    note: str | None = None
    category: str | None = None
    cache_id: int | None = Field(
        default=None,
        description=(
            "SupermarketSearchCache id. When set, store metadata (store, store_label, "
            "external_id, packaging, price_text, product_url, image_url) is resolved "
            "server-side from that cache row; client-supplied store fields are never trusted."
        ),
    )


class RecipeIngredientRead(BaseModel):
    id: int
    recipe_id: int
    name: str
    quantity: float
    unit: str
    note: str | None
    store: SupermarketStore | None = None
    store_label: str | None = None
    external_id: str | None = None
    category: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    image_url: str | None = None


class RecipeCreate(BaseModel):
    name: str
    description: str | None = None
    instructions: str
    steps: list[str] = Field(default_factory=list)
    utensils: list[str] = Field(default_factory=list)
    prep_minutes: int = 0
    cook_minutes: int = 0
    servings: int = 1
    tags: list[str] = Field(default_factory=list)
    source_url: str | None = None
    source_platform: str | None = None
    source_title: str | None = None
    source_description: str | None = None
    source_transcript: str | None = None
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)


class RecipeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    steps: list[str] | None = None
    utensils: list[str] | None = None
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    servings: int | None = None
    tags: list[str] | None = None
    source_url: str | None = None
    source_platform: str | None = None
    source_title: str | None = None
    source_description: str | None = None
    source_transcript: str | None = None
    ingredients: list[RecipeIngredientIn] | None = None


class RecipeCookRequest(BaseModel):
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None


class RecipeCookResult(BaseModel):
    recipe_id: int
    recipe_name: str
    cooked_at: datetime
    note: str | None = None
    missing_ingredients: list[MissingIngredientRead]
    pantry_consumption: list[MealIngredientConsumptionRead]
    meal_plan_id: int
    already_confirmed: bool = False


class RecipeUncookResult(BaseModel):
    recipe_id: int
    recipe_name: str
    already_unconfirmed: bool
    previously_confirmed_at: datetime | None = None
    note: str | None = None
    pantry_restore: list[MealIngredientRestoreRead]


class RecipeRead(BaseModel):
    id: int
    name: str
    description: str | None
    instructions: str
    steps: list[str]
    utensils: list[str]
    prep_minutes: int
    cook_minutes: int
    servings: int
    tags: list[str]
    source_url: str | None
    source_platform: str | None
    source_title: str | None
    source_description: str | None
    source_transcript: str | None
    ingredients: list[RecipeIngredientRead]
    created_at: datetime
    updated_at: datetime


class MissingIngredientRead(BaseModel):
    name: str
    needed_quantity: float
    available_quantity: float
    missing_quantity: float
    unit: str
    store: SupermarketStore | None = None
    store_label: str | None = None
    external_id: str | None = None
    category: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    image_url: str | None = None


class MealPlanCreate(BaseModel):
    planned_at: datetime | None = None
    planned_for: date | None = None
    slot: MealSlot | None = None
    recipe_id: int
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None
    auto_add_missing_ingredients: bool = True


class MealPlanUpdate(BaseModel):
    planned_at: datetime | None = None
    planned_for: date | None = None
    slot: MealSlot | None = None
    recipe_id: int | None = None
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None
    auto_add_missing_ingredients: bool | None = None


class MealPlanRead(BaseModel):
    id: int
    planned_at: datetime
    planned_for: date | None
    slot: MealSlot | None
    recipe_id: int
    recipe_name: str
    servings_override: int | None
    note: str | None
    auto_add_missing_ingredients: bool
    synced_grocery_at: datetime | None
    cooked: bool
    cooked_at: datetime | None
    cooked_note: str | None
    missing_ingredients: list[MissingIngredientRead]
    created_at: datetime
    updated_at: datetime


class MealPlanConfirmCooked(BaseModel):
    note: str | None = None


class MealCookLogCreate(BaseModel):
    recipe_id: int
    cooked_at: datetime | None = None
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None


class MealIngredientConsumptionRead(BaseModel):
    name: str
    unit: str
    required_quantity: float
    consumed_quantity: float
    missing_quantity: float


class MealPlanConfirmResult(BaseModel):
    meal_plan_id: int
    already_confirmed: bool
    confirmed_at: datetime
    note: str | None
    pantry_consumption: list[MealIngredientConsumptionRead]


class MealIngredientRestoreRead(BaseModel):
    name: str
    unit: str
    restored_quantity: float
    pantry_item_id: int


class MealPlanUnconfirmResult(BaseModel):
    meal_plan_id: int
    already_unconfirmed: bool
    previously_confirmed_at: datetime | None
    note: str | None
    pantry_restore: list[MealIngredientRestoreRead]
