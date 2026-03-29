import asyncio
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.core import scheduler as scheduler_module
from app.core.config import get_settings
from app.models import CalendarCategory, CalendarItem, CalendarSource
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

    async def fake_send_push_notification(title, message, priority=3, tags=None, click=None, icon=None, actions=None):
        sent_payloads.append(
            {
                "title": title,
                "message": message,
                "priority": priority,
                "tags": tags,
                "click": click,
                "icon": icon,
                "actions": actions,
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
