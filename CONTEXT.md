# AdamHUB

AdamHUB is a personal life-management backend (FastAPI + SQLModel) that keeps daily planning, groceries, pantry, recipes, fitness, finances, and AI orchestration in one system. It is being pivoted into a narrow SaaS whose MVP scope covers only Recipes, Meal-plans, Groceries, Pantry, and Supermarket connections; the remaining domains stay in the same codebase for the owner's personal use.

## Language

### Meal planning

**Recipe**:
A named, authored set of ingredients and preparation steps for a dish, optionally carrying source metadata from an imported URL and optionally store-backed ingredients.
_Avoid_: Dish, course, meal

**RecipeIngredient**:
A line item of a recipe — a name, quantity and unit — that may be backed by a supermarket product so it can be bought from a store.
_Avoid_: Recipe component, ingredient line, grocery line

**MealSlot**:
One of the three time-of-day slots a meal can be planned into: breakfast, lunch, dinner.
_Avoid_: Meal time, meal type, meal category

**MealPlan**:
A scheduled occurrence of a recipe on a day and slot, with an optional servings override and optional auto-add of missing ingredients to the grocery list.
_Avoid_: Meal booking, planned meal, dinner plan

**Cook confirmation**:
The record that a meal plan (or a recipe cooked without a plan) was actually cooked; it is what triggers pantry consumption and it can be undone via unconfirmation.
_Avoid_: Cook log, meal completion, mark-as-done

**Missing ingredient**:
A recipe ingredient whose required quantity, after servings scaling, exceeds what the pantry currently holds; these are the items a meal plan can auto-add to the grocery list.
_Avoid_: Shortage, out-of-stock item, deficit

### Groceries & pantry

**GroceryItem**:
A line on the shopping list with a quantity and unit; it may be store-backed, and checking it can restock the pantry.
_Avoid_: Shopping item, cart item, list entry

**PantryItem**:
A stock item kept at home, tracked with a current quantity, an optional reorder threshold, and an expiry date; stock only moves through explicit actions, checked groceries, or confirmed cooked meals.
_Avoid_: Stock item, inventory item, larder item

**Checked**:
The state of a grocery item meaning "bought and brought home"; its false→true transition restocks a matching pantry item, and unchecking reverses that restock.
_Avoid_: Bought, purchased, done

**Restock**:
The act of adding a checked grocery item's quantity into a matching pantry item; it happens exactly once per check and is reversed on uncheck.
_Avoid_: Sync, transfer, top-up

**GroceryPantrySync**:
The link row that records which pantry item a checked grocery item restocked and by how much, so unchecking can reverse the restock.
_Avoid_: Restock record, sync entry

### Supermarket connections

**SupermarketStore**:
A supported online grocery retailer (Intermarché, Uber Eats, Carrefour) with defined capabilities: search, product mapping, and cart automation.
_Avoid_: Retailer, supermarket brand, vendor

**SupermarketConnection**:
A user-owned set of cookies for one store, encrypted at rest; multiple can coexist per store (e.g. user + spouse), and the one flagged active is the default source the store's scrapers use.
_Avoid_: Session, login, credential

**SupermarketSearchCache**:
A cached product row returned by a store search; it is the only trusted source of store metadata, and other records reference it by id instead of trusting client-supplied store fields.
_Avoid_: Search result, product cache, lookup

**UbereatsAddress**:
A saved delivery address (with geocoded coordinates and a place reference) usable when scraping or ordering through Uber Eats; only one can be active at a time.
_Avoid_: Delivery address, saved location

**Store-backed**:
Describes a grocery, pantry or recipe-ingredient record whose store metadata (identifiers, label, price, product link) was resolved from a SupermarketSearchCache row rather than supplied by a client.
_Avoid_: Store-linked, supermarket-backed, mapped product

**SupermarketMapping**:
The durable link between a recipe ingredient or pantry item and a specific store product, carrying a snapshot of the product's attributes; a new mapping deactivates the previous one.
_Avoid_: Product link, store mapping, product assignment

**SupermarketStoreSelection**:
The chosen physical store location for a store (for example, a specific Uber Eats store) that store searches target.
_Avoid_: Selected store, store location

### Auth & tenancy

**Acting user**:
The user a multi-tenant request is scoped to: a signed-in SaaS user authenticates as themself, while the personal frontend authenticates as the Owner through a shared secret instead of a login.
_Avoid_: Current user, requester, caller

**Owner**:
The single account the personal frontend always acts as; it is not a superuser role, just the one Tenant that pre-dates the SaaS pivot.
_Avoid_: Admin, superuser, master account

**Tenant**:
A user's isolated data scope: every domain record belongs to exactly one tenant, so one tenant's records are invisible (not merely forbidden) to another. Rows created before tenancy existed belong to no tenant until an explicit one-off migration assigns them to the Owner.
_Avoid_: Account, organization, workspace
