from datetime import UTC, datetime, timedelta


def test_calendar_feed_returns_filtered_ics(client, auth_headers):
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    task_due = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    event_start = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    event_end = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)

    task = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Tâche exportée",
            "due_at": task_due.isoformat().replace("+00:00", "Z"),
            "estimated_minutes": 45,
        },
    )
    assert task.status_code == 200

    event = client.post(
        "/api/v1/events",
        headers=auth_headers,
        json={
            "title": "Événement caché",
            "start_at": event_start.isoformat().replace("+00:00", "Z"),
            "end_at": event_end.isoformat().replace("+00:00", "Z"),
        },
    )
    assert event.status_code == 200

    feed = client.post(
        "/api/v1/calendar/feeds",
        headers=auth_headers,
        json={
            "name": "Tâches AdamHUB",
            "sources": ["task"],
            "include_completed": True,
        },
    )
    assert feed.status_code == 200
    body = feed.json()
    assert body["ics_url"].endswith(".ics")
    assert body["webcal_url"].startswith("webcal://")

    public = client.get(f"/calendar/feed/{body['token']}.ics")
    assert public.status_code == 200
    assert public.headers["content-type"].startswith("text/calendar")
    assert "SUMMARY:Tâche exportée" in public.text
    assert "Événement caché" not in public.text
    assert "X-WR-CALNAME:Tâches AdamHUB" in public.text


def test_calendar_feed_supports_etag(client, auth_headers):
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    task_due = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

    created = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Tâche avec cache",
            "due_at": task_due.isoformat().replace("+00:00", "Z"),
        },
    )
    assert created.status_code == 200

    feed = client.post(
        "/api/v1/calendar/feeds",
        headers=auth_headers,
        json={"name": "Cache feed"},
    )
    assert feed.status_code == 200
    token = feed.json()["token"]

    first = client.get(f"/calendar/feed/{token}.ics")
    assert first.status_code == 200
    assert "etag" in first.headers

    second = client.get(
        f"/calendar/feed/{token}.ics",
        headers={"If-None-Match": first.headers["etag"]},
    )
    assert second.status_code == 304
