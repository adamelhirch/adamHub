from __future__ import annotations

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.core.auth import create_token, hash_api_key, hash_password, verify_password
from app.core.crypto import decrypt_text, encrypt_text
from app.core.security import require_api_key
from app.models import User
from app.services.email import hash_email_verification_token, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)
    display_name: str = Field(min_length=1, max_length=80)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailPayload(BaseModel):
    token: str = Field(min_length=1)


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str
    is_active: bool
    email_verified: bool
    created_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserRead


def _to_user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        email_verified=user.email_verified,
        created_at=user.created_at,
    )


@router.get("/check", dependencies=[Depends(require_api_key)])
def auth_check() -> dict:
    return {"ok": True}


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterPayload, session: SessionDep) -> AuthResponse:
    email = payload.email.lower().strip()
    statement = select(User).where(User.email == email)
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="Cet email est déjà inscrit")

    verification_token = secrets.token_urlsafe(32)
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        email_verification_token_hash=hash_email_verification_token(verification_token),
        email_verification_sent_at=datetime.now(UTC),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Cet email est déjà inscrit") from exc
    session.refresh(user)

    # Sending is best-effort: a missing Resend key (dev/test) or a Resend outage
    # must never fail signup. send_verification_email logs and returns False.
    await send_verification_email(session, user, verification_token)

    return AuthResponse(token=create_token(user), user=_to_user_read(user))


def _user_for_token(session: SessionDep, raw_token: str) -> User | None:
    """Find the user whose stored hash matches raw_token (constant-time compare).

    Returns None when no user holds the token (bad, expired or already-used).
    """
    token_hash = hash_email_verification_token(raw_token)
    statement = select(User).where(User.email_verification_token_hash.is_not(None))
    for candidate in session.exec(statement):
        if candidate.email_verification_token_hash is not None and secrets.compare_digest(
            candidate.email_verification_token_hash, token_hash
        ):
            return candidate
    return None


def _mark_verified(session: SessionDep, user: User) -> None:
    user.email_verified = True
    user.email_verification_token_hash = None
    user.email_verification_sent_at = None
    user.updated_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    session.refresh(user)


@router.post("/verify-email", response_model=UserRead)
def verify_email(payload: VerifyEmailPayload, session: SessionDep) -> UserRead:
    user = _user_for_token(session, payload.token)
    if user is None:
        raise HTTPException(status_code=400, detail="Lien de vérification invalide ou expiré")
    _mark_verified(session, user)
    return _to_user_read(user)


@router.get("/verify-email", response_class=HTMLResponse, include_in_schema=False)
def verify_email_from_link(token: str, session: SessionDep) -> HTMLResponse:
    """Browser-facing link target used inside the verification email."""
    user = _user_for_token(session, token)
    if user is None:
        return HTMLResponse(
            "<html><body style=\"font-family: sans-serif; padding: 24px;\">"
            "<h2>Lien invalide</h2>"
            "<p>Ce lien de vérification est invalide ou a déjà été utilisé.</p>"
            "</body></html>",
            status_code=400,
        )
    _mark_verified(session, user)
    return HTMLResponse(
        "<html><body style=\"font-family: sans-serif; padding: 24px;\">"
        "<h2>Email vérifié &#9989;</h2>"
        "<p>Votre adresse email est confirmée. Vous pouvez fermer cette page.</p>"
        "</body></html>"
    )


@router.post("/resend-verification")
async def resend_verification(session: SessionDep, current: CurrentUser) -> dict:
    if current.email_verified:
        raise HTTPException(status_code=400, detail="Votre email est déjà vérifié")

    verification_token = secrets.token_urlsafe(32)
    current.email_verification_token_hash = hash_email_verification_token(verification_token)
    current.email_verification_sent_at = datetime.now(UTC)
    current.updated_at = datetime.now(UTC)
    session.add(current)
    session.commit()
    session.refresh(current)

    await send_verification_email(session, current, verification_token)
    return {"message": "Email de vérification renvoyé"}


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginPayload, session: SessionDep) -> AuthResponse:
    email = payload.email.lower().strip()
    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    user.updated_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    session.refresh(user)

    return AuthResponse(token=create_token(user), user=_to_user_read(user))


@router.get("/me", response_model=UserRead)
def me(current: CurrentUser) -> UserRead:
    return _to_user_read(current)


class ApiKeyRead(BaseModel):
    api_key: str | None
    created_at: datetime | None


@router.get("/api-key", response_model=ApiKeyRead)
def get_api_key(current: CurrentUser) -> ApiKeyRead:
    """Kept always-visible (not show-once): decrypted on demand for Settings."""
    if not current.api_key_encrypted:
        return ApiKeyRead(api_key=None, created_at=None)
    return ApiKeyRead(api_key=decrypt_text(current.api_key_encrypted), created_at=current.api_key_created_at)


@router.post("/api-key", response_model=ApiKeyRead)
def create_or_regenerate_api_key(current: CurrentUser, session: SessionDep) -> ApiKeyRead:
    """Generate a fresh key, invalidating any previous one for this user."""
    raw_key = f"ahub_{secrets.token_urlsafe(32)}"
    current.api_key_encrypted = encrypt_text(raw_key)
    current.api_key_hash = hash_api_key(raw_key)
    current.api_key_created_at = datetime.now(UTC)
    current.updated_at = datetime.now(UTC)
    session.add(current)
    session.commit()
    return ApiKeyRead(api_key=raw_key, created_at=current.api_key_created_at)


@router.delete("/api-key", status_code=204)
def revoke_api_key(current: CurrentUser, session: SessionDep) -> None:
    current.api_key_encrypted = None
    current.api_key_hash = None
    current.api_key_created_at = None
    current.updated_at = datetime.now(UTC)
    session.add(current)
    session.commit()
