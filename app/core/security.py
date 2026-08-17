import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session


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
    session: Session = Depends(get_session),
) -> None:
    """Accept a valid X-API-Key (shared or per-user), or a valid Authorization Bearer JWT.

    This is only a boolean gate — it doesn't resolve *which* user, that's done
    right after by CurrentOrOwnerUser on routers (like supermarket) that layer
    both. A per-user key must pass this outer gate too, or MCP/API calls never
    reach that per-route tenant scoping at all.
    """
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

    # Defer to the auth module to avoid circular imports (mirrors _is_valid_bearer).
    from app.core.auth import resolve_user_by_api_key

    if resolve_user_by_api_key(session, x_api_key) is not None:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )
