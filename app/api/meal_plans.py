from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import MealPlan, MealPlanCookConfirmation, MealSlot, Recipe
from app.schemas import (
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

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=MealPlanRead)
def create_meal_plan(payload: MealPlanCreate, session: SessionDep) -> MealPlanRead:
    recipe = session.get(Recipe, payload.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    existing = session.exec(
        select(MealPlan).where(MealPlan.planned_for == payload.planned_for, MealPlan.slot == payload.slot)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A meal is already planned for this date and slot")

    meal_plan = MealPlan(**payload.model_dump())
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
    statement = select(MealPlan).order_by(MealPlan.planned_for.asc(), MealPlan.slot.asc()).limit(limit)
    if date_from is not None:
        statement = statement.where(MealPlan.planned_for >= date_from)
    if date_to is not None:
        statement = statement.where(MealPlan.planned_for <= date_to)
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

    target_date = updates.get("planned_for", meal_plan.planned_for)
    target_slot = updates.get("slot", meal_plan.slot)
    if target_date != meal_plan.planned_for or target_slot != meal_plan.slot:
        existing = session.exec(
            select(MealPlan).where(
                MealPlan.planned_for == target_date,
                MealPlan.slot == target_slot,
                MealPlan.id != meal_plan.id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="A meal is already planned for this date and slot")

    reset_cook_confirmation = (
        ("planned_for" in updates and updates.get("planned_for") != meal_plan.planned_for)
        or ("slot" in updates and updates.get("slot") != meal_plan.slot)
        or ("recipe_id" in updates and updates.get("recipe_id") != meal_plan.recipe_id)
        or ("servings_override" in updates and updates.get("servings_override") != meal_plan.servings_override)
    )

    for key, value in updates.items():
        setattr(meal_plan, key, value)

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
