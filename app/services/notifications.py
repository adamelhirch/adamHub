import logging
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

async def send_push_notification(
    title: str, 
    message: str, 
    priority: int = 3, 
    tags: list[str] | None = None,
    click: str | None = None,
    icon: str | None = None,
    actions: list[dict] | None = None
) -> bool:
    """
    Sends a push notification via NTFY.
    priority: 1 (min) to 5 (max/urgent)
    tags: short strings that ntfy translates into emojis (ex: 'warning', 'tada', 'loudspeaker')
    click: URL to open when the notification is clicked.
    icon: URL to an image to use as the icon.
    actions: List of dictionaries defining interactive buttons (see NTFY docs).
    """
    if not settings.ntfy_topic:
        logger.warning("Notification skipped: ADAMHUB_NTFY_TOPIC is not configured.")
        return False

    url = settings.ntfy_server.rstrip('/')
    
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
            response = await client.post(
                url,
                json=payload
            )
            response.raise_for_status()
            logger.info(f"Push notification sent successfully to topic {settings.ntfy_topic}: {title}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return False
