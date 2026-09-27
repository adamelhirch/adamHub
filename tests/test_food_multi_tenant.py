from datetime import date
from sqlmodel import Session, select

from app.models import GroceryItem, MealPlan, PantryItem, Recipe
from tests.conftest import register_user


def test_food_multi_tenant_isolation(client, test_engine):
    user_a = register_user(client, "alice@adamelhirch.com")
    user_b = register_user(client, "bob@adamelhirch.com")

    # 1. Groceries: Alice creates, Bob can't see or edit
    g_res = client.post("/api/v1/groceries", headers=user_a["headers"], json={"name": "Lait"})
    assert g_res.status_code == 200
    g_id = g_res.json()["id"]

    # Bob's grocery list should be empty
    bob_groceries = client.get("/api/v1/groceries", headers=user_b["headers"]).json()
    assert all(item["id"] != g_id for item in bob_groceries)

    # Bob cannot update Alice's grocery item
    bob_update = client.patch(f"/api/v1/groceries/{g_id}", headers=user_b["headers"], json={"checked": True})
    assert bob_update.status_code == 404

    # 2. Recipes: Alice creates, Bob cannot see or delete
    r_res = client.post("/api/v1/recipes", headers=user_a["headers"], json={"name": "Crêpes", "instructions": "Mélanger"})
    assert r_res.status_code == 200
    r_id = r_res.json()["id"]

    bob_recipes = client.get("/api/v1/recipes", headers=user_b["headers"]).json()
    assert all(r["id"] != r_id for r in bob_recipes)

    bob_del = client.delete(f"/api/v1/recipes/{r_id}", headers=user_b["headers"])
    assert bob_del.status_code == 404

    # 3. Pantry: Alice creates, Bob cannot see or consume
    p_res = client.post("/api/v1/pantry/items", headers=user_a["headers"], json={"name": "Sucre", "quantity": 1000, "unit": "g"})
    assert p_res.status_code == 200
    p_id = p_res.json()["id"]

    bob_pantry = client.get("/api/v1/pantry/items", headers=user_b["headers"]).json()
    assert all(p["id"] != p_id for p in bob_pantry)

    bob_consume = client.post(f"/api/v1/pantry/items/{p_id}/consume", headers=user_b["headers"], json={"amount": 100})
    assert bob_consume.status_code == 404

    # 4. Meal Plans: Two users can plan the same date and slot independently
    today = date.today().isoformat()
    mp_a = client.post(
        "/api/v1/meal-plans",
        headers=user_a["headers"],
        json={"planned_for": today, "slot": "dinner", "recipe_id": r_id},
    )
    assert mp_a.status_code == 200

    # Bob creates his own recipe to plan
    bob_r = client.post("/api/v1/recipes", headers=user_b["headers"], json={"name": "Pâtes", "instructions": "Cuire"}).json()["id"]
    mp_b = client.post(
        "/api/v1/meal-plans",
        headers=user_b["headers"],
        json={"planned_for": today, "slot": "dinner", "recipe_id": bob_r},
    )
    assert mp_b.status_code == 200
