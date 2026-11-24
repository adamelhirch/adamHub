"""Migrate existing recipes to relational Merise structures (RecipeStep, RecipeUtensil, RecipeTag, canonical Ingredient IDs)."""
from __future__ import annotations

import sys
from sqlmodel import Session, select

from app.core.db import engine
from app.models import Ingredient, Recipe, RecipeIngredient
from app.services.canonical_seed import seed_canonical_data
from app.services.meal_planning import sync_recipe_merise_associations


def migrate_recipes(session: Session) -> dict[str, int]:
    # 1. Ensure canonical seeds are present
    seed_counts = seed_canonical_data(session)

    # 2. Iterate recipes
    recipes = session.exec(select(Recipe)).all()
    migrated_recipes = 0
    linked_ingredients = 0

    for recipe in recipes:
        sync_recipe_merise_associations(session, recipe)
        migrated_recipes += 1

        # Link ingredients where ingredient_id is None
        ing_rows = session.exec(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == recipe.id,
                RecipeIngredient.ingredient_id.is_(None),  # type: ignore
            )
        ).all()

        for row in ing_rows:
            matched_ing = session.exec(
                select(Ingredient).where(Ingredient.name.ilike(row.name))
            ).first()
            if matched_ing:
                row.ingredient_id = matched_ing.id
                session.add(row)
                linked_ingredients += 1

    session.commit()
    return {
        "recipes_migrated": migrated_recipes,
        "ingredients_linked": linked_ingredients,
        **seed_counts,
    }


def main() -> None:
    print("[migrate] Migrating existing recipes to Merise structures...")
    with Session(engine) as session:
        result = migrate_recipes(session)
    print(f"[migrate] Migration complete: {result}")


if __name__ == "__main__":
    main()
