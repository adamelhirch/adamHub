import logging
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def build_hub_link(path: str, **query: str | int | float | None) -> str:
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"

    clean_query = {k: str(v) for k, v in query.items() if v is not None}
    if not clean_query:
        return f"{base}{normalized_path}"
    return f"{base}{normalized_path}?{urlencode(clean_query)}"


async def send_push_notification(
    title: str,
    message: str,
    priority: int = 3,
    tags: list[str] | None = None,
    click: str | None = None,
    icon: str | None = None,
    actions: list[dict] | None = None,
) -> bool:
    """
    Sends a push notification via NTFY.
    priority: 1 (min) to 5 (max/urgent)
    tags: short strings that ntfy translates into emojis.
    click: URL to open when the notification is clicked.
    icon: URL to an image to use as the icon.
    actions: List of dictionaries defining interactive buttons.
    """
    settings = get_settings()

    if not settings.ntfy_topic:
        logger.warning("Notification skipped: ADAMHUB_NTFY_TOPIC is not configured.")
        return False

    url = settings.ntfy_server.rstrip("/")

    payload = {
        "topic": settings.ntfy_topic,
        "message": message,
        "title": title,
        "priority": priority,
    }

    if tags:
        payload["tags"] = tags
    if click:
        payload["click"] = click
    if icon:
        payload["icon"] = icon
    if actions:
        payload["actions"] = actions

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Push notification sent to topic %s: %s", settings.ntfy_topic, title)
            return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send push notification: %s", exc)
        return False
