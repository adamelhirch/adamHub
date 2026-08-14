from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings, is_dev_or_test

logger = logging.getLogger(__name__)


_DEV_FALLBACK_SEED = "adamhub-dev-cookie-key"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    """Return a process-wide Fernet instance keyed by ADAMHUB_COOKIE_ENCRYPTION_KEY.

    get_settings() already refuses to start without a real key outside dev/test,
    so the fallback below only runs in an explicit dev/test context: derive a
    deterministic key from a fallback seed so that encrypted blobs persist across
    reloads on a developer's machine. Production MUST set ADAMHUB_COOKIE_ENCRYPTION_KEY.
    """
    settings = get_settings()
    raw = (settings.cookie_encryption_key or "").strip()
    if not raw:
        if not is_dev_or_test():
            raise RuntimeError("ADAMHUB_COOKIE_ENCRYPTION_KEY is not configured")
        # Derive a dev key (NOT secure for prod — log a one-line warning).
        logger.warning(
            "ADAMHUB_COOKIE_ENCRYPTION_KEY not set: using an insecure dev-only "
            "key derived from a public seed. Set a real Fernet key outside dev/test."
        )
        digest = hashlib.sha256(_DEV_FALLBACK_SEED.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)
    # Accept either a ready-made urlsafe-b64 32-byte Fernet key or any string we
    # hash into one. Prefer the explicit key form.
    try:
        return Fernet(raw.encode() if not raw.endswith("=") else raw.encode())
    except (ValueError, TypeError):
        digest = hashlib.sha256(raw.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_text(plaintext: str) -> str:
    if plaintext is None:
        raise ValueError("plaintext is required")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_text(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Could not decrypt — wrong COOKIE_ENCRYPTION_KEY ?") from exc
