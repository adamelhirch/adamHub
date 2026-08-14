"""Resolve store metadata for client records from a SupermarketSearchCache row.

This module is the single source of truth for the rule

    cache_id -> SupermarketSearchCache -> copy store fields

Store metadata is never fabricated from client input: the only trusted source is
a SupermarketSearchCache row. The `cache_id` key is consumed at the seam and
never persisted, and callers hold no knowledge of the cache table, the store
definition lookup, or the field names that count as "store metadata".
"""

from fastapi import HTTPException
from sqlmodel import Session

from app.models import SupermarketSearchCache
from app.services.supermarket_registry import get_store_definition

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
