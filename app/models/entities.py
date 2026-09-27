from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupermarketStore(str, Enum):
    INTERMARCHE = "intermarche"
    CARREFOUR = "carrefour"
    LECLERC = "leclerc"
    AUCHAN = "auchan"


class SupermarketTargetType(str, Enum):
    RECIPE_INGREDIENT = "recipe_ingredient"
    PANTRY_ITEM = "pantry_item"


class CartStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"


class MealSlot(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


# ---------------------------------------------------------------------------
# 1. Utilisateurs, Profil & Mémoire IA
# ---------------------------------------------------------------------------

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    display_name: str
    is_active: bool = True
    email_verified: bool = Field(default=False, index=True)
    email_verification_token_hash: str | None = None
    email_verification_sent_at: datetime | None = None
    api_key_encrypted: str | None = None
    api_key_hash: str | None = Field(default=None, index=True, unique=True)
    api_key_created_at: datetime | None = None
    ntfy_topic: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class UserProfile(SQLModel, table=True):
    """Préférences et contexte culinaire/alimentaire de l'utilisateur."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, unique=True)
    dietary_preferences: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    fitness_goals: str = Field(default="", max_length=500)
    lifestyle_notes: str = Field(default="", max_length=1000)
    ai_tone: str = Field(default="direct", max_length=50)
    onboarding_completed: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class UserMemory(SQLModel, table=True):
    """Faits persistants extraits par l'IA lors des conversations."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    category: str = Field(default="food", index=True, max_length=50)
    fact: str = Field(max_length=1000)
    confidence: float = Field(default=1.0)
    source: str = Field(default="conversation", max_length=50)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# 2. Courses (Groceries)
# ---------------------------------------------------------------------------

class GroceryItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    name: str
    quantity: float = 1
    unit: str = "item"
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = Field(default=None, index=True)
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    checked: bool = False
    in_cart: bool = Field(default=False, index=True)
    priority: int = 3
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class GroceryPantrySync(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    grocery_item_id: int = Field(foreign_key="groceryitem.id", index=True)
    pantry_item_id: int = Field(foreign_key="pantryitem.id", index=True)
    added_quantity: float = 0
    created_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# 3. Recettes & Planification de repas
# ---------------------------------------------------------------------------

class Recipe(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    name: str
    description: str | None = None
    instructions: str
    steps: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    utensils: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    prep_minutes: int = 0
    cook_minutes: int = 0
    servings: int = 1
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_url: str | None = None
    source_platform: str | None = None
    source_title: str | None = None
    source_description: str | None = None
    source_transcript: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class RecipeIngredient(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    name: str
    quantity: float = 1
    unit: str = "item"
    note: str | None = None
    cache_id: int | None = Field(default=None, foreign_key="supermarketsearchcache.id")
    store: SupermarketStore | None = None
    store_label: str | None = None
    external_id: str | None = Field(default=None, index=True)
    category: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    image_url: str | None = None


class MealPlan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    planned_at: datetime = Field(default_factory=utcnow)
    planned_for: date | None = None
    slot: MealSlot | None = None
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    servings_override: int | None = None
    note: str | None = None
    auto_add_missing_ingredients: bool = True
    synced_grocery_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MealPlanCookConfirmation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    meal_plan_id: int = Field(foreign_key="mealplan.id", index=True, unique=True)
    confirmed_at: datetime = Field(default_factory=utcnow)
    note: str | None = None
    pantry_consumption: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# 4. Garde-Manger (Pantry) & OpenFoodFacts
# ---------------------------------------------------------------------------

class PantryItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    name: str
    quantity: float = 0
    unit: str = "item"
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = Field(default=None, index=True)
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    min_quantity: float = 0
    expires_at: date | None = None
    location: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OpenFoodFactsCache(SQLModel, table=True):
    barcode: str = Field(primary_key=True, max_length=64)
    raw_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    product_name: str | None = None
    brand: str | None = None
    quantity_text: str | None = None
    categories: str | None = None
    image_url: str | None = None
    nutriscore: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


# ---------------------------------------------------------------------------
# 5. Supermarchés, Enseignes & Synchronisation Drive
# ---------------------------------------------------------------------------

class SupermarketProduct(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    packaging: str | None = None
    price: str | None = None
    image_url: str | None = None
    store: str
    external_id: str | None = Field(default=None, index=True)
    category: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SupermarketSearchCache(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    store: SupermarketStore = Field(index=True)
    query: str = Field(index=True)
    external_id: str | None = Field(default=None, index=True)
    name: str
    brand: str | None = None
    category: str | None = None
    packaging: str | None = None
    price_amount: float | None = None
    price_text: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utcnow, index=True)
    expires_at: datetime = Field(default_factory=utcnow, index=True)


class SupermarketMapping(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    target_type: SupermarketTargetType = Field(index=True)
    target_id: int = Field(index=True)
    store: SupermarketStore = Field(index=True)
    cache_id: int | None = Field(default=None, foreign_key="supermarketsearchcache.id", index=True)
    external_id: str
    store_label: str
    name_snapshot: str
    category_snapshot: str | None = None
    packaging_snapshot: str | None = None
    price_snapshot: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    last_verified_at: datetime = Field(default_factory=utcnow)
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SupermarketStoreSelection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    store: SupermarketStore = Field(index=True, unique=True)
    external_store_id: str
    store_label: str
    location_label: str | None = None
    raw_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SupermarketConnection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    store: SupermarketStore = Field(index=True)
    label: str
    cookies_encrypted: str
    is_active: bool = Field(default=False, index=True)
    customer_uuid: str | None = None
    last_used_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SupermarketCart(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "store", name="uq_supermarketcart_user_store"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )
    store: SupermarketStore
    status: CartStatus = Field(default=CartStatus.DRAFT)
    validated_at: datetime | None = None
    external_cart_ref: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SupermarketCartItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cart_id: int = Field(foreign_key="supermarketcart.id", ondelete="CASCADE", index=True)
    cache_id: int | None = Field(
        default=None, foreign_key="supermarketsearchcache.id", ondelete="SET NULL"
    )
    external_id: str | None = None
    name: str
    brand: str | None = None
    packaging: str | None = None
    price_amount: float | None = None
    price_text: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    quantity: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class UserStorePreference(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "store", name="uq_user_store_preference"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    store: SupermarketStore = Field(index=True)
    external_store_id: str
    store_label: str
    location_label: str | None = None
    pickup_type: str = Field(default="quai", max_length=32)
    optimization_strategy: str = Field(default="mdd", max_length=32)
    channel: str | None = None
    raw_context: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class GroceryToCartJob(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    store: SupermarketStore = Field(index=True)
    external_store_id: str
    status: str = Field(default="draft", index=True, max_length=32)
    optimization_strategy: str = Field(default="mdd", max_length=32)
    items_count: int = 0
    matched_count: int = 0
    substitutes_count: int = 0
    unmatched_count: int = 0
    estimated_total_cents: int = 0
    error_message: str | None = None
    synced_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MatchedCartItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="grocerytocartjob.id", index=True)
    grocery_item_id: int | None = Field(default=None, foreign_key="groceryitem.id", index=True)
    cache_id: int | None = Field(default=None, foreign_key="supermarketsearchcache.id", index=True)
    external_id: str | None = None
    name: str
    brand: str | None = None
    packaging: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    quantity: float = 1.0
    unit_price_cents: int = 0
    total_price_cents: int = 0
    match_type: str = Field(default="mdd", max_length=32)
    status: str = Field(default="staged", max_length=32)
    custom_note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SubstituteProposal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    matched_item_id: int = Field(foreign_key="matchedcartitem.id", index=True)
    alternative_cache_id: int = Field(foreign_key="supermarketsearchcache.id", index=True)
    alternative_name: str
    alternative_brand: str | None = None
    alternative_unit_price_cents: int = 0
    price_difference_cents: int = 0
    reason: str
    status: str = Field(default="pending", max_length=32)
    created_at: datetime = Field(default_factory=utcnow)
