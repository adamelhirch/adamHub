from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, delete, select

from app.models import SupermarketSearchCache, SupermarketStore
from app.services.scrapers.intermarche import search_intermarche

CACHE_TTL_DAYS = 15


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
) -> list[dict[str, Any]]:
    if store is not SupermarketStore.INTERMARCHE:
        raise ValueError(f"Unsupported supermarket store: {store}")

    raw_results = await search_intermarche(
        queries=queries,
        max_results=max_results,
        promotions_only=promotions_only,
    )

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
