from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, delete, select

from app.models import SupermarketSearchCache, SupermarketStore, SupermarketStoreSelection
from app.services.connections import (
    decrypt_cookies,
    get_active_connection,
    touch_connection,
)
from app.services.scrapers.carrefour import CarrefourAuthError, search_carrefour
from app.services.scrapers.intermarche import search_intermarche
from app.services.scrapers.ubereats import (
    UbereatsAuthError,
    UbereatsLocationError,
    search_in_store as search_ubereats_in_store,
)
from app.services.supermarket_registry import get_store_definition
from app.services.ubereats_addresses import get_active_address

CACHE_TTL_DAYS = 15


def get_selected_store(
    session: Session, store: SupermarketStore
) -> SupermarketStoreSelection | None:
    statement = select(SupermarketStoreSelection).where(SupermarketStoreSelection.store == store)
    return session.exec(statement).first()


def load_active_cookies(
    session: Session,
    store: SupermarketStore,
    user_id: int | None = None,
) -> list[dict[str, Any]] | None:
    """Pull the active connection's cookies for this store; None if no row in DB.

    When `user_id` is given, prefer that user's active connection; if missing,
    fall back to a shared (user_id IS NULL) connection. Callers can still fall
    back to legacy filesystem cookies when this returns None.
    """
    connection = None
    if user_id is not None:
        connection = get_active_connection(session, store, user_id=user_id)
    if connection is None:
        connection = get_active_connection(session, store, user_id=None)
    if connection is None:
        return None
    cookies = decrypt_cookies(connection)
    touch_connection(session, connection)
    return cookies


def _build_ubereats_target_location(session: Session) -> dict[str, Any] | None:
    """Compose Uber Eats getInStoreSearchV1.targetLocation from the active address."""
    address = get_active_address(session)
    if address is None:
        return None
    formatted = address.formatted_address
    return {
        "address": formatted,
        "streetAddress": formatted.split(",")[0].strip() or formatted,
        "city": (address.subtitle or "").strip() or "",
        "country": "FR",
        "postalCode": "",
        "region": "",
        "latitude": address.latitude,
        "longitude": address.longitude,
        "geo": {"city": "", "country": "fr", "region": ""},
        "locationType": "GROCERY_STORE",
    }


def upsert_selected_store(
    session: Session,
    store: SupermarketStore,
    *,
    external_store_id: str,
    store_label: str,
    location_label: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> SupermarketStoreSelection:
    selection = get_selected_store(session, store)
    now = datetime.now(UTC)
    if selection is None:
        selection = SupermarketStoreSelection(
            store=store,
            external_store_id=external_store_id,
            store_label=store_label,
            location_label=location_label,
            raw_payload=raw_payload or {},
            created_at=now,
            updated_at=now,
        )
    else:
        selection.external_store_id = external_store_id
        selection.store_label = store_label
        selection.location_label = location_label
        selection.raw_payload = raw_payload or {}
        selection.updated_at = now
    session.add(selection)
    session.commit()
    session.refresh(selection)
    return selection


def parse_price_amount(price_text: str | None) -> float | None:
    if not price_text:
        return None

    cleaned = (
        price_text.replace("€", "")
        .replace("/kg", "")
        .replace("/l", "")
        .replace(",", ".")
        .strip()
    )
    candidate = []
    dot_seen = False
    for char in cleaned:
        if char.isdigit():
            candidate.append(char)
        elif char == "." and not dot_seen:
            candidate.append(char)
            dot_seen = True
        elif candidate:
            break

    if not candidate:
        return None

    try:
        return float("".join(candidate))
    except ValueError:
        return None


def normalize_search_result(store: SupermarketStore, query: str, raw_item: dict[str, Any]) -> dict[str, Any]:
    name = (raw_item.get("name") or "").strip() or "Produit inconnu"
    brand = (raw_item.get("brand") or "").strip() or None
    packaging = (raw_item.get("packaging") or "").strip() or None
    price_text = (raw_item.get("price") or raw_item.get("price_text") or "").strip() or None
    image_url = raw_item.get("image") or raw_item.get("image_url")
    product_url = raw_item.get("product_url")
    external_id = (raw_item.get("id") or raw_item.get("external_id") or "").strip() or None

    return {
        "store": store,
        "query": query,
        "external_id": external_id,
        "name": name,
        "brand": brand,
        "category": raw_item.get("category"),
        "packaging": packaging,
        "price_amount": parse_price_amount(price_text),
        "price_text": price_text,
        "image_url": image_url,
        "product_url": product_url,
        "payload_json": raw_item,
    }


async def fetch_search_results(
    store: SupermarketStore,
    queries: list[str],
    max_results: int = 10,
    promotions_only: bool = False,
    sort_by: str | None = None,
    session: Session | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    definition = get_store_definition(store)
    if definition is None or not definition.supports_search:
        raise ValueError(f"Unsupported supermarket store: {store}")

    cookies = (
        load_active_cookies(session, store, user_id=user_id)
        if session is not None
        else None
    )

    if store == SupermarketStore.INTERMARCHE:
        raw_results = await search_intermarche(
            queries=queries,
            max_results=max_results,
            promotions_only=promotions_only,
            cookies=cookies,
        )
    elif store == SupermarketStore.CARREFOUR:
        raw_results = await search_carrefour(
            queries=queries,
            max_results=max_results,
            cookies=cookies,
        )
    elif store == SupermarketStore.UBEREATS:
        if session is None:
            raise ValueError("Uber Eats search requires a database session.")
        selection = get_selected_store(session, store)
        if selection is None:
            raise UbereatsLocationError(
                "No Uber Eats store selected. "
                "Call POST /supermarket/ubereats/selected-store first."
            )
        target_location = _build_ubereats_target_location(session)
        raw_results = await search_ubereats_in_store(
            store_uuid=selection.external_store_id,
            queries=queries,
            max_results=max_results,
            target_location=target_location,
            sort_by=sort_by,
            cookies=cookies,
        )
    else:
        raise ValueError(f"Unsupported supermarket store: {store}")

    normalized: list[dict[str, Any]] = []
    for query, items in raw_results.items():
        seen_external_ids: set[str] = set()
        for item in items:
            payload = normalize_search_result(store, query, item)
            ext_id = payload["external_id"]
            if ext_id and ext_id in seen_external_ids:
                continue
            if ext_id:
                seen_external_ids.add(ext_id)
            normalized.append(payload)
    return normalized


async def run_intermarche_scraper(
    session: Session,
    queries: list[str],
    max_results: int = 10,
    sort_by: str | None = None,
    promotions_only: bool = False,
) -> list[SupermarketSearchCache]:
    del sort_by
    normalized = await fetch_search_results(
        store=SupermarketStore.INTERMARCHE,
        queries=queries,
        max_results=max_results,
        promotions_only=promotions_only,
    )
    return upsert_search_cache(session, SupermarketStore.INTERMARCHE, normalized)


def upsert_search_cache(
    session: Session,
    store: SupermarketStore,
    results: list[dict[str, Any]],
    ttl_days: int = CACHE_TTL_DAYS,
) -> list[SupermarketSearchCache]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=ttl_days)

    session.exec(
        delete(SupermarketSearchCache).where(
            SupermarketSearchCache.store == store,
            SupermarketSearchCache.expires_at < now,
        ).execution_options(synchronize_session=False)
    )

    saved: list[SupermarketSearchCache] = []
    for result in results:
        statement = select(SupermarketSearchCache).where(
            SupermarketSearchCache.store == result["store"],
            SupermarketSearchCache.query == result["query"],
        )
        if result["external_id"]:
            statement = statement.where(SupermarketSearchCache.external_id == result["external_id"])
        else:
            statement = statement.where(SupermarketSearchCache.name == result["name"])

        existing = session.exec(statement).first()
        if existing:
            existing.brand = result["brand"]
            existing.category = result.get("category")
            existing.packaging = result["packaging"]
            existing.price_amount = result["price_amount"]
            existing.price_text = result["price_text"]
            existing.image_url = result["image_url"]
            existing.product_url = result["product_url"]
            existing.payload_json = result["payload_json"]
            existing.fetched_at = now
            existing.expires_at = expires_at
            session.add(existing)
            saved.append(existing)
            continue

        row = SupermarketSearchCache(
            store=result["store"],
            query=result["query"],
            external_id=result["external_id"],
            name=result["name"],
            brand=result["brand"],
            category=result.get("category"),
            packaging=result["packaging"],
            price_amount=result["price_amount"],
            price_text=result["price_text"],
            image_url=result["image_url"],
            product_url=result["product_url"],
            payload_json=result["payload_json"],
            fetched_at=now,
            expires_at=expires_at,
        )
        session.add(row)
        saved.append(row)

    session.commit()
    for row in saved:
        session.refresh(row)
    return saved
