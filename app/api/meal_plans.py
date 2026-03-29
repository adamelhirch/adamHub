from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import CalendarSource, MealPlan, MealPlanCookConfirmation, MealSlot, Recipe
from app.schemas import (
    MealCookLogCreate,
    MealPlanConfirmCooked,
    MealPlanConfirmResult,
    MealPlanCreate,
    MealPlanRead,
    MealPlanUnconfirmResult,
    MealPlanUpdate,
)
from app.services.meal_planning import (
    build_meal_plan_read,
    confirm_meal_plan_cooked,
    sync_meal_plan_to_grocery,
    unconfirm_meal_plan_cooked,
)
from app.services.calendar_hub import validate_calendar_slot_free

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"], dependencies=[Depends(require_api_key)])

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


@router.post("", response_model=MealPlanRead)
def create_meal_plan(payload: MealPlanCreate, session: SessionDep) -> MealPlanRead:
    recipe = session.get(Recipe, payload.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    planned_at = _resolve_planned_at(payload)
    try:
        validate_calendar_slot_free(session, planned_at, planned_at + timedelta(minutes=75), source=CalendarSource.MEAL_PLAN)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    meal_plan = MealPlan(**payload.model_dump(exclude={"planned_at"}), planned_at=planned_at)
    if meal_plan.planned_for is None:
        meal_plan.planned_for = planned_at.date()
    session.add(meal_plan)
    session.commit()
    session.refresh(meal_plan)

    if meal_plan.auto_add_missing_ingredients:
        sync_meal_plan_to_grocery(session, meal_plan)

    return build_meal_plan_read(session, meal_plan)


@router.get("", response_model=list[MealPlanRead])
def list_meal_plans(
    session: SessionDep,
    date_from: date | None = None,
    date_to: date | None = None,
    slot: MealSlot | None = None,
    limit: int = Query(default=100, ge=1, le=400),
) -> list[MealPlanRead]:
    statement = select(MealPlan).order_by(MealPlan.planned_at.asc()).limit(limit)
    if date_from is not None:
        statement = statement.where(MealPlan.planned_at >= datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc))
    if date_to is not None:
        statement = statement.where(MealPlan.planned_at <= datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc))
    if slot is not None:
        statement = statement.where(MealPlan.slot == slot)

    rows = session.exec(statement).all()
    return [build_meal_plan_read(session, row) for row in rows]


@router.get("/{meal_plan_id}", response_model=MealPlanRead)
def get_meal_plan(meal_plan_id: int, session: SessionDep) -> MealPlanRead:
    meal_plan = session.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    return build_meal_plan_read(session, meal_plan)


@router.patch("/{meal_plan_id}", response_model=MealPlanRead)
def update_meal_plan(meal_plan_id: int, payload: MealPlanUpdate, session: SessionDep) -> MealPlanRead:
    meal_plan = session.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    updates = payload.model_dump(exclude_unset=True)
    if "recipe_id" in updates:
        recipe = session.get(Recipe, updates["recipe_id"])
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

    preview_payload = payload.model_copy(update=updates)
    next_planned_at = _resolve_planned_at(preview_payload, current=meal_plan.planned_at)
    try:
        validate_calendar_slot_free(
            session,
            next_planned_at,
            next_planned_at + timedelta(minutes=75),
            source=CalendarSource.MEAL_PLAN,
            source_ref_id=meal_plan.id,
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
    meal_plan.planned_at = _resolve_planned_at(payload, current=meal_plan.planned_at)
    if meal_plan.planned_for is None:
        meal_plan.planned_for = meal_plan.planned_at.date()

    if reset_cook_confirmation:
        confirmation = session.exec(
            select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
        ).first()
        if confirmation:
            session.delete(confirmation)

    meal_plan.updated_at = datetime.now(timezone.utc)
    session.add(meal_plan)
    session.commit()
    session.refresh(meal_plan)

    return build_meal_plan_read(session, meal_plan)


@router.post("/{meal_plan_id}/sync-groceries")
def sync_meal_plan_groceries(meal_plan_id: int, session: SessionDep) -> dict:
    meal_plan = session.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    added, missing = sync_meal_plan_to_grocery(session, meal_plan)
    return {
        "meal_plan_id": meal_plan_id,
        "created_grocery_items": added,
        "missing_ingredients": [item.model_dump(mode="json") for item in missing],
    }


@router.post("/{meal_plan_id}/confirm-cooked", response_model=MealPlanConfirmResult)
def confirm_cooked_meal_plan(
    meal_plan_id: int,
    session: SessionDep,
    payload: MealPlanConfirmCooked | None = None,
) -> MealPlanConfirmResult:
    meal_plan = session.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    result = confirm_meal_plan_cooked(session, meal_plan, note=payload.note if payload else None)
    return MealPlanConfirmResult.model_validate(result)


@router.post("/{meal_plan_id}/unconfirm-cooked", response_model=MealPlanUnconfirmResult)
def unconfirm_cooked_meal_plan(
    meal_plan_id: int,
    session: SessionDep,
) -> MealPlanUnconfirmResult:
    meal_plan = session.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    result = unconfirm_meal_plan_cooked(session, meal_plan)
    return MealPlanUnconfirmResult.model_validate(result)


@router.post("/actions/log-cooked", response_model=MealPlanConfirmResult)
def log_cooked_without_plan(payload: MealCookLogCreate, session: SessionDep) -> MealPlanConfirmResult:
    recipe = session.get(Recipe, payload.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

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
    )
    session.add(meal_plan)
    session.commit()
    session.refresh(meal_plan)

    result = confirm_meal_plan_cooked(session, meal_plan, note=payload.note)
    return MealPlanConfirmResult.model_validate(result)


@router.delete("/{meal_plan_id}")
def delete_meal_plan(meal_plan_id: int, session: SessionDep) -> dict:
    meal_plan = session.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    confirmation = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
    ).first()
    if confirmation:
        session.delete(confirmation)
        session.commit()

    session.delete(meal_plan)
    session.commit()
    return {"ok": True, "deleted_id": meal_plan_id}
