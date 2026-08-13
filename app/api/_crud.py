from datetime import datetime, timezone
from typing import TypeVar

from fastapi import HTTPException
from sqlmodel import Session, SQLModel

ModelT = TypeVar("ModelT", bound=SQLModel)


def get_or_404(session: Session, model: type[ModelT], object_id: int, *, detail: str) -> ModelT:
    obj = session.get(model, object_id)
    if not obj:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def get_owned_or_404(
    session: Session,
    model: type[ModelT],
    object_id: int,
    *,
    user_id: int,
    detail: str,
) -> ModelT:
    """Fetch a row or 404 — including when it exists but belongs to another user.

    A 404 (not 403) is used on purpose so we don't leak whether a row with that
    id exists for a different tenant.
    """
    obj = session.get(model, object_id)
    if obj is None or getattr(obj, "user_id", None) != user_id:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def create(session: Session, obj: ModelT) -> ModelT:
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def apply_updates(obj: ModelT, updates: dict, *, touch: bool = False) -> ModelT:
    for key, value in updates.items():
        setattr(obj, key, value)
    if touch:
        obj.updated_at = datetime.now(timezone.utc)
    return obj


def save(session: Session, obj: ModelT) -> ModelT:
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def delete(session: Session, obj: ModelT) -> None:
    session.delete(obj)
    session.commit()
