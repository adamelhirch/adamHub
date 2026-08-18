from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.models import CalendarFeed


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


def test_legacy_feed_without_user_id_still_serves_owner_calendar(client, auth_headers, test_engine):
    # Pre-backfill feeds have user_id = NULL. Their public .ics must keep
    # working and resolve to the owner tenant (the backfill's semantics), never
    # to "all users" or to a stranger's calendar. Guard against the regression
    # where the token route stops scoping legacy feeds at all.
    with Session(test_engine) as session:
        session.add(
            CalendarFeed(name="Feed hérité", token="legacy-token-no-user", user_id=None, sources=["task"])
        )
        session.commit()

    tomorrow = datetime.now(UTC) + timedelta(days=1)
    task = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "title": "Tâche owner héritée",
            "due_at": tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        },
    )
    assert task.status_code == 200, task.text

    public = client.get("/calendar/feed/legacy-token-no-user.ics")
    assert public.status_code == 200
    assert "SUMMARY:Tâche owner héritée" in public.text
