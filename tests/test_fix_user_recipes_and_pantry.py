from sqlmodel import Session, select

from app.models import PantryItem, Recipe, RecipeIngredient
from scripts.fix_user_recipes_and_pantry_saumon import fix_recipes_and_pantry


def test_fix_recipes_and_pantry_idempotent(test_engine):
    with Session(test_engine) as session:
        # Create test recipe 1 with 2 item pavés
        r1 = Recipe(id=1, name="Saumon teriyaki avec riz", instructions="Cook it")
        session.add(r1)
        session.flush()
        ing1 = RecipeIngredient(
            recipe_id=r1.id,
            name="Saumon",
            quantity=2.0,
            unit="item",
            note="150 g chacun, pavés",
        )
        session.add(ing1)

        # Create test recipe 12 with 250 g
        r12 = Recipe(id=12, name="Pâtes crémeuses au saumon", instructions="Cook pasta")
        session.add(r12)
        session.flush()
        ing12 = RecipeIngredient(
            recipe_id=r12.id,
            name="Saumon",
            quantity=250.0,
            unit="g",
            note="pavé",
        )
        session.add(ing12)

        # Create pantry item 7 with 250 g
        p7 = PantryItem(
            id=7,
            name="Saumon",
            quantity=250.0,
            unit="g",
            category="Poisson",
            note="Acheté 3,60 € les 250 g (pavés)",
        )
        session.add(p7)
        session.commit()

        # Run fix
        stats = fix_recipes_and_pantry(session)
        assert stats["ingredients_updated"] >= 2
        assert stats["pantry_updated"] >= 1

        # Verify r1
        session.refresh(ing1)
        assert ing1.name == "Saumon frais"
        assert ing1.quantity == 300.0
        assert ing1.unit == "g"
        assert "2 pavés" in ing1.note

        # Verify r12
        session.refresh(ing12)
        assert ing12.name == "Saumon frais"
        assert ing12.quantity == 250.0
        assert ing12.unit == "g"

        # Verify p7
        session.refresh(p7)
        assert p7.name == "Saumon frais"
        assert p7.quantity == 250.0
        assert p7.unit == "g"
        assert p7.location == "Réfrigérateur"
        assert p7.category == "Poisson"

        # Run fix second time: idempotent
        stats2 = fix_recipes_and_pantry(session)
        assert stats2["ingredients_updated"] == 0
        assert stats2["pantry_updated"] == 0
