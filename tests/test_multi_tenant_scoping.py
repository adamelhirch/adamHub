from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import GroceryItem, MealPlan, PantryItem, Recipe

from tests.conftest import OWNER_EMAIL, register_user


def _db_user_id(test_engine, model, row_id: int) -> int | None:
    with Session(test_engine) as session:
        return session.get(model, row_id).user_id


def _create_recipe_for(client, headers, name="Poulet", servings=1) -> int:
    response = client.post(
        "/api/v1/recipes",
        headers=headers,
        json={"name": name, "instructions": "Cuire", "servings": servings},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


# ── Create auto-scopes to the authenticated user; client can't override ──────

def test_creating_resources_auto_assigns_user_id(client, test_engine, jwt_headers, owner_headers):
    user = client.get("/api/v1/auth/me", headers=jwt_headers).json()

    grocery_id = client.post("/api/v1/groceries", headers=jwt_headers, json={"name": "Lait"}).json()["id"]
    pantry_id = client.post("/api/v1/pantry/items", headers=jwt_headers, json={"name": "Farine"}).json()["id"]
    recipe_id = _create_recipe_for(client, jwt_headers)
    meal_plan = client.post(
        "/api/v1/meal-plans",
        headers=jwt_headers,
        json={"planned_for": date.today().isoformat(), "slot": "dinner", "recipe_id": recipe_id, "auto_add_missing_ingredients": False},
    )
    assert meal_plan.status_code == 200, meal_plan.text
    meal_plan_id = meal_plan.json()["id"]

    assert _db_user_id(test_engine, GroceryItem, grocery_id) == user["id"]
    assert _db_user_id(test_engine, PantryItem, pantry_id) == user["id"]
    assert _db_user_id(test_engine, Recipe, recipe_id) == user["id"]
    assert _db_user_id(test_engine, MealPlan, meal_plan_id) == user["id"]


def test_client_cannot_override_user_id_on_create(client, test_engine, jwt_headers):
    user = client.get("/api/v1/auth/me", headers=jwt_headers).json()
    other = register_user(client, "other@adamelhirch.com")["user"]

    # user_id is not part of any create schema and is silently ignored.
    grocery_id = client.post(
        "/api/v1/groceries",
        headers=jwt_headers,
        json={"name": "Lait", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, GroceryItem, grocery_id) == user["id"]

    recipe_id = client.post(
        "/api/v1/recipes",
        headers=jwt_headers,
        json={"name": "Omelette", "instructions": "Cuire", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, Recipe, recipe_id) == user["id"]

    pantry_id = client.post(
        "/api/v1/pantry/items",
        headers=jwt_headers,
        json={"name": "Farine", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, PantryItem, pantry_id) == user["id"]


def test_client_cannot_reassign_user_id_on_update(client, test_engine, jwt_headers):
    user = client.get("/api/v1/auth/me", headers=jwt_headers).json()
    other = register_user(client, "other2@adamelhirch.com")["user"]

    grocery_id = client.post("/api/v1/groceries", headers=jwt_headers, json={"name": "Lait"}).json()["id"]
    updated = client.patch(
        f"/api/v1/groceries/{grocery_id}",
        headers=jwt_headers,
        json={"checked": True, "user_id": other["id"]},
    )
    assert updated.status_code == 200
    assert _db_user_id(test_engine, GroceryItem, grocery_id) == user["id"]


# ── Cross-user access is 404 everywhere (no existence leak) ──────────────────

def _seed_resources_as_user_a(client, headers):
    grocery_id = client.post("/api/v1/groceries", headers=headers, json={"name": "Lait"}).json()["id"]
    pantry_id = client.post("/api/v1/pantry/items", headers=headers, json={"name": "Farine"}).json()["id"]
    recipe_id = _create_recipe_for(client, headers)
    meal_plan = client.post(
        "/api/v1/meal-plans",
        headers=headers,
        json={"planned_for": date.today().isoformat(), "slot": "dinner", "recipe_id": recipe_id, "auto_add_missing_ingredients": False},
    )
    return {
        "grocery": grocery_id,
        "pantry": pantry_id,
        "recipe": recipe_id,
        "meal_plan": meal_plan.json()["id"],
    }


def test_user_cannot_read_another_users_resources(client, jwt_headers):
    user_b = register_user(client, "reader-b@adamelhirch.com")
    user_a = register_user(client, "reader-a@adamelhirch.com")
    ids = _seed_resources_as_user_a(client, user_a["headers"])

    assert client.get(f"/api/v1/groceries/{ids['grocery']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/pantry/items/{ids['pantry']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/recipes/{ids['recipe']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/meal-plans/{ids['meal_plan']}", headers=user_b["headers"]).status_code == 404

    # Lists only expose the caller's own rows.
    assert client.get("/api/v1/groceries", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/pantry/items", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/recipes", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/meal-plans", headers=user_b["headers"]).json() == []


def test_user_cannot_modify_another_users_resources(client, jwt_headers):
    user_b = register_user(client, "modifier-b@adamelhirch.com")
    user_a = register_user(client, "modifier-a@adamelhirch.com")
    ids = _seed_resources_as_user_a(client, user_a["headers"])

    assert client.patch(f"/api/v1/groceries/{ids['grocery']}", headers=user_b["headers"], json={"checked": True}).status_code == 404
    assert client.patch(f"/api/v1/pantry/items/{ids['pantry']}", headers=user_b["headers"], json={"quantity": 0}).status_code == 404
    assert client.patch(f"/api/v1/recipes/{ids['recipe']}", headers=user_b["headers"], json={"name": "Hacked"}).status_code == 404
    assert client.patch(f"/api/v1/meal-plans/{ids['meal_plan']}", headers=user_b["headers"], json={"note": "Hacked"}).status_code == 404


def test_user_cannot_delete_or_act_on_another_users_resources(client, jwt_headers):
    user_b = register_user(client, "deleter-b@adamelhirch.com")
    user_a = register_user(client, "deleter-a@adamelhirch.com")
    ids = _seed_resources_as_user_a(client, user_a["headers"])

    assert client.delete(f"/api/v1/groceries/{ids['grocery']}", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/pantry/items/{ids['pantry']}", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/recipes/{ids['recipe']}", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/meal-plans/{ids['meal_plan']}", headers=user_b["headers"]).status_code == 404

    assert client.post(f"/api/v1/pantry/items/{ids['pantry']}/consume", headers=user_b["headers"], json={"amount": 1}).status_code == 404
    assert client.post(f"/api/v1/recipes/{ids['recipe']}/confirm-cooked", headers=user_b["headers"], json={}).status_code == 404
    assert client.post(f"/api/v1/recipes/{ids['recipe']}/unconfirm-cooked", headers=user_b["headers"]).status_code == 404
    assert client.post(f"/api/v1/meal-plans/{ids['meal_plan']}/sync-groceries", headers=user_b["headers"]).status_code == 404
    assert client.post(f"/api/v1/meal-plans/{ids['meal_plan']}/confirm-cooked", headers=user_b["headers"], json={}).status_code == 404
    assert client.post(f"/api/v1/meal-plans/{ids['meal_plan']}/unconfirm-cooked", headers=user_b["headers"]).status_code == 404


# ── Legacy API-key path resolves to the owner user ───────────────────────────

def test_legacy_api_key_scopes_to_owner_user(client, test_engine, auth_headers, owner_headers):
    # A legacy API-key request creates data scoped to the owner user.
    grocery_id = client.post("/api/v1/groceries", headers=auth_headers, json={"name": "Pain"}).json()["id"]
    recipe_id = _create_recipe_for(client, auth_headers, name="Pates")
    meal_plan = client.post(
        "/api/v1/meal-plans",
        headers=auth_headers,
        json={"planned_for": date.today().isoformat(), "slot": "lunch", "recipe_id": recipe_id, "auto_add_missing_ingredients": False},
    )
    assert meal_plan.status_code == 200, meal_plan.text
    meal_plan_id = meal_plan.json()["id"]

    # The owner (via JWT) sees everything the legacy key created.
    assert [i["id"] for i in client.get("/api/v1/groceries", headers=owner_headers).json()] == [grocery_id]
    assert [i["id"] for i in client.get("/api/v1/meal-plans", headers=owner_headers).json()] == [meal_plan_id]

    # A freshly-registered JWT user sees none of it.
    stranger = register_user(client, "stranger@adamelhirch.com")
    assert client.get("/api/v1/groceries", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/meal-plans", headers=stranger["headers"]).json() == []


def test_legacy_api_key_requires_owner_email_config(client, test_engine, auth_headers, monkeypatch):
    # Without ADAMHUB_OWNER_EMAIL the API-key path fails loudly instead of
    # silently creating unscoped rows.
    monkeypatch.setenv("ADAMHUB_OWNER_EMAIL", "")
    from app.core.config import get_settings
    get_settings.cache_clear()
    try:
        response = client.post("/api/v1/groceries", headers=auth_headers, json={"name": "Pain"})
        assert response.status_code == 500
        assert "ADAMHUB_OWNER_EMAIL" in response.json()["detail"]
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


# ── Meal-plan slot rule is per-user and ignores unrelated calendar items ──────

def test_two_users_can_plan_the_same_date_and_slot(client):
    user_a = register_user(client, "slot-a@adamelhirch.com")
    user_b = register_user(client, "slot-b@adamelhirch.com")
    target = (date.today() + timedelta(days=2)).isoformat()

    recipe_a = _create_recipe_for(client, user_a["headers"], name="Plat A")
    recipe_b = _create_recipe_for(client, user_b["headers"], name="Plat B")

    plan_a = client.post(
        "/api/v1/meal-plans",
        headers=user_a["headers"],
        json={"planned_for": target, "slot": "dinner", "recipe_id": recipe_a, "auto_add_missing_ingredients": False},
    )
    plan_b = client.post(
        "/api/v1/meal-plans",
        headers=user_b["headers"],
        json={"planned_for": target, "slot": "dinner", "recipe_id": recipe_b, "auto_add_missing_ingredients": False},
    )
    assert plan_a.status_code == 200, plan_a.text
    assert plan_b.status_code == 200, plan_b.text


def test_same_user_cannot_plan_same_date_and_slot_twice(client):
    user = register_user(client, "double-slot@adamelhirch.com")
    target = (date.today() + timedelta(days=3)).isoformat()
    recipe_id = _create_recipe_for(client, user["headers"])

    first = client.post(
        "/api/v1/meal-plans",
        headers=user["headers"],
        json={"planned_for": target, "slot": "dinner", "recipe_id": recipe_id, "auto_add_missing_ingredients": False},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/v1/meal-plans",
        headers=user["headers"],
        json={"planned_for": target, "slot": "dinner", "recipe_id": recipe_id, "auto_add_missing_ingredients": False},
    )
    assert second.status_code == 409
    assert "déjà" in second.json()["detail"].lower()

    # A different slot on the same day is still fine.
    lunch = client.post(
        "/api/v1/meal-plans",
        headers=user["headers"],
        json={"planned_for": target, "slot": "lunch", "recipe_id": recipe_id, "auto_add_missing_ingredients": False},
    )
    assert lunch.status_code == 200, lunch.text


def test_meal_plan_not_blocked_by_unrelated_task_at_same_time(client):
    user = register_user(client, "meal-not-blocked@adamelhirch.com")
    recipe_id = _create_recipe_for(client, user["headers"])

    # An unrelated one-shot task occupies the exact same time window.
    planned_for = (date.today() + timedelta(days=1)).isoformat()
    task = client.post(
        "/api/v1/tasks",
        headers=user["headers"],
        json={"title": "Réunion", "due_at": f"{planned_for}T12:30:00Z", "estimated_minutes": 30},
    )
    assert task.status_code == 200, task.text

    # Planning lunch for that same slot must NOT be blocked by the task.
    meal_plan = client.post(
        "/api/v1/meal-plans",
        headers=user["headers"],
        json={"planned_for": planned_for, "slot": "lunch", "recipe_id": recipe_id, "auto_add_missing_ingredients": False},
    )
    assert meal_plan.status_code == 200, meal_plan.text


def test_meal_plan_not_blocked_by_unrelated_event_at_same_time(client):
    user = register_user(client, "meal-not-blocked-event@adamelhirch.com")
    recipe_id = _create_recipe_for(client, user["headers"])
    planned_for = (date.today() + timedelta(days=1)).isoformat()

    event = client.post(
        "/api/v1/events",
        headers=user["headers"],
        json={
            "title": "Appel",
            "start_at": f"{planned_for}T19:30:00Z",
            "end_at": f"{planned_for}T20:00:00Z",
        },
    )
    assert event.status_code == 200, event.text

    meal_plan = client.post(
        "/api/v1/meal-plans",
        headers=user["headers"],
        json={"planned_for": planned_for, "slot": "dinner", "recipe_id": recipe_id, "auto_add_missing_ingredients": False},
    )
    assert meal_plan.status_code == 200, meal_plan.text


# ── Supermarket connection ownership (#58) ───────────────────────────────────

def _import_connection(client, headers, label="Mon drive", store="intermarche") -> int:
    response = client.post(
        "/api/v1/supermarket/connections/import",
        headers=headers,
        json={"store": store, "label": label, "cookies": [{"name": "session", "value": "abc"}], "activate": True},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_connection_owned_by_another_user_is_404(client, jwt_headers):
    owner = register_user(client, "conn-owner@adamelhirch.com")
    intruder = register_user(client, "conn-intruder@adamelhirch.com")

    connection_id = _import_connection(client, owner["headers"])

    # Lists are scoped: the intruder never sees the owner's connection.
    assert client.get("/api/v1/supermarket/connections", headers=intruder["headers"]).json() == []

    # Activate / delete of another user's connection are 404 (no existence leak).
    assert client.put(
        f"/api/v1/supermarket/connections/{connection_id}/activate", headers=intruder["headers"]
    ).status_code == 404
    assert client.delete(
        f"/api/v1/supermarket/connections/{connection_id}", headers=intruder["headers"]
    ).status_code == 404

    # The owner can still activate and delete it.
    assert client.put(
        f"/api/v1/supermarket/connections/{connection_id}/activate", headers=owner["headers"]
    ).status_code == 200
    assert client.delete(
        f"/api/v1/supermarket/connections/{connection_id}", headers=owner["headers"]
    ).status_code == 200


def test_legacy_null_connection_visible_to_owner_only(client, test_engine, auth_headers, owner_headers):
    # A pre-scoping connection has user_id = NULL.
    from app.models import SupermarketConnection, SupermarketStore
    from app.core.crypto import encrypt_text

    with Session(test_engine) as session:
        row = SupermarketConnection(
            user_id=None,
            store=SupermarketStore.INTERMARCHE,
            label="Legacy drive",
            cookies_encrypted=encrypt_text('[{"name": "session", "value": "abc"}]'),
            is_active=True,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        legacy_id = row.id

    # The owner (legacy API-key path AND owner JWT) still sees and operates it.
    assert [c["id"] for c in client.get("/api/v1/supermarket/connections", headers=auth_headers).json()] == [legacy_id]
    assert [c["id"] for c in client.get("/api/v1/supermarket/connections", headers=owner_headers).json()] == [legacy_id]
    assert client.put(
        f"/api/v1/supermarket/connections/{legacy_id}/activate", headers=auth_headers
    ).status_code == 200

    # A non-owner JWT user cannot see or touch the legacy connection.
    stranger = register_user(client, "legacy-stranger@adamelhirch.com")
    assert client.get("/api/v1/supermarket/connections", headers=stranger["headers"]).json() == []
    assert client.put(
        f"/api/v1/supermarket/connections/{legacy_id}/activate", headers=stranger["headers"]
    ).status_code == 404
    assert client.delete(
        f"/api/v1/supermarket/connections/{legacy_id}", headers=stranger["headers"]
    ).status_code == 404


# ── Backfill script: dry-run vs commit ───────────────────────────────────────

def test_backfill_dry_run_vs_commit(client, test_engine, owner_id):
    from scripts.backfill_owner_tenant import backfill, count_null_rows

    with Session(test_engine) as session:
        session.add(GroceryItem(name="Lait", user_id=None))
        session.add(GroceryItem(name="Pain", user_id=None))
        session.add(PantryItem(name="Farine", user_id=None))
        recipe = Recipe(name="Omelette", instructions="Cuire", user_id=None)
        session.add(recipe)
        session.flush()
        session.add(MealPlan(recipe_id=recipe.id, user_id=None))
        session.commit()

    with Session(test_engine) as session:
        assert count_null_rows(session) == {
            "groceryitem": 2,
            "pantryitem": 1,
            "recipe": 1,
            "mealplan": 1,
        }
        dry = backfill(session, owner_id, commit=False)
        assert dry["commit"] is False
        assert dry["updated"] == {"groceryitem": 0, "pantryitem": 0, "recipe": 0, "mealplan": 0}
        assert count_null_rows(session) == {
            "groceryitem": 2,
            "pantryitem": 1,
            "recipe": 1,
            "mealplan": 1,
        }

    with Session(test_engine) as session:
        committed = backfill(session, owner_id, commit=True)
        assert committed["commit"] is True
        assert committed["updated"] == {"groceryitem": 2, "pantryitem": 1, "recipe": 1, "mealplan": 1}
        assert count_null_rows(session) == {
            "groceryitem": 0,
            "pantryitem": 0,
            "recipe": 0,
            "mealplan": 0,
        }

    # Idempotent: a second run reports zero NULL rows to claim.
    with Session(test_engine) as session:
        again = backfill(session, owner_id, commit=True)
        assert again["updated"] == {"groceryitem": 0, "pantryitem": 0, "recipe": 0, "mealplan": 0}

    # The claimed rows now belong to the owner and show up for the owner.
    with Session(test_engine) as session:
        assert session.exec(select(GroceryItem)).all()[0].user_id == owner_id


def test_backfill_rejects_unknown_owner(client, test_engine):
    from scripts.backfill_owner_tenant import resolve_owner

    with Session(test_engine) as session:
        assert resolve_owner(session, "does-not-exist@adamelhirch.com") is None
        assert resolve_owner(session, OWNER_EMAIL) is not None
