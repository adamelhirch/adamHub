from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import (
    GroceryItem,
    MealPlan,
    MealPlanCookConfirmation,
    PantryItem,
    Recipe,
    RecipeIngredient,
)
from app.schemas import MealPlanRead, MissingIngredientRead

_UNIT_BASE: dict[str, tuple[str, float]] = {
    "kg": ("g", 1000.0),
    "g": ("g", 1.0),
    "l": ("ml", 1000.0),
    "ml": ("ml", 1.0),
}


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _to_base(quantity: float, unit: str) -> tuple[float, str]:
    normalized_unit = unit.strip().lower() if unit else "item"
    base = _UNIT_BASE.get(normalized_unit)
    if not base:
        return quantity, normalized_unit
    base_unit, factor = base
    return quantity * factor, base_unit


def _unit_meta(unit: str) -> tuple[str, float]:
    normalized_unit = unit.strip().lower() if unit else "item"
    base = _UNIT_BASE.get(normalized_unit)
    if not base:
        return normalized_unit, 1.0
    base_unit, factor = base
    return base_unit, factor


def _from_base(quantity: float, unit: str) -> float:
    _, factor = _unit_meta(unit)
    if factor == 0:
        return quantity
    return quantity / factor


def _scaled_recipe_ingredients(
    session: Session,
    recipe: Recipe,
    servings_override: int | None = None,
) -> list[tuple[RecipeIngredient, float, float, str]]:
    ingredients = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
    ).all()

    ratio = 1.0
    if servings_override and recipe.servings > 0:
        ratio = servings_override / recipe.servings

    scaled: list[tuple[RecipeIngredient, float, float, str]] = []
    for ingredient in ingredients:
        needed_qty_raw = (ingredient.quantity or 0.0) * ratio
        needed_qty_base, base_unit = _to_base(needed_qty_raw, ingredient.unit or "item")
        scaled.append((ingredient, needed_qty_raw, needed_qty_base, base_unit))
    return scaled


def compute_recipe_missing_ingredients(
    session: Session,
    recipe: Recipe,
    servings_override: int | None = None,
) -> list[MissingIngredientRead]:
    pantry = session.exec(select(PantryItem)).all()
    pantry_stock: dict[tuple[str, str], float] = {}
    for item in pantry:
        key_name = _normalize_name(item.name)
        qty, base_unit = _to_base(item.quantity or 0.0, item.unit or "item")
        key = (key_name, base_unit)
        pantry_stock[key] = pantry_stock.get(key, 0.0) + qty

    missing: list[MissingIngredientRead] = []
    for ingredient, needed_qty_raw, needed_qty, base_unit in _scaled_recipe_ingredients(
        session, recipe, servings_override
    ):
        key = (_normalize_name(ingredient.name), base_unit)
        available = pantry_stock.get(key, 0.0)

        if available + 1e-9 < needed_qty:
            missing.append(
                MissingIngredientRead(
                    name=ingredient.name,
                    needed_quantity=round(needed_qty_raw, 3),
                    available_quantity=round(available, 3),
                    missing_quantity=round(needed_qty - available, 3),
                    unit=base_unit,
                    store=ingredient.store,
                    store_label=ingredient.store_label,
                    external_id=ingredient.external_id,
                    category=ingredient.category,
                    packaging=ingredient.packaging,
                    price_text=ingredient.price_text,
                    product_url=ingredient.product_url,
                    image_url=ingredient.image_url,
                )
            )

    return missing


def add_missing_to_grocery(
    session: Session,
    missing: list[MissingIngredientRead],
    note_prefix: str | None = None,
) -> int:
    if not missing:
        return 0

    existing_unchecked = session.exec(select(GroceryItem).where(GroceryItem.checked == False)).all()  # noqa: E712
    indexed: dict[tuple[str, str], GroceryItem] = {}
    for item in existing_unchecked:
        indexed[(_normalize_name(item.name), (item.unit or "item").strip().lower())] = item

    added = 0
    now = datetime.now(timezone.utc)
    for ing in missing:
        key = (_normalize_name(ing.name), (ing.unit or "item").strip().lower())
        current = indexed.get(key)
        if current:
            current.quantity = round((current.quantity or 0.0) + (ing.missing_quantity or 0.0), 3)
            if note_prefix:
                base_note = current.note or ""
                marker = f"{note_prefix}: {ing.name}"
                if marker not in base_note:
                    current.note = f"{base_note}\n{marker}".strip()
            current.updated_at = now
            session.add(current)
            continue

        created = GroceryItem(
            name=ing.name,
            quantity=max(0.0, ing.missing_quantity),
            unit=ing.unit,
            category=ing.category or "meal-plan",
            image_url=ing.image_url,
            store_label=ing.store_label,
            external_id=ing.external_id,
            packaging=ing.packaging,
            price_text=ing.price_text,
            product_url=ing.product_url,
            checked=False,
            priority=2,
            note=f"{note_prefix}: {ing.name}" if note_prefix else None,
        )
        session.add(created)
        indexed[key] = created
        added += 1

    session.commit()
    return added


def consume_recipe_ingredients(
    session: Session,
    recipe: Recipe,
    servings_override: int | None = None,
) -> list[dict]:
    pantry_items = session.exec(select(PantryItem)).all()
    now = datetime.now(timezone.utc)
    consumption: list[dict] = []

    for ingredient, needed_qty_raw, needed_base, base_unit in _scaled_recipe_ingredients(
        session, recipe, servings_override
    ):
        remaining = max(0.0, needed_base)
        consumed_base = 0.0
        normalized_name = _normalize_name(ingredient.name)

        matching = [
            item
            for item in pantry_items
            if _normalize_name(item.name) == normalized_name and _to_base(item.quantity or 0.0, item.unit or "item")[1] == base_unit
        ]
        matching.sort(key=lambda x: x.updated_at)

        for item in matching:
            if remaining <= 1e-9:
                break
            available_base, _ = _to_base(item.quantity or 0.0, item.unit or "item")
            if available_base <= 1e-9:
                continue

            consume_base = min(remaining, available_base)
            if consume_base <= 1e-9:
                continue

            new_available = max(0.0, available_base - consume_base)
            item.quantity = round(max(0.0, _from_base(new_available, item.unit or "item")), 3)
            item.updated_at = now
            session.add(item)

            consumed_base += consume_base
            remaining -= consume_base

        consumed_raw = _from_base(consumed_base, ingredient.unit or "item")
        missing_raw = _from_base(max(0.0, remaining), ingredient.unit or "item")
        consumption.append(
            {
                "name": ingredient.name,
                "unit": ingredient.unit or "item",
                "required_quantity": round(max(0.0, needed_qty_raw), 3),
                "consumed_quantity": round(max(0.0, consumed_raw), 3),
                "missing_quantity": round(max(0.0, missing_raw), 3),
            }
        )

    session.commit()
    return consumption


def build_meal_plan_read(session: Session, meal_plan: MealPlan) -> MealPlanRead:
    confirmation = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
    ).first()

    recipe = session.get(Recipe, meal_plan.recipe_id)
    if not recipe:
        recipe_name = "[missing recipe]"
        missing: list[MissingIngredientRead] = []
    else:
        recipe_name = recipe.name
        missing = compute_recipe_missing_ingredients(session, recipe, meal_plan.servings_override)

    return MealPlanRead(
        id=meal_plan.id,
        planned_at=meal_plan.planned_at,
        planned_for=meal_plan.planned_for,
        slot=meal_plan.slot,
        recipe_id=meal_plan.recipe_id,
        recipe_name=recipe_name,
        servings_override=meal_plan.servings_override,
        note=meal_plan.note,
        auto_add_missing_ingredients=meal_plan.auto_add_missing_ingredients,
        synced_grocery_at=meal_plan.synced_grocery_at,
        cooked=confirmation is not None,
        cooked_at=confirmation.confirmed_at if confirmation else None,
        cooked_note=confirmation.note if confirmation else None,
        missing_ingredients=missing,
        created_at=meal_plan.created_at,
        updated_at=meal_plan.updated_at,
    )


def sync_meal_plan_to_grocery(session: Session, meal_plan: MealPlan) -> tuple[int, list[MissingIngredientRead]]:
    recipe = session.get(Recipe, meal_plan.recipe_id)
    if not recipe:
        return 0, []

    missing = compute_recipe_missing_ingredients(session, recipe, meal_plan.servings_override)
    note_prefix = f"meal {meal_plan.planned_at.isoformat()}"
    added = add_missing_to_grocery(session, missing, note_prefix=note_prefix)

    meal_plan.synced_grocery_at = datetime.now(timezone.utc)
    meal_plan.updated_at = datetime.now(timezone.utc)
    session.add(meal_plan)
    session.commit()
    session.refresh(meal_plan)

    return added, missing


def confirm_meal_plan_cooked(session: Session, meal_plan: MealPlan, note: str | None = None) -> dict:
    existing = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
    ).first()
    if existing:
        return {
            "meal_plan_id": meal_plan.id,
            "already_confirmed": True,
            "confirmed_at": existing.confirmed_at,
            "note": existing.note,
            "pantry_consumption": existing.pantry_consumption or [],
        }

    recipe = session.get(Recipe, meal_plan.recipe_id)
    if not recipe:
        raise ValueError("recipe_id not found")

    now = datetime.now(timezone.utc)
    consumption = consume_recipe_ingredients(session, recipe, meal_plan.servings_override)

    confirmation = MealPlanCookConfirmation(
        meal_plan_id=meal_plan.id,
        confirmed_at=now,
        note=note,
        pantry_consumption=consumption,
    )
    session.add(confirmation)
    meal_plan.updated_at = now
    session.add(meal_plan)
    session.commit()
    session.refresh(confirmation)

    return {
        "meal_plan_id": meal_plan.id,
        "already_confirmed": False,
        "confirmed_at": confirmation.confirmed_at,
        "note": confirmation.note,
        "pantry_consumption": consumption,
    }


def unconfirm_meal_plan_cooked(session: Session, meal_plan: MealPlan) -> dict:
    confirmation = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
    ).first()
    if not confirmation:
        return {
            "meal_plan_id": meal_plan.id,
            "already_unconfirmed": True,
            "previously_confirmed_at": None,
            "note": None,
            "pantry_restore": [],
        }

    now = datetime.now(timezone.utc)
    pantry_items = session.exec(select(PantryItem)).all()
    restored: list[dict] = []
    for row in confirmation.pantry_consumption or []:
        name = str(row.get("name") or "").strip()
        unit = str(row.get("unit") or "item")
        consumed_quantity = float(row.get("consumed_quantity") or 0.0)
        if not name or consumed_quantity <= 0:
            continue

        consumed_base, base_unit = _to_base(consumed_quantity, unit)
        normalized_name = _normalize_name(name)
        matching = [
            item
            for item in pantry_items
            if _normalize_name(item.name) == normalized_name
            and _unit_meta(item.unit or "item")[0] == base_unit
        ]
        matching.sort(key=lambda x: x.updated_at, reverse=True)
        target = matching[0] if matching else None

        if target:
            restore_in_item_unit = _from_base(consumed_base, target.unit or "item")
            target.quantity = round((target.quantity or 0.0) + restore_in_item_unit, 3)
            target.updated_at = now
            session.add(target)
            restored.append(
                {
                    "name": name,
                    "unit": target.unit or "item",
                    "restored_quantity": round(max(0.0, restore_in_item_unit), 3),
                    "pantry_item_id": target.id,
                }
            )
            continue

        created = PantryItem(
            name=name,
            quantity=round(max(0.0, consumed_quantity), 3),
            unit=unit or "item",
            category="meal-plan",
            min_quantity=0,
            note=f"rollback meal #{meal_plan.id}",
            updated_at=now,
        )
        session.add(created)
        session.flush()
        pantry_items.append(created)
        restored.append(
            {
                "name": name,
                "unit": created.unit,
                "restored_quantity": round(max(0.0, consumed_quantity), 3),
                "pantry_item_id": created.id,
            }
        )

    previous_confirmed_at = confirmation.confirmed_at
    previous_note = confirmation.note
    session.delete(confirmation)
    meal_plan.updated_at = now
    session.add(meal_plan)
    session.commit()

    return {
        "meal_plan_id": meal_plan.id,
        "already_unconfirmed": False,
        "previously_confirmed_at": previous_confirmed_at,
        "note": previous_note,
        "pantry_restore": restored,
    }
