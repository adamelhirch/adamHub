from datetime import UTC, datetime, timedelta


def test_habit_crud_and_logging(client, auth_headers):
    created = client.post(
        "/api/v1/habits",
        headers=auth_headers,
        json={
            "name": "Boire de l'eau",
            "description": "2 litres",
            "frequency": "daily",
            "target_per_period": 1,
        },
    )
    assert created.status_code == 200
    habit = created.json()
    assert habit["name"] == "Boire de l'eau"
    assert habit["active"] is True
    habit_id = habit["id"]

    updated = client.patch(
        f"/api/v1/habits/{habit_id}",
        headers=auth_headers,
        json={
            "description": "2,5 litres",
            "target_per_period": 2,
            "active": False,
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["description"] == "2,5 litres"
    assert updated_body["target_per_period"] == 2
    assert updated_body["active"] is False

    listed = client.get(
        "/api/v1/habits",
        headers=auth_headers,
        params={"active_only": False},
    )
    assert listed.status_code == 200
    habits = listed.json()
    assert len(habits) == 1
    assert habits[0]["id"] == habit_id

    logged = client.post(
        f"/api/v1/habits/{habit_id}/logs",
        headers=auth_headers,
        json={"value": 1, "note": "matin"},
    )
    assert logged.status_code == 200
    log = logged.json()
    assert log["habit_id"] == habit_id
    assert log["value"] == 1
    assert log["note"] == "matin"

    logs = client.get(
        f"/api/v1/habits/{habit_id}/logs",
        headers=auth_headers,
        params={"limit": 10},
    )
    assert logs.status_code == 200
    logs_body = logs.json()
    assert len(logs_body) == 1
    assert logs_body[0]["habit_id"] == habit_id


def test_scheduled_habit_is_projected_in_calendar(client, auth_headers):
    target_day = datetime.now(UTC).date() + timedelta(days=1)

    created = client.post(
        "/api/v1/habits",
        headers=auth_headers,
        json={
            "name": "Lecture",
            "frequency": "daily",
            "target_per_period": 1,
            "schedule_time": "20:00",
            "duration_minutes": 25,
        },
    )
    assert created.status_code == 200
    habit_id = created.json()["id"]

    calendar = client.get(
        "/api/v1/calendar/items",
        headers=auth_headers,
        params={
            "from_at": f"{target_day.isoformat()}T00:00:00Z",
            "to_at": f"{target_day.isoformat()}T23:59:59Z",
            "include_completed": True,
            "limit": 200,
        },
    )
    assert calendar.status_code == 200
    matches = [
        item
        for item in calendar.json()
        if item["source"] == "habit" and item["source_ref_id"] == habit_id
    ]
    assert len(matches) == 1
    assert matches[0]["start_at"] == f"{target_day.isoformat()}T20:00:00Z"


def test_habit_creation_rejects_overlap_with_existing_calendar_item(client, auth_headers):
    target_day = datetime.now(UTC).date() + timedelta(days=2)

    manual = client.post(
        "/api/v1/calendar/items",
        headers=auth_headers,
        json={
            "title": "Appel client",
            "start_at": f"{target_day.isoformat()}T07:00:00Z",
            "end_at": f"{target_day.isoformat()}T07:45:00Z",
            "all_day": False,
        },
    )
    assert manual.status_code == 200

    created = client.post(
        "/api/v1/habits",
        headers=auth_headers,
        json={
            "name": "Étirements",
            "frequency": "daily",
            "target_per_period": 1,
            "schedule_time": "07:15",
            "duration_minutes": 20,
        },
    )
    assert created.status_code == 409
    assert "overlaps" in created.json()["detail"].lower()


def test_habit_with_multiple_schedule_times_creates_multiple_calendar_occurrences(
    client,
    auth_headers,
):
    target_day = datetime.now(UTC).date() + timedelta(days=1)

    created = client.post(
        "/api/v1/habits",
        headers=auth_headers,
        json={
            "name": "Hydratation",
            "frequency": "daily",
            "target_per_period": 2,
            "schedule_times": ["08:00", "14:00"],
            "duration_minutes": 10,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["schedule_times"] == ["08:00", "14:00"]

    calendar = client.get(
        "/api/v1/calendar/items",
        headers=auth_headers,
        params={
            "from_at": f"{target_day.isoformat()}T00:00:00Z",
            "to_at": f"{target_day.isoformat()}T23:59:59Z",
            "include_completed": True,
            "limit": 200,
        },
    )
    assert calendar.status_code == 200
    matches = [
        item
        for item in calendar.json()
        if item["source"] == "habit" and item["title"] == "Hydratation"
    ]
    assert len(matches) == 2
    assert [item["start_at"] for item in matches] == [
        f"{target_day.isoformat()}T08:00:00Z",
        f"{target_day.isoformat()}T14:00:00Z",
    ]


def test_weekly_habit_with_multiple_weekdays_creates_occurrences_on_each_day(
    client,
    auth_headers,
):
    today = datetime.now(UTC).date()
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    next_wednesday = next_monday + timedelta(days=2)

    created = client.post(
        "/api/v1/habits",
        headers=auth_headers,
        json={
            "name": "Marche rapide",
            "frequency": "weekly",
            "target_per_period": 2,
            "schedule_times": ["07:30"],
            "schedule_weekdays": [0, 2],
            "duration_minutes": 20,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["schedule_weekdays"] == [0, 2]

    calendar = client.get(
        "/api/v1/calendar/items",
        headers=auth_headers,
        params={
            "from_at": f"{next_monday.isoformat()}T00:00:00Z",
            "to_at": f"{(next_wednesday + timedelta(days=1)).isoformat()}T00:00:00Z",
            "include_completed": True,
            "limit": 200,
        },
    )
    assert calendar.status_code == 200
    matches = [
        item
        for item in calendar.json()
        if item["source"] == "habit" and item["title"] == "Marche rapide"
    ]
    assert len(matches) == 2
    assert [item["start_at"] for item in matches] == [
        f"{next_monday.isoformat()}T07:30:00Z",
        f"{next_wednesday.isoformat()}T07:30:00Z",
    ]
