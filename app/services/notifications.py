import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_push_notification(title: str, message: str, priority: int = 3, tags: list[str] | None = None) -> bool:
    """
    Sends a push notification via NTFY.
    priority: 1 (min) to 5 (max/urgent)
    tags: short strings that ntfy translates into emojis (ex: 'warning', 'tada', 'loudspeaker')
    """
    if not settings.ADAMHUB_NTFY_TOPIC:
        logger.warning("Notification skipped: ADAMHUB_NTFY_TOPIC is not configured.")
        return False

    url = f"{settings.ADAMHUB_NTFY_SERVER.rstrip('/')}/{settings.ADAMHUB_NTFY_TOPIC}"
    
    headers = {
        "Title": title.encode("utf-8").decode("latin-1"),  # ntfy expects utf-8 disguised in headers
        "Priority": str(priority),
    }

    if tags:
        headers["Tags"] = ",".join(tags)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                data=message.encode("utf-8"),
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"Push notification sent successfully to topic {settings.ADAMHUB_NTFY_TOPIC}: {title}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return False
