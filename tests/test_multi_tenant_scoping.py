from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import (
    Account,
    Budget,
    CalendarEvent,
    FinanceTransaction,
    FitnessMeasurement,
    FitnessSession,
    Goal,
    GoalMilestone,
    GroceryItem,
    Habit,
    HabitLog,
    MealPlan,
    Note,
    PantryItem,
    Recipe,
    SavingsGoal,
    Subscription,

    Task,
    TransactionKind,
)

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


def _create_note_for(client, headers, title="Note", kind="note") -> int:
    response = client.post(
        "/api/v1/notes",
        headers=headers,
        json={"title": title, "content": "Contenu", "kind": kind},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_goal_for(client, headers, title="Apprendre le piano") -> int:
    response = client.post("/api/v1/goals", headers=headers, json={"title": title})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_fitness_session_for(
    client, headers, title="Séance fit", planned_at="2026-08-22T06:00:00Z", duration_minutes=45
) -> int:
    response = client.post(
        "/api/v1/fitness/sessions",
        headers=headers,
        json={"title": title, "planned_at": planned_at, "duration_minutes": duration_minutes},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_fitness_measurement_for(
    client, headers, recorded_at="2026-08-22T06:30:00Z", body_weight_kg=80.0
) -> int:
    response = client.post(
        "/api/v1/fitness/measurements",
        headers=headers,
        json={"recorded_at": recorded_at, "body_weight_kg": body_weight_kg},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_subscription_for(
    client,
    headers,
    name="Netflix",
    amount=12.99,
    next_due_date: date | None = None,
) -> int:
    """Create one subscription via the API, defaulting to a date 10 days out."""
    if next_due_date is None:
        next_due_date = date.today() + timedelta(days=10)
    response = client.post(
        "/api/v1/subscriptions",
        headers=headers,
        json={
            "name": name,
            "amount": amount,
            "next_due_date": next_due_date.isoformat(),
            "interval": "monthly",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_habit_for(client, headers, name="Boire de l'eau") -> int:
    response = client.post("/api/v1/habits", headers=headers, json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _log_habit_for(client, headers, habit_id: int, value: int = 1) -> int:
    response = client.post(
        f"/api/v1/habits/{habit_id}/logs",
        headers=headers,
        json={"value": value, "note": "matin"},

    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_task_for(client, headers, title="Réunion") -> int:
    # No due_at => schedule_mode NONE => no calendar slot to validate, so tasks
    # from different tenants never collide in the shared calendar projection.
    response = client.post("/api/v1/tasks", headers=headers, json={"title": title})
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
    note_id = _create_note_for(client, jwt_headers)
    goal_id = _create_goal_for(client, jwt_headers, title="Courir un 10 km")
    fitness_session_id = _create_fitness_session_for(client, jwt_headers, title="Séance auto")
    measurement_id = _create_fitness_measurement_for(client, jwt_headers)

    subscription_id = _create_subscription_for(client, jwt_headers, name="Apple One")
    habit_id = _create_habit_for(client, jwt_headers, name="Étirer le dos")
    habit_log_id = _log_habit_for(client, jwt_headers, habit_id)

    task_id = _create_task_for(client, jwt_headers, title="Préparer le voyage")

    assert _db_user_id(test_engine, GroceryItem, grocery_id) == user["id"]
    assert _db_user_id(test_engine, PantryItem, pantry_id) == user["id"]
    assert _db_user_id(test_engine, Recipe, recipe_id) == user["id"]
    assert _db_user_id(test_engine, MealPlan, meal_plan_id) == user["id"]
    assert _db_user_id(test_engine, Note, note_id) == user["id"]
    assert _db_user_id(test_engine, Goal, goal_id) == user["id"]
    assert _db_user_id(test_engine, FitnessSession, fitness_session_id) == user["id"]
    assert _db_user_id(test_engine, FitnessMeasurement, measurement_id) == user["id"]

    assert _db_user_id(test_engine, Subscription, subscription_id) == user["id"]
    assert _db_user_id(test_engine, Habit, habit_id) == user["id"]
    assert _db_user_id(test_engine, HabitLog, habit_log_id) == user["id"]

    assert _db_user_id(test_engine, Task, task_id) == user["id"]



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

    note_id = client.post(
        "/api/v1/notes",
        headers=jwt_headers,
        json={"title": "Note", "content": "Contenu", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, Note, note_id) == user["id"]

    goal_id = client.post(
        "/api/v1/goals",
        headers=jwt_headers,
        json={"title": "Lire 12 livres", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, Goal, goal_id) == user["id"]

    fitness_session_id = client.post(
        "/api/v1/fitness/sessions",
        headers=jwt_headers,
        json={"title": "Séance", "planned_at": "2026-08-22T06:00:00Z", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, FitnessSession, fitness_session_id) == user["id"]

    measurement_id = client.post(
        "/api/v1/fitness/measurements",
        headers=jwt_headers,
        json={"recorded_at": "2026-08-22T06:30:00Z", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, FitnessMeasurement, measurement_id) == user["id"]

    subscription_id = client.post(
        "/api/v1/subscriptions",
        headers=jwt_headers,
        json={
            "name": "Netflix",
            "amount": 12.99,
            "next_due_date": (date.today() + timedelta(days=15)).isoformat(),
            "interval": "monthly",
            "user_id": other["id"],
        },
    ).json()["id"]
    assert _db_user_id(test_engine, Subscription, subscription_id) == user["id"]
    habit_id = client.post(
        "/api/v1/habits",
        headers=jwt_headers,
        json={"name": "Courir", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, Habit, habit_id) == user["id"]

    task_id = client.post(
        "/api/v1/tasks",
        headers=jwt_headers,
        json={"title": "Ménage", "user_id": other["id"]},
    ).json()["id"]
    assert _db_user_id(test_engine, Task, task_id) == user["id"]



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

    goal_id = _create_goal_for(client, jwt_headers, title="Gravir un sommet")
    patched_goal = client.patch(
        f"/api/v1/goals/{goal_id}",
        headers=jwt_headers,
        json={"progress_percent": 50, "user_id": other["id"]},
    )
    assert patched_goal.status_code == 200
    assert _db_user_id(test_engine, Goal, goal_id) == user["id"]

    fitness_session_id = _create_fitness_session_for(client, jwt_headers, title="Séance")
    patched_session = client.patch(
        f"/api/v1/fitness/sessions/{fitness_session_id}",
        headers=jwt_headers,
        json={"note": "x", "user_id": other["id"]},
    )
    assert patched_session.status_code == 200
    assert _db_user_id(test_engine, FitnessSession, fitness_session_id) == user["id"]

    measurement_id = _create_fitness_measurement_for(client, jwt_headers)
    patched_measurement = client.patch(
        f"/api/v1/fitness/measurements/{measurement_id}",
        headers=jwt_headers,
        json={"body_weight_kg": 81.0, "user_id": other["id"]},
    )
    assert patched_measurement.status_code == 200
    assert _db_user_id(test_engine, FitnessMeasurement, measurement_id) == user["id"]

    subscription_id = _create_subscription_for(client, jwt_headers, name="Preview")
    patched_subscription = client.patch(
        f"/api/v1/subscriptions/{subscription_id}",
        headers=jwt_headers,
        json={"amount": 20.0, "user_id": other["id"]},
    )
    assert patched_subscription.status_code == 200
    assert _db_user_id(test_engine, Subscription, subscription_id) == user["id"]
    habit_id = _create_habit_for(client, jwt_headers, name="Lire")
    patched_habit = client.patch(
        f"/api/v1/habits/{habit_id}",
        headers=jwt_headers,
        json={"description": "20 pages", "user_id": other["id"]},
    )
    assert patched_habit.status_code == 200
    assert _db_user_id(test_engine, Habit, habit_id) == user["id"]

    task_id = _create_task_for(client, jwt_headers, title="Réunion annuelle")
    patched_task = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=jwt_headers,
        json={"title": "Réunion déplacée", "user_id": other["id"]},
    )
    assert patched_task.status_code == 200
    assert _db_user_id(test_engine, Task, task_id) == user["id"]



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
    note_id = _create_note_for(client, headers, title="Note privée")
    journal_id = _create_note_for(client, headers, title="Journal privé", kind="journal")
    goal_id = _create_goal_for(client, headers, title="Objectif secret de A")
    subscription_id = _create_subscription_for(
        client, headers, name="Abonnement privé de A", next_due_date=date.today() + timedelta(days=10)
    )

    task_id = _create_task_for(client, headers, title="Tâche secrète de A")
    milestone = client.post(
        f"/api/v1/goals/{goal_id}/milestones",
        headers=headers,
        json={"title": "Premiere etape"},
    )
    assert milestone.status_code == 200, milestone.text
    fitness_session_id = _create_fitness_session_for(client, headers, title="Séance secrète")
    measurement_id = _create_fitness_measurement_for(client, headers)

    habit_id = _create_habit_for(client, headers, name="Méditation secrète")
    habit_log_id = _log_habit_for(client, headers, habit_id)

    return {
        "grocery": grocery_id,
        "pantry": pantry_id,
        "recipe": recipe_id,
        "meal_plan": meal_plan.json()["id"],
        "note": note_id,
        "journal": journal_id,
        "goal": goal_id,
        "task": task_id,
        "milestone": milestone.json()["id"],
        "fitness_session": fitness_session_id,
        "measurement": measurement_id,

        "subscription": subscription_id,
        "habit": habit_id,
        "habit_log": habit_log_id,

    }


def test_user_cannot_read_another_users_resources(client, jwt_headers):
    user_b = register_user(client, "reader-b@adamelhirch.com")
    user_a = register_user(client, "reader-a@adamelhirch.com")
    ids = _seed_resources_as_user_a(client, user_a["headers"])

    assert client.get(f"/api/v1/groceries/{ids['grocery']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/pantry/items/{ids['pantry']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/recipes/{ids['recipe']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/meal-plans/{ids['meal_plan']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/notes/{ids['note']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/notes/{ids['journal']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/goals/{ids['goal']}", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/goals/{ids['goal']}/milestones", headers=user_b["headers"]).status_code == 404
    assert client.get(f"/api/v1/subscriptions/{ids['subscription']}", headers=user_b["headers"]).status_code == 404
    assert client.patch(f"/api/v1/habits/{ids['habit']}", headers=user_b["headers"], json={"active": False}).status_code == 404
    assert client.get(f"/api/v1/habits/{ids['habit']}/logs", headers=user_b["headers"]).status_code == 404

    # Lists only expose the caller's own rows (journal included).
    assert client.get("/api/v1/groceries", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/pantry/items", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/recipes", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/meal-plans", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/notes", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/notes/journal", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/goals", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/fitness/sessions", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/fitness/measurements", headers=user_b["headers"]).json() == []

    assert client.get("/api/v1/subscriptions", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/subscriptions/upcoming", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/subscriptions/projection", headers=user_b["headers"]).json()["monthly_total"] == 0.0
    assert client.get("/api/v1/habits", headers=user_b["headers"]).json() == []

    assert client.get("/api/v1/tasks", headers=user_b["headers"]).json() == []



def test_user_cannot_modify_another_users_resources(client, jwt_headers):
    user_b = register_user(client, "modifier-b@adamelhirch.com")
    user_a = register_user(client, "modifier-a@adamelhirch.com")
    ids = _seed_resources_as_user_a(client, user_a["headers"])

    assert client.patch(f"/api/v1/groceries/{ids['grocery']}", headers=user_b["headers"], json={"checked": True}).status_code == 404
    assert client.patch(f"/api/v1/pantry/items/{ids['pantry']}", headers=user_b["headers"], json={"quantity": 0}).status_code == 404
    assert client.patch(f"/api/v1/recipes/{ids['recipe']}", headers=user_b["headers"], json={"name": "Hacked"}).status_code == 404
    assert client.patch(f"/api/v1/meal-plans/{ids['meal_plan']}", headers=user_b["headers"], json={"note": "Hacked"}).status_code == 404
    assert client.patch(f"/api/v1/notes/{ids['note']}", headers=user_b["headers"], json={"title": "Hacked"}).status_code == 404
    assert client.patch(f"/api/v1/subscriptions/{ids['subscription']}", headers=user_b["headers"], json={"amount": 0.01}).status_code == 404
    assert client.patch(f"/api/v1/goals/{ids['goal']}", headers=user_b["headers"], json={"title": "Hacked"}).status_code == 404
    assert client.patch(
        f"/api/v1/fitness/sessions/{ids['fitness_session']}", headers=user_b["headers"], json={"note": "Hacked"}
    ).status_code == 404
    assert client.post(
        f"/api/v1/fitness/sessions/{ids['fitness_session']}/complete", headers=user_b["headers"], json={}
    ).status_code == 404
    assert client.patch(
        f"/api/v1/fitness/measurements/{ids['measurement']}", headers=user_b["headers"], json={"body_weight_kg": 1}
    ).status_code == 404

    assert client.patch(f"/api/v1/habits/{ids['habit']}", headers=user_b["headers"], json={"name": "Hacked"}).status_code == 404
    assert client.patch(f"/api/v1/tasks/{ids['task']}", headers=user_b["headers"], json={"title": "Hacked"}).status_code == 404

    assert (
        client.patch(
            f"/api/v1/goals/{ids['goal']}/milestones/{ids['milestone']}",
            headers=user_b["headers"],
            json={"completed": True},
        ).status_code
        == 404
    )


def test_user_cannot_delete_or_act_on_another_users_resources(client, jwt_headers):
    user_b = register_user(client, "deleter-b@adamelhirch.com")
    user_a = register_user(client, "deleter-a@adamelhirch.com")
    ids = _seed_resources_as_user_a(client, user_a["headers"])

    assert client.delete(f"/api/v1/groceries/{ids['grocery']}", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/pantry/items/{ids['pantry']}", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/recipes/{ids['recipe']}", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/meal-plans/{ids['meal_plan']}", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/notes/{ids['note']}", headers=user_b["headers"]).status_code == 404

    assert client.post(f"/api/v1/pantry/items/{ids['pantry']}/consume", headers=user_b["headers"], json={"amount": 1}).status_code == 404
    assert client.post(f"/api/v1/recipes/{ids['recipe']}/confirm-cooked", headers=user_b["headers"], json={}).status_code == 404
    assert client.post(f"/api/v1/recipes/{ids['recipe']}/unconfirm-cooked", headers=user_b["headers"]).status_code == 404
    assert client.post(f"/api/v1/meal-plans/{ids['meal_plan']}/sync-groceries", headers=user_b["headers"]).status_code == 404
    assert client.post(f"/api/v1/meal-plans/{ids['meal_plan']}/confirm-cooked", headers=user_b["headers"], json={}).status_code == 404
    assert client.post(f"/api/v1/meal-plans/{ids['meal_plan']}/unconfirm-cooked", headers=user_b["headers"]).status_code == 404
    assert client.post(f"/api/v1/goals/{ids['goal']}/milestones", headers=user_b["headers"], json={"title": "Intrusion"}).status_code == 404
    assert client.delete(f"/api/v1/fitness/sessions/{ids['fitness_session']}", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/fitness/measurements/{ids['measurement']}", headers=user_b["headers"]).status_code == 404

    assert client.post(f"/api/v1/habits/{ids['habit']}/logs", headers=user_b["headers"], json={"value": 1}).status_code == 404

    assert client.post(f"/api/v1/tasks/{ids['task']}/complete", headers=user_b["headers"]).status_code == 404
    assert client.delete(f"/api/v1/tasks/{ids['task']}", headers=user_b["headers"]).status_code == 404



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
    note_id = _create_note_for(client, auth_headers, title="Note legacy")
    goal_id = _create_goal_for(client, auth_headers, title="Objectif legacy")
    fitness_session_id = _create_fitness_session_for(client, auth_headers, title="Séance legacy")
    measurement_id = _create_fitness_measurement_for(client, auth_headers)

    subscription_id = _create_subscription_for(
        client, auth_headers, name="Abonnement legacy", next_due_date=date.today() + timedelta(days=14)
    )
    habit_id = _create_habit_for(client, auth_headers, name="Habitude legacy")

    task_id = _create_task_for(client, auth_headers, title="Tâche legacy")

    # The owner (via JWT) sees everything the legacy key created.
    assert [i["id"] for i in client.get("/api/v1/groceries", headers=owner_headers).json()] == [grocery_id]
    assert [i["id"] for i in client.get("/api/v1/meal-plans", headers=owner_headers).json()] == [meal_plan_id]
    assert [n["id"] for n in client.get("/api/v1/notes", headers=owner_headers).json()] == [note_id]
    assert [g["id"] for g in client.get("/api/v1/goals", headers=owner_headers).json()] == [goal_id]
    assert [s["id"] for s in client.get("/api/v1/fitness/sessions", headers=owner_headers).json()] == [fitness_session_id]
    assert [m["id"] for m in client.get("/api/v1/fitness/measurements", headers=owner_headers).json()] == [measurement_id]

    assert [h["id"] for h in client.get("/api/v1/habits", headers=owner_headers).json()] == [habit_id]

    assert [s["id"] for s in client.get("/api/v1/subscriptions", headers=owner_headers).json()] == [subscription_id]

    assert [t["id"] for t in client.get("/api/v1/tasks", headers=owner_headers).json()] == [task_id]

    # A freshly-registered JWT user sees none of it.
    stranger = register_user(client, "stranger@adamelhirch.com")
    assert client.get("/api/v1/groceries", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/meal-plans", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/notes", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/goals", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/fitness/sessions", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/fitness/measurements", headers=stranger["headers"]).json() == []

    assert client.get("/api/v1/subscriptions", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/habits", headers=stranger["headers"]).json() == []

    assert client.get("/api/v1/tasks", headers=stranger["headers"]).json() == []



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


def test_meal_plan_not_blocked_by_unrelated_task_at_same_time(client, auth_headers):
    user = register_user(client, "meal-not-blocked@adamelhirch.com")
    recipe_id = _create_recipe_for(client, user["headers"])

    # An unrelated one-shot task occupies the exact same time window. The task
    # is created through the legacy X-API-Key path, which resolves to the owner
    # tenant (tasks is tenant-scoped since t6).
    planned_for = (date.today() + timedelta(days=1)).isoformat()
    task = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
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


def test_meal_plan_not_blocked_by_unrelated_event_at_same_time(client, auth_headers):
    user = register_user(client, "meal-not-blocked-event@adamelhirch.com")
    recipe_id = _create_recipe_for(client, user["headers"])
    planned_for = (date.today() + timedelta(days=1)).isoformat()

    event = client.post(
        "/api/v1/events",
        headers=auth_headers,
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


# ── Skill goal.* actions are scoped to the acting user ───────────────────────

def test_skill_goal_actions_scoped_to_acting_user(client, test_engine):
    from sqlmodel import Session

    from app.models import User
    from app.skill.actions import execute_action

    owner = register_user(client, "skill-goal-a@adamelhirch.com")
    intruder = register_user(client, "skill-goal-b@adamelhirch.com")

    with Session(test_engine) as session:
        owner_user = session.get(User, int(owner["user"]["id"]))
        intruder_user = session.get(User, int(intruder["user"]["id"]))

        created = execute_action("goal.create", {"title": "Objectif A"}, session, user=owner_user)
        goal_id = created["goal"]["id"]
        assert created["goal"]["status"] == "planned"

        # The intruder's list never sees owner A's goal.
        assert execute_action("goal.list", {}, session, user=intruder_user)["goals"] == []

        # Direct access to the other user's goal fails without leaking existence.
        for action, payload in [
            ("goal.get", {"goal_id": goal_id}),
            ("goal.update", {"goal_id": goal_id, "title": "Hacked"}),
            ("goal.add_milestone", {"goal_id": goal_id, "title": "Intrusion"}),
            ("goal.list_milestones", {"goal_id": goal_id}),
            ("goal.update_milestone", {"goal_id": goal_id, "milestone_id": 1, "completed": True}),
        ]:
            try:
                execute_action(action, payload, session, user=intruder_user)
                raise AssertionError(f"{action} should have failed for the intruder")
            except ValueError as exc:
                assert "not found" in str(exc)

        # The owner still fully operates on it: get, update, milestone lifecycle.
        got = execute_action("goal.get", {"goal_id": goal_id}, session, user=owner_user)
        assert got["goal"]["id"] == goal_id
        execute_action("goal.update", {"goal_id": goal_id, "progress_percent": 25}, session, user=owner_user)
        milestone = execute_action(
            "goal.add_milestone", {"goal_id": goal_id, "title": "Etape 1"}, session, user=owner_user
        )
        milestone_id = milestone["milestone"]["id"]
        execute_action(
            "goal.update_milestone",
            {"goal_id": goal_id, "milestone_id": milestone_id, "completed": True},
            session,
            user=owner_user,
        )
        milestones = execute_action("goal.list_milestones", {"goal_id": goal_id}, session, user=owner_user)
        assert milestones["milestones"][0]["completed"] is True


# ── Skill subscription.* actions are scoped to the acting user ──────────────

def test_skill_subscription_actions_scoped_to_acting_user(client, test_engine):
    from app.models import User
    from app.skill.actions import execute_action

    owner = register_user(client, "skill-sub-a@adamelhirch.com")
    intruder = register_user(client, "skill-sub-b@adamelhirch.com")

    with Session(test_engine) as session:
        owner_user = session.get(User, int(owner["user"]["id"]))
        intruder_user = session.get(User, int(intruder["user"]["id"]))

        created = execute_action(
            "subscription.create",
            {"name": "Netflix", "amount": 12.99, "next_due_date": (date.today() + timedelta(days=3)).isoformat()},
            session,
            user=owner_user,
        )
        sub_id = created["subscription"]["id"]

        # The intruder's lists/upcoming/projection never see owner A's rows.
        assert execute_action("subscription.list", {}, session, user=intruder_user)["subscriptions"] == []
        assert execute_action("subscription.upcoming", {"days": 30}, session, user=intruder_user)["subscriptions"] == []
        assert (
            execute_action("subscription.projection", {}, session, user=intruder_user)["projection"]["monthly_total"]
            == 0.0
        )

        # Direct access to the other user's subscription fails without leaking existence.
        for action, payload in [
            ("subscription.get", {"subscription_id": sub_id}),
            ("subscription.update", {"subscription_id": sub_id, "amount": 0.01}),
        ]:
            try:
                execute_action(action, payload, session, user=intruder_user)
                raise AssertionError(f"{action} should have failed for the intruder")
            except ValueError as exc:
                assert "not found" in str(exc)

        # The owner still fully operates on it: get, update, list, upcoming, projection.
        got = execute_action("subscription.get", {"subscription_id": sub_id}, session, user=owner_user)
        assert got["subscription"]["id"] == sub_id
        execute_action("subscription.update", {"subscription_id": sub_id, "amount": 20.0}, session, user=owner_user)
        listed = execute_action("subscription.list", {}, session, user=owner_user)["subscriptions"]
        assert [s["id"] for s in listed] == [sub_id]
        upcoming = execute_action("subscription.upcoming", {"days": 30}, session, user=owner_user)["subscriptions"]
        assert [s["id"] for s in upcoming] == [sub_id]
        projection = execute_action("subscription.projection", {}, session, user=owner_user)["projection"]
        assert projection["monthly_total"] == 20.0


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
        session.add(Note(title="Note legacy", content="Contenu", user_id=None))
        session.add(Account(name="Livret A", user_id=None))
        session.add(
            Subscription(
                name="Apple One",
                amount=4.99,
                currency="EUR",
                next_due_date=date.today() + timedelta(days=25),
                user_id=None,
            )
        )
        goal = SavingsGoal(title="Voyage", target_amount=5000.0, current_amount=1000.0, user_id=None)
        session.add(goal)
        hiking_goal = Goal(title="Gravir l'Everest", user_id=None)
        session.add(hiking_goal)
        session.flush()
        session.add(GoalMilestone(goal_id=hiking_goal.id, title="Camp de base"))
        legacy_habit = Habit(name="Méditation", user_id=None)
        session.add(legacy_habit)
        session.flush()
        session.add(HabitLog(habit_id=legacy_habit.id, user_id=None))

        session.add(Task(title="Tâche legacy", user_id=None))
        session.commit()

    with Session(test_engine) as session:
        assert count_null_rows(session) == {
            "groceryitem": 2,
            "pantryitem": 1,
            "recipe": 1,
            "mealplan": 1,
            "note": 1,
            "account": 1,
            "savingsgoal": 1,
            "goal": 1,
            "subscription": 1,
            "habit": 1,
            "habitlog": 1,
            "task": 1,
            "financetransaction": 0,
            "budget": 0,
            "fitnessmeasurement": 0,
            "fitnesssession": 0,

            "calendarevent": 0,

        }
        dry = backfill(session, owner_id, commit=False)
        assert dry["commit"] is False
        assert dry["updated"] == {
            "groceryitem": 0,
            "pantryitem": 0,
            "recipe": 0,
            "mealplan": 0,
            "note": 0,
            "account": 0,
            "savingsgoal": 0,
            "goal": 0,
            "subscription": 0,
            "habit": 0,
            "habitlog": 0,
            "task": 0,
            "financetransaction": 0,
            "budget": 0,
            "fitnessmeasurement": 0,
            "fitnesssession": 0,

            "calendarevent": 0,

        }
        assert count_null_rows(session) == {
            "groceryitem": 2,
            "pantryitem": 1,
            "recipe": 1,
            "mealplan": 1,
            "note": 1,
            "account": 1,
            "savingsgoal": 1,
            "goal": 1,
            "subscription": 1,
            "habit": 1,
            "habitlog": 1,
            "task": 1,
            "financetransaction": 0,
            "budget": 0,
            "fitnessmeasurement": 0,
            "fitnesssession": 0,

            "calendarevent": 0,

        }

    with Session(test_engine) as session:
        committed = backfill(session, owner_id, commit=True)
        assert committed["commit"] is True
        assert committed["updated"] == {
            "groceryitem": 2,
            "pantryitem": 1,
            "recipe": 1,
            "mealplan": 1,
            "note": 1,
            "account": 1,
            "savingsgoal": 1,
            "goal": 1,
            "subscription": 1,
            "habit": 1,
            "habitlog": 1,
            "task": 1,
            "financetransaction": 0,
            "budget": 0,
            "fitnessmeasurement": 0,
            "fitnesssession": 0,

            "calendarevent": 0,

        }
        assert count_null_rows(session) == {
            "groceryitem": 0,
            "pantryitem": 0,
            "recipe": 0,
            "mealplan": 0,
            "note": 0,
            "account": 0,
            "savingsgoal": 0,
            "goal": 0,
            "subscription": 0,
            "habit": 0,
            "habitlog": 0,
            "task": 0,
            "financetransaction": 0,
            "budget": 0,
            "fitnessmeasurement": 0,
            "fitnesssession": 0,

            "calendarevent": 0,

        }

    # Idempotent: a second run reports zero NULL rows to claim.
    with Session(test_engine) as session:
        again = backfill(session, owner_id, commit=True)
        assert again["updated"] == {
            "groceryitem": 0,
            "pantryitem": 0,
            "recipe": 0,
            "mealplan": 0,
            "note": 0,
            "account": 0,
            "savingsgoal": 0,
            "goal": 0,
            "subscription": 0,
            "habit": 0,
            "habitlog": 0,
            "task": 0,
            "financetransaction": 0,
            "budget": 0,
            "fitnessmeasurement": 0,
            "fitnesssession": 0,

            "calendarevent": 0,

        }

    # The claimed rows now belong to the owner and show up for the owner.
    with Session(test_engine) as session:
        assert session.exec(select(GroceryItem)).all()[0].user_id == owner_id
        assert session.exec(select(Goal)).all()[0].user_id == owner_id
        assert session.exec(select(Habit)).all()[0].user_id == owner_id
        assert session.exec(select(HabitLog)).all()[0].user_id == owner_id

        assert session.exec(select(Task)).all()[0].user_id == owner_id


def test_backfill_rejects_unknown_owner(client, test_engine):
    from scripts.backfill_owner_tenant import resolve_owner

    with Session(test_engine) as session:
        assert resolve_owner(session, "does-not-exist@adamelhirch.com") is None
        assert resolve_owner(session, OWNER_EMAIL) is not None


def test_backfill_claims_subscription_rows_for_owner(client, test_engine, owner_id, auth_headers, owner_headers):
    from scripts.backfill_owner_tenant import backfill

    with Session(test_engine) as session:
        sub = Subscription(
            name="Legacy SaaS",
            amount=9.99,
            currency="EUR",
            next_due_date=date.today() + timedelta(days=20),
            user_id=None,
        )
        session.add(sub)
        session.commit()
        legacy_id = sub.id

    # Pre-scoping NULL rows are invisible to everyone until the backfill claims them.
    assert client.get("/api/v1/subscriptions", headers=auth_headers).json() == []

    with Session(test_engine) as session:
        result = backfill(session, owner_id, commit=True)
    assert result["commit"] is True
    assert result["updated"]["subscription"] == 1

    # After backfill the owner finds their rows again via both auth paths;
    # a non-owner JWT user still cannot see or touch them.
    assert [s["id"] for s in client.get("/api/v1/subscriptions", headers=auth_headers).json()] == [legacy_id]
    assert [s["id"] for s in client.get("/api/v1/subscriptions", headers=owner_headers).json()] == [legacy_id]
    stranger = register_user(client, "subscription-backfill-stranger@adamelhirch.com")
    assert client.get("/api/v1/subscriptions", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/subscriptions/upcoming", headers=stranger["headers"]).json() == []
    assert client.patch(
        f"/api/v1/subscriptions/{legacy_id}", headers=stranger["headers"], json={"amount": 0}
    ).status_code == 404

# ── Task scoping: API + skill (t6) ───────────────────────────────────────────

def test_legacy_tasks_claimed_by_backfill_are_visible_to_owner_only(client, test_engine, owner_id, auth_headers, owner_headers):
    from scripts.backfill_owner_tenant import backfill

    with Session(test_engine) as session:
        session.add(Task(title="Tâche d'avant la scoping", user_id=None))
        session.commit()

    # Pre-scoping NULL rows are invisible to everyone until the backfill claims them.
    assert client.get("/api/v1/tasks", headers=auth_headers).json() == []

    with Session(test_engine) as session:
        committed = backfill(session, owner_id, commit=True)
        assert committed["updated"]["task"] == 1

    # The owner finds the pre-backfill task again via both auth paths.
    assert [t["title"] for t in client.get("/api/v1/tasks", headers=auth_headers).json()] == ["Tâche d'avant la scoping"]
    assert [t["title"] for t in client.get("/api/v1/tasks", headers=owner_headers).json()] == ["Tâche d'avant la scoping"]

    # A non-owner user still sees none of it.
    stranger = register_user(client, "task-backfill-stranger@adamelhirch.com")
    assert client.get("/api/v1/tasks", headers=stranger["headers"]).json() == []
    assert client.patch("/api/v1/tasks/1", headers=stranger["headers"], json={"title": "Hacked"}).status_code == 404


def test_skill_task_actions_scoped_to_acting_user(client, test_engine):
    # The skill HTTP gateway is still Owner-only (ADR-0001), so the handler
    # seam is exercised directly — the same seam MCP dispatches through.
    from app.models import User
    from app.skill.actions import execute_action

    owner = register_user(client, "skill-task-a@adamelhirch.com")
    intruder = register_user(client, "skill-task-b@adamelhirch.com")

    with Session(test_engine) as session:
        owner_user = session.get(User, int(owner["user"]["id"]))
        intruder_user = session.get(User, int(intruder["user"]["id"]))

        created = execute_action("task.create", {"title": "Tâche A"}, session, user=owner_user)
        task_id = created["task"]["id"]
        assert created["task"]["status"] == "todo"

        # The intruder's list never sees owner A's task.
        assert execute_action("task.list", {}, session, user=intruder_user)["tasks"] == []

        # Direct access to the other user's task fails without leaking existence.
        for action, payload in [
            ("task.update", {"task_id": task_id, "title": "Hacked"}),
            ("task.complete", {"task_id": task_id}),
            ("task.delete", {"task_id": task_id}),
        ]:
            try:
                execute_action(action, payload, session, user=intruder_user)
                raise AssertionError(f"{action} should have failed for the intruder")
            except ValueError as exc:
                assert "not found" in str(exc)

        # The owner still fully operates on it: update, complete, list, delete.
        updated = execute_action("task.update", {"task_id": task_id, "priority": "high"}, session, user=owner_user)
        assert updated["task"]["priority"] == "high"
        completed = execute_action("task.complete", {"task_id": task_id}, session, user=owner_user)
        assert completed["task"]["status"] == "done"
        listed = execute_action("task.list", {"status": "done"}, session, user=owner_user)["tasks"]
        assert [t["id"] for t in listed] == [task_id]
        execute_action("task.delete", {"task_id": task_id}, session, user=owner_user)
        assert execute_action("task.list", {}, session, user=owner_user)["tasks"] == []


# ── Finance scoping: transactions & budgets (t1) ─────────────────────────────

def _seed_finance_for(client, headers, month="2026-04") -> tuple[int, int]:
    tx = client.post(
        "/api/v1/finances/transactions",
        headers=headers,
        json={
            "kind": "expense",
            "amount": 55.5,
            "currency": "EUR",
            "category": "resto",
            "occurred_at": f"{month}-15T12:00:00Z",
        },
    )
    assert tx.status_code == 200, tx.text
    budget = client.post(
        "/api/v1/finances/budgets",
        headers=headers,
        json={"month": month, "category": "resto", "monthly_limit": 200.0},
    )
    assert budget.status_code == 200, budget.text
    return tx.json()["id"], budget.json()["id"]


def test_finance_create_auto_scopes_to_user(client, test_engine, jwt_headers):
    user = client.get("/api/v1/auth/me", headers=jwt_headers).json()
    tx_id, budget_id = _seed_finance_for(client, jwt_headers)

    assert _db_user_id(test_engine, FinanceTransaction, tx_id) == user["id"]
    assert _db_user_id(test_engine, Budget, budget_id) == user["id"]


def test_finance_client_cannot_override_user_id_on_create(client, test_engine, jwt_headers):
    user = client.get("/api/v1/auth/me", headers=jwt_headers).json()
    other = register_user(client, "finance-override@adamelhirch.com")["user"]

    tx = client.post(
        "/api/v1/finances/transactions",
        headers=jwt_headers,
        json={"kind": "expense", "amount": 10, "currency": "EUR", "category": "test", "user_id": other["id"]},
    )
    assert tx.status_code == 200, tx.text
    budget = client.post(
        "/api/v1/finances/budgets",
        headers=jwt_headers,
        json={"month": "2026-02", "category": "test", "monthly_limit": 100.0, "user_id": other["id"]},
    )
    assert budget.status_code == 200, budget.text

    assert _db_user_id(test_engine, FinanceTransaction, tx.json()["id"]) == user["id"]
    assert _db_user_id(test_engine, Budget, budget.json()["id"]) == user["id"]


def test_user_cannot_see_another_users_finance_data(client):
    user_b = register_user(client, "finance-b@adamelhirch.com")
    user_a = register_user(client, "finance-a@adamelhirch.com")
    _seed_finance_for(client, user_a["headers"], month="2026-04")

    # Lists only expose the caller's own rows.
    assert client.get("/api/v1/finances/transactions", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/finances/budgets", headers=user_b["headers"]).json() == []

    # The month summary aggregates only the caller's own rows.
    summary = client.get("/api/v1/finances/summary?year=2026&month=4", headers=user_b["headers"]).json()
    assert summary["income"] == 0.0
    assert summary["expense"] == 0.0
    assert summary["budgets"] == []


def test_user_month_summary_only_mixes_own_budgets_and_transactions(client):
    user = register_user(client, "finance-mix@adamelhirch.com")
    _seed_finance_for(client, user["headers"], month="2026-05")
    client.post(
        "/api/v1/finances/transactions",
        headers=user["headers"],
        json={"kind": "income", "amount": 900.0, "currency": "EUR", "category": "salary", "occurred_at": "2026-05-02T09:00:00Z"},
    )

    summary = client.get("/api/v1/finances/summary?year=2026&month=5", headers=user["headers"]).json()
    assert summary["income"] == 900.0
    assert summary["expense"] == 55.5
    assert len(summary["budgets"]) == 1
    assert summary["budgets"][0]["category"] == "resto"


def test_legacy_api_key_finance_scopes_to_owner_user(client, auth_headers, owner_headers):
    # Legacy API-key rows (via the finances API and the skill actions) are
    # scoped to the owner user; the owner's JWT sees them, a second user doesn't.
    tx = client.post(
        "/api/v1/finances/transactions",
        headers=auth_headers,
        json={"kind": "expense", "amount": 12.0, "currency": "EUR", "category": "legacy-api", "occurred_at": "2026-06-10T10:00:00Z"},
    )
    assert tx.status_code == 200, tx.text

    budget = client.post(
        "/api/v1/finances/budgets",
        headers=auth_headers,
        json={"month": "2026-06", "category": "legacy-api", "monthly_limit": 100.0},
    )
    assert budget.status_code == 200, budget.text

    skill_tx = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "finance.add_transaction", "input": {"kind": "expense", "amount": 7.0, "currency": "EUR", "category": "skill-api", "occurred_at": "2026-06-11T10:00:00Z"}},
    )
    assert skill_tx.status_code == 200, skill_tx.text
    skill_budget = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "finance.create_budget", "input": {"month": "2026-06", "category": "skill-api", "monthly_limit": 50.0}},
    )
    assert skill_budget.status_code == 200, skill_budget.text

    owner_txs = client.get("/api/v1/finances/transactions", headers=owner_headers).json()
    owner_budgets = client.get("/api/v1/finances/budgets", headers=owner_headers).json()
    assert sorted(t["category"] for t in owner_txs) == ["legacy-api", "skill-api"]
    assert sorted(b["category"] for b in owner_budgets) == ["legacy-api", "skill-api"]

    stranger = register_user(client, "finance-legacy-stranger@adamelhirch.com")
    assert client.get("/api/v1/finances/transactions", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/finances/budgets", headers=stranger["headers"]).json() == []


def test_skill_finance_month_summary_is_scoped_to_caller(client, auth_headers):
    # Owner seeds data via the skill action; a JWT user with no data gets an
    # empty summary even though the owner's rows exist.
    client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "finance.add_transaction", "input": {"kind": "income", "amount": 30.0, "currency": "EUR", "category": "skill", "occurred_at": "2026-07-10T10:00:00Z"}},
    )
    stranger = register_user(client, "finance-summary-stranger@adamelhirch.com")
    empty = client.get("/api/v1/finances/summary?year=2026&month=7", headers=stranger["headers"]).json()
    assert empty["income"] == 0.0
    assert empty["expense"] == 0.0
    assert empty["budgets"] == []

    owner_summary = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "finance.month_summary", "input": {"year": 2026, "month": 7}},
    ).json()["data"]["summary"]
    assert owner_summary["income"] == 30.0
    assert owner_summary["expense"] == 0.0


def test_backfill_claims_finance_rows_for_owner(client, test_engine, owner_id, auth_headers, owner_headers):
    from scripts.backfill_owner_tenant import backfill

    with Session(test_engine) as session:
        session.add(
            FinanceTransaction(kind=TransactionKind.EXPENSE, amount=42.0, category="legacy", user_id=None)
        )
        session.add(Budget(month="2026-01", category="legacy", monthly_limit=100.0, user_id=None))
        session.commit()

    with Session(test_engine) as session:
        committed = backfill(session, owner_id, commit=True)
        assert committed["updated"]["financetransaction"] == 1
        assert committed["updated"]["budget"] == 1

    # The owner finds their pre-backfill rows again via both auth paths.
    assert [t["category"] for t in client.get("/api/v1/finances/transactions", headers=auth_headers).json()] == ["legacy"]
    assert [b["category"] for b in client.get("/api/v1/finances/budgets", headers=owner_headers).json()] == ["legacy"]

    # A non-owner user still sees none of it.
    stranger = register_user(client, "finance-backfill-stranger@adamelhirch.com")
    assert client.get("/api/v1/finances/transactions", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/finances/budgets", headers=stranger["headers"]).json() == []
# ── Patrimony ownership (accounts + savings goals) ───────────────────────────

def _seed_patrimony_for(client, headers):
    account = client.post(
        "/api/v1/patrimony/accounts",
        headers=headers,
        json={"name": "Livret A", "account_type": "savings", "balance": 1200.0},
    )
    assert account.status_code == 200, account.text
    goal = client.post(
        "/api/v1/patrimony/goals",
        headers=headers,
        json={"title": "Voyage", "target_amount": 5000.0, "account_id": account.json()["id"]},
    )
    assert goal.status_code == 200, goal.text
    return {"account": account.json()["id"], "goal": goal.json()["id"]}


def test_patrimony_create_auto_assigns_user_id(client, test_engine, jwt_headers):
    user = client.get("/api/v1/auth/me", headers=jwt_headers).json()
    ids = _seed_patrimony_for(client, jwt_headers)

    assert _db_user_id(test_engine, Account, ids["account"]) == user["id"]
    assert _db_user_id(test_engine, SavingsGoal, ids["goal"]) == user["id"]


def test_patrimony_cross_tenant_is_404(client):
    user_a = register_user(client, "patrimony-a@adamelhirch.com")
    user_b = register_user(client, "patrimony-b@adamelhirch.com")
    ids = _seed_patrimony_for(client, user_a["headers"])

    # Lists only expose the caller's own rows.
    assert client.get("/api/v1/patrimony/accounts", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/patrimony/goals", headers=user_b["headers"]).json() == []
    overview = client.get("/api/v1/patrimony/overview", headers=user_b["headers"]).json()
    assert overview["accounts"] == []
    assert overview["goals"] == []
    assert overview["net_worth"] == 0.0

    # Reads/writes on another user's account or goal are 404 (no existence leak).
    assert client.patch(
        f"/api/v1/patrimony/accounts/{ids['account']}", headers=user_b["headers"], json={"balance": 0}
    ).status_code == 404
    assert client.delete(f"/api/v1/patrimony/accounts/{ids['account']}", headers=user_b["headers"]).status_code == 404
    assert client.patch(
        f"/api/v1/patrimony/goals/{ids['goal']}", headers=user_b["headers"], json={"target_amount": 1}
    ).status_code == 404
    assert client.delete(f"/api/v1/patrimony/goals/{ids['goal']}", headers=user_b["headers"]).status_code == 404

    # The owner still sees and operates everything the tenant created.
    assert [acc["id"] for acc in client.get("/api/v1/patrimony/accounts", headers=user_a["headers"]).json()] == [ids["account"]]
    assert client.patch(
        f"/api/v1/patrimony/accounts/{ids['account']}", headers=user_a["headers"], json={"balance": 5}
    ).status_code == 200
    assert client.delete(f"/api/v1/patrimony/goals/{ids['goal']}", headers=user_a["headers"]).status_code == 204


def test_patrimony_skill_actions_are_user_scoped(client, test_engine):
    # The skill HTTP gateway is still Owner-only (ADR-0001), so the handler
    # seam is exercised directly — the same seam MCP dispatches through.
    from app.core.auth import hash_password
    from app.models import User
    from app.skill.actions import execute_action

    with Session(test_engine) as session:
        user_a = User(
            email="skill-patrimony-a@adamelhirch.com",
            password_hash=hash_password("password-123"),
            display_name="A",
        )
        user_b = User(
            email="skill-patrimony-b@adamelhirch.com",
            password_hash=hash_password("password-123"),
            display_name="B",
        )
        session.add(user_a)
        session.add(user_b)
        session.commit()
        session.refresh(user_a)
        session.refresh(user_b)

    with Session(test_engine) as session:
        created = execute_action(
            "patrimony.add_account",
            {"name": "PEA", "account_type": "investment", "balance": 100.0},
            session,
            user=user_a,
        )
        account_id = created["account"]["id"]

        # B's calls never see A's account (and cannot update it).
        assert execute_action("patrimony.list_accounts", {}, session, user=user_b)["accounts"] == []
        assert execute_action("patrimony.overview", {}, session, user=user_b)["overview"]["accounts"] == []
        assert execute_action("patrimony.overview", {}, session, user=user_b)["overview"]["net_worth"] == 0.0
        try:
            execute_action("patrimony.update_account", {"account_id": account_id, "balance": 999}, session, user=user_b)
            raise AssertionError("expected ValueError for cross-tenant update_account")
        except ValueError as exc:
            assert "not found" in str(exc)

        # Goals created by A are invisible to B; B cannot update or delete them.
        a_goal = execute_action(
            "patrimony.add_goal",
            {"title": "Voyage", "target_amount": 5000.0, "account_id": account_id},
            session,
            user=user_a,
        )
        goal_id = a_goal["goal"]["id"]
        assert execute_action("patrimony.list_goals", {}, session, user=user_b)["goals"] == []
        for action, input_ in (
            ("patrimony.update_goal", {"goal_id": goal_id, "target_amount": 1}),
            ("patrimony.delete_goal", {"goal_id": goal_id}),
        ):
            try:
                execute_action(action, input_, session, user=user_b)
                raise AssertionError(f"expected ValueError for cross-tenant {action}")
            except ValueError as exc:
                assert "not found" in str(exc)

        # A still sees its rows and can operate them.
        assert [acc["name"] for acc in execute_action("patrimony.list_accounts", {}, session, user=user_a)["accounts"]] == ["PEA"]


def test_patrimony_backfill_claims_legacy_rows_to_owner(client, test_engine, owner_id, auth_headers):
    from scripts.backfill_owner_tenant import backfill

    with Session(test_engine) as session:
        account = Account(name="Livret A", balance=1200.0, user_id=None)
        session.add(account)
        session.flush()
        session.add(SavingsGoal(title="Voyage", target_amount=5000.0, account_id=account.id, user_id=None))
        session.commit()
        legacy_account_id = account.id

    # Pre-scoping NULL rows are invisible to everyone until the backfill claims them.
    assert client.get("/api/v1/patrimony/accounts", headers=auth_headers).json() == []

    with Session(test_engine) as session:
        result = backfill(session, owner_id, commit=True)
    assert result["commit"] is True
    assert result["updated"]["account"] == 1
    assert result["updated"]["savingsgoal"] == 1

    # After backfill the owner (legacy API-key path) sees and operates the rows;
    # a non-owner JWT user still cannot see or touch them.
    assert [acc["id"] for acc in client.get("/api/v1/patrimony/accounts", headers=auth_headers).json()] == [legacy_account_id]
    stranger = register_user(client, "patrimony-stranger@adamelhirch.com")
    assert client.get("/api/v1/patrimony/accounts", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/patrimony/goals", headers=stranger["headers"]).json() == []
    assert client.patch(
        f"/api/v1/patrimony/accounts/{legacy_account_id}", headers=stranger["headers"], json={"balance": 0}
    ).status_code == 404

# ── Fitness ownership (user_id on sessions & measurements, t9) ────────────────

def test_fitness_cross_tenant_is_404(client):
    user_a = register_user(client, "fitness-a@adamelhirch.com")
    user_b = register_user(client, "fitness-b@adamelhirch.com")
    session_id = _create_fitness_session_for(client, user_a["headers"], title="Seance A")
    measurement_id = _create_fitness_measurement_for(client, user_a["headers"])

    # Lists only expose the caller's own rows.
    assert client.get("/api/v1/fitness/sessions", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/fitness/measurements", headers=user_b["headers"]).json() == []

    # The overview only aggregates the caller's own rows.
    overview = client.get("/api/v1/fitness", headers=user_b["headers"])
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["stats"]["planned_sessions"] == 0
    assert body["recent_sessions"] == []
    assert body["measurements"] == []

    # Reads/writes on another user's session or measurement are 404 (no existence leak).
    assert client.patch(
        f"/api/v1/fitness/sessions/{session_id}", headers=user_b["headers"], json={"note": "Hacked"}
    ).status_code == 404
    assert client.post(
        f"/api/v1/fitness/sessions/{session_id}/complete", headers=user_b["headers"], json={}
    ).status_code == 404
    assert client.delete(f"/api/v1/fitness/sessions/{session_id}", headers=user_b["headers"]).status_code == 404
    assert client.patch(
        f"/api/v1/fitness/measurements/{measurement_id}", headers=user_b["headers"], json={"body_weight_kg": 1}
    ).status_code == 404
    assert client.delete(f"/api/v1/fitness/measurements/{measurement_id}", headers=user_b["headers"]).status_code == 404

    # The tenant that owns the rows still reads, writes and deletes them.
    assert client.patch(
        f"/api/v1/fitness/sessions/{session_id}", headers=user_a["headers"], json={"note": "OK"}
    ).status_code == 200
    assert client.patch(
        f"/api/v1/fitness/measurements/{measurement_id}", headers=user_a["headers"], json={"body_weight_kg": 82.0}
    ).status_code == 200
    assert client.delete(f"/api/v1/fitness/measurements/{measurement_id}", headers=user_a["headers"]).status_code == 200


def test_fitness_skill_actions_are_user_scoped(client, test_engine):
    # The skill HTTP gateway is still Owner-only (ADR-0001), so the handler
    # seam is exercised directly — the same seam MCP dispatches through.
    from app.models import User
    from app.skill.actions import execute_action

    owner = register_user(client, "skill-fitness-a@adamelhirch.com")
    intruder = register_user(client, "skill-fitness-b@adamelhirch.com")

    with Session(test_engine) as session:
        owner_user = session.get(User, int(owner["user"]["id"]))
        intruder_user = session.get(User, int(intruder["user"]["id"]))

        created = execute_action(
            "fitness.create_session",
            {"title": "Séance A", "planned_at": "2026-08-22T06:00:00Z", "duration_minutes": 45},
            session,
            user=owner_user,
        )
        session_id = created["session"]["id"]

        measurement = execute_action(
            "fitness.add_measurement",
            {"recorded_at": "2026-08-22T06:30:00Z", "body_weight_kg": 80.0},
            session,
            user=owner_user,
        )
        measurement_id = measurement["measurement"]["id"]

        # The intruder never sees the owner's fitness data.
        assert execute_action("fitness.list_sessions", {}, session, user=intruder_user)["sessions"] == []
        assert execute_action("fitness.list_measurements", {}, session, user=intruder_user)["measurements"] == []
        overview = execute_action("fitness.overview", {}, session, user=intruder_user)["overview"]
        assert overview["stats"]["planned_sessions"] == 0
        assert overview["recent_sessions"] == []
        assert overview["measurements"] == []

        # Direct operations on the other user's rows fail without leaking existence.
        for action, payload in [
            ("fitness.update_session", {"session_id": session_id, "title": "Hacked"}),
            ("fitness.complete_session", {"session_id": session_id}),
            ("fitness.delete_session", {"session_id": session_id}),
            ("fitness.update_measurement", {"measurement_id": measurement_id, "body_weight_kg": 1}),
            ("fitness.delete_measurement", {"measurement_id": measurement_id}),
        ]:
            try:
                execute_action(action, payload, session, user=intruder_user)
                raise AssertionError(f"{action} should have failed for the intruder")
            except ValueError as exc:
                assert "not found" in str(exc)

        # The owner still fully operates on its session and measurement.
        assert execute_action("fitness.list_sessions", {}, session, user=owner_user)["sessions"][0]["id"] == session_id
        execute_action("fitness.update_session", {"session_id": session_id, "note": "Intense"}, session, user=owner_user)
        execute_action("fitness.complete_session", {"session_id": session_id, "effort_rating": 8}, session, user=owner_user)
        execute_action("fitness.delete_session", {"session_id": session_id}, session, user=owner_user)
        execute_action("fitness.delete_measurement", {"measurement_id": measurement_id}, session, user=owner_user)


def test_fitness_backfill_claims_legacy_rows_to_owner(client, test_engine, owner_id, auth_headers):
    from scripts.backfill_owner_tenant import backfill

    with Session(test_engine) as session:
        session.add(
            FitnessSession(title="Séance legacy", planned_at=datetime(2026, 8, 22, 6, tzinfo=timezone.utc), user_id=None)
        )
        session.add(
            FitnessMeasurement(recorded_at=datetime(2026, 8, 22, 6, 30, tzinfo=timezone.utc), body_weight_kg=88.0, user_id=None)
        )
        session.commit()

    # Pre-scoping NULL rows are invisible to everyone until the backfill claims them.
    assert client.get("/api/v1/fitness/sessions", headers=auth_headers).json() == []
    assert client.get("/api/v1/fitness/measurements", headers=auth_headers).json() == []

    with Session(test_engine) as session:
        result = backfill(session, owner_id, commit=True)
    assert result["commit"] is True
    assert result["updated"]["fitnesssession"] == 1
    assert result["updated"]["fitnessmeasurement"] == 1

    # After backfill the owner (legacy API-key path) sees and operates the rows.
    assert len(client.get("/api/v1/fitness/sessions", headers=auth_headers).json()) == 1
    assert len(client.get("/api/v1/fitness/measurements", headers=auth_headers).json()) == 1

    # A non-owner JWT user still cannot see or touch them.
    stranger = register_user(client, "fitness-backfill-stranger@adamelhirch.com")
    assert client.get("/api/v1/fitness/sessions", headers=stranger["headers"]).json() == []
    assert client.get("/api/v1/fitness/measurements", headers=stranger["headers"]).json() == []
# ── Habits ownership (Habit + HabitLog, t10) ─────────────────────────────────

def test_habit_cross_tenant_is_404(client):
    user_a = register_user(client, "habit-a@adamelhirch.com")
    user_b = register_user(client, "habit-b@adamelhirch.com")
    habit_id = _create_habit_for(client, user_a["headers"], name="Lire 30 minutes")
    _log_habit_for(client, user_a["headers"], habit_id)

    # Lists only expose the caller's own rows.
    assert client.get("/api/v1/habits", headers=user_b["headers"]).json() == []

    # Reads/writes/logs on another user's habit are 404 (no existence leak).
    assert client.patch(
        f"/api/v1/habits/{habit_id}", headers=user_b["headers"], json={"active": False}
    ).status_code == 404
    assert client.post(
        f"/api/v1/habits/{habit_id}/logs", headers=user_b["headers"], json={"value": 1}
    ).status_code == 404
    assert client.get(f"/api/v1/habits/{habit_id}/logs", headers=user_b["headers"]).status_code == 404

    # The owner still sees and operates everything they created.
    assert [h["id"] for h in client.get("/api/v1/habits", headers=user_a["headers"]).json()] == [habit_id]
    assert client.patch(
        f"/api/v1/habits/{habit_id}", headers=user_a["headers"], json={"description": "20 min"}
    ).status_code == 200
    assert len(client.get(f"/api/v1/habits/{habit_id}/logs", headers=user_a["headers"]).json()) == 1


def test_habit_skill_actions_are_user_scoped(client, test_engine):
    # The handler seam is exercised directly — the same seam MCP dispatches through.
    from app.models import User
    from app.skill.actions import execute_action

    owner = register_user(client, "skill-habit-a@adamelhirch.com")
    intruder = register_user(client, "skill-habit-b@adamelhirch.com")

    with Session(test_engine) as session:
        owner_user = session.get(User, int(owner["user"]["id"]))
        intruder_user = session.get(User, int(intruder["user"]["id"]))

        created = execute_action("habit.create", {"name": "Boire de l'eau"}, session, user=owner_user)
        habit_id = created["habit"]["id"]

        # The intruder's list never sees owner A's habit.
        assert execute_action("habit.list", {}, session, user=intruder_user)["habits"] == []

        # Direct access to the other user's habit fails without leaking existence.
        for action, payload in [
            ("habit.update", {"habit_id": habit_id, "description": "Hacked"}),
            ("habit.set_active", {"habit_id": habit_id, "active": False}),
            ("habit.log", {"habit_id": habit_id, "value": 1}),
            ("habit.list_logs", {"habit_id": habit_id}),
        ]:
            try:
                execute_action(action, payload, session, user=intruder_user)
                raise AssertionError(f"{action} should have failed for the intruder")
            except ValueError as exc:
                assert "not found" in str(exc)

        # The owner still fully operates on it: update, set_active, logging.
        assert [h["id"] for h in execute_action("habit.list", {}, session, user=owner_user)["habits"]] == [habit_id]
        execute_action("habit.update", {"habit_id": habit_id, "description": "2 litres"}, session, user=owner_user)
        execute_action("habit.set_active", {"habit_id": habit_id, "active": True}, session, user=owner_user)
        log = execute_action("habit.log", {"habit_id": habit_id, "value": 2}, session, user=owner_user)
        assert log["log"]["habit_id"] == habit_id
        logs = execute_action("habit.list_logs", {"habit_id": habit_id}, session, user=owner_user)
        assert [entry["value"] for entry in logs["logs"]] == [2]


def test_habit_backfill_claims_legacy_rows_to_owner(client, test_engine, owner_id, auth_headers):
    from scripts.backfill_owner_tenant import backfill

    with Session(test_engine) as session:
        habit = Habit(name="Méditation matinale", user_id=None)
        session.add(habit)
        session.flush()
        session.add(HabitLog(habit_id=habit.id, user_id=None))
        session.commit()
        legacy_habit_id = habit.id

    # Pre-scoping NULL rows are invisible to everyone until the backfill claims them.
    assert client.get("/api/v1/habits", headers=auth_headers).json() == []

    with Session(test_engine) as session:
        result = backfill(session, owner_id, commit=True)
    assert result["commit"] is True
    assert result["updated"]["habit"] == 1
    assert result["updated"]["habitlog"] == 1

    # After backfill the owner (legacy API-key path) sees and operates the rows;
    # a non-owner JWT user still cannot see or touch them.
    assert [h["id"] for h in client.get("/api/v1/habits", headers=auth_headers).json()] == [legacy_habit_id]
    stranger = register_user(client, "habit-stranger@adamelhirch.com")
    assert client.get("/api/v1/habits", headers=stranger["headers"]).json() == []
    assert client.patch(
        f"/api/v1/habits/{legacy_habit_id}", headers=stranger["headers"], json={"description": "x"}
    ).status_code == 404
    assert client.get(f"/api/v1/habits/{legacy_habit_id}/logs", headers=stranger["headers"]).status_code == 404


# ── Events ownership (CalendarEvent — distinct from CalendarItem) ────────────

def _create_event_for(client, headers, when=None) -> int:
    from datetime import UTC, datetime, timedelta

    # +3 days keeps the event inside the default 7-day "upcoming" window.
    start = when or datetime.now(UTC) + timedelta(days=3)
    end = start + timedelta(minutes=30)
    response = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "title": "Rendez-vous",
            "start_at": start.isoformat().replace("+00:00", "Z"),
            "end_at": end.isoformat().replace("+00:00", "Z"),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_events_create_auto_scopes_to_user_and_cannot_override(client, test_engine, jwt_headers):
    user = client.get("/api/v1/auth/me", headers=jwt_headers).json()
    other = register_user(client, "event-override@adamelhirch.com")["user"]

    # user_id is not part of EventCreate and is silently ignored.
    event_id = client.post(
        "/api/v1/events",
        headers=jwt_headers,
        json={
            "title": "Appel",
            "start_at": "2031-06-01T10:00:00Z",
            "end_at": "2031-06-01T10:30:00Z",
            "user_id": other["id"],
        },
    ).json()["id"]
    assert _db_user_id(test_engine, CalendarEvent, event_id) == user["id"]

    patched = client.patch(
        f"/api/v1/events/{event_id}",
        headers=jwt_headers,
        json={"title": "Renommé", "user_id": other["id"]},
    )
    assert patched.status_code == 200
    assert _db_user_id(test_engine, CalendarEvent, event_id) == user["id"]


def test_events_cross_tenant_is_404(client):
    user_a = register_user(client, "event-a@adamelhirch.com")
    user_b = register_user(client, "event-b@adamelhirch.com")
    event_id = _create_event_for(client, user_a["headers"])

    # Reads/writes on another user's event are 404 (no existence leak).
    assert client.get(f"/api/v1/events/{event_id}", headers=user_b["headers"]).status_code == 404
    assert client.patch(
        f"/api/v1/events/{event_id}", headers=user_b["headers"], json={"title": "Hacked"}
    ).status_code == 404
    assert client.delete(f"/api/v1/events/{event_id}", headers=user_b["headers"]).status_code == 404

    # Lists and upcoming only expose the caller's own rows.
    assert client.get("/api/v1/events", headers=user_b["headers"]).json() == []
    assert client.get("/api/v1/events/upcoming", headers=user_b["headers"]).json() == []

    # The owner still sees and operates the event.
    assert client.get(f"/api/v1/events/{event_id}", headers=user_a["headers"]).status_code == 200
    assert [e["id"] for e in client.get("/api/v1/events", headers=user_a["headers"]).json()] == [event_id]
    assert [e["id"] for e in client.get("/api/v1/events/upcoming", headers=user_a["headers"]).json()] == [event_id]


def test_legacy_api_key_events_scoped_to_owner_user(client, auth_headers, owner_headers):
    event_id = _create_event_for(client, auth_headers)

    # The owner (via JWT) sees everything the legacy key created.
    assert [e["id"] for e in client.get("/api/v1/events", headers=owner_headers).json()] == [event_id]
    assert [e["id"] for e in client.get("/api/v1/events/upcoming", headers=owner_headers).json()] == [event_id]

    # A freshly-registered JWT user sees none of it.
    stranger = register_user(client, "event-legacy-stranger@adamelhirch.com")
    assert client.get("/api/v1/events", headers=stranger["headers"]).json() == []
    assert client.get(f"/api/v1/events/{event_id}", headers=stranger["headers"]).status_code == 404


def test_skill_event_actions_scoped_to_acting_user(client, test_engine):
    from sqlmodel import Session

    from app.models import User
    from app.skill.actions import execute_action

    owner = register_user(client, "skill-event-a@adamelhirch.com")
    intruder = register_user(client, "skill-event-b@adamelhirch.com")

    with Session(test_engine) as session:
        owner_user = session.get(User, int(owner["user"]["id"]))
        intruder_user = session.get(User, int(intruder["user"]["id"]))

        created = execute_action(
            "event.create",
            {"title": "Appel A", "start_at": "2031-07-01T09:00:00Z", "end_at": "2031-07-01T09:30:00Z"},
            session,
            user=owner_user,
        )
        event_id = created["event"]["id"]

        # The intruder's list/upcoming never see owner A's event.
        assert execute_action("event.list", {}, session, user=intruder_user)["events"] == []
        assert execute_action("event.upcoming", {}, session, user=intruder_user)["events"] == []

        # Direct access to the other user's event fails without leaking existence.
        for action, payload in [
            ("event.get", {"event_id": event_id}),
            ("event.update", {"event_id": event_id, "title": "Hacked"}),
            ("event.delete", {"event_id": event_id}),
        ]:
            try:
                execute_action(action, payload, session, user=intruder_user)
                raise AssertionError(f"{action} should have failed for the intruder")
            except ValueError as exc:
                assert "not found" in str(exc)

        # The owner still fully operates on it: get, update, list.
        got = execute_action("event.get", {"event_id": event_id}, session, user=owner_user)
        assert got["event"]["id"] == event_id
        execute_action("event.update", {"event_id": event_id, "title": "Renommé"}, session, user=owner_user)
        assert [e["id"] for e in execute_action("event.list", {}, session, user=owner_user)["events"]] == [event_id]


def test_backfill_claims_events_for_owner(client, test_engine, owner_id, auth_headers, owner_headers):
    from datetime import UTC, datetime, timedelta

    from scripts.backfill_owner_tenant import backfill

    with Session(test_engine) as session:
        session.add(
            CalendarEvent(
                title="Legacy event",
                start_at=datetime.now(UTC) + timedelta(days=5),
                end_at=datetime.now(UTC) + timedelta(days=5, minutes=30),
                user_id=None,
            )
        )
        session.commit()

    # Pre-scoping NULL rows are invisible to everyone until the backfill claims them.
    assert client.get("/api/v1/events", headers=auth_headers).json() == []

    with Session(test_engine) as session:
        committed = backfill(session, owner_id, commit=True)
    assert committed["commit"] is True
    assert committed["updated"]["calendarevent"] == 1

    # After backfill the owner (legacy API-key path and owner JWT) sees the rows;
    # a non-owner JWT user still sees none of them.
    assert [e["title"] for e in client.get("/api/v1/events", headers=auth_headers).json()] == ["Legacy event"]
    assert [e["title"] for e in client.get("/api/v1/events", headers=owner_headers).json()] == ["Legacy event"]
    stranger = register_user(client, "event-backfill-stranger@adamelhirch.com")
    assert client.get("/api/v1/events", headers=stranger["headers"]).json() == []
