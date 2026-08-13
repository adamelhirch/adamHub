from fastapi import APIRouter, Depends, Query
from sqlmodel import select

from app.api._crud import apply_updates, create, delete, get_owned_or_404, save
from app.api.deps import CurrentOrOwnerUser, SessionDep
from app.models import GroceryItem, GroceryPantrySync
from app.schemas import GroceryItemCreate, GroceryItemRead, GroceryItemUpdate
from app.services.grocery_pantry import (
    resolve_store_metadata,
    sync_checked_grocery_item_to_pantry,
    unsync_checked_grocery_item_from_pantry,
)

router = APIRouter(prefix="/groceries", tags=["groceries"])


@router.post("", response_model=GroceryItemRead)
def create_grocery_item(
    payload: GroceryItemCreate, session: SessionDep, user: CurrentOrOwnerUser
) -> GroceryItemRead:
    data = resolve_store_metadata(session, payload.model_dump())
    item = create(session, GroceryItem(**data, user_id=user.id))
    return GroceryItemRead.model_validate(item, from_attributes=True)


@router.get("", response_model=list[GroceryItemRead])
def list_grocery_items(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    checked: bool | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[GroceryItemRead]:
    statement = (
        select(GroceryItem)
        .where(GroceryItem.user_id == user.id)
        .order_by(GroceryItem.checked.asc(), GroceryItem.priority.asc())
        .limit(limit)
    )
    if checked is not None:
        statement = statement.where(GroceryItem.checked == checked)

    items = session.exec(statement).all()
    return [GroceryItemRead.model_validate(item, from_attributes=True) for item in items]


@router.patch("/{item_id}", response_model=GroceryItemRead)
def update_grocery_item(
    item_id: int,
    payload: GroceryItemUpdate,
    session: SessionDep,
    user: CurrentOrOwnerUser,
) -> GroceryItemRead:
    item = get_owned_or_404(session, GroceryItem, item_id, user_id=user.id, detail="Grocery item not found")

    was_checked = item.checked
    updates = payload.model_dump(exclude_unset=True)
    if "cache_id" in updates:
        updates = resolve_store_metadata(session, updates)
    apply_updates(item, updates, touch=True)
    item = save(session, item)

    if not was_checked and item.checked:
        sync_checked_grocery_item_to_pantry(session, item, user_id=user.id)
    elif was_checked and not item.checked:
        unsync_checked_grocery_item_from_pantry(session, item)

    return GroceryItemRead.model_validate(item, from_attributes=True)


@router.delete("/{item_id}")
def delete_grocery_item(
    item_id: int, session: SessionDep, user: CurrentOrOwnerUser
) -> dict:
    item = get_owned_or_404(session, GroceryItem, item_id, user_id=user.id, detail="Grocery item not found")

    # Keep sync table consistent (important with PostgreSQL FK checks).
    sync_rows = session.exec(
        select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == item_id)
    ).all()
    for row in sync_rows:
        session.delete(row)
    if sync_rows:
        # Flush these deletes first to satisfy FK constraints on PostgreSQL.
        session.commit()

    delete(session, item)
    return {"ok": True, "deleted_id": item_id}
