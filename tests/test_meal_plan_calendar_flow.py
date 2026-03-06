from datetime import date


def test_meal_confirm_unconfirm_and_calendar_completion(client, auth_headers):
    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Egg", "quantity": 5, "unit": "item", "min_quantity": 0},
    )
    assert pantry.status_code == 200
    pantry_id = pantry.json()["id"]

    recipe = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Omelette",
            "instructions": "Cook eggs",
            "servings": 1,
            "ingredients": [{"name": "Egg", "quantity": 2, "unit": "item"}],
        },
    )
    assert recipe.status_code == 200
    recipe_id = recipe.json()["id"]

    planned_for = date.today().isoformat()
    meal_plan = client.post(
        "/api/v1/meal-plans",
        headers=auth_headers,
        json={
            "planned_for": planned_for,
            "slot": "dinner",
            "recipe_id": recipe_id,
            "auto_add_missing_ingredients": False,
        },
    )
    assert meal_plan.status_code == 200
    meal_plan_id = meal_plan.json()["id"]

    confirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/confirm-cooked", headers=auth_headers, json={"note": "done"})
    assert confirm.status_code == 200
    assert confirm.json()["already_confirmed"] is False

    pantry_rows = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    egg_row = next(row for row in pantry_rows if row["id"] == pantry_id)
    assert egg_row["quantity"] == 3.0

    confirm_again = client.post(f"/api/v1/meal-plans/{meal_plan_id}/confirm-cooked", headers=auth_headers, json={})
    assert confirm_again.status_code == 200
    assert confirm_again.json()["already_confirmed"] is True
    egg_row_after_second_confirm = next(row for row in client.get("/api/v1/pantry/items", headers=auth_headers).json() if row["id"] == pantry_id)
    assert egg_row_after_second_confirm["quantity"] == 3.0

    sync = client.post("/api/v1/calendar/sync", headers=auth_headers)
    assert sync.status_code == 200
    calendar_rows = client.get(
        "/api/v1/calendar/items",
        headers=auth_headers,
        params={"include_completed": True, "limit": 500},
    )
    assert calendar_rows.status_code == 200
    meal_item = next(
        row
        for row in calendar_rows.json()
        if row["source"] == "meal_plan" and row["source_ref_id"] == meal_plan_id
    )
    assert meal_item["completed"] is True

    unconfirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/unconfirm-cooked", headers=auth_headers)
    assert unconfirm.status_code == 200
    assert unconfirm.json()["already_unconfirmed"] is False

    egg_row_after_unconfirm = next(row for row in client.get("/api/v1/pantry/items", headers=auth_headers).json() if row["id"] == pantry_id)
    assert egg_row_after_unconfirm["quantity"] == 5.0

    unconfirm_again = client.post(f"/api/v1/meal-plans/{meal_plan_id}/unconfirm-cooked", headers=auth_headers)
    assert unconfirm_again.status_code == 200
    assert unconfirm_again.json()["already_unconfirmed"] is True

    sync_after = client.post("/api/v1/calendar/sync", headers=auth_headers)
    assert sync_after.status_code == 200
    calendar_rows_after = client.get(
        "/api/v1/calendar/items",
        headers=auth_headers,
        params={"include_completed": True, "limit": 500},
    )
    meal_item_after = next(
        row
        for row in calendar_rows_after.json()
        if row["source"] == "meal_plan" and row["source_ref_id"] == meal_plan_id
    )
    assert meal_item_after["completed"] is False
