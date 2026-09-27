from datetime import UTC, datetime, timedelta


def test_recipe_cook_confirmation_clamps_at_zero_and_reports_missing(client, auth_headers):
    # 1. Create a recipe with 2 ingredients: 200g riz, 100ml sauce
    rec_res = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Saumon teriyaki avec riz",
            "instructions": "Cuire le riz, napper de sauce.",
            "servings": 2,
            "prep_minutes": 15,
            "cook_minutes": 30,
            "ingredients": [
                {"name": "Riz basmati", "quantity": 200, "unit": "g"},
                {"name": "Sauce teriyaki", "quantity": 100, "unit": "ml"},
            ],
        },
    )
    assert rec_res.status_code == 200
    recipe_id = rec_res.json()["id"]

    # 2. Add partial stock in pantry: only 50g of riz (deficit of 150g), 0ml of sauce (deficit 100ml)
    pantry_res = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={
            "name": "Riz basmati",
            "quantity": 50,
            "unit": "g",
            "min_quantity": 0,
        },
    )
    assert pantry_res.status_code == 200
    pantry_id = pantry_res.json()["id"]

    # 3. Confirm cooked without error - partial stock is deducted down to 0, missing ingredients reported
    cook_res = client.post(
        f"/api/v1/recipes/{recipe_id}/confirm-cooked",
        headers=auth_headers,
        json={"servings_override": 2, "note": "Dîner test"},
    )
    assert cook_res.status_code == 200
    cook_data = cook_res.json()
    assert cook_data["recipe_id"] == recipe_id
    assert cook_data["already_confirmed"] is False

    # Check pantry was clamped down to 0, not negative
    check_pantry = client.get("/api/v1/pantry/items", headers=auth_headers)
    assert check_pantry.status_code == 200
    pantry_item = next(p for p in check_pantry.json() if p["id"] == pantry_id)
    assert pantry_item["quantity"] == 0.0

    # Check missing ingredients reported
    missing = {m["name"]: m for m in cook_data["missing_ingredients"]}
    assert "Riz basmati" in missing
    assert missing["Riz basmati"]["missing_quantity"] == 150.0
    assert "Sauce teriyaki" in missing
    assert missing["Sauce teriyaki"]["missing_quantity"] == 100.0

    # 4. Unconfirm cooked - restores exact stock to 50g
    uncook_res = client.post(
        f"/api/v1/recipes/{recipe_id}/unconfirm-cooked",
        headers=auth_headers,
    )
    assert uncook_res.status_code == 200
    assert uncook_res.json()["already_unconfirmed"] is False

    restored_pantry = client.get("/api/v1/pantry/items", headers=auth_headers)
    assert restored_pantry.status_code == 200
    restored_item = next(p for p in restored_pantry.json() if p["id"] == pantry_id)
    assert restored_item["quantity"] == 50.0


def test_recipe_add_to_groceries_selective_and_scaled(client, auth_headers):
    # Recipe for 2 servings: 200g riz, 100g saumon, 20g sésame
    rec_res = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Bowl saumon",
            "instructions": "Mélanger les ingrédients.",
            "servings": 2,
            "ingredients": [
                {"name": "Riz blanc", "quantity": 200, "unit": "g", "category": "Féculents"},
                {"name": "Saumon", "quantity": 100, "unit": "g", "category": "Poisson"},
                {"name": "Graines de sésame", "quantity": 20, "unit": "g", "category": "Épicerie"},
            ],
        },
    )
    assert rec_res.status_code == 200
    recipe_data = rec_res.json()
    recipe_id = recipe_data["id"]
    ing_map = {ing["name"]: ing["id"] for ing in recipe_data["ingredients"]}

    # Batch add only Riz and Saumon, scaling from 2 to 4 servings (x2)
    selected_ids = [ing_map["Riz blanc"], ing_map["Saumon"]]
    add_res = client.post(
        f"/api/v1/recipes/{recipe_id}/add-to-groceries",
        headers=auth_headers,
        json={
            "ingredient_ids": selected_ids,
            "servings_override": 4,
            "missing_only": False,
        },
    )
    assert add_res.status_code == 200
    res_data = add_res.json()
    assert res_data["recipe_id"] == recipe_id
    assert res_data["added_count"] == 2

    # Verify grocery items were added with scaled quantities
    groceries_res = client.get("/api/v1/groceries", headers=auth_headers)
    assert groceries_res.status_code == 200
    items = {item["name"]: item for item in groceries_res.json()}

    assert "Riz blanc" in items
    assert items["Riz blanc"]["quantity"] == 400.0  # 200 * (4/2)
    assert "Saumon" in items
    assert items["Saumon"]["quantity"] == 200.0  # 100 * (4/2)
    assert "Graines de sésame" not in items


def test_recipe_add_to_groceries_missing_only(client, auth_headers):
    # Recipe with Flour (200g) and Sugar (100g)
    rec_res = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Gâteau nature",
            "instructions": "Mélanger et cuire.",
            "servings": 4,
            "ingredients": [
                {"name": "Farine T55", "quantity": 200, "unit": "g"},
                {"name": "Sucre en poudre", "quantity": 100, "unit": "g"},
            ],
        },
    )
    assert rec_res.status_code == 200
    recipe_id = rec_res.json()["id"]

    # Flour is in pantry (300g > 200g needed), Sugar is missing (0 in pantry)
    client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Farine T55", "quantity": 300, "unit": "g"},
    )

    add_res = client.post(
        f"/api/v1/recipes/{recipe_id}/add-to-groceries",
        headers=auth_headers,
        json={"missing_only": True},
    )
    assert add_res.status_code == 200
    res_data = add_res.json()
    assert res_data["added_count"] == 1
    assert res_data["items"][0]["name"] == "Sucre en poudre"


def test_meal_plan_creation_with_recipe(client, auth_headers):
    # Recipe with 15m prep and 45m cook -> total 60m duration
    rec_res = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Ragoût mijoté",
            "instructions": "Laisser mijoter.",
            "servings": 2,
            "prep_minutes": 15,
            "cook_minutes": 45,
            "ingredients": [{"name": "Boeuf", "quantity": 300, "unit": "g"}],
        },
    )
    assert rec_res.status_code == 200
    recipe_id = rec_res.json()["id"]

    target_date = (datetime.now(UTC) + timedelta(days=2)).date()
    valid_time = datetime.combine(target_date, datetime.min.time().replace(hour=20, minute=0)).replace(tzinfo=UTC)
    success_res = client.post(
        "/api/v1/meal-plans",
        headers=auth_headers,
        json={
            "recipe_id": recipe_id,
            "planned_at": valid_time.isoformat(),
            "auto_add_missing_ingredients": False,
        },
    )
    assert success_res.status_code == 200
    data = success_res.json()
    assert data["recipe_id"] == recipe_id


def test_recipe_servings_scaling_and_instructions_patch(client, auth_headers):
    rec_res = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Pâtes carbo",
            "instructions": "Mélanger pâtes et lardons.",
            "servings": 2,
            "ingredients": [{"name": "Pâtes", "quantity": 150, "unit": "g"}],
        },
    )
    assert rec_res.status_code == 200
    recipe_id = rec_res.json()["id"]

    patch_res = client.patch(
        f"/api/v1/recipes/{recipe_id}",
        headers=auth_headers,
        json={
            "instructions": "Version authentique : guanciale et pecorino.",
            "servings": 4,
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["instructions"] == "Version authentique : guanciale et pecorino."
    assert updated["servings"] == 4


def test_recipe_tenant_isolation(client, auth_headers):
    # User 1 creates a recipe
    rec_res = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Secret User 1 Recipe",
            "instructions": "Top secret.",
            "servings": 1,
            "ingredients": [{"name": "Secret Spice", "quantity": 5, "unit": "g"}],
        },
    )
    assert rec_res.status_code == 200
    recipe_id = rec_res.json()["id"]

    # Register User 2
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@test.com",
            "password": "user2-pass-secure",
            "display_name": "User Two",
        },
    )
    assert reg_res.status_code == 201
    user2_token = reg_res.json()["token"]
    user2_headers = {"Authorization": f"Bearer {user2_token}"}

    # User 2 cannot access, cook, or add to groceries for User 1's recipe
    assert client.get(f"/api/v1/recipes/{recipe_id}", headers=user2_headers).status_code == 404
    assert client.post(f"/api/v1/recipes/{recipe_id}/confirm-cooked", headers=user2_headers).status_code == 404
    assert client.post(f"/api/v1/recipes/{recipe_id}/add-to-groceries", headers=user2_headers).status_code == 404


def test_delete_recipe_cascades_meal_plans_and_confirmations(client, auth_headers):
    # 1. Create a recipe with ingredients
    rec_res = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Risotto Saumon Test Cascade",
            "instructions": "Cuire et servir.",
            "servings": 2,
            "ingredients": [
                {"name": "Riz arborio", "quantity": 200, "unit": "g"},
                {"name": "Saumon frais", "quantity": 250, "unit": "g"},
            ],
        },
    )
    assert rec_res.status_code == 200
    recipe_id = rec_res.json()["id"]

    # 2. Plan a meal with this recipe
    plan_date = (datetime.now(UTC) + timedelta(days=3)).date()
    plan_time = datetime.combine(plan_date, datetime.min.time().replace(hour=19, minute=0)).replace(tzinfo=UTC)
    plan_res = client.post(
        "/api/v1/meal-plans",
        headers=auth_headers,
        json={
            "recipe_id": recipe_id,
            "planned_at": plan_time.isoformat(),
        },
    )
    assert plan_res.status_code == 200

    # 3. Confirm cook to create a MealPlanCookConfirmation
    cook_res = client.post(
        f"/api/v1/recipes/{recipe_id}/confirm-cooked",
        headers=auth_headers,
        json={"servings_override": 2},
    )
    assert cook_res.status_code == 200

    # 4. Deleting the recipe must succeed atomically without FK constraint errors
    del_res = client.delete(f"/api/v1/recipes/{recipe_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json() == {"ok": True, "deleted_id": recipe_id}

    # 5. Verify recipe is gone
    assert client.get(f"/api/v1/recipes/{recipe_id}", headers=auth_headers).status_code == 404


def test_recipe_cook_confirmation_saumon_frais_decrements_pantry(client, auth_headers):
    # 1. Create recipe with Saumon frais (250g)
    rec_res = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Pâtes crémeuses au saumon",
            "instructions": "Cuire les pâtes et le saumon.",
            "servings": 2,
            "ingredients": [
                {"name": "Saumon frais", "quantity": 250, "unit": "g", "note": "pavé"},
            ],
        },
    )
    assert rec_res.status_code == 200
    recipe_id = rec_res.json()["id"]

    # 2. Add stock in pantry: 250g Saumon frais
    pantry_res = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={
            "name": "Saumon frais",
            "quantity": 250,
            "unit": "g",
            "category": "Poisson",
            "location": "Réfrigérateur",
        },
    )
    assert pantry_res.status_code == 200
    pantry_id = pantry_res.json()["id"]

    # 3. Confirm cooked: exact deduction of 250g -> 0
    cook_res = client.post(
        f"/api/v1/recipes/{recipe_id}/confirm-cooked",
        headers=auth_headers,
        json={"servings_override": 2},
    )
    assert cook_res.status_code == 200
    assert cook_res.json()["missing_ingredients"] == []

    # Check pantry is at 0
    pantry_check = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    item = next(p for p in pantry_check if p["id"] == pantry_id)
    assert item["quantity"] == 0.0


