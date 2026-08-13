from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    GroceryItem,
    MealPlan,
    MealPlanCookConfirmation,
    MealSlot,
    PantryItem,
    Recipe,
    RecipeIngredient,
    SupermarketSearchCache,
)
from app.schemas import MealPlanRead, MissingIngredientRead
from app.services.supermarket_registry import get_store_definition

_UNIT_BASE: dict[str, tuple[str, float]] = {
    "kg": ("g", 1000.0),
    "g": ("g", 1.0),
    "l": ("ml", 1000.0),
    "ml": ("ml", 1.0),
}


@dataclass
class ConsumptionResult:
    """Outcome of consuming a recipe's ingredients from the pantry.

    summary: per-ingredient aggregates (name/unit/required/consumed/missing).
    lots: per-pantry-item consumption records used to reverse stock exactly on unconfirm.
    """

    summary: list[dict] = field(default_factory=list)
    lots: list[dict] = field(default_factory=list)


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


def validate_meal_plan_slot_free(
    session: Session,
    *,
    user_id: int,
    planned_for: date,
    slot: MealSlot | None,
    exclude_plan_id: int | None = None,
) -> None:
    """Reject a meal plan only if the SAME user already plans a meal for the slot.

    This replaces the generic cross-domain calendar overlap check for meal plans:
    planning lunch must not be blocked by an unrelated task/event at the same hour.
    Recipe.confirm_cooked marker plans are excluded — they are internal records of
    a past cook, not scheduled meals.
    """
    statement = (
        exclude_recipe_confirm_marker_plans(select(MealPlan))
        .where(
            MealPlan.user_id == user_id,
            MealPlan.planned_for == planned_for,
            MealPlan.slot == slot,
        )
    )
    if exclude_plan_id is not None:
        statement = statement.where(MealPlan.id != exclude_plan_id)
    existing = session.exec(statement).first()
    if existing is not None:
        raise ValueError("Vous avez déjà un repas planifié pour ce créneau")


def compute_recipe_missing_ingredients(
    session: Session,
    recipe: Recipe,
    servings_override: int | None = None,
    *,
    user_id: int | None = None,
) -> list[MissingIngredientRead]:
    statement = select(PantryItem)
    if user_id is not None:
        statement = statement.where(PantryItem.user_id == user_id)
    pantry = session.exec(statement).all()
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
    *,
    user_id: int | None = None,
) -> int:
    if not missing:
        return 0

    existing_statement = select(GroceryItem).where(GroceryItem.checked == False)  # noqa: E712
    if user_id is not None:
        existing_statement = existing_statement.where(GroceryItem.user_id == user_id)
    existing_unchecked = session.exec(existing_statement).all()
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
            user_id=user_id,
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
    *,
    user_id: int | None = None,
) -> ConsumptionResult:
    statement = select(PantryItem)
    if user_id is not None:
        statement = statement.where(PantryItem.user_id == user_id)
    pantry_items = session.exec(statement).all()
    now = datetime.now(timezone.utc)
    summary: list[dict] = []
    lots: list[dict] = []

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
            lots.append(
                {
                    "name": ingredient.name,
                    "unit": ingredient.unit or "item",
                    "pantry_item_id": item.id,
                    "consumed_quantity": round(max(0.0, _from_base(consume_base, ingredient.unit or "item")), 3),
                }
            )

        consumed_raw = _from_base(consumed_base, ingredient.unit or "item")
        missing_raw = _from_base(max(0.0, remaining), ingredient.unit or "item")
        summary.append(
            {
                "name": ingredient.name,
                "unit": ingredient.unit or "item",
                "required_quantity": round(max(0.0, needed_qty_raw), 3),
                "consumed_quantity": round(max(0.0, consumed_raw), 3),
                "missing_quantity": round(max(0.0, missing_raw), 3),
            }
        )

    session.commit()
    return ConsumptionResult(summary=summary, lots=lots)


def build_meal_plan_read(
    session: Session,
    meal_plan: MealPlan,
    *,
    user_id: int | None = None,
) -> MealPlanRead:
    confirmation = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
    ).first()

    recipe = session.get(Recipe, meal_plan.recipe_id)
    if not recipe:
        recipe_name = "[missing recipe]"
        missing: list[MissingIngredientRead] = []
    else:
        recipe_name = recipe.name
        missing = compute_recipe_missing_ingredients(
            session, recipe, meal_plan.servings_override, user_id=user_id
        )

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


def sync_meal_plan_to_grocery(
    session: Session,
    meal_plan: MealPlan,
    *,
    user_id: int | None = None,
) -> tuple[int, list[MissingIngredientRead]]:
    recipe = session.get(Recipe, meal_plan.recipe_id)
    if not recipe:
        return 0, []

    missing = compute_recipe_missing_ingredients(
        session, recipe, meal_plan.servings_override, user_id=user_id
    )
    note_prefix = f"meal {meal_plan.planned_at.isoformat()}"
    added = add_missing_to_grocery(session, missing, note_prefix=note_prefix, user_id=user_id)

    meal_plan.synced_grocery_at = datetime.now(timezone.utc)
    meal_plan.updated_at = datetime.now(timezone.utc)
    session.add(meal_plan)
    session.commit()
    session.refresh(meal_plan)

    return added, missing


def confirm_meal_plan_cooked(
    session: Session,
    meal_plan: MealPlan,
    note: str | None = None,
    *,
    user_id: int | None = None,
) -> dict:
    existing = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
    ).first()
    if existing:
        stored = existing.pantry_consumption or []
        summary = stored.get("summary") if isinstance(stored, dict) else stored
        return {
            "meal_plan_id": meal_plan.id,
            "already_confirmed": True,
            "confirmed_at": existing.confirmed_at,
            "note": existing.note,
            "pantry_consumption": summary or [],
        }

    recipe = session.get(Recipe, meal_plan.recipe_id)
    if not recipe:
        raise ValueError("recipe_id not found")

    now = datetime.now(timezone.utc)
    consumption = consume_recipe_ingredients(
        session, recipe, meal_plan.servings_override, user_id=user_id
    )

    confirmation = MealPlanCookConfirmation(
        meal_plan_id=meal_plan.id,
        confirmed_at=now,
        note=note,
        pantry_consumption={"summary": consumption.summary, "lots": consumption.lots},
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
        "pantry_consumption": consumption.summary,
    }


def _restore_consumption_lot(
    session: Session,
    pantry_items: list[PantryItem],
    row: dict,
    meal_plan_id: int,
    now: datetime,
    *,
    user_id: int | None = None,
) -> dict | None:
    """Restore one consumption lot back into the exact pantry row that was consumed.

    Falls back to a name/unit heuristic (and finally to creating a fresh pantry row)
    for legacy confirmation records that predate per-lot tracking.
    """
    name = str(row.get("name") or "").strip()
    unit = str(row.get("unit") or "item")
    consumed_quantity = float(row.get("consumed_quantity") or 0.0)
    if not name or consumed_quantity <= 0:
        return None

    target: PantryItem | None = None
    pantry_item_id = row.get("pantry_item_id")
    if pantry_item_id is not None:
        target = next((item for item in pantry_items if item.id == pantry_item_id), None)

    if target is None:
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
        restore_in_item_unit = _from_base(_to_base(consumed_quantity, unit)[0], target.unit or "item")
        target.quantity = round((target.quantity or 0.0) + restore_in_item_unit, 3)
        target.updated_at = now
        session.add(target)
        return {
            "name": name,
            "unit": target.unit or "item",
            "restored_quantity": round(max(0.0, restore_in_item_unit), 3),
            "pantry_item_id": target.id,
        }

    created = PantryItem(
        name=name,
        quantity=round(max(0.0, consumed_quantity), 3),
        unit=unit or "item",
        category="meal-plan",
        min_quantity=0,
        note=f"rollback meal #{meal_plan_id}",
        updated_at=now,
        user_id=user_id,
    )
    session.add(created)
    session.flush()
    pantry_items.append(created)
    return {
        "name": name,
        "unit": created.unit,
        "restored_quantity": round(max(0.0, consumed_quantity), 3),
        "pantry_item_id": created.id,
    }


def unconfirm_meal_plan_cooked(
    session: Session,
    meal_plan: MealPlan,
    *,
    user_id: int | None = None,
) -> dict:
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
    statement = select(PantryItem)
    if user_id is not None:
        statement = statement.where(PantryItem.user_id == user_id)
    pantry_items = session.exec(statement).all()
    stored = confirmation.pantry_consumption or []
    if isinstance(stored, dict):
        lots = stored.get("lots") or []
    else:
        lots = stored

    restored: list[dict] = []
    for row in lots:
        entry = _restore_consumption_lot(
            session, pantry_items, row, meal_plan.id, now, user_id=user_id
        )
        if entry:
            restored.append(entry)

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


def reset_meal_plan_cook_confirmation(session: Session, meal_plan: MealPlan) -> dict | None:
    """Undo a meal plan's cook confirmation (restoring pantry stock) if one exists.

    Returns the unconfirm result dict when a confirmation was present, else None.
    Used when editing a confirmed meal plan invalidates its confirmation.
    """
    confirmation = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
    ).first()
    if not confirmation:
        return None
    return unconfirm_meal_plan_cooked(session, meal_plan)


# Marker used to link a recipe-level "confirm cooked" to an ad-hoc MealPlan that
# carries the MealPlanCookConfirmation record (same record type as the meal-plan flow).
RECIPE_CONFIRM_MARKER = "recipe.confirm_cooked"


def exclude_recipe_confirm_marker_plans(statement):
    """Filter recipe.confirm_cooked carrier plans out of a MealPlan select.

    Marker rows only exist to carry a MealPlanCookConfirmation for recipe-level
    confirmations; they must never surface in meal-plan listings or calendar
    projections. ``MealPlan.note`` is nullable, so NULL notes are kept explicitly
    (a plain ``note != marker`` comparison would silently drop them).
    """
    return statement.where(
        or_(MealPlan.note.is_(None), MealPlan.note != RECIPE_CONFIRM_MARKER)
    )


def _recipe_confirmation_plan(session: Session, recipe: Recipe) -> MealPlan | None:
    return session.exec(
        select(MealPlan).where(
            MealPlan.recipe_id == recipe.id,
            MealPlan.note == RECIPE_CONFIRM_MARKER,
        )
    ).first()


def confirm_recipe_cooked(
    session: Session,
    recipe: Recipe,
    servings_override: int | None = None,
    note: str | None = None,
    *,
    user_id: int | None = None,
) -> dict:
    """Confirm a recipe cooked without an explicit meal plan.

    Mirrors the meal-plan flow by reusing MealPlanCookConfirmation: an ad-hoc
    MealPlan (note = RECIPE_CONFIRM_MARKER) carries the confirmation record, so
    confirm is idempotent and can be reversed via unconfirm_recipe_cooked.
    """
    plan = _recipe_confirmation_plan(session, recipe)
    if plan is None:
        now = datetime.now(timezone.utc)
        plan = MealPlan(
            planned_at=now,
            planned_for=now.date(),
            recipe_id=recipe.id,
            servings_override=servings_override,
            note=RECIPE_CONFIRM_MARKER,
            auto_add_missing_ingredients=False,
            user_id=user_id,
        )
        session.add(plan)
        session.commit()
        session.refresh(plan)
    else:
        # Reused from a previous confirm/unconfirm cycle: refresh its timestamp so
        # planned_at tracks the current cook rather than the very first one.
        existing = session.exec(
            select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == plan.id)
        ).first()
        if existing is None:
            now = datetime.now(timezone.utc)
            plan.planned_at = now
            plan.planned_for = now.date()
            plan.updated_at = now
            session.add(plan)
            session.commit()

    missing = compute_recipe_missing_ingredients(
        session, recipe, plan.servings_override, user_id=user_id
    )
    result = confirm_meal_plan_cooked(session, plan, note=note, user_id=user_id)
    result["recipe_id"] = recipe.id
    result["recipe_name"] = recipe.name
    result["meal_plan_id"] = plan.id
    result["missing_ingredients"] = missing
    return result


def unconfirm_recipe_cooked(
    session: Session,
    recipe: Recipe,
    *,
    user_id: int | None = None,
) -> dict:
    """Undo a recipe-level cooked confirmation and restore pantry stock."""
    plan = _recipe_confirmation_plan(session, recipe)
    if plan is None:
        return {
            "recipe_id": recipe.id,
            "recipe_name": recipe.name,
            "already_unconfirmed": True,
            "previously_confirmed_at": None,
            "note": None,
            "pantry_restore": [],
        }
    result = unconfirm_meal_plan_cooked(session, plan, user_id=user_id)
    result["recipe_id"] = recipe.id
    result["recipe_name"] = recipe.name
    return result


def resolve_recipe_ingredient_fields(session: Session, ingredient_in) -> dict:
    """Return the fields to persist on a RecipeIngredient for validated input.

    Store metadata is never taken from the client: it is resolved server-side from
    the SupermarketSearchCache row referenced by ``cache_id`` (the same mechanism
    used by create_or_replace_mapping). Client-supplied store fields are ignored.
    """
    fields: dict = {
        "name": ingredient_in.name,
        "quantity": ingredient_in.quantity,
        "unit": ingredient_in.unit,
        "note": ingredient_in.note,
        "category": ingredient_in.category,
        "store": None,
        "store_label": None,
        "external_id": None,
        "packaging": None,
        "price_text": None,
        "product_url": None,
        "image_url": None,
    }
    cache_id = getattr(ingredient_in, "cache_id", None)
    if cache_id is None:
        return fields

    cache_row = session.get(SupermarketSearchCache, cache_id)
    if cache_row is None:
        raise ValueError(f"cache_id {cache_id} does not reference a known supermarket search result")

    definition = get_store_definition(cache_row.store)
    fields.update(
        {
            "store": cache_row.store,
            "store_label": definition.label if definition else cache_row.store.value,
            "external_id": cache_row.external_id,
            "category": cache_row.category or fields["category"],
            "packaging": cache_row.packaging,
            "price_text": cache_row.price_text,
            "product_url": cache_row.product_url,
            "image_url": cache_row.image_url,
        }
    )
    return fields
