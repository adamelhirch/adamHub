from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import GroceryItem, GroceryPantrySync, PantryItem
from app.services.store_catalog import reject_fabricated_store_fields, resolve_store_fields
from app.services.units import from_base, normalize_name, to_base


def _normalized_like_pattern(normalized_name: str) -> str:
    """Build a LIKE pattern matching any stored name that could normalize to ``normalized_name``.

    ``normalize_name`` collapses whitespace runs and lowercases, so the pattern
    joins the name's tokens with ``%`` to tolerate arbitrary spacing in the
    stored value. LIKE wildcards (``%``, ``_``) present in the name are escaped.
    The pattern is a superset of exact ``normalize_name`` equality: the caller's
    Python mini-scan still re-verifies before merging, keeping semantics unchanged.

    Limit: the pre-filter is not index-backed (``lower(name) LIKE ...``), and
    ``lower()`` on SQLite only folds ASCII case, so non-ASCII uppercase in a
    stored name may be skipped on SQLite (PostgreSQL is Unicode-aware). If
    that ever matters, ``normalize_name`` is deterministic on the stored name,
    so a derived, indexed ``normalized_name`` column populated at write time
    would make the filter an exact index-backed equality.
    """
    escaped = normalized_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + escaped.replace(" ", "%") + "%"


def resolve_store_metadata(session: Session, data: dict) -> dict:
    """Resolve store-backed metadata from a SupermarketSearchCache row.

    The `cache_id` key is consumed here and never persisted. When no cache_id
    is provided, any fabricated store metadata field is rejected; when a
    cache_id is provided it must reference a real cache row and its metadata
    replaces whatever the client submitted.
    """
    cache_id = data.pop("cache_id", None)

    if cache_id is None:
        reject_fabricated_store_fields(data)
        return data

    resolved = resolve_store_fields(session, cache_id)
    for field in ("external_id", "store_label", "price_text", "product_url", "packaging", "image_url"):
        data[field] = resolved[field]
    return data


def sync_checked_grocery_item_to_pantry(
    session: Session,
    grocery_item: GroceryItem,
    *,
    user_id: int | None = None,
) -> dict:
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

    normalized_name = normalize_name(grocery_item.name)
    quantity = max(0.0, float(grocery_item.quantity or 0.0))
    grocery_base_quantity, grocery_base_unit = to_base(quantity, grocery_item.unit or "item")

    # Pre-filter in SQL instead of loading the whole pantry in memory: only
    # rows whose stored name could normalize to the grocery name are candidates.
    # The LIKE pattern tolerates case/whitespace variance; unit compatibility is
    # still decided below via to_base, so semantics are unchanged (2 kg merges
    # into a 2000 g row).
    statement = select(PantryItem).where(
        func.lower(PantryItem.name).like(_normalized_like_pattern(normalized_name), escape="\\")
    )
    if user_id is not None:
        statement = statement.where(PantryItem.user_id == user_id)
    candidates = session.exec(statement).all()

    # Match on normalized name + base unit so "2 kg" merges into a "2000 g"
    # pantry row instead of creating a duplicate.
    target = None
    for item in candidates:
        if normalize_name(item.name) == normalized_name:
            _, pantry_base_unit = to_base(1.0, item.unit or "item")
            if pantry_base_unit == grocery_base_unit:
                target = item
                break

    now = datetime.now(timezone.utc)

    if target:
        added_quantity = from_base(grocery_base_quantity, target.unit or "item")
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
            user_id=user_id,
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
