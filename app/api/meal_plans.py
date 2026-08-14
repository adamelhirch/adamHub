from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api._crud import get_owned_or_404
from app.api.deps import CurrentOrOwnerUser, SessionDep
from app.models import MealPlan, MealPlanCookConfirmation, MealSlot, Recipe
from app.schemas import (
    MealCookLogCreate,
    MealPlanConfirmCooked,
    MealPlanConfirmResult,
    MealPlanCreate,
    MealPlanRead,
    MealPlanUnconfirmResult,
    MealPlanUpdate,
)
from app.services.cook import (
    confirm_meal_plan_cooked,
    reset_meal_plan_cook_confirmation,
    unconfirm_meal_plan_cooked,
)
from app.services.meal_planning import (
    build_meal_plan_read,
    sync_meal_plan_to_grocery,
    validate_meal_plan_slot_free,
    visible_meal_plans,
)

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])

_SLOT_DEFAULT_TIME: dict[MealSlot, time] = {
    MealSlot.BREAKFAST: time(hour=8, minute=0),
    MealSlot.LUNCH: time(hour=12, minute=30),
    MealSlot.DINNER: time(hour=19, minute=30),
}


def _resolve_planned_at(payload: MealPlanCreate | MealPlanUpdate, current: datetime | None = None) -> datetime:
    if getattr(payload, "planned_at", None) is not None:
        planned = payload.planned_at
    elif getattr(payload, "planned_for", None) is not None:
        slot = getattr(payload, "slot", None)
        slot_time = _SLOT_DEFAULT_TIME.get(slot, time(hour=12, minute=0))
        planned = datetime.combine(payload.planned_for, slot_time).replace(tzinfo=timezone.utc)
    elif current is not None:
        planned = current
    else:
        planned = datetime.now(timezone.utc)

    if planned.tzinfo is None:
        planned = planned.replace(tzinfo=timezone.utc)
    return planned.astimezone(timezone.utc)


def _get_owned_recipe(session, recipe_id: int, user_id: int) -> Recipe:
    return get_owned_or_404(session, Recipe, recipe_id, user_id=user_id, detail="Recipe not found")


@router.post("", response_model=MealPlanRead)
def create_meal_plan(
    payload: MealPlanCreate, session: SessionDep, user: CurrentOrOwnerUser
) -> MealPlanRead:
    _get_owned_recipe(session, payload.recipe_id, user.id)

    planned_at = _resolve_planned_at(payload)
    planned_for = payload.planned_for or planned_at.date()
    try:
        validate_meal_plan_slot_free(
            session,
            user_id=user.id,
            planned_for=planned_for,
            slot=payload.slot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    meal_plan = MealPlan(
        **payload.model_dump(exclude={"planned_at"}), planned_at=planned_at, user_id=user.id
    )
    if meal_plan.planned_for is None:
        meal_plan.planned_for = planned_at.date()
    session.add(meal_plan)
    session.commit()
    session.refresh(meal_plan)

    if meal_plan.auto_add_missing_ingredients:
        sync_meal_plan_to_grocery(session, meal_plan, user_id=user.id)

    return build_meal_plan_read(session, meal_plan, user_id=user.id)


@router.get("", response_model=list[MealPlanRead])
def list_meal_plans(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    date_from: date | None = None,
    date_to: date | None = None,
    slot: MealSlot | None = None,
    limit: int = Query(default=100, ge=1, le=400),
) -> list[MealPlanRead]:
    rows = visible_meal_plans(
        session,
        user_id=user.id,
        date_from=date_from,
        date_to=date_to,
        slot=slot,
        limit=limit,
    )
    return [build_meal_plan_read(session, row, user_id=user.id) for row in rows]


@router.get("/{meal_plan_id}", response_model=MealPlanRead)
def get_meal_plan(
    meal_plan_id: int, session: SessionDep, user: CurrentOrOwnerUser
) -> MealPlanRead:
    meal_plan = get_owned_or_404(
        session, MealPlan, meal_plan_id, user_id=user.id, detail="Meal plan not found"
    )
    return build_meal_plan_read(session, meal_plan, user_id=user.id)


@router.patch("/{meal_plan_id}", response_model=MealPlanRead)
def update_meal_plan(
    meal_plan_id: int,
    payload: MealPlanUpdate,
    session: SessionDep,
    user: CurrentOrOwnerUser,
) -> MealPlanRead:
    meal_plan = get_owned_or_404(
        session, MealPlan, meal_plan_id, user_id=user.id, detail="Meal plan not found"
    )

    updates = payload.model_dump(exclude_unset=True)
    if "recipe_id" in updates:
        _get_owned_recipe(session, updates["recipe_id"], user.id)

    next_planned_at = _resolve_planned_at(payload, current=meal_plan.planned_at)
    next_planned_for = updates.get("planned_for", meal_plan.planned_for)
    if next_planned_for is None:
        next_planned_for = next_planned_at.date()
    next_slot = updates.get("slot", meal_plan.slot)
    try:
        validate_meal_plan_slot_free(
            session,
            user_id=user.id,
            planned_for=next_planned_for,
            slot=next_slot,
            exclude_plan_id=meal_plan.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    reset_cook_confirmation = (
        ("planned_at" in updates and updates.get("planned_at") != meal_plan.planned_at)
        or
        ("planned_for" in updates and updates.get("planned_for") != meal_plan.planned_for)
        or ("slot" in updates and updates.get("slot") != meal_plan.slot)
        or ("recipe_id" in updates and updates.get("recipe_id") != meal_plan.recipe_id)
        or ("servings_override" in updates and updates.get("servings_override") != meal_plan.servings_override)
    )

    for key, value in updates.items():
        setattr(meal_plan, key, value)
    meal_plan.planned_at = next_planned_at
    meal_plan.planned_for = next_planned_for

    if reset_cook_confirmation:
        reset_meal_plan_cook_confirmation(session, meal_plan)

    meal_plan.updated_at = datetime.now(timezone.utc)
    session.add(meal_plan)
    session.commit()
    session.refresh(meal_plan)

    return build_meal_plan_read(session, meal_plan, user_id=user.id)


@router.post("/{meal_plan_id}/sync-groceries")
def sync_meal_plan_groceries(
    meal_plan_id: int, session: SessionDep, user: CurrentOrOwnerUser
) -> dict:
    meal_plan = get_owned_or_404(
        session, MealPlan, meal_plan_id, user_id=user.id, detail="Meal plan not found"
    )

    added, missing = sync_meal_plan_to_grocery(session, meal_plan, user_id=user.id)
    return {
        "meal_plan_id": meal_plan_id,
        "created_grocery_items": added,
        "missing_ingredients": [item.model_dump(mode="json") for item in missing],
    }


@router.post("/{meal_plan_id}/confirm-cooked", response_model=MealPlanConfirmResult)
def confirm_cooked_meal_plan(
    meal_plan_id: int,
    session: SessionDep,
    user: CurrentOrOwnerUser,
    payload: MealPlanConfirmCooked | None = None,
) -> MealPlanConfirmResult:
    meal_plan = get_owned_or_404(
        session, MealPlan, meal_plan_id, user_id=user.id, detail="Meal plan not found"
    )

    result = confirm_meal_plan_cooked(
        session, meal_plan, note=payload.note if payload else None, user_id=user.id
    )
    return MealPlanConfirmResult.model_validate(result)


@router.post("/{meal_plan_id}/unconfirm-cooked", response_model=MealPlanUnconfirmResult)
def unconfirm_cooked_meal_plan(
    meal_plan_id: int,
    session: SessionDep,
    user: CurrentOrOwnerUser,
) -> MealPlanUnconfirmResult:
    meal_plan = get_owned_or_404(
        session, MealPlan, meal_plan_id, user_id=user.id, detail="Meal plan not found"
    )

    result = unconfirm_meal_plan_cooked(session, meal_plan, user_id=user.id)
    return MealPlanUnconfirmResult.model_validate(result)


@router.post("/actions/log-cooked", response_model=MealPlanConfirmResult)
def log_cooked_without_plan(
    payload: MealCookLogCreate, session: SessionDep, user: CurrentOrOwnerUser
) -> MealPlanConfirmResult:
    _get_owned_recipe(session, payload.recipe_id, user.id)

    cooked_at = payload.cooked_at or datetime.now(timezone.utc)
    if cooked_at.tzinfo is None:
        cooked_at = cooked_at.replace(tzinfo=timezone.utc)
    cooked_at = cooked_at.astimezone(timezone.utc)

    meal_plan = MealPlan(
        planned_at=cooked_at,
        planned_for=cooked_at.date(),
        recipe_id=payload.recipe_id,
        servings_override=payload.servings_override,
        note=payload.note or "cooked without explicit planning",
        auto_add_missing_ingredients=False,
        user_id=user.id,
    )
    session.add(meal_plan)
    session.commit()
    session.refresh(meal_plan)

    result = confirm_meal_plan_cooked(session, meal_plan, note=payload.note, user_id=user.id)
    return MealPlanConfirmResult.model_validate(result)


@router.delete("/{meal_plan_id}")
def delete_meal_plan(meal_plan_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> dict:
    meal_plan = get_owned_or_404(
        session, MealPlan, meal_plan_id, user_id=user.id, detail="Meal plan not found"
    )

    confirmation = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
    ).first()
    if confirmation:
        session.delete(confirmation)
        session.commit()

    session.delete(meal_plan)
    session.commit()
    return {"ok": True, "deleted_id": meal_plan_id}
