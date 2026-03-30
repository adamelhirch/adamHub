from datetime import UTC, datetime, timedelta


def _next_weekday(base_day, weekday: int):
    delta = (weekday - base_day.weekday()) % 7
    if delta == 0:
        delta = 7
    return base_day + timedelta(days=delta)


def test_task_creation_rejects_overlap_with_fitness_session(client, auth_headers):
    fitness = client.post(
        "/api/v1/fitness/sessions",
        headers=auth_headers,
        json={
            "title": "Séance du soir",
            "session_type": "strength",
            "planned_at": "2026-03-29T18:00:00Z",
            "duration_minutes": 60,
            "exercises": [{"name": "Squats", "mode": "reps", "reps": 12}],
        },
    )
    assert fitness.status_code == 200

    task = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Créer le plan du lendemain",
            "due_at": "2026-03-29T18:30:00Z",
            "estimated_minutes": 30,
        },
    )
    assert task.status_code == 409
    assert "overlaps" in task.json()["detail"].lower()


def test_task_creation_rejects_overlap_with_meal_plan(client, auth_headers):
    recipe = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Poulet riz",
            "instructions": "Cuire le poulet puis servir avec du riz.",
            "servings": 2,
            "ingredients": [{"name": "Poulet", "quantity": 1, "unit": "item"}],
        },
    )
    assert recipe.status_code == 200

    meal_plan = client.post(
        "/api/v1/meal-plans",
        headers=auth_headers,
        json={
            "planned_at": "2026-03-29T12:30:00Z",
            "recipe_id": recipe.json()["id"],
            "auto_add_missing_ingredients": False,
        },
    )
    assert meal_plan.status_code == 200

    task = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Réunion équipe",
            "due_at": "2026-03-29T12:45:00Z",
        },
    )
    assert task.status_code == 409
    assert "overlaps" in task.json()["detail"].lower()


def test_manual_calendar_item_rejects_overlap_with_generated_item(client, auth_headers):
    task = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Préparer le panier",
            "due_at": "2026-03-29T09:00:00Z",
        },
    )
    assert task.status_code == 200

    sync = client.post("/api/v1/calendar/sync", headers=auth_headers)
    assert sync.status_code == 200
    assert sync.json()["generated_by_source"]["task"] == 1

    manual_item = client.post(
        "/api/v1/calendar/items",
        headers=auth_headers,
        json={
            "title": "Créneau perso",
            "start_at": "2026-03-29T09:15:00Z",
            "end_at": "2026-03-29T09:45:00Z",
            "all_day": False,
        },
    )
    assert manual_item.status_code == 409
    assert "overlaps" in manual_item.json()["detail"].lower()


def test_event_creation_rejects_overlap_with_meal_plan(client, auth_headers):
    recipe = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Salade",
            "instructions": "Assembler",
            "servings": 2,
            "ingredients": [{"name": "Laitue", "quantity": 1, "unit": "item"}],
        },
    )
    assert recipe.status_code == 200

    meal_plan = client.post(
        "/api/v1/meal-plans",
        headers=auth_headers,
        json={
            "planned_at": "2026-03-29T12:30:00Z",
            "recipe_id": recipe.json()["id"],
            "auto_add_missing_ingredients": False,
        },
    )
    assert meal_plan.status_code == 200

    event = client.post(
        "/api/v1/events",
        headers=auth_headers,
        json={
            "title": "Appel",
            "description": "Conflit attendu",
            "start_at": "2026-03-29T12:45:00Z",
            "end_at": "2026-03-29T13:15:00Z",
        },
    )
    assert event.status_code == 409
    assert "overlaps" in event.json()["detail"].lower()


def test_subscription_creation_rejects_overlap_with_fitness_session(client, auth_headers):
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
        "/api/v1/subscriptions",
        headers=auth_headers,
        json={
            "name": "Netflix",
            "amount": 12.99,
            "next_due_date": "2026-03-29",
            "interval": "monthly",
        },
    )
    assert subscription.status_code == 409
    assert "overlaps" in subscription.json()["detail"].lower()


def test_daily_task_is_projected_in_calendar_window(client, auth_headers):
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)

    created = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Routine du matin",
            "schedule_mode": "daily",
            "schedule_time": "09:00",
            "estimated_minutes": 30,
        },
    )
    assert created.status_code == 200

    response = client.get(
        "/api/v1/calendar/items",
        headers=auth_headers,
        params={
            "from_at": f"{tomorrow.isoformat()}T00:00:00Z",
            "to_at": f"{tomorrow.isoformat()}T23:59:59Z",
            "include_completed": True,
            "limit": 200,
        },
    )
    assert response.status_code == 200
    items = response.json()

    matching = [
        item
        for item in items
        if item["source"] == "task"
        and item["title"] == "Routine du matin"
        and item["metadata"]["schedule_mode"] == "daily"
    ]
    assert len(matching) == 1
    assert matching[0]["start_at"] == f"{tomorrow.isoformat()}T09:00:00Z"


def test_weekly_task_overlap_is_rejected(client, auth_headers):
    today = datetime.now(UTC).date()
    next_monday = _next_weekday(today, 0)

    existing = client.post(
        "/api/v1/calendar/items",
        headers=auth_headers,
        json={
            "title": "Créneau déjà pris",
            "start_at": f"{next_monday.isoformat()}T10:00:00Z",
            "end_at": f"{next_monday.isoformat()}T10:45:00Z",
            "all_day": False,
        },
    )
    assert existing.status_code == 200

    created = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Point hebdo",
            "schedule_mode": "weekly",
            "schedule_time": "10:15",
            "schedule_weekday": 0,
            "estimated_minutes": 30,
        },
    )
    assert created.status_code == 409
    assert "overlaps" in created.json()["detail"].lower()
