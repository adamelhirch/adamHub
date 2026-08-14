from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import PantryItem


def _pantry_qty(client, auth_headers, name: str) -> float:
    rows = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    return next(row for row in rows if row["name"] == name)["quantity"]


def _create_pantry(client, auth_headers, name: str, quantity: float, unit: str = "item") -> int:
    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": name, "quantity": quantity, "unit": unit, "min_quantity": 0},
    )
    assert pantry.status_code == 200
    return pantry.json()["id"]


def _create_recipe(client, auth_headers, name: str, ingredients: list[dict], servings: int = 1) -> int:
    recipe = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={"name": name, "instructions": "Cuire", "servings": servings, "ingredients": ingredients},
    )
    assert recipe.status_code == 200
    return recipe.json()["id"]


def _create_meal_plan(client, auth_headers, recipe_id: int, **overrides) -> int:
    payload = {
        "planned_for": date.today().isoformat(),
        "slot": "dinner",
        "recipe_id": recipe_id,
        "auto_add_missing_ingredients": False,
    }
    payload.update(overrides)
    meal_plan = client.post("/api/v1/meal-plans", headers=auth_headers, json=payload)
    assert meal_plan.status_code == 200
    return meal_plan.json()["id"]


def test_meal_confirm_unconfirm_and_calendar_completion(client, auth_headers):
    pantry_id = _create_pantry(client, auth_headers, "Egg", 5)
    recipe_id = _create_recipe(client, auth_headers, "Omelette", [{"name": "Egg", "quantity": 2, "unit": "item"}])
    meal_plan_id = _create_meal_plan(client, auth_headers, recipe_id)

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


def test_edit_confirmed_meal_plan_restores_pantry_stock(client, auth_headers):
    _create_pantry(client, auth_headers, "Egg", 5)
    recipe_id = _create_recipe(client, auth_headers, "Omelette", [{"name": "Egg", "quantity": 2, "unit": "item"}])
    meal_plan_id = _create_meal_plan(client, auth_headers, recipe_id)

    confirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/confirm-cooked", headers=auth_headers, json={"note": "fait"})
    assert confirm.status_code == 200
    assert _pantry_qty(client, auth_headers, "Egg") == 3.0

    # Editing portions invalidates the confirmation and must restore the consumed stock.
    edit = client.patch(f"/api/v1/meal-plans/{meal_plan_id}", headers=auth_headers, json={"servings_override": 2})
    assert edit.status_code == 200
    assert edit.json()["cooked"] is False
    assert _pantry_qty(client, auth_headers, "Egg") == 5.0

    # Re-confirming then editing the date must restore stock again.
    re_confirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/confirm-cooked", headers=auth_headers, json={})
    assert re_confirm.status_code == 200
    assert re_confirm.json()["already_confirmed"] is False
    assert _pantry_qty(client, auth_headers, "Egg") == 1.0  # 2 portions x 2 eggs

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    edit_date = client.patch(f"/api/v1/meal-plans/{meal_plan_id}", headers=auth_headers, json={"planned_for": tomorrow})
    assert edit_date.status_code == 200
    assert edit_date.json()["cooked"] is False
    assert _pantry_qty(client, auth_headers, "Egg") == 5.0


def test_confirm_unconfirm_cycle_preserves_pantry_lots(client, auth_headers, test_engine, owner_id):
    now = datetime.now(timezone.utc)
    with Session(test_engine) as session:
        session.add(PantryItem(name="Farine", quantity=300, unit="g", min_quantity=0, updated_at=now - timedelta(days=2), user_id=owner_id))
        session.add(PantryItem(name="Farine", quantity=200, unit="g", min_quantity=0, updated_at=now - timedelta(days=1), user_id=owner_id))
        session.commit()

    recipe_id = _create_recipe(client, auth_headers, "Crepes", [{"name": "Farine", "quantity": 400, "unit": "g"}])
    meal_plan_id = _create_meal_plan(client, auth_headers, recipe_id)

    def flour_rows():
        rows = client.get("/api/v1/pantry/items", headers=auth_headers).json()
        return sorted([row for row in rows if row["name"] == "Farine"], key=lambda row: row["id"])

    confirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/confirm-cooked", headers=auth_headers, json={})
    assert confirm.status_code == 200
    first, second = flour_rows()
    assert (first["quantity"], second["quantity"]) == (0.0, 100.0)

    # Confirm -> unconfirm -> confirm -> unconfirm must land back on the exact
    # per-row quantities each time (no redistribution or orphaned metadata).
    for _ in range(2):
        unconfirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/unconfirm-cooked", headers=auth_headers)
        assert unconfirm.status_code == 200
        assert unconfirm.json()["already_unconfirmed"] is False
        first, second = flour_rows()
        assert (first["quantity"], second["quantity"]) == (300.0, 200.0)

        confirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/confirm-cooked", headers=auth_headers, json={})
        assert confirm.status_code == 200
        assert confirm.json()["already_confirmed"] is False
        first, second = flour_rows()
        assert (first["quantity"], second["quantity"]) == (0.0, 100.0)


def test_unconfirm_legacy_confirmation_shape_restores_stock(client, auth_headers, test_engine):
    from app.models import MealPlanCookConfirmation

    _create_pantry(client, auth_headers, "Egg", 5)
    recipe_id = _create_recipe(client, auth_headers, "Omelette", [{"name": "Egg", "quantity": 2, "unit": "item"}])
    meal_plan_id = _create_meal_plan(client, auth_headers, recipe_id)

    # Simulate a confirmation created before per-lot tracking (aggregate list,
    # no pantry_item_id) with the pantry already consumed.
    with Session(test_engine) as session:
        pantry = session.exec(select(PantryItem)).one()
        pantry.quantity = 3.0
        session.add(pantry)
        confirmation = MealPlanCookConfirmation(
            meal_plan_id=meal_plan_id,
            note="old shape",
            pantry_consumption=[
                {"name": "Egg", "unit": "item", "required_quantity": 2.0, "consumed_quantity": 2.0, "missing_quantity": 0.0}
            ],
        )
        session.add(confirmation)
        session.commit()

    unconfirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/unconfirm-cooked", headers=auth_headers)
    assert unconfirm.status_code == 200
    assert unconfirm.json()["already_unconfirmed"] is False
    assert _pantry_qty(client, auth_headers, "Egg") == 5.0


def test_skill_meal_plan_update_restores_stock(client, auth_headers):
    _create_pantry(client, auth_headers, "Egg", 5)
    recipe_id = _create_recipe(client, auth_headers, "Omelette", [{"name": "Egg", "quantity": 2, "unit": "item"}])
    meal_plan_id = _create_meal_plan(client, auth_headers, recipe_id)

    confirm = client.post(f"/api/v1/meal-plans/{meal_plan_id}/confirm-cooked", headers=auth_headers, json={})
    assert confirm.status_code == 200
    assert _pantry_qty(client, auth_headers, "Egg") == 3.0

    updated = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "meal_plan.update", "input": {"meal_plan_id": meal_plan_id, "servings_override": 2}},
    )
    assert updated.status_code == 200
    assert updated.json()["ok"] is True
    assert updated.json()["data"]["meal_plan"]["cooked"] is False
    assert _pantry_qty(client, auth_headers, "Egg") == 5.0


def test_recipe_confirm_cooked_idempotent_and_unconfirm(client, auth_headers):
    pantry_id = _create_pantry(client, auth_headers, "Riz", 4)
    recipe_id = _create_recipe(client, auth_headers, "Riz saute", [{"name": "Riz", "quantity": 2, "unit": "item"}])

    def riz_qty() -> float:
        rows = client.get("/api/v1/pantry/items", headers=auth_headers).json()
        return next(row for row in rows if row["id"] == pantry_id)["quantity"]

    first = client.post(f"/api/v1/recipes/{recipe_id}/confirm-cooked", headers=auth_headers, json={"note": "cuit"})
    assert first.status_code == 200
    assert first.json()["already_confirmed"] is False
    assert first.json()["meal_plan_id"] > 0
    assert riz_qty() == 2.0

    second = client.post(f"/api/v1/recipes/{recipe_id}/confirm-cooked", headers=auth_headers, json={})
    assert second.status_code == 200
    assert second.json()["already_confirmed"] is True
    assert riz_qty() == 2.0  # idempotent: no double consumption

    unconfirm = client.post(f"/api/v1/recipes/{recipe_id}/unconfirm-cooked", headers=auth_headers)
    assert unconfirm.status_code == 200
    assert unconfirm.json()["already_unconfirmed"] is False
    assert riz_qty() == 4.0

    unconfirm_again = client.post(f"/api/v1/recipes/{recipe_id}/unconfirm-cooked", headers=auth_headers)
    assert unconfirm_again.status_code == 200
    assert unconfirm_again.json()["already_unconfirmed"] is True


def test_skill_recipe_confirm_unconfirm_cooked(client, auth_headers):
    _create_pantry(client, auth_headers, "Riz", 4)
    recipe_id = _create_recipe(client, auth_headers, "Riz saute", [{"name": "Riz", "quantity": 2, "unit": "item"}])

    confirmed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.confirm_cooked", "input": {"recipe_id": recipe_id}},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["already_confirmed"] is False
    assert _pantry_qty(client, auth_headers, "Riz") == 2.0

    again = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.confirm_cooked", "input": {"recipe_id": recipe_id}},
    )
    assert again.status_code == 200
    assert again.json()["data"]["already_confirmed"] is True
    assert _pantry_qty(client, auth_headers, "Riz") == 2.0

    unconfirmed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.unconfirm_cooked", "input": {"recipe_id": recipe_id}},
    )
    assert unconfirmed.status_code == 200
    assert unconfirmed.json()["data"]["already_unconfirmed"] is False
    assert _pantry_qty(client, auth_headers, "Riz") == 4.0


def test_recipe_confirm_cooked_marker_plan_hidden_from_meal_plans_and_calendar(client, auth_headers):
    _create_pantry(client, auth_headers, "Riz", 4)
    recipe_id = _create_recipe(client, auth_headers, "Riz saute", [{"name": "Riz", "quantity": 2, "unit": "item"}])
    real_plan_id = _create_meal_plan(client, auth_headers, recipe_id)

    confirm = client.post(f"/api/v1/recipes/{recipe_id}/confirm-cooked", headers=auth_headers, json={})
    assert confirm.status_code == 200
    marker_plan_id = confirm.json()["meal_plan_id"]
    assert marker_plan_id != real_plan_id

    plans = client.get("/api/v1/meal-plans", headers=auth_headers, params={"limit": 400}).json()
    plan_ids = [plan["id"] for plan in plans]
    assert marker_plan_id not in plan_ids
    assert real_plan_id in plan_ids

    skill_list = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "meal_plan.list", "input": {"limit": 400}},
    )
    assert skill_list.status_code == 200
    skill_plan_ids = [plan["id"] for plan in skill_list.json()["data"]["meal_plans"]]
    assert marker_plan_id not in skill_plan_ids
    assert real_plan_id in skill_plan_ids

    sync = client.post("/api/v1/calendar/sync", headers=auth_headers)
    assert sync.status_code == 200
    calendar_rows = client.get(
        "/api/v1/calendar/items",
        headers=auth_headers,
        params={"include_completed": True, "limit": 500},
    )
    assert calendar_rows.status_code == 200
    meal_ref_ids = [row["source_ref_id"] for row in calendar_rows.json() if row["source"] == "meal_plan"]
    assert marker_plan_id not in meal_ref_ids
    assert real_plan_id in meal_ref_ids


def test_recipe_confirm_cooked_refreshes_marker_plan_timestamp(client, auth_headers, test_engine):
    from app.models import MealPlan

    _create_pantry(client, auth_headers, "Riz", 4)
    recipe_id = _create_recipe(client, auth_headers, "Riz saute", [{"name": "Riz", "quantity": 2, "unit": "item"}])

    client.post(f"/api/v1/recipes/{recipe_id}/confirm-cooked", headers=auth_headers, json={})
    client.post(f"/api/v1/recipes/{recipe_id}/unconfirm-cooked", headers=auth_headers)

    # Backdate the marker plan to simulate a stale plan from a long-ago cook.
    stale = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    with Session(test_engine) as session:
        plan = session.exec(select(MealPlan).where(MealPlan.note == "recipe.confirm_cooked")).one()
        plan.planned_at = stale
        plan.planned_for = stale.date()
        session.add(plan)
        session.commit()

    # Re-confirm after an unconfirm cycle: the reused marker plan's planned_at must
    # track the current cook instead of the stale one.
    client.post(f"/api/v1/recipes/{recipe_id}/confirm-cooked", headers=auth_headers, json={})

    with Session(test_engine) as session:
        plan = session.exec(select(MealPlan).where(MealPlan.note == "recipe.confirm_cooked")).one()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        assert abs((now - plan.planned_at).total_seconds()) < 5
        assert plan.planned_for == now.date()


def test_store_backed_recipe_ingredients_sync_to_groceries(client, auth_headers, test_engine):
    from app.models import SupermarketSearchCache, SupermarketStore
    from app.services.store_catalog import upsert_search_cache

    cache = upsert_search_cache(
        Session(test_engine),
        SupermarketStore.INTERMARCHE,
        [
            {
                "store": SupermarketStore.INTERMARCHE,
                "query": "poulet",
                "external_id": "chicken-001",
                "name": "Aiguillettes de poulet",
                "brand": "Le Gaulois",
                "category": "Volaille",
                "packaging": "la barquette de 500 g",
                "price_amount": 4.89,
                "price_text": "4,89 €",
                "image_url": "https://img.test/chicken-001.png",
                "product_url": "https://shop.test/chicken-001",
                "payload_json": {},
            }
        ],
    )[0]
    assert isinstance(cache, SupermarketSearchCache)

    recipe = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Poulet sauce soja",
            "instructions": "Cook the chicken",
            "servings": 2,
            "ingredients": [
                {
                    "name": "Aiguillettes de poulet",
                    "quantity": 1,
                    "unit": "item",
                    "cache_id": cache.id,
                    # Fabricated store metadata must be ignored in favour of the
                    # server-side cache resolution.
                    "store": "carrefour",
                    "store_label": "Fabricated",
                    "external_id": "fabricated-999",
                    "packaging": "fabricated packaging",
                    "price_text": "999,99 €",
                    "product_url": "https://evil.test/fake",
                    "image_url": "https://evil.test/fake.png",
                }
            ],
        },
    )
    assert recipe.status_code == 200
    recipe_id = recipe.json()["id"]
    ingredient = recipe.json()["ingredients"][0]
    assert ingredient["store"] == "intermarche"
    assert ingredient["store_label"] == "Intermarché"
    assert ingredient["external_id"] == "chicken-001"
    assert ingredient["packaging"] == "la barquette de 500 g"
    assert ingredient["price_text"] == "4,89 €"
    assert ingredient["product_url"] == "https://shop.test/chicken-001"
    assert ingredient["image_url"] == "https://img.test/chicken-001.png"
    assert ingredient["category"] == "Volaille"

    meal_plan_id = _create_meal_plan(client, auth_headers, recipe_id)

    sync = client.post(f"/api/v1/meal-plans/{meal_plan_id}/sync-groceries", headers=auth_headers)
    assert sync.status_code == 200
    assert sync.json()["created_grocery_items"] == 1

    groceries = client.get("/api/v1/groceries", headers=auth_headers, params={"checked": False})
    assert groceries.status_code == 200
    grocery = next(item for item in groceries.json() if item["name"] == "Aiguillettes de poulet")
    assert grocery["store_label"] == "Intermarché"
    assert grocery["external_id"] == "chicken-001"
    assert grocery["packaging"] == "la barquette de 500 g"
    assert grocery["price_text"] == "4,89 €"
    assert grocery["product_url"] == "https://shop.test/chicken-001"


def test_visible_meal_plans_owns_marker_exclusion(test_engine, owner_id):
    from app.models import MealPlan, MealSlot, Recipe
    from app.services.meal_planning import RECIPE_CONFIRM_MARKER, visible_meal_plans

    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).replace(hour=19, minute=30)
    with Session(test_engine) as session:
        recipe = Recipe(name="Riz", instructions="Cuire", servings=1, user_id=owner_id)
        session.add(recipe)
        session.commit()
        session.refresh(recipe)

        session.add(MealPlan(user_id=owner_id, planned_at=now, planned_for=now.date(), slot=MealSlot.DINNER, recipe_id=recipe.id, note="real plan"))
        session.add(MealPlan(user_id=owner_id, planned_at=yesterday, planned_for=yesterday.date(), slot=MealSlot.DINNER, recipe_id=recipe.id, note="yesterday plan"))
        session.add(MealPlan(user_id=owner_id, planned_at=now, planned_for=now.date(), slot=MealSlot.DINNER, recipe_id=recipe.id, note=RECIPE_CONFIRM_MARKER))
        session.add(MealPlan(user_id=None, planned_at=now, planned_for=now.date(), slot=MealSlot.DINNER, recipe_id=recipe.id, note=None))
        session.commit()

        # Marker carrier rows are invisible; real plans (including NULL notes) are kept.
        all_notes = {plan.note for plan in visible_meal_plans(session)}
        assert all_notes == {"real plan", "yesterday plan", None}

        # User scoping applies when requested.
        owner_notes = [plan.note for plan in visible_meal_plans(session, user_id=owner_id)]
        assert owner_notes == ["yesterday plan", "real plan"]

        # planned_for + slot scoping (the slot-free validation shape).
        slot_notes = [
            plan.note
            for plan in visible_meal_plans(session, user_id=owner_id, planned_for=now.date(), slot=MealSlot.DINNER)
        ]
        assert slot_notes == ["real plan"]

        # date_from/date_to bound planned_at (UTC day edges) after the marker exclusion.
        day_notes = {plan.note for plan in visible_meal_plans(session, user_id=owner_id, date_from=now.date(), date_to=now.date())}
        assert day_notes == {"real plan"}

        # limit applies after the marker exclusion.
        assert len(visible_meal_plans(session, limit=2)) == 2


def test_recipe_ingredient_rejects_unknown_cache_id(client, auth_headers):
    recipe = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Recette",
            "instructions": "Cuire",
            "ingredients": [{"name": "Lait", "quantity": 1, "unit": "L", "cache_id": 999999}],
        },
    )
    assert recipe.status_code == 404


def test_recipe_ingredient_store_metadata_dropped_without_cache_id(client, auth_headers):
    recipe = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Recette simple",
            "instructions": "Cuire",
            "ingredients": [
                {
                    "name": "Lait",
                    "quantity": 1,
                    "unit": "L",
                    "store": "intermarche",
                    "store_label": "Fabricated",
                    "external_id": "fake-123",
                    "price_text": "1,99 €",
                }
            ],
        },
    )
    assert recipe.status_code == 200
    ingredient = recipe.json()["ingredients"][0]
    assert ingredient["store"] is None
    assert ingredient["store_label"] is None
    assert ingredient["external_id"] is None
    assert ingredient["price_text"] is None
