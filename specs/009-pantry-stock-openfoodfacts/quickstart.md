# Quickstart & Validation Guide: Pantry Stock & Open Food Facts Scanner

**Feature**: `009-pantry-stock-openfoodfacts`  
**Date**: 2026-09-15  
**Status**: Completed  

This guide provides runnable end-to-end verification scenarios for testing pantry stock editing, ingredient normalization, and Open Food Facts barcode integration.

---

## 1. Prerequisites & Environment Setup

Ensure the virtual environment and dependencies are ready:

```bash
# Backend checks
uv run --extra dev pytest -k "test_ingredient_normalization or test_pantry"

# Mobile frontend checks
cd app-saas && npm run typecheck && npm run lint && cd ..

# Web frontend checks
cd web && npm run build && cd ..
```

---

## 2. Validation Scenario 1: User Data Correction Script

Run the targeted database fix script to correct the user's existing recipes and pantry item:

```bash
uv run python scripts/fix_user_recipes_and_pantry_saumon.py
```

### Expected Output
- Recipe `Saumon teriyaki avec riz`: ingredient `Saumon` updated to `Saumon frais` (`300.0 g`, note: `2 pavés de 150 g`).
- Recipe `Pâtes crémeuses au saumon`: ingredient `Saumon` updated to `Saumon frais` (`250.0 g`, note: `pavé`).
- Pantry item `Saumon` (ID 7): name updated to `Saumon frais` (`250.0 g`, category `Poisson`, location `Réfrigérateur`).

Verify with Python:
```bash
uv run python -c "
from sqlmodel import select, Session
from app.core.db import engine
from app.models import Recipe, PantryItem, RecipeIngredient

with Session(engine) as session:
    p = session.exec(select(PantryItem).where(PantryItem.id == 7)).first()
    print('Pantry item:', p.name, p.quantity, p.unit, p.location)
    r = session.exec(select(Recipe).where(Recipe.name.like('%Saumon%'))).all()
    for rec in r:
        ings = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == rec.id, RecipeIngredient.name.like('%Saumon%'))).all()
        for i in ings:
            print(f'Recipe {rec.name}: {i.name} ({i.quantity} {i.unit}, note={i.note})')
"
```

---

## 3. Validation Scenario 2: Open Food Facts Barcode Lookup

Test the backend Open Food Facts integration service directly:

```bash
uv run python -c "
import asyncio
from app.services.openfoodfacts import lookup_openfoodfacts_barcode

async def test():
    # Barcode for Carrefour Extra Penne Rigate 500g
    result = await lookup_openfoodfacts_barcode('3560070557451')
    print('Lookup result:', result)
    assert result.found is True
    assert 'penne' in result.suggested_name.lower() or 'pâtes' in result.suggested_name.lower()
    assert result.quantity == 500.0
    assert result.unit == 'g'

asyncio.run(test())
"
```

Test the REST API endpoint:
```bash
curl -s http://localhost:8000/api/v1/pantry/barcode/3560070557451 | jq .
```

---

## 4. Validation Scenario 3: Direct Stock Editing (API & UI)

Update an existing pantry item's quantity, unit, and expiration date:

```bash
curl -X PATCH http://localhost:8000/api/v1/pantry/items/7 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Saumon frais",
    "quantity": 300.0,
    "unit": "g",
    "category": "Poisson",
    "location": "Réfrigérateur",
    "expires_at": "2026-09-20",
    "note": "2 pavés"
  }' | jq .
```

### Expected Outcome
Returns HTTP 200 with the modified attributes. In the mobile app (`app-saas`) and web UI (`web`), opening the pantry screen displays the item with exact quantity `300 g`, and tapping the item allows direct numeric editing without clicking +/- 50 times.

---

## 5. Validation Scenario 4: AI Guardrails & Unit Whitelist

Verify that `canonical_ingredient()` in `app/services/units.py` normalizes cuts like "pavés" into standard metric units and notes:

```bash
uv run python -c "
from app.services.units import canonical_ingredient

name, unit, note = canonical_ingredient('Saumon frais', 'pavés', '2 pièces')
print('Normalized:', name, unit, note)
assert unit == 'g' or unit == 'item'
assert 'pavé' in note.lower()
"
```

Verify that the full pytest suite passes:
```bash
uv run --extra dev pytest tests/test_ingredient_normalization.py tests/test_grocery_pantry_flow.py tests/test_openfoodfacts_pantry.py
```
