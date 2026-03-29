from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import SupermarketSearchCache, SupermarketStore, SupermarketTargetType
from app.schemas import (
    SupermarketMappingCreate,
    SupermarketMappingRead,
    SupermarketSearchRequest,
    SupermarketSearchResult,
    SupermarketStoreRead,
)
from app.services.scraper_service import fetch_search_results, upsert_search_cache
from app.services.supermarket_registry import list_store_definitions
from app.services.supermarket_mapping import (
    create_or_replace_mapping,
    deactivate_mapping,
    get_active_mapping,
)

router = APIRouter(prefix="/supermarket", tags=["supermarket"], dependencies=[Depends(require_api_key)])


def _to_result(row: SupermarketSearchCache) -> SupermarketSearchResult:
    return SupermarketSearchResult(
        cache_id=row.id,
        store=row.store,
        query=row.query,
        external_id=row.external_id,
        name=row.name,
        brand=row.brand,
        category=row.category,
        packaging=row.packaging,
        price_amount=row.price_amount,
        price_text=row.price_text,
        image_url=row.image_url,
        product_url=row.product_url,
        fetched_at=row.fetched_at,
        expires_at=row.expires_at,
    )


@router.get("/stores", response_model=list[SupermarketStoreRead])
def list_supported_stores() -> list[SupermarketStoreRead]:
    return [
        SupermarketStoreRead(
            key=definition.key,
            label=definition.label,
            supports_search=definition.supports_search,
            supports_mapping=definition.supports_mapping,
            supports_cart_automation=definition.supports_cart_automation,
        )
        for definition in list_store_definitions()
    ]


@router.post("/search", response_model=list[SupermarketSearchResult])
async def run_search(payload: SupermarketSearchRequest, session: SessionDep) -> list[SupermarketSearchResult]:
    try:
        normalized = await fetch_search_results(
            store=payload.store,
            queries=payload.queries,
            max_results=payload.max_results,
            promotions_only=payload.promotions_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = upsert_search_cache(session, payload.store, normalized)
    return [_to_result(row) for row in rows]


@router.get("/search", response_model=list[SupermarketSearchResult])
def get_cached_search_results(
    session: SessionDep,
    store: SupermarketStore = Query(default=SupermarketStore.INTERMARCHE),
    query: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SupermarketSearchResult]:
    now = datetime.now(UTC)
    statement = select(SupermarketSearchCache).where(
        SupermarketSearchCache.store == store,
        SupermarketSearchCache.expires_at >= now,
    )
    if query:
        statement = statement.where(SupermarketSearchCache.query == query)
    rows = session.exec(
        statement.order_by(SupermarketSearchCache.fetched_at.desc(), SupermarketSearchCache.id.desc()).limit(limit)
    ).all()
    return [_to_result(row) for row in rows]


@router.put("/mappings/recipe-ingredients/{ingredient_id}", response_model=SupermarketMappingRead)
def upsert_recipe_ingredient_mapping(
    ingredient_id: int,
    payload: SupermarketMappingCreate,
    session: SessionDep,
) -> SupermarketMappingRead:
    mapping = create_or_replace_mapping(session, SupermarketTargetType.RECIPE_INGREDIENT, ingredient_id, payload)
    return SupermarketMappingRead.model_validate(mapping, from_attributes=True)


@router.put("/mappings/pantry-items/{item_id}", response_model=SupermarketMappingRead)
def upsert_pantry_item_mapping(
    item_id: int,
    payload: SupermarketMappingCreate,
    session: SessionDep,
) -> SupermarketMappingRead:
    mapping = create_or_replace_mapping(session, SupermarketTargetType.PANTRY_ITEM, item_id, payload)
    return SupermarketMappingRead.model_validate(mapping, from_attributes=True)


@router.get("/mappings/recipe-ingredients/{ingredient_id}", response_model=SupermarketMappingRead | None)
def get_recipe_ingredient_mapping(ingredient_id: int, session: SessionDep) -> SupermarketMappingRead | None:
    mapping = get_active_mapping(session, SupermarketTargetType.RECIPE_INGREDIENT, ingredient_id)
    if mapping is None:
        return None
    return SupermarketMappingRead.model_validate(mapping, from_attributes=True)


@router.get("/mappings/pantry-items/{item_id}", response_model=SupermarketMappingRead | None)
def get_pantry_item_mapping(item_id: int, session: SessionDep) -> SupermarketMappingRead | None:
    mapping = get_active_mapping(session, SupermarketTargetType.PANTRY_ITEM, item_id)
    if mapping is None:
        return None
    return SupermarketMappingRead.model_validate(mapping, from_attributes=True)


@router.delete("/mappings/{mapping_id}", response_model=SupermarketMappingRead)
def delete_mapping(mapping_id: int, session: SessionDep) -> SupermarketMappingRead:
    mapping = deactivate_mapping(session, mapping_id)
    return SupermarketMappingRead.model_validate(mapping, from_attributes=True)
