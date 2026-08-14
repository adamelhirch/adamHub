from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, Request
from sqlmodel import Session, select

from app.core.config import get_settings, is_dev_or_test
from app.models import User


def _truncate_password(plain: str) -> bytes:
    """bcrypt only inspects the first 72 bytes — make that explicit."""
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    if not plain or len(plain) < 6:
        raise ValueError("Password must be at least 6 characters")
    return bcrypt.hashpw(_truncate_password(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_truncate_password(plain), hashed.encode("ascii"))
    except Exception:
        return False


@lru_cache(maxsize=1)
def _jwt_secret() -> str:
    settings = get_settings()
    raw = (settings.jwt_secret or "").strip()
    if raw:
        return raw
    # get_settings() already refuses to start without ADAMHUB_JWT_SECRET outside
    # dev/test, so reaching this fallback only happens in an explicit dev/test
    # context: derive a deterministic secret so tokens persist across reloads.
    if not is_dev_or_test():
        raise RuntimeError("ADAMHUB_JWT_SECRET is not configured")
    seed = "adamhub-dev-jwt-secret"
    digest = hashlib.sha256(seed.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode()


def create_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization") or request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def resolve_user_from_request(request: Request, session: Session) -> User:
    token = _extract_bearer(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token")
    payload = decode_token(token)
    user_id_raw = payload.get("sub")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Malformed token") from exc
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def resolve_optional_user(request: Request, session: Session) -> User | None:
    """Return the current user if a Bearer token is present and valid, else None.

    Lets endpoints work for both legacy X-API-Key (single-user) and the new
    JWT flow (multi-user) during the transition.
    """
    token = _extract_bearer(request)
    if not token:
        return None
    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def resolve_owner_user(session: Session) -> User:
    """Resolve the legacy owner user configured via ADAMHUB_OWNER_EMAIL.

    The owner is the single user all API-key-only traffic (the personal web
    frontend) is scoped to. Raising a 500 here (instead of silently proceeding
    with user_id=None) makes a missing or invalid owner config impossible to
    ignore.
    """
    settings = get_settings()
    owner_email = (settings.owner_email or "").strip().lower()
    if not owner_email:
        raise HTTPException(
            status_code=500,
            detail=(
                "ADAMHUB_OWNER_EMAIL is not configured. Set it to the email of "
                "the user that API-key-only requests should be scoped to."
            ),
        )
    user = session.exec(select(User).where(User.email == owner_email)).first()
    if user is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"ADAMHUB_OWNER_EMAIL user '{owner_email}' does not exist. "
                "Register that account first via POST /auth/register."
            ),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=500,
            detail=f"ADAMHUB_OWNER_EMAIL user '{owner_email}' is inactive.",
        )
    return user


def resolve_current_or_owner_user(request: Request, session: Session) -> User:
    """Resolve the acting user for the multi-tenant domain routers.

    Resolution order:
    1. A valid JWT Bearer token -> that user.
    2. A valid shared X-API-Key (legacy web frontend) -> the ADAMHUB_OWNER_EMAIL user.
    3. Neither -> 401, exactly like require_api_key.
    """
    user = resolve_optional_user(request, session)
    if user is not None:
        return user

    settings = get_settings()
    x_api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if x_api_key and any(
        secrets.compare_digest(x_api_key, key) for key in settings.api_keys_list
    ):
        return resolve_owner_user(session)

    raise HTTPException(
        status_code=401,
        detail="Missing API key or Bearer token",
    )


def require_owner_only(request: Request, session: Session) -> User:
    """Gate the unscoped off-MVP domain routers to the Owner only.

    These domains (finances, tasks, calendar, …) are not user-scoped, so a
    SaaS user must never reach them. Resolution order:
    1. A valid JWT Bearer token: allowed only if it belongs to ADAMHUB_OWNER_EMAIL;
       any other user is rejected with a plain 401 (no existence leak).
    2. A valid shared X-API-Key (legacy personal frontend) -> the owner.
    3. Neither -> 401, exactly like require_api_key.
    """
    user = resolve_current_or_owner_user(request, session)
    owner_email = (get_settings().owner_email or "").strip().lower()
    if user.email.strip().lower() == owner_email:
        return user

    raise HTTPException(status_code=401, detail="Not authorized")
