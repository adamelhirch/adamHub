# Data Model: Pantry Stock Management, Ingredient Normalization & Open Food Facts Scanner

**Feature**: `009-pantry-stock-openfoodfacts`  
**Date**: 2026-09-15  
**Status**: Completed  

---

## 1. Entities & Schemas

### 1.1 `PantryItem` (SQLModel Entity)

Represents physical food items currently in the household inventory.

```python
class PantryItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    name: str  # Cleaned culinary name (e.g. "Saumon frais", "Pâtes penne", "Riz basmati")
    quantity: float = Field(default=0, ge=0)
    unit: str = Field(default="item")  # Strictly from allowed unit vocabulary
    category: str | None = None  # e.g. "Poisson", "Épicerie", "Frais", "Viande", etc.
    image_url: str | None = None
    store_label: str | None = None  # Brand / Store (e.g. "Carrefour Extra", "Barilla")
    external_id: str | None = Field(default=None, index=True)  # EAN barcode or store product ID
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    min_quantity: float = Field(default=0, ge=0)
    expires_at: date | None = None
    location: str | None = None  # Storage: "Réfrigérateur", "Placard", "Congélateur"
    note: str | None = None  # Preparation, cuts, piece counts (e.g. "2 pavés", "paquet ouvert")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
```

**Key Constraints & Invariants**:
- Multi-tenancy: `user_id` foreign key is indexed and required for tenant isolation (Constitution Principle I).
- Non-negative stock: `quantity >= 0` enforced by DB schema and API logic (Constitution Principle III).
- Disambiguated Name: Incompatible food states must be separated in `name` (e.g. `Saumon frais` vs `Saumon fumé`).

---

### 1.2 `RecipeIngredient` (SQLModel Entity)

Represents an ingredient required by a recipe.

```python
class RecipeIngredient(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    name: str  # Canonical base ingredient with culinary nature (e.g. "Saumon frais")
    quantity: float = Field(ge=0)
    unit: str  # Standardized metric unit ("g", "kg", "ml", "cl", "l") or natural piece ("item")
    note: str | None = None  # Cuts, preparations, or piece counts (e.g. "2 pavés de 150 g", "émincé")
    category: str | None = None
    cache_id: int | None = Field(default=None, foreign_key="supermarketsearchcache.id")
    external_id: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    price_text: str | None = None
    store_label: str | None = None
    sort_order: int = 0
```

**Key Constraints & Invariants**:
- Physical Measurability: Meats, fish, liquids, pasta, grains, and bulk items MUST use metric units (`g`, `kg`, `ml`, `cl`, `l`).
- Unit `item` is reserved exclusively for naturally whole piece items (eggs, avocados, lemons, onions).
- Prohibited Units: Cut nouns ("pavés", "morceaux", "tranches", "gousses") are banned in `unit` and relocated to `note`.

---

### 1.3 `OpenFoodFactsCache` (SQLModel Entity)

Local persistent cache for Open Food Facts lookups to prevent redundant external API hits.

```python
class OpenFoodFactsCache(SQLModel, table=True):
    barcode: str = Field(primary_key=True, max_length=64)
    raw_payload: dict = Field(sa_column=Column(JSON))
    product_name: str | None = None
    brand: str | None = None
    quantity_text: str | None = None
    categories: str | None = None
    image_url: str | None = None
    nutriscore: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
```

---

### 1.4 Ephemeral Pydantic Schemas (API Contracts)

#### `OpenFoodFactsProductDraft`
Data structure returned by `GET /api/v1/pantry/barcode/{barcode}`:

```python
class OpenFoodFactsProductDraft(BaseModel):
    barcode: str
    found: bool
    raw_name: str | None = None
    brand: str | None = None
    suggested_name: str  # Cleaned culinary-specific name (e.g. "Pâtes penne")
    quantity: float = 1.0
    unit: str = "item"  # Standard unit ("g", "kg", "ml", "cl", "l", "item")
    category: str | None = None  # e.g. "Épicerie"
    image_url: str | None = None
    nutriscore: str | None = None
    packaging: str | None = None
    location: str = "Placard"  # Suggested default based on category
    missing_fields: list[str] = Field(default_factory=list)  # e.g. ["expires_at"]
```

#### `PantryItemUpdate` (Enhanced)
Payload for `PATCH /api/v1/pantry/items/{id}`:

```python
class PantryItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = None
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    min_quantity: float | None = Field(default=None, ge=0)
    expires_at: date | None = None
    location: str | None = None
    note: str | None = None
```

---

## 2. Unit Vocabulary & Normalization Matrix

| Input Name & Unit | Normalized Name | Normalized Unit | Normalized Note | Category |
|-------------------|-----------------|-----------------|-----------------|----------|
| "Saumon", qty: 2, unit: "pavés" | "Saumon frais" | "g" (or "item") | "2 pavés" | "Poisson" |
| "Saumon (pavés)", qty: 250, unit: "g" | "Saumon frais" | "g" | "pavé" | "Poisson" |
| "Pâtes Carrefour Extra Penne 500g" | "Pâtes penne" | "g" (qty: 500) | Brand: "Carrefour Extra" | "Épicerie" |
| "Avocat Hass", qty: 2, unit: "pièces" | "Avocat" | "item" | "Hass" | "Fruits" |
| "Lait demi-écrémé 1L" | "Lait demi-écrémé" | "l" (qty: 1) | Brand: extracted | "Produits_laitiers" |

---

## 3. State Transitions & Lifecycle

```
[ Barcode Scanned / Typed ]
           │
           ▼
[ OpenFoodFacts Service ]
    ├── Found ────► [ Cleaned Draft Generated ] ──► [ User Review & Edit Sheet ]
    │                                                        │ (User validates / completes)
    └── Not Found ──────────────────────────────────────────►│
                                                             ▼
                                                    [ POST /pantry/items ]
                                                             │
                                                             ▼
                                                    [ PantryItem Created ]
                                                             │
                              ┌──────────────────────────────┴──────────────────────────────┐
                              ▼                                                             ▼
                    [ User Direct Edit ]                                         [ Cook Confirmation ]
               (PATCH /pantry/items/{id})                                     (POST /recipes/{id}/confirm-cooked)
                 - Direct numeric qty input                                    - Matches canonical name ("Saumon frais")
                 - Update dates, notes, units                                  - Decrements exact grams (no negative stock)
```
