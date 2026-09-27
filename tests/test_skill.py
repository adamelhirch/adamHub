def test_skill_manifest_and_execute_action(client, auth_headers):
    manifest = client.get("/api/v1/skill/manifest", headers=auth_headers)
    assert manifest.status_code == 200
    body = manifest.json()
    assert body["name"] == "adamhub-life-skill"
    actions = [item["action"] for item in body["actions"]]
    assert "meal_plan.confirm_cooked" in actions
    assert "meal_plan.unconfirm_cooked" in actions
    assert "supermarket.list_stores" in actions
    assert "grocery.add_item" in actions
    assert "recipe.add" in actions
    assert "pantry.add_item" in actions

    stores = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "supermarket.list_stores", "input": {}},
    )
    assert stores.status_code == 200
    stores_payload = stores.json()
    assert stores_payload["ok"] is True
    assert stores_payload["data"]["stores"][0]["key"] == "intermarche"


def test_skill_smoke_pantry_add_and_list(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "pantry.add_item", "input": {"name": "Farine", "quantity": 2, "unit": "kg"}},
    )
    assert created.status_code == 200
    item = created.json()["data"]["item"]
    assert item["name"] == "Farine"
    assert item["quantity"] == 2.0

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "pantry.list_items", "input": {}},
    )
    assert listed.status_code == 200
    assert [row["name"] for row in listed.json()["data"]["items"]] == ["Farine"]


def test_skill_smoke_recipe_add_list_get_delete(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.add", "input": {"name": "Omelette", "instructions": "Cuire"}},
    )
    assert created.status_code == 200
    recipe_id = created.json()["data"]["recipe"]["id"]

    fetched = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.get", "input": {"recipe_id": recipe_id}},
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["recipe"]["name"] == "Omelette"

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.list", "input": {}},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]["recipes"]] == [recipe_id]

    deleted = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.delete", "input": {"recipe_id": recipe_id}},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_id"] == recipe_id

    gone = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.get", "input": {"recipe_id": recipe_id}},
    )
    assert gone.status_code == 400
    assert "not found" in gone.json()["detail"]


def test_skill_smoke_meal_plan_log_cooked_and_list(client, auth_headers):
    recipe = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.add", "input": {"name": "Pâtes", "instructions": "Cuire"}},
    )
    assert recipe.status_code == 200
    recipe_id = recipe.json()["data"]["recipe"]["id"]

    logged = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "meal_plan.log_cooked",
            "input": {"recipe_id": recipe_id, "cooked_at": "2031-07-10T19:00:00Z"},
        },
    )
    assert logged.status_code == 200
    assert logged.json()["data"]["meal_plan"]["recipe_id"] == recipe_id

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "meal_plan.list", "input": {}},
    )
    assert listed.status_code == 200
    assert len(listed.json()["data"]["meal_plans"]) == 1


def test_skill_smoke_grocery_add_list_check_delete(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "grocery.add_item", "input": {"name": "Lait", "quantity": 2, "unit": "L"}},
    )
    assert created.status_code == 200
    item_id = created.json()["data"]["item"]["id"]

    checked = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "grocery.check_item", "input": {"item_id": item_id, "checked": True}},
    )
    assert checked.status_code == 200
    assert checked.json()["data"]["pantry_sync"]["synced"] is True

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "grocery.list_items", "input": {}},
    )
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()["data"]["items"]] == ["Lait"]
    assert listed.json()["data"]["items"][0]["checked"] is True

    deleted = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "grocery.delete_item", "input": {"item_id": item_id}},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_id"] == item_id


def test_skill_recipe_confirm_cooked_rejects_invalid_servings_override(client, auth_headers):
    recipe = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.add", "input": {"name": "Risotto", "instructions": "Cuire"}},
    )
    assert recipe.status_code == 200
    recipe_id = recipe.json()["data"]["recipe"]["id"]

    invalid = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "recipe.confirm_cooked",
            "input": {"recipe_id": recipe_id, "servings_override": "abc"},
        },
    )
    assert invalid.status_code == 400
    assert "servings_override" in invalid.json()["detail"]

    # A valid override on the same recipe still works.
    valid = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "recipe.confirm_cooked",
            "input": {"recipe_id": recipe_id, "servings_override": 2},
        },
    )
    assert valid.status_code == 200


def test_skill_meal_plan_add_with_slot_succeeds(client, auth_headers):
    recipe = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "recipe.add", "input": {"name": "Ragoût", "instructions": "Mijoter"}},
    )
    assert recipe.status_code == 200
    recipe_id = recipe.json()["data"]["recipe"]["id"]

    added = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "meal_plan.add",
            "input": {"recipe_id": recipe_id, "slot": "lunch"},
        },
    )
    assert added.status_code == 200
    plan = added.json()["data"]["meal_plan"]
    assert plan["recipe_id"] == recipe_id
    assert plan["slot"] == "lunch"


def test_skill_grocery_check_item_returns_full_item_after_pantry_sync(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "grocery.add_item", "input": {"name": "Fromage", "quantity": 1, "unit": "piece"}},
    )
    assert created.status_code == 200
    item_id = created.json()["data"]["item"]["id"]

    checked = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "grocery.check_item", "input": {"item_id": item_id, "checked": True}},
    )
    assert checked.status_code == 200
    data = checked.json()["data"]
    assert data["pantry_sync"]["synced"] is True

    item = data["item"]
    assert item
    assert item["id"] == item_id
    assert item["name"] == "Fromage"
    assert item["quantity"] == 1
    assert item["checked"] is True


def test_skill_supermarket_list_offering_contexts(client, auth_headers, monkeypatch):
    async def fake_list_auchan_offering_contexts(**kwargs):
        assert kwargs["zipcode"] == "31400"
        assert kwargs["city"] == "Toulouse"
        return [
            {
                "pos_id": "aa33fa5e-98bd-4944-8576-86f10d7cb589",
                "pos_type": "DRIVE",
                "seller_id": "4c663296-54a8-45f6-b385-0be86b4dfe98",
                "store_reference": "6007",
                "channel": "PICK_UP",
                "name": "Auchan Drive Supermarché Toulouse Pontjumeaux",
                "address": "31000 Toulouse",
                "distance": "2.15 km",
            }
        ]

    monkeypatch.setattr("app.skill.actions.list_auchan_offering_contexts", fake_list_auchan_offering_contexts)

    executed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "supermarket.list_offering_contexts",
            "input": {"zipcode": "31400", "city": "Toulouse", "latitude": 43.604464, "longitude": 1.444243},
        },
    )
    assert executed.status_code == 200, executed.text
    contexts = executed.json()["data"]["contexts"]
    assert len(contexts) == 1
    assert contexts[0]["seller_id"] == "4c663296-54a8-45f6-b385-0be86b4dfe98"
    assert contexts[0]["name"] == "Auchan Drive Supermarché Toulouse Pontjumeaux"


def test_skill_supermarket_select_auchan_store(client, auth_headers, monkeypatch):
    async def fake_select_auchan_store(context, cookies=None):
        assert context.seller_id == "4c663296-54a8-45f6-b385-0be86b4dfe98"
        assert context.store_reference == "6007"
        return {"id": "cf9f3c53-f09b-44c2-ab45-c24debf45fe3", "activeContexts": []}

    monkeypatch.setattr("app.skill.actions.select_auchan_store", fake_select_auchan_store)

    executed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "supermarket.select_auchan_store",
            "input": {
                "seller_id": "4c663296-54a8-45f6-b385-0be86b4dfe98",
                "store_reference": "6007",
                "store_label": "Auchan Drive Supermarché Toulouse Pontjumeaux",
                "zipcode": "31400",
                "city": "Toulouse",
                "latitude": 43.604464,
                "longitude": 1.444243,
            },
        },
    )
    assert executed.status_code == 200, executed.text
    selection = executed.json()["data"]["selection"]
    assert selection["external_store_id"] == "4c663296-54a8-45f6-b385-0be86b4dfe98"
    assert selection["store_label"] == "Auchan Drive Supermarché Toulouse Pontjumeaux"
