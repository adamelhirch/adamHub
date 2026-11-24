from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_user


def test_units_of_measure_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    # 1. Initially empty
    resp = client.get("/api/v1/units", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Create unit
    payload = {"code": "g", "label": "Gramme", "magnitude_type": "mass"}
    resp = client.post("/api/v1/units", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["code"] == "g"
    assert created["label"] == "Gramme"
    assert created["magnitude_type"] == "mass"

    # 3. Duplicate code -> 409 Conflict
    resp = client.post("/api/v1/units", json=payload, headers=auth_headers)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]

    # 4. List units
    client.post(
        "/api/v1/units",
        json={"code": "ml", "label": "Millilitre", "magnitude_type": "volume"},
        headers=auth_headers,
    )
    resp = client.get("/api/v1/units", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    codes = [u["code"] for u in data]
    assert "g" in codes
    assert "ml" in codes


def test_ingredients_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Create required unit first
    resp_unit = client.post(
        "/api/v1/units",
        json={"code": "g", "label": "Gramme", "magnitude_type": "mass"},
        headers=auth_headers,
    )
    assert resp_unit.status_code == 201

    # 1. Create ingredient with unit
    ing_payload = {
        "name": "Farine de blé T55",
        "category": "Epicerie",
        "default_unit_code": "g",
    }
    resp = client.post("/api/v1/ingredients", json=ing_payload, headers=auth_headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] is not None
    assert created["name"] == "Farine de blé T55"
    assert created["category"] == "Epicerie"
    assert created["default_unit_code"] == "g"
    ing_id = created["id"]

    # 2. Duplicate ingredient name -> 409
    resp = client.post("/api/v1/ingredients", json=ing_payload, headers=auth_headers)
    assert resp.status_code == 409

    # 3. Create ingredient with unknown unit -> 400
    bad_payload = {"name": "Lait entier", "default_unit_code": "unknown_unit"}
    resp = client.post("/api/v1/ingredients", json=bad_payload, headers=auth_headers)
    assert resp.status_code == 400

    # 4. Get ingredient by ID
    resp = client.get(f"/api/v1/ingredients/{ing_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Farine de blé T55"

    resp = client.get("/api/v1/ingredients/99999", headers=auth_headers)
    assert resp.status_code == 404

    # 5. Search & filter ingredients
    client.post(
        "/api/v1/ingredients",
        json={"name": "Sucre en poudre", "category": "Epicerie", "default_unit_code": "g"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/ingredients",
        json={"name": "Pomme Gala", "category": "Fruits et Légumes"},
        headers=auth_headers,
    )

    resp = client.get("/api/v1/ingredients?query=farine", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["name"] == "Farine de blé T55"

    resp = client.get("/api/v1/ingredients?category=Epicerie", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 6. Update ingredient
    patch_resp = client.patch(
        f"/api/v1/ingredients/{ing_id}",
        json={"name": "Farine de blé T45", "category": "Epicerie fine"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Farine de blé T45"
    assert patch_resp.json()["category"] == "Epicerie fine"

    # 7. Delete ingredient
    del_resp = client.delete(f"/api/v1/ingredients/{ing_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    resp = client.get(f"/api/v1/ingredients/{ing_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_utensils_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    # 1. Create utensil
    resp = client.post("/api/v1/utensils", json={"name": "Fouet"}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Fouet"

    # 2. Duplicate utensil -> 409
    resp = client.post("/api/v1/utensils", json={"name": "Fouet"}, headers=auth_headers)
    assert resp.status_code == 409

    # 3. List & filter
    client.post("/api/v1/utensils", json={"name": "Spatule en bois"}, headers=auth_headers)
    resp = client.get("/api/v1/utensils?query=spatule", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Spatule en bois"


def test_tags_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    # 1. Create tag
    resp = client.post("/api/v1/tags", json={"label": "Rapide"}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["label"] == "Rapide"

    # 2. Duplicate tag -> 409
    resp = client.post("/api/v1/tags", json={"label": "Rapide"}, headers=auth_headers)
    assert resp.status_code == 409

    # 3. List & filter
    client.post("/api/v1/tags", json={"label": "Sans cuisson"}, headers=auth_headers)
    resp = client.get("/api/v1/tags?query=cuisson", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["label"] == "Sans cuisson"


def test_dietary_preferences_and_user_links(client: TestClient, auth_headers: dict[str, str]) -> None:
    # 1. Create canonical dietary preferences
    pref1 = client.post(
        "/api/v1/dietary-preferences",
        json={"name": "Végétarien", "description": "Sans viande ni poisson"},
        headers=auth_headers,
    ).json()
    pref2 = client.post(
        "/api/v1/dietary-preferences",
        json={"name": "Sans gluten", "description": "Exclut le blé, orge, seigle"},
        headers=auth_headers,
    ).json()

    # Duplicate -> 409
    resp = client.post(
        "/api/v1/dietary-preferences",
        json={"name": "Végétarien"},
        headers=auth_headers,
    )
    assert resp.status_code == 409

    # 2. Check my preferences initially empty for owner
    resp = client.get("/api/v1/dietary-preferences/my", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []

    # 3. Associate preferences for owner
    resp = client.put(
        "/api/v1/dietary-preferences/my",
        json={"dietary_preference_ids": [pref1["id"], pref2["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    owner_prefs = resp.json()
    assert len(owner_prefs) == 2
    names = [p["name"] for p in owner_prefs]
    assert "Sans gluten" in names
    assert "Végétarien" in names

    # 4. Multi-tenant isolation test: another user has distinct preferences
    user2 = register_user(client, "user2@test.com")
    resp2 = client.get("/api/v1/dietary-preferences/my", headers=user2["headers"])
    assert resp2.status_code == 200
    assert resp2.json() == []

    client.put(
        "/api/v1/dietary-preferences/my",
        json={"dietary_preference_ids": [pref1["id"]]},
        headers=user2["headers"],
    )
    resp2 = client.get("/api/v1/dietary-preferences/my", headers=user2["headers"])
    assert len(resp2.json()) == 1
    assert resp2.json()[0]["name"] == "Végétarien"

    # Owner still has 2 preferences
    resp_owner = client.get("/api/v1/dietary-preferences/my", headers=auth_headers)
    assert len(resp_owner.json()) == 2

    # 5. Invalid preference ID -> 400
    resp_bad = client.put(
        "/api/v1/dietary-preferences/my",
        json={"dietary_preference_ids": [99999]},
        headers=auth_headers,
    )
    assert resp_bad.status_code == 400
    assert "Unknown dietary preference IDs" in resp_bad.json()["detail"]


def test_canonical_seed_service(client: TestClient, auth_headers: dict[str, str], test_engine) -> None:
    from sqlmodel import Session
    from app.services.canonical_seed import seed_canonical_data

    # First run seeds all reference data
    with Session(test_engine) as session:
        counts = seed_canonical_data(session)

    assert counts["units"] > 0
    assert counts["dietary_preferences"] > 0
    assert counts["utensils"] > 0
    assert counts["tags"] > 0
    assert counts["ingredients"] > 0

    # API endpoints now return the seeded reference data
    resp_units = client.get("/api/v1/units", headers=auth_headers)
    assert resp_units.status_code == 200
    assert len(resp_units.json()) >= 16

    resp_ing = client.get("/api/v1/ingredients?category=Épicerie salée", headers=auth_headers)
    assert resp_ing.status_code == 200
    assert len(resp_ing.json()) >= 10

    # Second run is idempotent (0 added)
    with Session(test_engine) as session:
        counts_second = seed_canonical_data(session)

    assert counts_second["units"] == 0
    assert counts_second["dietary_preferences"] == 0
    assert counts_second["utensils"] == 0
    assert counts_second["tags"] == 0
    assert counts_second["ingredients"] == 0


def test_recipe_creation_auto_populates_merise_associations(
    client: TestClient, auth_headers: dict[str, str], test_engine
) -> None:
    from sqlmodel import Session, select
    from app.models import RecipeStep, RecipeUtensil, RecipeTag, RecipeIngredient
    from app.services.canonical_seed import seed_canonical_data

    # Seed canonical data
    with Session(test_engine) as session:
        seed_canonical_data(session)

    # Create recipe via API
    recipe_payload = {
        "name": "Pâtes au Pesto",
        "description": "Recette rapide et fraîche",
        "instructions": "Cuire les pâtes.\nAjouter le pesto.",
        "steps": ["Faire bouillir l'eau", "Cuire les pâtes", "Égoutter et mélanger avec le pesto"],
        "utensils": ["Casserole", "Passoire", "Saladier"],
        "tags": ["Rapide (< 20 min)", "Facile"],
        "prep_minutes": 5,
        "cook_minutes": 10,
        "servings": 2,
        "ingredients": [
            {
                "name": "Pâtes Spaghetti",
                "quantity": 250,
                "unit": "g",
            },
            {
                "name": "Huile d'olive extra vierge",
                "quantity": 30,
                "unit": "ml",
            },
        ],
    }

    resp = client.post("/api/v1/recipes", json=recipe_payload, headers=auth_headers)
    assert resp.status_code == 200
    recipe_data = resp.json()
    recipe_id = recipe_data["id"]

    # Verify ingredient_id was automatically resolved to canonical Ingredient ID
    assert len(recipe_data["ingredients"]) == 2
    assert recipe_data["ingredients"][0]["ingredient_id"] is not None
    assert recipe_data["ingredients"][1]["ingredient_id"] is not None

    # Verify RecipeStep, RecipeUtensil, RecipeTag in DB
    with Session(test_engine) as session:
        steps = session.exec(
            select(RecipeStep).where(RecipeStep.recipe_id == recipe_id).order_by(RecipeStep.order)
        ).all()
        assert len(steps) == 3
        assert steps[0].instruction == "Faire bouillir l'eau"
        assert steps[1].instruction == "Cuire les pâtes"
        assert steps[2].instruction == "Égoutter et mélanger avec le pesto"

        utensils = session.exec(select(RecipeUtensil).where(RecipeUtensil.recipe_id == recipe_id)).all()
        assert len(utensils) == 3

        tags = session.exec(select(RecipeTag).where(RecipeTag.recipe_id == recipe_id)).all()
        assert len(tags) == 2
