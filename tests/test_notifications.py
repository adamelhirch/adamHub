import asyncio
from datetime import date, timedelta

from sqlmodel import Session

from app.core import scheduler as scheduler_module
from app.core.config import get_settings
from app.models import PantryItem, User
from app.services.notifications import build_hub_link


def test_build_hub_link_uses_public_base_url(monkeypatch):
    monkeypatch.setenv("ADAMHUB_PUBLIC_BASE_URL", "http://localhost:5173")
    get_settings.cache_clear()

    url = build_hub_link("/pantry", item=42)

    assert url == "http://localhost:5173/pantry?item=42"
    get_settings.cache_clear()


def test_expiring_pantry_items_notification(test_engine, monkeypatch):
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
                "topic": topic,
            }
        )
        return True

    monkeypatch.setattr(scheduler_module, "send_push_notification", fake_send_push_notification)

    today = date.today()
    with Session(test_engine) as session:
        item = PantryItem(
            name="Yaourt nature",
            quantity=2,
            unit="pot",
            expires_at=today + timedelta(days=1),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    asyncio.run(scheduler_module.check_expiring_pantry_items())

    assert len(sent_payloads) == 1
    assert "Yaourt nature" in sent_payloads[0]["title"]
    assert sent_payloads[0]["click"] is not None
    assert f"item={item_id}" in sent_payloads[0]["click"]

    get_settings.cache_clear()
