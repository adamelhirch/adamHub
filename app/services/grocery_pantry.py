from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import GroceryItem, GroceryPantrySync, PantryItem


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


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
    normalized_unit = _normalize(grocery_item.unit or "item")

    for item in pantry_items:
        if _normalize(item.name) == normalized_name and _normalize(item.unit or "item") == normalized_unit:
            target = item
            break

    quantity = max(0.0, float(grocery_item.quantity or 0.0))
    now = datetime.now(timezone.utc)

    if target:
        target.quantity = round((target.quantity or 0.0) + quantity, 3)
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

    sync_row = GroceryPantrySync(grocery_item_id=grocery_item.id, pantry_item_id=target.id)
    session.add(sync_row)
    session.commit()

    return {"synced": True, "pantry_item_id": target.id, "added_quantity": quantity}
