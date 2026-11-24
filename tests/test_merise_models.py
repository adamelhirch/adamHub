from collections.abc import Generator
from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import (
    DietaryPreference,
    GroceryItem,
    Ingredient,
    PantryItem,
    Recipe,
    RecipeIngredient,
    RecipeStep,
    RecipeTag,
    RecipeUtensil,
    Tag,
    UnitOfMeasure,
    User,
    UserDietaryPreference,
    Utensil,
)


@pytest.fixture()
def session(test_engine) -> Generator[Session, None, None]:
    with Session(test_engine) as sess:
        yield sess


def test_unit_of_measure_creation(session: Session) -> None:
    gram = UnitOfMeasure(
        code="g",
        label="Gramme",
        magnitude_type="mass",
        conversion_factor_to_base=1.0,
    )
    kg = UnitOfMeasure(
        code="kg",
        label="Kilogramme",
        magnitude_type="mass",
        conversion_factor_to_base=1000.0,
    )
    session.add(gram)
    session.add(kg)
    session.commit()

    saved_gram = session.exec(select(UnitOfMeasure).where(UnitOfMeasure.code == "g")).first()
    assert saved_gram is not None
    assert saved_gram.label == "Gramme"
    assert saved_gram.conversion_factor_to_base == 1.0


def test_canonical_ingredient_with_unit(session: Session) -> None:
    piece = UnitOfMeasure(code="piece", label="Pièce", magnitude_type="count")
    session.add(piece)
    session.commit()

    tomato = Ingredient(name="Tomate", category="Frais", default_unit_code="piece")
    session.add(tomato)
    session.commit()
    session.refresh(tomato)

    assert tomato.id is not None
    assert tomato.name == "Tomate"
    assert tomato.default_unit_code == "piece"


def test_dietary_preference_and_user_link(session: Session) -> None:
    user = User(
        email="test_diet@example.com",
        password_hash="fakehash",
        display_name="Diet User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    vegan = DietaryPreference(name="Végan", description="Aucun produit d'origine animale")
    session.add(vegan)
    session.commit()
    session.refresh(vegan)

    user_pref = UserDietaryPreference(user_id=user.id, dietary_preference_id=vegan.id)
    session.add(user_pref)
    session.commit()

    saved = session.exec(
        select(UserDietaryPreference).where(UserDietaryPreference.user_id == user.id)
    ).first()
    assert saved is not None
    assert saved.dietary_preference_id == vegan.id


def test_recipe_steps_utensils_tags_and_canonical_ingredient(session: Session) -> None:
    recipe = Recipe(
        name="Pâtes Carbonara",
        description="Recette traditionnelle italienne",
        instructions="Cuire les pâtes et mélanger",
        prep_minutes=10,
        cook_minutes=15,
        servings=2,
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    # 1. Étapes
    step1 = RecipeStep(recipe_id=recipe.id, order=1, instruction="Faire bouillir l'eau salée", duration_minutes=5)
    step2 = RecipeStep(recipe_id=recipe.id, order=2, instruction="Cuire les pâtes al dente", duration_minutes=10)
    session.add(step1)
    session.add(step2)

    # 2. Ustensiles
    pan = Utensil(name="Poêle à frire")
    session.add(pan)
    session.commit()
    session.refresh(pan)
    rec_utensil = RecipeUtensil(recipe_id=recipe.id, utensil_id=pan.id)
    session.add(rec_utensil)

    # 3. Tags
    italian = Tag(label="Italien")
    session.add(italian)
    session.commit()
    session.refresh(italian)
    rec_tag = RecipeTag(recipe_id=recipe.id, tag_id=italian.id)
    session.add(rec_tag)

    # 4. Ingrédient canonique relié
    pasta_ing = Ingredient(name="Spaghetti", category="Épicerie")
    session.add(pasta_ing)
    session.commit()
    session.refresh(pasta_ing)

    line = RecipeIngredient(
        recipe_id=recipe.id,
        ingredient_id=pasta_ing.id,
        name="Spaghetti",
        quantity=200,
        unit="g",
        note="al dente",
    )
    session.add(line)
    session.commit()

    # Vérifications
    steps = session.exec(select(RecipeStep).where(RecipeStep.recipe_id == recipe.id).order_by(RecipeStep.order)).all()
    assert len(steps) == 2
    assert steps[0].instruction == "Faire bouillir l'eau salée"

    utensils = session.exec(select(RecipeUtensil).where(RecipeUtensil.recipe_id == recipe.id)).all()
    assert len(utensils) == 1
    assert utensils[0].utensil_id == pan.id

    tags = session.exec(select(RecipeTag).where(RecipeTag.recipe_id == recipe.id)).all()
    assert len(tags) == 1
    assert tags[0].tag_id == italian.id

    ingredients = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
    assert len(ingredients) == 1
    assert ingredients[0].ingredient_id == pasta_ing.id


def test_pantry_and_grocery_canonical_links(session: Session) -> None:
    flour = Ingredient(name="Farine de blé T55", category="Épicerie")
    session.add(flour)
    session.commit()
    session.refresh(flour)

    pantry = PantryItem(
        ingredient_id=flour.id,
        name="Farine",
        quantity=1.0,
        unit="kg",
        min_quantity=0.5,
    )
    grocery = GroceryItem(
        ingredient_id=flour.id,
        name="Farine T55",
        quantity=2.0,
        unit="kg",
    )
    session.add(pantry)
    session.add(grocery)
    session.commit()

    session.refresh(pantry)
    session.refresh(grocery)
    assert pantry.ingredient_id == flour.id
    assert grocery.ingredient_id == flour.id


def test_recipe_sync_and_migration(session: Session) -> None:
    from app.services.meal_planning import sync_recipe_merise_associations
    from scripts.migrate_recipes_to_merise import migrate_recipes

    # Create a recipe with legacy JSON fields
    recipe = Recipe(
        name="Quiche Lorraine",
        description="Quiche traditionnelle",
        instructions="Étaler la pâte.\nBattre les œufs avec la crème.\nAjouter les lardons.\nCuire 30 min au four.",
        steps=["Étaler la pâte", "Battre les œufs et la crème", "Ajouter les lardons", "Enfourner"],
        utensils=["Moule à tarte", "Fouet", "Four"],
        tags=["Traditionnel", "Four", "Facile"],
        servings=4,
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    # Pre-create canonical ingredient for Lardons
    lardons = Ingredient(name="Lardons fumés", category="Boucherie")
    session.add(lardons)
    session.commit()

    # Add legacy ingredient without ingredient_id
    ing_row = RecipeIngredient(
        recipe_id=recipe.id,
        name="Lardons fumés",
        quantity=200,
        unit="g",
    )
    session.add(ing_row)
    session.commit()

    # Run migration
    stats = migrate_recipes(session)
    assert stats["recipes_migrated"] >= 1
    assert stats["ingredients_linked"] >= 1

    # Verify steps were created
    steps = session.exec(select(RecipeStep).where(RecipeStep.recipe_id == recipe.id).order_by(RecipeStep.order)).all()
    assert len(steps) == 4
    assert steps[0].instruction == "Étaler la pâte"

    # Verify utensils were linked
    utensils = session.exec(select(RecipeUtensil).where(RecipeUtensil.recipe_id == recipe.id)).all()
    assert len(utensils) == 3

    # Verify tags were linked
    tags = session.exec(select(RecipeTag).where(RecipeTag.recipe_id == recipe.id)).all()
    assert len(tags) == 3

    # Verify ingredient_id was linked
    session.refresh(ing_row)
    assert ing_row.ingredient_id == lardons.id
