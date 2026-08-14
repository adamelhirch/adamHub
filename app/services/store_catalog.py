"""The single deep module for the supermarket catalog.

This is the one seam through which callers reach every supermarket capability:
store definitions, the cache-backed resolution of store metadata, durable
product mappings, and the search orchestration that feeds the cache. The
per-store scraping adapters live in ``app/services/scrapers/`` and are
dispatched to from here; this module holds no store-specific network or parsing
knowledge.

This module is the single source of truth for the rule

    cache_id -> SupermarketSearchCache -> copy store fields

Store metadata is never fabricated from client input: the only trusted source is
a SupermarketSearchCache row. The ``cache_id`` key is consumed at the seam and
never persisted, and callers hold no knowledge of the cache table, the store
definition lookup, or the field names that count as "store metadata".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models import (
    PantryItem,
    RecipeIngredient,
    SupermarketMapping,
    SupermarketSearchCache,
    SupermarketStore,
    SupermarketStoreSelection,
    SupermarketTargetType,
)
from app.schemas import SupermarketMappingCreate
from app.services.connections import (
    decrypt_cookies,
    get_active_connection,
    touch_connection,
)
from app.services.scrapers.carrefour import search_carrefour
from app.services.scrapers.intermarche import search_intermarche
from app.services.scrapers.ubereats import (
    UbereatsLocationError,
    search_in_store as search_ubereats_in_store,
)
from app.services.ubereats_addresses import get_active_address

CACHE_TTL_DAYS = 15


@dataclass(frozen=True, slots=True)
class SupermarketStoreDefinition:
    key: SupermarketStore
    label: str
    supports_search: bool = True
    supports_mapping: bool = True
    supports_cart_automation: bool = False
    scraper_name: str | None = None
    notes: str | None = None


STORE_REGISTRY: tuple[SupermarketStoreDefinition, ...] = (
    SupermarketStoreDefinition(
        key=SupermarketStore.INTERMARCHE,
        label="Intermarché",
        scraper_name="intermarche",
        notes="Live HTML scraping with optional Camoufox fallback.",
    ),
    SupermarketStoreDefinition(
        key=SupermarketStore.UBEREATS,
        label="Uber Eats",
        scraper_name="ubereats",
        supports_mapping=False,
        supports_cart_automation=True,
        notes=(
            "Internal JSON API scraping. Requires data/cookies_ubereats.json and "
            "a selected store (POST /supermarket/ubereats/selected-store)."
        ),
    ),
    SupermarketStoreDefinition(
        key=SupermarketStore.CARREFOUR,
        label="Carrefour",
        scraper_name="carrefour",
        supports_mapping=False,
        notes=(
            "Carrefour Drive search via /api/marketing/search. Requires "
            "data/cookies_carrefour.json from a logged-in browser session "
            "with a Drive store selected (prices are store-specific)."
        ),
    ),
)


def list_store_definitions() -> list[SupermarketStoreDefinition]:
    return list(STORE_REGISTRY)


def get_store_definition(store: SupermarketStore) -> SupermarketStoreDefinition | None:
    for definition in STORE_REGISTRY:
        if definition.key == store:
            return definition
    return None


def supports_store(store: SupermarketStore) -> bool:
    return get_store_definition(store) is not None


# Client-facing store metadata fields that must never be fabricated: they are
# only ever populated server-side from a SupermarketSearchCache row. Supplying
# one without a cache_id is a 422.
STORE_METADATA_FIELDS = ("external_id", "store_label", "price_text", "product_url")


def reject_fabricated_store_fields(fields: dict) -> None:
    """Reject client-supplied store metadata that has no cache_id backing.

    Raises a 422 when any STORE_METADATA_FIELDS key carries a truthy value: the
    client is trying to fabricate store metadata instead of referencing a cache
    row.
    """
    fabricated = [field for field in STORE_METADATA_FIELDS if fields.get(field)]
    if fabricated:
        raise HTTPException(
            status_code=422,
            detail=(
                "Store metadata fields (external_id, store_label, price_text, "
                "product_url) require a valid cache_id"
            ),
        )


def resolve_store_fields(session: Session, cache_id: int) -> dict:
    """Resolve the store-backed fields for a SupermarketSearchCache row.

    Raises a 404 when no cache row matches the id. Returns every field the cache
    row authoritatively provides (store identity, product name/category, and the
    store metadata fields); each caller picks the subset it persists.
    """
    cache_row = session.get(SupermarketSearchCache, cache_id)
    if cache_row is None:
        raise HTTPException(status_code=404, detail="Search cache entry not found")

    definition = get_store_definition(cache_row.store)
    return {
        "store": cache_row.store,
        "external_id": cache_row.external_id,
        "store_label": definition.label if definition else cache_row.store.value,
        "name": cache_row.name,
        "category": cache_row.category,
        "packaging": cache_row.packaging,
        "price_text": cache_row.price_text,
        "product_url": cache_row.product_url,
        "image_url": cache_row.image_url,
    }


def _validate_target_exists(session: Session, target_type: SupermarketTargetType, target_id: int) -> None:
    if target_type is SupermarketTargetType.RECIPE_INGREDIENT:
        row = session.get(RecipeIngredient, target_id)
    elif target_type is SupermarketTargetType.PANTRY_ITEM:
        row = session.get(PantryItem, target_id)
    else:
        row = None
    if row is None:
        raise HTTPException(status_code=404, detail=f"{target_type.value} not found")


def get_active_mapping(
    session: Session,
    target_type: SupermarketTargetType,
    target_id: int,
    store: SupermarketStore | None = None,
) -> SupermarketMapping | None:
    statement = select(SupermarketMapping).where(
        SupermarketMapping.target_type == target_type,
        SupermarketMapping.target_id == target_id,
        SupermarketMapping.active.is_(True),
    )
    if store is not None:
        statement = statement.where(SupermarketMapping.store == store)
    return session.exec(statement.order_by(SupermarketMapping.updated_at.desc())).first()


def create_or_replace_mapping(
    session: Session,
    target_type: SupermarketTargetType,
    target_id: int,
    payload: SupermarketMappingCreate,
) -> SupermarketMapping:
    _validate_target_exists(session, target_type, target_id)

    definition = get_store_definition(payload.store)
    if definition is None or not definition.supports_mapping:
        raise HTTPException(status_code=400, detail=f"Unsupported supermarket store: {payload.store.value}")

    # cache_id is mandatory: the snapshot fields are resolved from the cache row
    # server-side instead of trusting client-supplied strings.
    resolved = resolve_store_fields(session, payload.cache_id)
    if resolved["store"] != payload.store:
        raise HTTPException(status_code=400, detail="cache_id store does not match payload store")

    previous = get_active_mapping(session, target_type, target_id, payload.store)
    if previous is not None:
        previous.active = False
        previous.updated_at = datetime.now(UTC)
        session.add(previous)

    verified_at = payload.last_verified_at or datetime.now(UTC)
    mapping = SupermarketMapping(
        target_type=target_type,
        target_id=target_id,
        store=payload.store,
        external_id=resolved["external_id"],
        store_label=resolved["store_label"],
        name_snapshot=resolved["name"],
        category_snapshot=resolved["category"],
        packaging_snapshot=resolved["packaging"],
        price_snapshot=resolved["price_text"],
        product_url=resolved["product_url"],
        image_url=resolved["image_url"],
        last_verified_at=verified_at,
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping


def deactivate_mapping(session: Session, mapping_id: int) -> SupermarketMapping:
    mapping = session.get(SupermarketMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Supermarket mapping not found")

    mapping.active = False
    mapping.updated_at = datetime.now(UTC)
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping


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
