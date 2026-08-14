"""Cook confirmations: the only place pantry stock moves on a cook.

The invariant "pantry only moves on explicit cook confirmation" lives here and
only here. Every stock-decreasing write is reached through a confirm-cooked
entry point (``confirm_meal_plan_cooked`` / ``confirm_recipe_cooked``), and every
restore runs through the corresponding unconfirm entry point
(``unconfirm_meal_plan_cooked`` / ``unconfirm_recipe_cooked``).

The module is deep by construction: callers (meal_planning reads, the REST
routes, and the skill actions) cross a small interface — confirm, unconfirm,
reset, and the ``RECIPE_CONFIRM_MARKER`` — while the consumption bookkeeping
(``consume_recipe_ingredients``, ``_restore_consumption_lot``,
``_recipe_confirmation_plan``) and the scaling/missing math it shares with the
meal-planning read side stay hidden behind it.

The marker that ties a recipe-level confirm to an ad-hoc MealPlan carrier row is
owned here; ``meal_planning.visible_meal_plans`` imports it so the read side
never re-defines the cook contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import (
    MealPlan,
    MealPlanCookConfirmation,
    PantryItem,
    Recipe,
    RecipeIngredient,
)
from app.schemas import MissingIngredientRead
from app.services.units import from_base, normalize_name, to_base, unit_meta


@dataclass
class ConsumptionResult:
    """Outcome of consuming a recipe's ingredients from the pantry.

    summary: per-ingredient aggregates (name/unit/required/consumed/missing).
    lots: per-pantry-item consumption records used to reverse stock exactly on unconfirm.
    """

    summary: list[dict] = field(default_factory=list)
    lots: list[dict] = field(default_factory=list)


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
        needed_qty_base, base_unit = to_base(needed_qty_raw, ingredient.unit or "item")
        scaled.append((ingredient, needed_qty_raw, needed_qty_base, base_unit))
    return scaled


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
        key_name = normalize_name(item.name)
        qty, base_unit = to_base(item.quantity or 0.0, item.unit or "item")
        key = (key_name, base_unit)
        pantry_stock[key] = pantry_stock.get(key, 0.0) + qty

    missing: list[MissingIngredientRead] = []
    for ingredient, needed_qty_raw, needed_qty, base_unit in _scaled_recipe_ingredients(
        session, recipe, servings_override
    ):
        key = (normalize_name(ingredient.name), base_unit)
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
        normalized_name = normalize_name(ingredient.name)

        matching = [
            item
            for item in pantry_items
            if normalize_name(item.name) == normalized_name and to_base(item.quantity or 0.0, item.unit or "item")[1] == base_unit
        ]
        matching.sort(key=lambda x: x.updated_at)

        for item in matching:
            if remaining <= 1e-9:
                break
            available_base, _ = to_base(item.quantity or 0.0, item.unit or "item")
            if available_base <= 1e-9:
                continue

            consume_base = min(remaining, available_base)
            if consume_base <= 1e-9:
                continue

            new_available = max(0.0, available_base - consume_base)
            item.quantity = round(max(0.0, from_base(new_available, item.unit or "item")), 3)
            item.updated_at = now
            session.add(item)

            consumed_base += consume_base
            remaining -= consume_base
            lots.append(
                {
                    "name": ingredient.name,
                    "unit": ingredient.unit or "item",
                    "pantry_item_id": item.id,
                    "consumed_quantity": round(max(0.0, from_base(consume_base, ingredient.unit or "item")), 3),
                }
            )

        consumed_raw = from_base(consumed_base, ingredient.unit or "item")
        missing_raw = from_base(max(0.0, remaining), ingredient.unit or "item")
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
        consumed_base, base_unit = to_base(consumed_quantity, unit)
        normalized_name = normalize_name(name)
        matching = [
            item
            for item in pantry_items
            if normalize_name(item.name) == normalized_name
            and unit_meta(item.unit or "item")[0] == base_unit
        ]
        matching.sort(key=lambda x: x.updated_at, reverse=True)
        target = matching[0] if matching else None

    if target:
        restore_in_item_unit = from_base(to_base(consumed_quantity, unit)[0], target.unit or "item")
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
