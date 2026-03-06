from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import GroceryPantrySync, PantryItem
from app.schemas import (
    PantryConsume,
    PantryItemCreate,
    PantryItemRead,
    PantryItemUpdate,
    PantryOverview,
)
from app.services.life import build_pantry_overview

router = APIRouter(prefix="/pantry", tags=["pantry"], dependencies=[Depends(require_api_key)])


@router.post("/items", response_model=PantryItemRead)
def create_pantry_item(payload: PantryItemCreate, session: SessionDep) -> PantryItemRead:
    item = PantryItem(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return PantryItemRead.model_validate(item, from_attributes=True)


@router.get("/items", response_model=list[PantryItemRead])
def list_pantry_items(
    session: SessionDep,
    low_stock_only: bool = False,
    expiring_in_days: int | None = Query(default=None, ge=1, le=3650),
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[PantryItemRead]:
    statement = select(PantryItem).order_by(PantryItem.updated_at.desc()).limit(limit)
    if low_stock_only:
        statement = statement.where(PantryItem.quantity <= PantryItem.min_quantity)
    if expiring_in_days is not None:
        until = date.today() + timedelta(days=expiring_in_days)
        statement = statement.where(PantryItem.expires_at.is_not(None), PantryItem.expires_at <= until)

    items = session.exec(statement).all()
    return [PantryItemRead.model_validate(item, from_attributes=True) for item in items]


@router.patch("/items/{item_id}", response_model=PantryItemRead)
def update_pantry_item(item_id: int, payload: PantryItemUpdate, session: SessionDep) -> PantryItemRead:
    item = session.get(PantryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pantry item not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)

    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    return PantryItemRead.model_validate(item, from_attributes=True)


@router.post("/items/{item_id}/consume", response_model=PantryItemRead)
def consume_pantry_item(item_id: int, payload: PantryConsume, session: SessionDep) -> PantryItemRead:
    item = session.get(PantryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pantry item not found")

    item.quantity = max(0.0, item.quantity - payload.amount)
    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    return PantryItemRead.model_validate(item, from_attributes=True)


@router.delete("/items/{item_id}")
def delete_pantry_item(item_id: int, session: SessionDep) -> dict:
    item = session.get(PantryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pantry item not found")

    # Keep sync table consistent (important with PostgreSQL FK checks).
    sync_rows = session.exec(
        select(GroceryPantrySync).where(GroceryPantrySync.pantry_item_id == item_id)
    ).all()
    for row in sync_rows:
        session.delete(row)
    if sync_rows:
        # Flush these deletes first to satisfy FK constraints on PostgreSQL.
        session.commit()

    session.delete(item)
    session.commit()
    return {"ok": True, "deleted_id": item_id}


@router.get("/overview", response_model=PantryOverview)
def pantry_overview(session: SessionDep, days: int = Query(default=7, ge=1, le=365)) -> PantryOverview:
    return build_pantry_overview(session, days=days)
