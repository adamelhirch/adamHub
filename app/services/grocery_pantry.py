from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import GroceryItem, GroceryPantrySync, PantryItem, SupermarketSearchCache
from app.services.meal_planning import _from_base, _to_base
from app.services.supermarket_registry import get_store_definition

# Client-facing store metadata fields that must never be fabricated: they are
# only ever populated server-side from a SupermarketSearchCache row.
STORE_METADATA_FIELDS = ("external_id", "store_label", "price_text", "product_url")


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def resolve_store_metadata(session: Session, data: dict) -> dict:
    """Resolve store-backed metadata from a SupermarketSearchCache row.

    The `cache_id` key is consumed here and never persisted. When no cache_id
    is provided, any fabricated store metadata field is rejected; when a
    cache_id is provided it must reference a real cache row and its metadata
    replaces whatever the client submitted.
    """
    cache_id = data.pop("cache_id", None)

    fabricated = [field for field in STORE_METADATA_FIELDS if data.get(field)]
    if cache_id is None:
        if fabricated:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Store metadata fields (external_id, store_label, price_text, "
                    "product_url) require a valid cache_id"
                ),
            )
        return data

    cache_row = session.get(SupermarketSearchCache, cache_id)
    if cache_row is None:
        raise HTTPException(status_code=404, detail="Search cache entry not found")

    definition = get_store_definition(cache_row.store)
    data["external_id"] = cache_row.external_id
    data["store_label"] = definition.label if definition else cache_row.store.value
    data["price_text"] = cache_row.price_text
    data["product_url"] = cache_row.product_url
    data["packaging"] = cache_row.packaging
    data["image_url"] = cache_row.image_url
    return data


def _quantity_and_base(quantity: float, unit: str) -> tuple[float, str]:
    base_quantity, base_unit = _to_base(max(0.0, float(quantity or 0.0)), unit or "item")
    return base_quantity, base_unit


def sync_checked_grocery_item_to_pantry(session: Session, grocery_item: GroceryItem) -> dict:
    if not grocery_item.checked:
        return {"synced": False, "reason": "grocery item is not checked"}

    already = session.exec(
        select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == grocery_item.id)
    ).first()
    if already:
        return {
            "synced": False,
            "reason": "already synced",
            "pantry_item_id": already.pantry_item_id,
        }

    pantry_items = session.exec(select(PantryItem)).all()
    target = None
    normalized_name = _normalize(grocery_item.name)
    quantity = max(0.0, float(grocery_item.quantity or 0.0))
    grocery_base_quantity, grocery_base_unit = _quantity_and_base(quantity, grocery_item.unit or "item")

    # Match on normalized name + base unit so "2 kg" merges into a "2000 g"
    # pantry row instead of creating a duplicate.
    for item in pantry_items:
        if _normalize(item.name) == normalized_name:
            _, pantry_base_unit = _quantity_and_base(1.0, item.unit or "item")
            if pantry_base_unit == grocery_base_unit:
                target = item
                break

    now = datetime.now(timezone.utc)

    if target:
        added_quantity = _from_base(grocery_base_quantity, target.unit or "item")
        target.quantity = round((target.quantity or 0.0) + added_quantity, 3)
        if not target.image_url and grocery_item.image_url:
            target.image_url = grocery_item.image_url
        if not target.store_label and grocery_item.store_label:
            target.store_label = grocery_item.store_label
        if not target.external_id and grocery_item.external_id:
            target.external_id = grocery_item.external_id
        if not target.packaging and grocery_item.packaging:
            target.packaging = grocery_item.packaging
        if not target.price_text and grocery_item.price_text:
            target.price_text = grocery_item.price_text
        if not target.product_url and grocery_item.product_url:
            target.product_url = grocery_item.product_url
        target.updated_at = now
        session.add(target)
    else:
        added_quantity = quantity
        target = PantryItem(
            name=grocery_item.name,
            quantity=quantity,
            unit=grocery_item.unit or "item",
            category=grocery_item.category,
            image_url=grocery_item.image_url,
            store_label=grocery_item.store_label,
            external_id=grocery_item.external_id,
            packaging=grocery_item.packaging,
            price_text=grocery_item.price_text,
            product_url=grocery_item.product_url,
            min_quantity=0,
            note=f"auto from grocery #{grocery_item.id}",
            updated_at=now,
        )
        session.add(target)
        session.commit()
        session.refresh(target)

    sync_row = GroceryPantrySync(
        grocery_item_id=grocery_item.id,
        pantry_item_id=target.id,
        added_quantity=added_quantity,
    )
    session.add(sync_row)
    session.commit()

    return {"synced": True, "pantry_item_id": target.id, "added_quantity": added_quantity}


def unsync_checked_grocery_item_from_pantry(session: Session, grocery_item: GroceryItem) -> dict:
    """Reverse a previous check→pantry restock.

    Looks up the GroceryPantrySync row created on the false→true transition,
    subtracts its added_quantity from the linked pantry item and clears the
    sync row so re-checking restocks again. Idempotent: if no sync row exists
    there is nothing to reverse.
    """
    sync_row = session.exec(
        select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == grocery_item.id)
    ).first()
    if sync_row is None:
        return {"synced": False, "reason": "no sync row to reverse"}

    pantry_item = session.get(PantryItem, sync_row.pantry_item_id)
    if pantry_item is not None:
        pantry_item.quantity = round(
            max(0.0, (pantry_item.quantity or 0.0) - (sync_row.added_quantity or 0.0)),
            3,
        )
        pantry_item.updated_at = datetime.now(timezone.utc)
        session.add(pantry_item)

    removed_quantity = sync_row.added_quantity or 0.0
    session.delete(sync_row)
    session.commit()

    return {
        "synced": True,
        "pantry_item_id": sync_row.pantry_item_id,
        "removed_quantity": removed_quantity,
    }
