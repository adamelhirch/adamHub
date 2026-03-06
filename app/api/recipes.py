from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import Recipe, RecipeIngredient
from app.schemas import RecipeCreate, RecipeRead
from app.services.life import build_recipe_read

router = APIRouter(prefix="/recipes", tags=["recipes"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=RecipeRead)
def create_recipe(payload: RecipeCreate, session: SessionDep) -> RecipeRead:
    recipe = Recipe(
        name=payload.name,
        description=payload.description,
        instructions=payload.instructions,
        prep_minutes=payload.prep_minutes,
        cook_minutes=payload.cook_minutes,
        servings=payload.servings,
        tags=payload.tags,
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
