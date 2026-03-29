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
