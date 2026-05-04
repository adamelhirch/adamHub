import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings


def _is_valid_bearer(authorization: str | None) -> bool:
    """Return True if the Authorization header carries a JWT we can decode."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return False
    token = authorization[7:].strip()
    if not token:
        return False
    # Defer the actual validation to the auth module to avoid circular imports.
    from app.core.auth import decode_token

    try:
        decode_token(token)
        return True
    except HTTPException:
        return False


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """Accept either a valid X-API-Key or a valid Authorization Bearer JWT."""
    if _is_valid_bearer(authorization):
        return

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key or Bearer token",
        )

    for key in settings.api_keys_list:
        if secrets.compare_digest(x_api_key, key):
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )
