import asyncio
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.core import scheduler as scheduler_module
from app.core.config import get_settings
from app.models import CalendarCategory, CalendarItem, CalendarSource, User
from app.services.notifications import build_hub_link


def test_build_hub_link_uses_public_base_url(monkeypatch):
    monkeypatch.setenv("ADAMHUB_PUBLIC_BASE_URL", "http://localhost:5173")
    get_settings.cache_clear()

    url = build_hub_link("/calendar", day="2026-03-06", item=42)

    assert url == "http://localhost:5173/calendar?day=2026-03-06&item=42"
    get_settings.cache_clear()


def test_due_calendar_reminder_sends_click_and_marks_notified(test_engine, monkeypatch):
    monkeypatch.setenv("ADAMHUB_PUBLIC_BASE_URL", "http://localhost:5173")
    get_settings.cache_clear()

    monkeypatch.setattr(scheduler_module, "engine", test_engine)

    sent_payloads: list[dict] = []

    async def fake_send_push_notification(title, message, priority=3, tags=None, click=None, icon=None, actions=None, topic=None):
        sent_payloads.append(
            {
                "title": title,
                "message": message,
                "priority": priority,
                "tags": tags,
                "click": click,
                "icon": icon,
                "actions": actions,
                "topic": topic,
            }
        )
        return True

    monkeypatch.setattr(scheduler_module, "send_push_notification", fake_send_push_notification)

    now = datetime.now(UTC)
    with Session(test_engine) as session:
        item = CalendarItem(
            title="Reminder test",
            description="Check reminder",
            start_at=now + timedelta(minutes=2),
            end_at=now + timedelta(minutes=32),
            category=CalendarCategory.TASK,
            source=CalendarSource.MANUAL,
            generated=False,
            completed=False,
            notification_enabled=True,
            reminder_offsets_min=[1],
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    asyncio.run(scheduler_module.send_due_calendar_reminders(within_minutes=10))

    assert len(sent_payloads) == 1
    assert sent_payloads[0]["title"] == "Reminder: Reminder test"
    assert sent_payloads[0]["click"] is not None
    assert sent_payloads[0]["click"].startswith("http://localhost:5173/calendar?")
    assert f"item={item_id}" in sent_payloads[0]["click"]

    with Session(test_engine) as session:
        refreshed = session.get(CalendarItem, item_id)
        assert refreshed is not None
        assert refreshed.last_notified_at is not None

    get_settings.cache_clear()


def test_due_calendar_reminder_routes_to_owner_ntfy_topic(test_engine, monkeypatch):
    """Each reminder goes to its calendar item owner's ntfy topic; users
    without a configured topic fall back to the global ADAMHUB_NTFY_TOPIC."""
    monkeypatch.setenv("ADAMHUB_PUBLIC_BASE_URL", "http://localhost:5173")
    monkeypatch.setenv("ADAMHUB_NTFY_TOPIC", "global-reminders")
    get_settings.cache_clear()

    monkeypatch.setattr(scheduler_module, "engine", test_engine)

    sent_payloads: list[dict] = []

    async def fake_send_push_notification(title, message, priority=3, tags=None, click=None, icon=None, actions=None, topic=None):
        sent_payloads.append({"title": title, "topic": topic})
        return True

    monkeypatch.setattr(scheduler_module, "send_push_notification", fake_send_push_notification)

    now = datetime.now(UTC)
    with Session(test_engine) as session:
        user_a = User(
            email="alice@example.com",
            password_hash="x",
            display_name="Alice",
            ntfy_topic="alice-topic",
        )
        user_b = User(
            email="bob@example.com",
            password_hash="x",
            display_name="Bob",
            ntfy_topic="bob-topic",
        )
        user_c = User(
            email="carol@example.com",
            password_hash="x",
            display_name="Carol",
        )  # no personal topic -> global default
        session.add_all([user_a, user_b, user_c])
        session.commit()
        for user, title in [
            (user_a, "Alice item"),
            (user_b, "Bob item"),
            (user_c, "Carol item"),
        ]:
            session.add(
                CalendarItem(
                    title=title,
                    user_id=user.id,
                    start_at=now + timedelta(minutes=2),
                    end_at=now + timedelta(minutes=32),
                    category=CalendarCategory.TASK,
                    source=CalendarSource.MANUAL,
                    generated=False,
                    notification_enabled=True,
                    reminder_offsets_min=[1],
                )
            )
        session.commit()

    asyncio.run(scheduler_module.send_due_calendar_reminders(within_minutes=10))

    by_title = {payload["title"]: payload["topic"] for payload in sent_payloads}
    assert by_title["Reminder: Alice item"] == "alice-topic"
    assert by_title["Reminder: Bob item"] == "bob-topic"
    assert by_title["Reminder: Carol item"] == "global-reminders"

    get_settings.cache_clear()
