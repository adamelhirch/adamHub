from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.models import PantryItem
from app.services.scrapers.ubereats import (
    UbereatsAuthError,
    _build_client,
    load_ubereats_cookies,
)
from app.services.ubereats_cart import _post


UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


class UbereatsOrderError(RuntimeError):
    pass


def extract_order_uuid(text: str) -> str | None:
    """Extract a UUID from a tracking URL or raw input."""
    if not text:
        return None
    match = UUID_RE.search(text)
    return match.group(0).lower() if match else None


def _format_price_eur(cents: int | None) -> str | None:
    if cents is None or cents <= 0:
        return None
    return f"{cents / 100:.2f} €".replace(".", ",")


def _summarize_order(uuid: str, order: dict[str, Any]) -> dict[str, Any]:
    base = order.get("baseEaterOrder") or {}
    store = order.get("storeInfo") or {}
    fare = order.get("fareInfo") or {}
    completed_at = base.get("completedAt") or base.get("lastStateChangeAt")
    return {
        "uuid": uuid,
        "store_title": store.get("title"),
        "store_image_url": store.get("heroImageUrl"),
        "completed_at": completed_at,
        "is_completed": bool(base.get("isCompleted")),
        "is_cancelled": bool(base.get("isCancelled")),
        "num_items": base.get("numItems") or 0,
        "total_quantity": base.get("totalQuantity") or 0,
        "total_text": (fare.get("totalCharge") or {}).get("formattedAmount")
        or (fare.get("subtotal") or {}).get("formattedAmount"),
    }


async def list_past_orders(
    limit: int = 20, cookies: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    if cookies is None:
        cookies = load_ubereats_cookies()
    if not cookies:
        raise UbereatsAuthError(
            "No Uber Eats cookies on disk. Provide `data/cookies_ubereats.json`."
        )
    async with _build_client(cookies) as client:
        data = await _post(client, "/_p/api/getPastOrdersV1", {})
    orders_map = data.get("ordersMap") or {}
    summaries = [_summarize_order(uuid, order) for uuid, order in orders_map.items()]
    summaries.sort(key=lambda s: s.get("completed_at") or "", reverse=True)
    return summaries[:limit]


async def get_order(
    order_uuid: str, cookies: list[dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    """Fetch one order by uuid. Looks in past orders first, then active orders."""
    if cookies is None:
        cookies = load_ubereats_cookies()
    if not cookies:
        raise UbereatsAuthError(
            "No Uber Eats cookies on disk. Provide `data/cookies_ubereats.json`."
        )
    async with _build_client(cookies) as client:
        # 1) Past orders (delivered) — most common case after a completed order.
        past = await _post(client, "/_p/api/getPastOrdersV1", {})
        order = (past.get("ordersMap") or {}).get(order_uuid)
        if order is not None:
            return order

        # 2) Fall back to active orders (in flight, not yet in history).
        active = await _post(client, "/_p/api/getActiveOrdersV1", {})
        for entry in active.get("orders") or []:
            base = (entry or {}).get("baseEaterOrder") or {}
            if base.get("uuid") == order_uuid or entry.get("uuid") == order_uuid:
                return entry
    return None


def is_shared_tracking_only(order: dict[str, Any]) -> bool:
    """Detect orders accessible via tracking link but without item details.

    These orders (typically placed by a friend who shared the tracking URL) only
    expose `feedCards`/`orderInfo` for status display — the shoppingCart is not
    exposed by Uber Eats for privacy reasons.
    """
    base = order.get("baseEaterOrder")
    if isinstance(base, dict) and base.get("shoppingCart"):
        return False
    return order.get("orderInfo") is not None and not order.get("baseEaterOrder")


def extract_delivered_items(order: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the items actually delivered for this order, with normalized fields.

    `shoppingCart.items[]` reflects the final state after substitutions.
    Items with quantity == 0 are skipped (likely out of stock without substitute).
    """
    base = order.get("baseEaterOrder") or {}
    raw_items = (base.get("shoppingCart") or {}).get("items") or []
    delivered: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        quantity = raw.get("quantity") or 0
        if quantity <= 0:
            continue
        delivered.append(
            {
                "external_id": raw.get("uuid"),
                "name": raw.get("title") or "Article Uber Eats",
                "quantity": int(quantity),
                "price_cents": raw.get("price") if isinstance(raw.get("price"), (int, float)) else None,
                "store_uuid": raw.get("storeUuid"),
                "section_uuid": raw.get("sectionUuid"),
                "subsection_uuid": raw.get("subsectionUuid"),
            }
        )
    return delivered


def _upsert_pantry_item(
    session: Session,
    item: dict[str, Any],
    store_label: str,
    *,
    user_id: int | None = None,
) -> tuple[PantryItem, bool]:
    """Create a PantryItem or increment quantity if one with the same external_id exists.
    Returns (item, created) where `created` is True for fresh rows.
    """
    now = datetime.now(UTC)
    existing: PantryItem | None = None
    if item.get("external_id"):
        statement = select(PantryItem).where(PantryItem.external_id == item["external_id"])
        if user_id is not None:
            statement = statement.where(PantryItem.user_id == user_id)
        existing = session.exec(statement).first()

    quantity = float(item.get("quantity") or 0)
    price_text = _format_price_eur(item.get("price_cents"))

    if existing is not None:
        existing.quantity = (existing.quantity or 0) + quantity
        existing.updated_at = now
        if not existing.price_text and price_text:
            existing.price_text = price_text
        if not existing.store_label:
            existing.store_label = store_label
        session.add(existing)
        return existing, False

    pantry = PantryItem(
        name=item["name"],
        quantity=quantity,
        unit="item",
        store_label=store_label,
        external_id=item.get("external_id"),
        price_text=price_text,
        note=f"Importé depuis {store_label}",
        created_at=now,
        updated_at=now,
        user_id=user_id,
    )
    session.add(pantry)
    return pantry, True


async def import_order_to_pantry(
    session: Session,
    order_uuid: str,
    cookies: list[dict[str, Any]] | None = None,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    order = await get_order(order_uuid, cookies=cookies)
    if order is None:
        raise UbereatsOrderError(
            f"Commande {order_uuid} introuvable (ni dans l'historique, ni active). "
            "Vérifie que tu es bien connecté avec le bon compte Uber Eats."
        )

    if is_shared_tracking_only(order):
        raise UbereatsOrderError(
            "Cette commande a été passée par un autre compte Uber Eats (lien de suivi partagé). "
            "Uber Eats n'expose pas les articles de ces commandes — seul le statut de livraison "
            "est visible. Saisis les articles à la main dans le garde-manger."
        )

    items = extract_delivered_items(order)
    if not items:
        return {"order_uuid": order_uuid, "items_imported": 0, "items_updated": 0, "items": []}

    store_label = (order.get("storeInfo") or {}).get("title") or "Uber Eats"

    created_count = 0
    updated_count = 0
    serialized: list[dict[str, Any]] = []
    for item in items:
        pantry, created = _upsert_pantry_item(
            session, item, store_label=store_label, user_id=user_id
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
        serialized.append(
            {
                "name": pantry.name,
                "quantity": pantry.quantity,
                "external_id": pantry.external_id,
                "price_text": pantry.price_text,
                "created": created,
            }
        )
    session.commit()
    return {
        "order_uuid": order_uuid,
        "items_imported": created_count,
        "items_updated": updated_count,
        "items": serialized,
        "store_label": store_label,
    }
