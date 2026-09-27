from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.api._crud import get_owned_or_404
from app.api.deps import CurrentOrOwnerUser, SessionDep
from app.models import (
    GroceryItem,
    MealPlan,
    MealPlanCookConfirmation,
    Recipe,
    RecipeIngredient,
)
from app.schemas import (
    RecipeAddToGroceriesRequest,
    RecipeAddToGroceriesResult,
    RecipeCookRequest,
    RecipeCookResult,
    RecipeCreate,
    RecipeRead,
    RecipeUncookResult,
    RecipeUpdate,
)
from app.services.cook import (
    compute_recipe_missing_ingredients,
    confirm_recipe_cooked as confirm_recipe_cooked_service,
    unconfirm_recipe_cooked as unconfirm_recipe_cooked_service,
)
from app.services.meal_planning import build_recipe_read, resolve_recipe_ingredient_fields
from app.services.units import normalize_name

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _ingredient_fields(session: Session, ingredient):
    return resolve_recipe_ingredient_fields(session, ingredient)


@router.post("", response_model=RecipeRead)
def create_recipe(payload: RecipeCreate, session: SessionDep, user: CurrentOrOwnerUser) -> RecipeRead:
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
        user_id=user.id,
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    for ingredient in payload.ingredients:
        row = RecipeIngredient(recipe_id=recipe.id, **_ingredient_fields(session, ingredient))
        session.add(row)

    recipe.updated_at = datetime.now(timezone.utc)
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    return build_recipe_read(session, recipe)


@router.patch("/{recipe_id}", response_model=RecipeRead)
def update_recipe(
    recipe_id: int,
    payload: RecipeUpdate,
    session: SessionDep,
    user: CurrentOrOwnerUser,
) -> RecipeRead:
    recipe = get_owned_or_404(session, Recipe, recipe_id, user_id=user.id, detail="Recipe not found")

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
            row = RecipeIngredient(recipe_id=recipe.id, **_ingredient_fields(session, ingredient))
            session.add(row)
        recipe.updated_at = datetime.now(timezone.utc)
        session.add(recipe)
        session.commit()

    session.refresh(recipe)
    return build_recipe_read(session, recipe)


@router.get("", response_model=list[RecipeRead])
def list_recipes(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RecipeRead]:
    recipes = session.exec(
        select(Recipe)
        .where(Recipe.user_id == user.id)
        .order_by(Recipe.created_at.desc())
        .limit(limit)
    ).all()
    return [build_recipe_read(session, recipe) for recipe in recipes]


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> RecipeRead:
    recipe = get_owned_or_404(session, Recipe, recipe_id, user_id=user.id, detail="Recipe not found")
    return build_recipe_read(session, recipe)


@router.post("/{recipe_id}/confirm-cooked", response_model=RecipeCookResult)
def confirm_recipe_cooked(
    recipe_id: int,
    session: SessionDep,
    user: CurrentOrOwnerUser,
    payload: RecipeCookRequest | None = None,
) -> RecipeCookResult:
    recipe = get_owned_or_404(session, Recipe, recipe_id, user_id=user.id, detail="Recipe not found")

    servings_override = payload.servings_override if payload else None
    note = payload.note if payload else None
    result = confirm_recipe_cooked_service(
        session, recipe, servings_override, note, user_id=user.id
    )

    return RecipeCookResult(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        cooked_at=result["confirmed_at"],
        note=result["note"],
        missing_ingredients=result["missing_ingredients"],
        pantry_consumption=result["pantry_consumption"],
        meal_plan_id=result["meal_plan_id"],
        already_confirmed=result["already_confirmed"],
    )


@router.post("/{recipe_id}/unconfirm-cooked", response_model=RecipeUncookResult)
def unconfirm_recipe_cooked(
    recipe_id: int, session: SessionDep, user: CurrentOrOwnerUser
) -> RecipeUncookResult:
    recipe = get_owned_or_404(session, Recipe, recipe_id, user_id=user.id, detail="Recipe not found")
    result = unconfirm_recipe_cooked_service(session, recipe, user_id=user.id)
    return RecipeUncookResult.model_validate(result)


@router.post("/{recipe_id}/add-to-groceries", response_model=RecipeAddToGroceriesResult)
def add_recipe_to_groceries(
    recipe_id: int,
    session: SessionDep,
    user: CurrentOrOwnerUser,
    payload: RecipeAddToGroceriesRequest | None = None,
) -> RecipeAddToGroceriesResult:
    recipe = get_owned_or_404(session, Recipe, recipe_id, user_id=user.id, detail="Recipe not found")

    ingredients = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
    ).all()

    req = payload or RecipeAddToGroceriesRequest()

    if req.ingredient_ids is not None:
        selected_ids = set(req.ingredient_ids)
        ingredients = [ing for ing in ingredients if ing.id in selected_ids]

    ratio = 1.0
    if req.servings_override and recipe.servings > 0:
        ratio = req.servings_override / recipe.servings

    if req.missing_only:
        missing_list = compute_recipe_missing_ingredients(
            session, recipe, req.servings_override, user_id=user.id
        )
        missing_names = {normalize_name(m.name) for m in missing_list if (m.missing_quantity or 0) > 0}
        ingredients = [ing for ing in ingredients if normalize_name(ing.name) in missing_names]

    existing_statement = select(GroceryItem).where(GroceryItem.checked == False)  # noqa: E712
    if user.id is not None:
        existing_statement = existing_statement.where(GroceryItem.user_id == user.id)
    existing_items = session.exec(existing_statement).all()
    indexed_existing = {
        (normalize_name(item.name), (item.unit or "item").strip().lower()): item
        for item in existing_items
    }

    now = datetime.now(timezone.utc)
    added_items: list[dict] = []
    recipe_note = f"Recette: {recipe.name}"

    for ing in ingredients:
        needed_qty = round((ing.quantity or 0.0) * ratio, 3)
        unit_str = ing.unit or "item"
        key = (normalize_name(ing.name), unit_str.strip().lower())

        if key in indexed_existing:
            item = indexed_existing[key]
            item.quantity = round((item.quantity or 0.0) + needed_qty, 3)
            if item.note:
                if recipe_note not in item.note:
                    item.note = f"{item.note}\n{recipe_note}"
            else:
                item.note = recipe_note
            item.updated_at = now
            session.add(item)
            added_items.append({
                "id": item.id,
                "name": item.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "category": item.category,
                "checked": item.checked,
                "recipe_id": recipe.id,
            })
        else:
            new_item = GroceryItem(
                user_id=user.id,
                name=ing.name,
                quantity=needed_qty,
                unit=unit_str,
                category=ing.category or "Recettes",
                image_url=ing.image_url,
                store_label=ing.store_label,
                external_id=ing.external_id,
                packaging=ing.packaging,
                price_text=ing.price_text,
                product_url=ing.product_url,
                checked=False,
                priority=2,
                note=recipe_note,
                created_at=now,
                updated_at=now,
            )
            session.add(new_item)
            session.flush()
            indexed_existing[key] = new_item
            added_items.append({
                "id": new_item.id,
                "name": new_item.name,
                "quantity": new_item.quantity,
                "unit": new_item.unit,
                "category": new_item.category,
                "checked": new_item.checked,
                "recipe_id": recipe.id,
            })

    session.commit()

    return RecipeAddToGroceriesResult(
        recipe_id=recipe.id,
        added_count=len(added_items),
        items=added_items,
    )


@router.delete("/{recipe_id}")
def delete_recipe(recipe_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> dict:
    recipe = get_owned_or_404(session, Recipe, recipe_id, user_id=user.id, detail="Recipe not found")

    # 1. Cleanly delete cook confirmations for all meal plans referencing this recipe
    meal_plans = session.exec(
        select(MealPlan).where(MealPlan.recipe_id == recipe.id)
    ).all()
    for meal_plan in meal_plans:
        confirmations = session.exec(
            select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == meal_plan.id)
        ).all()
        for confirmation in confirmations:
            session.delete(confirmation)
    session.flush()

    # 2. Cleanly delete meal plans referencing this recipe
    for meal_plan in meal_plans:
        session.delete(meal_plan)
    session.flush()

    # 3. Cleanly delete recipe ingredients
    ingredient_rows = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
    for row in ingredient_rows:
        session.delete(row)
    session.flush()

    # 4. Atomically delete the recipe itself in the same transaction
    session.delete(recipe)
    session.commit()
    return {"ok": True, "deleted_id": recipe_id}

