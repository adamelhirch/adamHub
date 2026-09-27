import sys
from sqlmodel import Session, select

from app.core.db import engine
from app.models import PantryItem, Recipe, RecipeIngredient


def fix_recipes_and_pantry(session: Session) -> dict[str, int]:
    """Updates ambiguous 'Saumon' entries to 'Saumon frais' with metric units."""
    stats = {"recipes_updated": 0, "ingredients_updated": 0, "pantry_updated": 0}

    # 1. Update Recipe Ingredients for Saumon
    salmon_ingredients = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.name.ilike("saumon%"))
    ).all()

    for ing in salmon_ingredients:
        # Check if it needs normalization
        changed = False
        if ing.name == "Saumon":
            ing.name = "Saumon frais"
            changed = True

        # Recipe 1: 2 item -> 300 g
        if ing.unit == "item" and ing.recipe_id == 1:
            ing.quantity = 300.0
            ing.unit = "g"
            ing.note = "2 pavés de 150 g"
            changed = True
        elif ing.recipe_id == 12:
            if ing.note is None or ing.note == "":
                ing.note = "pavé"
                changed = True

        if changed:
            session.add(ing)
            stats["ingredients_updated"] += 1

    # 2. Update Pantry Item 7 or any generic Saumon in pantry
    pantry_items = session.exec(
        select(PantryItem).where(PantryItem.name.ilike("saumon%"))
    ).all()

    for item in pantry_items:
        changed = False
        if item.name == "Saumon":
            item.name = "Saumon frais"
            changed = True
        if not item.location:
            item.location = "Réfrigérateur"
            changed = True
        if not item.category:
            item.category = "Poisson"
            changed = True
        if item.id == 7 and item.note and "pavé" in item.note.lower() and item.note != "2 pavés":
            item.note = "2 pavés"
            changed = True

        if changed:
            session.add(item)
            stats["pantry_updated"] += 1

    session.commit()
    return stats


def main() -> None:
    with Session(engine) as session:
        print("Starting data correction for recipes and pantry salmon...")
        stats = fix_recipes_and_pantry(session)
        print(f"Correction completed: {stats}")


if __name__ == "__main__":
    main()
