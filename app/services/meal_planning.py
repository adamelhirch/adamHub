from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    GroceryItem,
    MealPlan,
    MealPlanCookConfirmation,
    MealSlot,
    Recipe,
)
from app.schemas import MealPlanRead, MissingIngredientRead
from app.services.cook import RECIPE_CONFIRM_MARKER, compute_recipe_missing_ingredients
from app.services.store_fields import resolve_store_fields
from app.services.units import normalize_name


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
    Reads through visible_meal_plans, which keeps recipe.confirm_cooked marker rows
    (internal records of a past cook, not scheduled meals) out of the check.
    """
    for plan in visible_meal_plans(
        session,
        user_id=user_id,
        planned_for=planned_for,
        slot=slot,
    ):
        if plan.id != exclude_plan_id:
            raise ValueError("Vous avez déjà un repas planifié pour ce créneau")


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
        indexed[(normalize_name(item.name), (item.unit or "item").strip().lower())] = item

    added = 0
    now = datetime.now(timezone.utc)
    for ing in missing:
        key = (normalize_name(ing.name), (ing.unit or "item").strip().lower())
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


def _exclude_recipe_confirm_marker_plans(statement):
    """Filter recipe.confirm_cooked carrier plans out of a MealPlan select.

    Marker rows only exist to carry a MealPlanCookConfirmation for recipe-level
    confirmations; they must never surface in meal-plan listings or calendar
    projections. ``MealPlan.note`` is nullable, so NULL notes are kept explicitly
    (a plain ``note != marker`` comparison would silently drop them).

    The marker constant is owned by cook.py — the module that creates those rows —
    and imported here so the read side never re-defines the cook contract.
    """
    return statement.where(
        or_(MealPlan.note.is_(None), MealPlan.note != RECIPE_CONFIRM_MARKER)
    )


def visible_meal_plans(
    session: Session,
    *,
    user_id: int | None = None,
    planned_for: date | None = None,
    slot: MealSlot | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
) -> list[MealPlan]:
    """The one safe way to read MealPlan rows for display or calendar projection.

    Owns the recipe.confirm_cooked marker exclusion: ad-hoc MealPlan rows that only
    carry a recipe-level cook confirmation are internal bookkeeping and must never
    surface in meal-plan listings or calendar feeds. Callers pass their filters and
    get back only rows that are safe to show — the marker never needs mentioning.
    ``date_from``/``date_to`` bound ``planned_at`` (UTC day edges).
    """
    statement = _exclude_recipe_confirm_marker_plans(select(MealPlan))
    if user_id is not None:
        statement = statement.where(MealPlan.user_id == user_id)
    if planned_for is not None:
        statement = statement.where(MealPlan.planned_for == planned_for)
    if slot is not None:
        statement = statement.where(MealPlan.slot == slot)
    if date_from is not None:
        statement = statement.where(
            MealPlan.planned_at >= datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
        )
    if date_to is not None:
        statement = statement.where(
            MealPlan.planned_at <= datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)
        )
    statement = statement.order_by(MealPlan.planned_at.asc())
    if limit is not None:
        statement = statement.limit(limit)
    return session.exec(statement).all()


def resolve_recipe_ingredient_fields(session: Session, ingredient_in) -> dict:
    """Return the fields to persist on a RecipeIngredient for validated input.

    Store metadata is never taken from the client: it is resolved server-side
    from the SupermarketSearchCache row referenced by ``cache_id`` (the same
    mechanism used by create_or_replace_mapping). Client-supplied store fields
    are ignored.
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

    resolved = resolve_store_fields(session, cache_id)
    fields.update(
        {
            "store": resolved["store"],
            "store_label": resolved["store_label"],
            "external_id": resolved["external_id"],
            "category": resolved["category"] or fields["category"],
            "packaging": resolved["packaging"],
            "price_text": resolved["price_text"],
            "product_url": resolved["product_url"],
            "image_url": resolved["image_url"],
        }
    )
    return fields
