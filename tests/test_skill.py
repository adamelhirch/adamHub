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


def test_skill_ubereats_save_address_missing_coordinates_is_a_400(client, auth_headers):
    response = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "ubereats.save_address",
            "input": {"label": "Maison", "formatted_address": "1 rue de la Paix, Paris"},
        },
    )
    assert response.status_code == 400
    assert "latitude and longitude are required" in response.json()["detail"]

