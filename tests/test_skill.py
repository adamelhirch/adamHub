def test_skill_manifest_and_execute_action(client, auth_headers):
    manifest = client.get("/api/v1/skill/manifest", headers=auth_headers)
    assert manifest.status_code == 200
    body = manifest.json()
    assert body["name"] == "adamhub-life-skill"
    actions = [item["action"] for item in body["actions"]]
    assert "meal_plan.confirm_cooked" in actions
    assert "meal_plan.unconfirm_cooked" in actions
    assert "supermarket.list_stores" in actions
    assert "fitness.create_session" in actions
    assert "patrimony.add_account" in actions

    executed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "task.create", "input": {"title": "skill created task", "priority": "medium"}},
    )
    assert executed.status_code == 200
    payload = executed.json()
    assert payload["ok"] is True
    assert payload["action"] == "task.create"
    assert payload["data"]["task"]["title"] == "skill created task"

    stores = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "supermarket.list_stores", "input": {}},
    )
    assert stores.status_code == 200
    stores_payload = stores.json()
    assert stores_payload["ok"] is True
    assert stores_payload["data"]["stores"][0]["key"] == "intermarche"

    fitness = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "fitness.create_session",
            "input": {
                "title": "Skill fitness",
                "planned_at": "2026-03-29T18:00:00Z",
                "duration_minutes": 45,
                "exercises": [{"name": "Pompes", "mode": "reps", "reps": 12}],
            },
        },
    )
    assert fitness.status_code == 200
    fitness_payload = fitness.json()
    assert fitness_payload["ok"] is True
    assert fitness_payload["data"]["session"]["title"] == "Skill fitness"

    patrimony = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "patrimony.add_account",
            "input": {
                "name": "Livret A",
                "account_type": "savings",
                "balance": 1200.0,
            },
        },
    )
    assert patrimony.status_code == 200
    patrimony_payload = patrimony.json()
    assert patrimony_payload["ok"] is True
    assert patrimony_payload["data"]["account"]["name"] == "Livret A"


def test_skill_task_create_rejects_overlap_with_existing_fitness_session(client, auth_headers):
    fitness = client.post(
        "/api/v1/fitness/sessions",
        headers=auth_headers,
        json={
            "title": "Skill overlap",
            "session_type": "strength",
            "planned_at": "2026-03-29T18:00:00Z",
            "duration_minutes": 60,
            "exercises": [{"name": "Squats", "mode": "reps", "reps": 12}],
        },
    )
    assert fitness.status_code == 200

    task = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "task.create",
            "input": {
                "title": "Should overlap",
                "due_at": "2026-03-29T18:30:00Z",
                "estimated_minutes": 30,
            },
        },
    )
    assert task.status_code == 400
    assert "overlaps" in task.json()["detail"].lower()


def test_skill_calendar_add_item_rejects_overlap_with_existing_task(client, auth_headers):
    task = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Task already planned",
            "due_at": "2026-03-29T09:00:00Z",
            "estimated_minutes": 30,
        },
    )
    assert task.status_code == 200

    calendar_item = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "calendar.add_item",
            "input": {
                "title": "Manual overlap",
                "start_at": "2026-03-29T09:15:00Z",
                "end_at": "2026-03-29T09:45:00Z",
                "all_day": False,
            },
        },
    )
    assert calendar_item.status_code == 400
    assert "overlaps" in calendar_item.json()["detail"].lower()


def test_skill_task_create_returns_structured_subtasks(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "task.create",
            "input": {
                "title": "Checklist task",
                "description": "Freeform note",
                "subtasks": [
                    {"title": "Step 1", "completed": False},
                    {"title": "Step 2", "completed": True},
                ],
                "due_at": "2026-03-29T09:00:00Z",
                "estimated_minutes": 30,
            },
        },
    )
    assert created.status_code == 200
    payload = created.json()["data"]["task"]
    assert payload["description"] == "Freeform note"
    assert len(payload["subtasks"]) == 2
    assert payload["subtasks"][0]["title"] == "Step 1"
    assert payload["subtasks"][0]["completed"] is False
    assert payload["subtasks"][0]["id"]
    assert payload["subtasks"][1]["completed"] is True


def test_skill_non_scalar_id_is_a_400_not_a_500(client, auth_headers):
    # int([1, 2]) would raise a TypeError -> raw 500; _int_id must surface a 400.
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "task.create", "input": {"title": "to delete", "priority": "medium"}},
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["task"]["id"]

    missing = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "task.complete", "input": {"task_id": ["not", "scalar"]}},
    )
    assert missing.status_code == 400
    assert "integer" in missing.json()["detail"]

    wrong_type = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "task.complete", "input": {"task_id": {"id": task_id}}},
    )
    assert wrong_type.status_code == 400


def test_skill_task_delete(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "task.create", "input": {"title": "Delete me", "priority": "low"}},
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["task"]["id"]

    deleted = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "task.delete", "input": {"task_id": task_id}},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"ok": True, "deleted_id": task_id}

    gone = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "task.delete", "input": {"task_id": task_id}},
    )
    assert gone.status_code == 400
    assert "not found" in gone.json()["detail"]


def test_skill_event_create_rejects_overlap_with_manual_item(client, auth_headers):
    manual = client.post(
        "/api/v1/calendar/items",
        headers=auth_headers,
        json={
            "title": "Bloc déjà pris",
            "start_at": "2026-03-29T12:30:00Z",
            "end_at": "2026-03-29T13:00:00Z",
            "all_day": False,
        },
    )
    assert manual.status_code == 200

    event = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "event.create",
            "input": {
                "title": "Appel",
                "start_at": "2026-03-29T12:45:00Z",
                "end_at": "2026-03-29T13:15:00Z",
            },
        },
    )
    assert event.status_code == 400
    assert "overlaps" in event.json()["detail"].lower()


def test_skill_event_update_rejects_overlap_with_manual_item(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "event.create",
            "input": {
                "title": "Séance",
                "start_at": "2026-03-29T10:00:00Z",
                "end_at": "2026-03-29T10:30:00Z",
            },
        },
    )
    assert created.status_code == 200
    event_id = created.json()["data"]["event"]["id"]

    manual = client.post(
        "/api/v1/calendar/items",
        headers=auth_headers,
        json={
            "title": "Bloc concurrent",
            "start_at": "2026-03-29T11:00:00Z",
            "end_at": "2026-03-29T11:30:00Z",
            "all_day": False,
        },
    )
    assert manual.status_code == 200

    updated = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "event.update",
            "input": {
                "event_id": event_id,
                "start_at": "2026-03-29T11:00:00Z",
                "end_at": "2026-03-29T11:30:00Z",
            },
        },
    )
    assert updated.status_code == 400
    assert "overlaps" in updated.json()["detail"].lower()


def test_skill_subscription_create_rejects_overlap_with_fitness(client, auth_headers):
    fitness = client.post(
        "/api/v1/fitness/sessions",
        headers=auth_headers,
        json={
            "title": "Cardio",
            "session_type": "cardio",
            "planned_at": "2026-03-29T09:00:00Z",
            "duration_minutes": 45,
            "exercises": [{"name": "Run", "mode": "duration", "duration_minutes": 45}],
        },
    )
    assert fitness.status_code == 200

    subscription = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "subscription.create",
            "input": {
                "name": "Netflix",
                "amount": 12.99,
                "next_due_date": "2026-03-29",
                "interval": "monthly",
            },
        },
    )
    assert subscription.status_code == 400
    assert "overlaps" in subscription.json()["detail"].lower()


def test_skill_habit_create_rejects_overlap_with_manual_item(client, auth_headers):
    from datetime import UTC, datetime, timedelta

    target_day = datetime.now(UTC).date() + timedelta(days=2)

    manual = client.post(
        "/api/v1/calendar/items",
        headers=auth_headers,
        json={
            "title": "Médecine",
            "start_at": f"{target_day.isoformat()}T07:00:00Z",
            "end_at": f"{target_day.isoformat()}T07:45:00Z",
            "all_day": False,
        },
    )
    assert manual.status_code == 200

    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "habit.create",
            "input": {
                "name": "Étirements",
                "frequency": "daily",
                "schedule_time": "07:15",
                "duration_minutes": 20,
            },
        },
    )
    assert created.status_code == 400
    assert "overlaps" in created.json()["detail"].lower()


def test_skill_habit_update_normalizes_schedule_and_rejects_overlap(client, auth_headers):
    from datetime import UTC, datetime, timedelta

    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "habit.create", "input": {"name": "Lecture", "frequency": "daily"}},
    )
    assert created.status_code == 200
    habit_id = created.json()["data"]["habit"]["id"]

    target_day = datetime.now(UTC).date() + timedelta(days=3)
    manual = client.post(
        "/api/v1/calendar/items",
        headers=auth_headers,
        json={
            "title": "RDV déjà pris",
            "start_at": f"{target_day.isoformat()}T20:00:00Z",
            "end_at": f"{target_day.isoformat()}T20:30:00Z",
            "all_day": False,
        },
    )
    assert manual.status_code == 200

    updated = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "habit.update",
            "input": {"habit_id": habit_id, "schedule_times": ["19:00"]},
        },
    )
    assert updated.status_code == 200
    body = updated.json()["data"]["habit"]
    assert body["schedule_time"] == "19:00"
    assert body["schedule_times"] == ["19:00"]

    conflicting = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "habit.update",
            "input": {"habit_id": habit_id, "schedule_time": "20:00", "duration_minutes": 30},
        },
    )
    assert conflicting.status_code == 400
    assert "overlaps" in conflicting.json()["detail"].lower()


# ── B2: smoke coverage per domain (create/list/get/delete via skill/execute) ──


def test_skill_smoke_habit_create_and_list(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "habit.create", "input": {"name": "Lire 20 pages", "frequency": "daily"}},
    )
    assert created.status_code == 200
    habit = created.json()["data"]["habit"]
    assert habit["name"] == "Lire 20 pages"
    assert habit["active"] is True

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "habit.list", "input": {}},
    )
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()["data"]["habits"]] == ["Lire 20 pages"]


def test_skill_smoke_goal_create_list_get(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "goal.create", "input": {"title": "Courir un 10 km"}},
    )
    assert created.status_code == 200
    goal_id = created.json()["data"]["goal"]["id"]

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "goal.list", "input": {}},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]["goals"]] == [goal_id]

    fetched = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "goal.get", "input": {"goal_id": goal_id}},
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["goal"]["title"] == "Courir un 10 km"


def test_skill_smoke_event_create_and_list(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "event.create",
            "input": {
                "title": "RDV kiné",
                "start_at": "2031-05-10T09:00:00Z",
                "end_at": "2031-05-10T09:30:00Z",
            },
        },
    )
    assert created.status_code == 200
    event = created.json()["data"]["event"]
    assert event["title"] == "RDV kiné"

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "event.list", "input": {"from_at": "2031-05-01T00:00:00Z"}},
    )
    assert listed.status_code == 200
    assert [item["title"] for item in listed.json()["data"]["events"]] == ["RDV kiné"]


def test_skill_smoke_subscription_create_list_get(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "subscription.create",
            "input": {"name": "Netflix", "amount": 12.99, "next_due_date": "2031-06-01"},
        },
    )
    assert created.status_code == 200
    subscription_id = created.json()["data"]["subscription"]["id"]

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "subscription.list", "input": {}},
    )
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()["data"]["subscriptions"]] == ["Netflix"]

    fetched = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "subscription.get", "input": {"subscription_id": subscription_id}},
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["subscription"]["amount"] == 12.99


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


def test_skill_smoke_note_create_list_get(client, auth_headers):
    created = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "note.create", "input": {"title": "Idée", "content": "Écrire un livre", "tags": ["créatif"]}},
    )
    assert created.status_code == 200
    note_id = created.json()["data"]["note"]["id"]

    listed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "note.list", "input": {}},
    )
    assert listed.status_code == 200
    assert [item["title"] for item in listed.json()["data"]["notes"]] == ["Idée"]

    fetched = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "note.get", "input": {"note_id": note_id}},
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["note"]["content"] == "Écrire un livre"


def test_skill_smoke_linear_uses_cache_not_live(client, auth_headers):
    projects = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "linear.projects", "input": {"source": "cache"}},
    )
    assert projects.status_code == 200
    assert projects.json()["data"]["projects"] == []

    issues = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "linear.issues", "input": {"source": "cache"}},
    )
    assert issues.status_code == 200
    assert issues.json()["data"]["issues"] == []


# ── B2: regression for bug #66 (invalid servings_override -> 400, never 500) ──


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


# ── B2: network-touching actions must fail cleanly (400), never 500 ──────────


def test_skill_network_actions_fail_cleanly_before_hitting_the_network(client, auth_headers):
    cases = [
        ("video.fetch", {}, "url is required"),
        ("supermarket.search", {"store": "colruyt", "queries": ["lait"]}, "intermarche"),
    ]
    for action, payload, expected_detail in cases:
        response = client.post(
            "/api/v1/skill/execute",
            headers=auth_headers,
            json={"action": action, "input": payload},
        )
        assert response.status_code == 400, f"{action}: {response.text}"
        if expected_detail:
            assert expected_detail in response.json()["detail"]


# ── F1: meal_plan.add with a slot must return 200, never 500 ──────────────────


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


# ── F1: grocery.check_item response must keep a non-empty item after pantry sync


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


# ── T5: Auchan store selection skill actions (offering contexts + selected store)


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

