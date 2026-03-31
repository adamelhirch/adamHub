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
