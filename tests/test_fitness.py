def test_fitness_session_supports_structured_exercises(client, auth_headers):
    created = client.post(
        "/api/v1/fitness/sessions",
        headers=auth_headers,
        json={
            "title": "Séance test",
            "session_type": "strength",
            "planned_at": "2026-03-29T18:00:00Z",
            "duration_minutes": 60,
            "exercises": [
                {
                    "name": "Squats",
                    "mode": "reps",
                    "reps": 12,
                    "note": "Contrôlé",
                },
                {
                    "name": "Planche",
                    "mode": "duration",
                    "duration_minutes": 3,
                },
            ],
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["title"] == "Séance test"
    assert payload["exercises"][0]["name"] == "Squats"
    assert payload["exercises"][0]["mode"] == "reps"
    assert payload["exercises"][0]["reps"] == 12
    assert payload["exercises"][1]["name"] == "Planche"
    assert payload["exercises"][1]["mode"] == "duration"
    assert payload["exercises"][1]["duration_minutes"] == 3

    updated = client.patch(
        f"/api/v1/fitness/sessions/{payload['id']}",
        headers=auth_headers,
        json={
            "exercises": [
                {
                    "name": "Squats",
                    "mode": "reps",
                    "reps": 15,
                }
            ],
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["exercises"][0]["reps"] == 15


def test_fitness_session_accepts_legacy_exercise_strings(client, auth_headers):
    created = client.post(
        "/api/v1/fitness/sessions",
        headers=auth_headers,
        json={
            "title": "Séance legacy",
            "planned_at": "2026-03-29T19:00:00Z",
            "exercises": ["Pompes", "Gainage"],
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["exercises"][0]["name"] == "Pompes"
    assert payload["exercises"][0]["mode"] == "reps"
    assert payload["exercises"][1]["name"] == "Gainage"


def test_fitness_session_syncs_to_calendar(client, auth_headers):
    created = client.post(
        "/api/v1/fitness/sessions",
        headers=auth_headers,
        json={
            "title": "Cardio run",
            "session_type": "cardio",
            "planned_at": "2026-03-29T20:00:00Z",
            "duration_minutes": 40,
            "exercises": [{"name": "Running", "mode": "duration", "duration_minutes": 40}],
        },
    )
    assert created.status_code == 200
    session_id = created.json()["id"]

    sync = client.post("/api/v1/calendar/sync", headers=auth_headers)
    assert sync.status_code == 200
    assert sync.json()["generated_by_source"]["fitness_session"] == 1

    calendar_rows = client.get(
        "/api/v1/calendar/items",
        headers=auth_headers,
        params={"generated_only": True, "include_completed": True, "limit": 1000},
    )
    assert calendar_rows.status_code == 200
    row = next(item for item in calendar_rows.json() if item["source"] == "fitness_session" and item["source_ref_id"] == session_id)
    assert row["title"] == "Fitness: Cardio run"
    assert row["completed"] is False
