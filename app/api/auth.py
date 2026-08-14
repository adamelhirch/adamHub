from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.core.auth import create_token, hash_password, verify_password
from app.core.security import require_api_key
from app.models import User


router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)
    display_name: str = Field(min_length=1, max_length=80)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str
    is_active: bool
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
        created_at=user.created_at,
    )


@router.get("/check", dependencies=[Depends(require_api_key)])
def auth_check() -> dict:
    return {"ok": True}


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterPayload, session: SessionDep) -> AuthResponse:
    email = payload.email.lower().strip()
    statement = select(User).where(User.email == email)
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="Cet email est déjà inscrit")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Cet email est déjà inscrit") from exc
    session.refresh(user)

    return AuthResponse(token=create_token(user), user=_to_user_read(user))


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
