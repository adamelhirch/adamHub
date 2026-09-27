from datetime import datetime, timezone
from sqlmodel import Session, select

from app.models.entities import GroceryItem, Recipe, RecipeIngredient, User
from app.schemas.meal_planning import MissingIngredientRead
from app.services.meal_planning import add_missing_to_grocery, resolve_recipe_ingredient_fields
from app.services.units import canonical_ingredient, normalize_name, to_base


def test_canonical_ingredient_parsing():
    # 1. Cuts in parentheses for measurable protein
    name, unit, note = canonical_ingredient("Saumon (pavés)", "pavés", "150 g chacun")
    assert name == "Saumon"
    assert unit == "g"
    assert "pavés" in note
    assert "150 g chacun" in note

    # 2. Cut prefix in name
    name, unit, note = canonical_ingredient("Pave de saumon", "g", None)
    assert name == "Saumon"
    assert unit == "g"
    assert note == "pavé"

    # 3. Unit synonym normalization
    name, unit, note = canonical_ingredient("Huile d'olive", "c. a s.", None)
    assert name == "Huile d'olive"
    assert unit == "c. à soupe"

    # 4. Gousses d'ail (whole piece item)
    name, unit, note = canonical_ingredient("Gousses d'ail", "gousses", None)
    assert name == "Ail"
    assert unit == "item"
    assert "gousse" in note.lower()

    # 5. Empty unit defaults to item for natural whole produce
    name, unit, note = canonical_ingredient("Échalote", "", None)
    assert name == "Échalote"
    assert unit == "item"

    # 6. Physical measurability on proteins: cut becomes note, unit becomes 'g'
    name, unit, note = canonical_ingredient("Saumon frais", "pavés", "2 pièces")
    assert name == "Saumon frais"
    assert unit == "g"
    assert "pavé" in note.lower()

    name, unit, note = canonical_ingredient("Filet de poulet", "filets", None)
    assert name == "Poulet"
    assert unit == "g"
    assert "filet" in note.lower()

    name, unit, note = canonical_ingredient("Steak de boeuf", "steaks", None)
    assert name == "Boeuf"
    assert unit == "g"
    assert "steak" in note.lower()

    # 7. Natural whole items strictly use 'item'
    for whole_item in ["Avocat", "Pomme", "Oeuf", "Citron", "Oignon"]:
        n, u, nt = canonical_ingredient(whole_item, "", None)
        assert n == whole_item
        assert u == "item"


def test_normalize_name_equivalence():
    assert normalize_name("Saumon (pavés)") == normalize_name("Pave de saumon") == normalize_name("Saumon")
    assert normalize_name("Pâtes") == normalize_name("Pates") == normalize_name("Pâte")
    assert normalize_name("Oignons") == normalize_name("Oignon")
    assert normalize_name("Gousses d'ail") == normalize_name("Ail")
    assert normalize_name("Blanc de poulet") == normalize_name("Poulet")


def test_grocery_consolidation_with_canonical_ingredients(test_engine):
    with Session(test_engine) as session:
        user = User(
            email="test_canonical@example.com",
            password_hash="hash",
            display_name="Test User",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Recipe 1: Pave de saumon (250g)
        missing_1 = [
            MissingIngredientRead(
                name="Pave de saumon",
                needed_quantity=250.0,
                available_quantity=0.0,
                missing_quantity=250.0,
                unit="g",
            )
        ]
        added_1 = add_missing_to_grocery(
            session, missing_1, note_prefix="Recette 1", user_id=user.id
        )
        assert added_1 == 1

        # Recipe 2: Saumon (pavés) (250g)
        missing_2 = [
            MissingIngredientRead(
                name="Saumon (pavés)",
                needed_quantity=250.0,
                available_quantity=0.0,
                missing_quantity=250.0,
                unit="g",
            )
        ]
        added_2 = add_missing_to_grocery(
            session, missing_2, note_prefix="Recette 2", user_id=user.id
        )
        # Should consolidate into existing grocery item rather than create a duplicate
        assert added_2 == 0

        items = session.exec(
            select(GroceryItem).where(GroceryItem.user_id == user.id)
        ).all()
        assert len(items) == 1
        assert items[0].name == "Saumon"
        assert items[0].quantity == 500.0
        assert items[0].unit == "g"
        assert "Recette 1: Saumon" in items[0].note
        assert "Recette 2: Saumon" in items[0].note


def test_resolve_recipe_ingredient_fields_canonicalizes(test_engine):
    with Session(test_engine) as session:
        raw_ing = {
            "name": "Pavé de saumon",
            "quantity": 2.0,
            "unit": "pavés",
            "note": "frais",
        }
        resolved = resolve_recipe_ingredient_fields(session, raw_ing)
        assert resolved["name"] == "Saumon"
        assert resolved["unit"] == "g"
        assert "frais" in resolved["note"]
        assert "pavé" in resolved["note"].lower()
