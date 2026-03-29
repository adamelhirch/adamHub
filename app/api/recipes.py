from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import MealPlan, MealPlanCookConfirmation, Recipe, RecipeIngredient
from app.schemas import RecipeCookRequest, RecipeCookResult, RecipeCreate, RecipeRead, RecipeUpdate
from app.services.calendar_hub import sync_generated_calendar_items
from app.services.life import build_recipe_read
from app.services.meal_planning import compute_recipe_missing_ingredients, consume_recipe_ingredients

router = APIRouter(prefix="/recipes", tags=["recipes"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=RecipeRead)
def create_recipe(payload: RecipeCreate, session: SessionDep) -> RecipeRead:
    recipe = Recipe(
        name=payload.name,
        description=payload.description,
        instructions=payload.instructions,
        steps=payload.steps,
        utensils=payload.utensils,
        prep_minutes=payload.prep_minutes,
        cook_minutes=payload.cook_minutes,
        servings=payload.servings,
        tags=payload.tags,
        source_url=payload.source_url,
        source_platform=payload.source_platform,
        source_title=payload.source_title,
        source_description=payload.source_description,
        source_transcript=payload.source_transcript,
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    for ingredient in payload.ingredients:
        row = RecipeIngredient(recipe_id=recipe.id, **ingredient.model_dump())
        session.add(row)

    recipe.updated_at = datetime.now(timezone.utc)
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    return build_recipe_read(session, recipe)


@router.patch("/{recipe_id}", response_model=RecipeRead)
def update_recipe(recipe_id: int, payload: RecipeUpdate, session: SessionDep) -> RecipeRead:
    recipe = session.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    updates = payload.model_dump(exclude_unset=True)
    ingredients = updates.pop("ingredients", None)
    for key, value in updates.items():
        setattr(recipe, key, value)
    recipe.updated_at = datetime.now(timezone.utc)
    session.add(recipe)
    session.commit()

    if ingredients is not None:
        for existing in session.exec(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
        ).all():
            session.delete(existing)
        session.commit()
        for ingredient in ingredients:
            row = RecipeIngredient(recipe_id=recipe.id, **ingredient.model_dump())
            session.add(row)
        recipe.updated_at = datetime.now(timezone.utc)
        session.add(recipe)
        session.commit()

    session.refresh(recipe)
    return build_recipe_read(session, recipe)


@router.get("", response_model=list[RecipeRead])
def list_recipes(session: SessionDep, limit: int = Query(default=50, ge=1, le=200)) -> list[RecipeRead]:
    recipes = session.exec(select(Recipe).order_by(Recipe.created_at.desc()).limit(limit)).all()
    return [build_recipe_read(session, recipe) for recipe in recipes]


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, session: SessionDep) -> RecipeRead:
    recipe = session.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return build_recipe_read(session, recipe)


@router.post("/{recipe_id}/confirm-cooked", response_model=RecipeCookResult)
def confirm_recipe_cooked(
    recipe_id: int,
    session: SessionDep,
    payload: RecipeCookRequest | None = None,
) -> RecipeCookResult:
    recipe = session.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    servings_override = payload.servings_override if payload else None
    note = payload.note if payload else None
    missing = compute_recipe_missing_ingredients(session, recipe, servings_override)
    consumption = consume_recipe_ingredients(session, recipe, servings_override)

    return RecipeCookResult(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        cooked_at=datetime.now(timezone.utc),
        note=note,
        missing_ingredients=missing,
        pantry_consumption=consumption,
    )


@router.delete("/{recipe_id}")
def delete_recipe(recipe_id: int, session: SessionDep) -> dict:
    recipe = session.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ingredient_rows = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
    for row in ingredient_rows:
        session.delete(row)
    if ingredient_rows:
        session.commit()

    meal_plans = session.exec(select(MealPlan).where(MealPlan.recipe_id == recipe.id)).all()
    for meal_plan in meal_plans:
        confirmation = session.exec(
            select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
        ).first()
        if confirmation:
            session.delete(confirmation)
        session.delete(meal_plan)
    if meal_plans:
        session.commit()

    session.delete(recipe)
    session.commit()
    sync_generated_calendar_items(session)
    return {"ok": True, "deleted_id": recipe_id}
