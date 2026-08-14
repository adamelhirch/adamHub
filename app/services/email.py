import hashlib
import logging
from urllib.parse import urlencode

import httpx
from sqlmodel import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def hash_email_verification_token(token: str) -> str:
    """SHA-256 of the raw token; only the hash is ever persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_verification_url(token: str) -> str:
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    return f"{base}/api/v1/auth/verify-email?{urlencode({'token': token})}"


async def send_verification_email(session: Session, user, token: str) -> bool:
    """Send a verification email via Resend (async, never raises).

    Returns True when the email was handed to Resend, False when Resend is not
    configured (dev/test) or the call failed. Callers must never block signup
    on the result.
    """
    settings = get_settings()

    if not settings.resend_api_key:
        logger.warning("Email verification skipped: ADAMHUB_RESEND_API_KEY is not configured.")
        return False

    verify_url = build_verification_url(token)
    html = (
        "<div style=\"font-family: sans-serif; max-width: 480px; margin: 0 auto;\">"
        f"<h2>Bienvenue {user.display_name} &#128075;</h2>"
        "<p>Cliquez sur le lien ci-dessous pour vérifier votre adresse email et "
        "activer votre compte AdamHUB :</p>"
        f"<p><a href=\"{verify_url}\" style=\"display: inline-block; padding: 12px 20px; "
        "background: #1f6feb; color: #fff; border-radius: 6px; "
        "text-decoration: none;\">Vérifier mon email</a></p>"
        f"<p>Si le bouton ne fonctionne pas : <a href=\"{verify_url}\">{verify_url}</a></p>"
        "</div>"
    )

    payload = {
        "from": settings.email_from,
        "to": [user.email],
        "subject": "AdamHUB — Vérifiez votre adresse email",
        "html": html,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info("Verification email sent to %s", user.email)
            return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send verification email to %s: %s", user.email, exc)
        return False
