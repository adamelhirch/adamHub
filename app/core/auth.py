from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, Request
from sqlmodel import Session

from app.core.config import get_settings
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
    # Dev fallback: derive deterministic secret so tokens persist across reloads.
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
