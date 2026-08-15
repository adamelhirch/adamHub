from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import CurrentOrOwnerUser, SessionDep
from app.core.security import require_api_key
from app.models import (
    SupermarketConnection,
    SupermarketSearchCache,
    SupermarketStore,
    SupermarketTargetType,
)
from app.schemas import (
    AuchanOfferingContext,
    AuchanStoreSelectionRequest,
    SupermarketConnectionImport,
    SupermarketConnectionRead,
    SupermarketMappingCreate,
    SupermarketMappingRead,
    SupermarketSearchRequest,
    SupermarketSearchResult,
    SupermarketStoreRead,
    SupermarketStoreSelectionRead,
)
from app.services.connections import (
    activate_connection as activate_supermarket_connection,
    delete_connection as delete_supermarket_connection,
    list_connections as list_supermarket_connections,
    upsert_connection as upsert_supermarket_connection,
)
from app.services.store_catalog import (
    create_or_replace_mapping,
    deactivate_mapping,
    fetch_search_results,
    get_active_mapping,
    get_selected_store,
    list_store_definitions,
    load_active_cookies,
    upsert_search_cache,
    upsert_selected_store,
)

router = APIRouter(prefix="/supermarket", tags=["supermarket"], dependencies=[Depends(require_api_key)])


def _is_owner_user(user) -> bool:
    """True when the acting user is the configured ADAMHUB_OWNER_EMAIL user.

    The owner is the legacy single-user path: connections with a NULL user_id
    (created before per-user scoping) belong to it and must stay visible/usable.
    """
    from app.core.config import get_settings

    settings = get_settings()
    owner_email = (settings.owner_email or "").strip().lower()
    return bool(owner_email) and (getattr(user, "email", "") or "").strip().lower() == owner_email


def _connection_is_operable(existing, user) -> bool:
    """A connection can be listed/activated/deleted by the acting user."""
    if existing is None:
        return True
    if existing.user_id is not None:
        return existing.user_id == user.id
    return _is_owner_user(user)


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


def _connection_to_read(row) -> SupermarketConnectionRead:
    try:
        from app.services.connections import decrypt_cookies
        cookies_count = len(decrypt_cookies(row))
    except Exception:
        cookies_count = 0
    return SupermarketConnectionRead(
        id=row.id,
        store=row.store,
        label=row.label,
        is_active=row.is_active,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        cookies_count=cookies_count,
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
            supports_promotions_filter=definition.supports_promotions_filter,
        )
        for definition in list_store_definitions()
    ]


@router.get("/connections", response_model=list[SupermarketConnectionRead])
def list_connections_endpoint(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    store: SupermarketStore | None = Query(default=None),
) -> list[SupermarketConnectionRead]:
    rows = list_supermarket_connections(session, store, user_id=user.id)
    if _is_owner_user(user):
        # Legacy (pre-scoping) connections with a NULL user_id belong to the
        # single-user owner and must remain visible to the personal frontend.
        rows += list_supermarket_connections(session, store, user_id=None)
    return [_connection_to_read(row) for row in rows]


@router.post("/connections/import", response_model=SupermarketConnectionRead)
def import_connection_endpoint(
    payload: SupermarketConnectionImport,
    session: SessionDep,
    user: CurrentOrOwnerUser,
) -> SupermarketConnectionRead:
    if not payload.cookies and not payload.credentials:
        raise HTTPException(
            status_code=400,
            detail="cookies or credentials must be provided",
        )
    label = payload.label.strip()
    if not label:
        label = (user.display_name or f"{payload.store.value}-connection").strip()
    connection = upsert_supermarket_connection(
        session,
        store=payload.store,
        label=label,
        cookies=payload.cookies,
        credentials=payload.credentials.model_dump() if payload.credentials else None,
        activate=payload.activate,
        connection_id=payload.connection_id,
        user_id=user.id,
    )
    return _connection_to_read(connection)


@router.put("/connections/{connection_id}/activate", response_model=SupermarketConnectionRead)
def activate_connection_endpoint(
    connection_id: int, session: SessionDep, user: CurrentOrOwnerUser
) -> SupermarketConnectionRead:
    # Check ownership BEFORE mutating: activating deactivates every other active
    # connection for that store, so a cross-user 404 must not leave side effects.
    existing = session.get(SupermarketConnection, connection_id)
    if not _connection_is_operable(existing, user):
        raise HTTPException(status_code=404, detail="Connection not found")
    connection = activate_supermarket_connection(session, connection_id, user_id=user.id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _connection_to_read(connection)


@router.delete("/connections/{connection_id}", response_model=SupermarketConnectionRead)
def delete_connection_endpoint(
    connection_id: int, session: SessionDep, user: CurrentOrOwnerUser
) -> SupermarketConnectionRead:
    existing = session.get(SupermarketConnection, connection_id)
    if not _connection_is_operable(existing, user):
        raise HTTPException(status_code=404, detail="Connection not found")
    connection = delete_supermarket_connection(session, connection_id, user_id=user.id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _connection_to_read(connection)


@router.post("/search", response_model=list[SupermarketSearchResult])
async def run_search(
    payload: SupermarketSearchRequest, session: SessionDep, user: CurrentOrOwnerUser
) -> list[SupermarketSearchResult]:
    try:
        normalized = await fetch_search_results(
            store=payload.store,
            queries=payload.queries,
            max_results=payload.max_results,
            promotions_only=payload.promotions_only,
            sort_by=payload.sort_by,
            session=session,
            user_id=user.id,
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


def _auchan_cookies(session: SessionDep, user_id: int | None = None) -> list[dict]:
    """DB connection cookies for Auchan, falling back to the filesystem export."""
    from app.services.scrapers.auchan import load_auchan_cookies

    return load_active_cookies(session, SupermarketStore.AUCHAN, user_id=user_id) or load_auchan_cookies()


@router.get("/auchan/offering-contexts", response_model=list[AuchanOfferingContext])
async def list_auchan_offering_contexts_endpoint(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    zipcode: str = Query(..., min_length=3, max_length=16),
    city: str = Query(..., min_length=2, max_length=128),
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    country: str = Query(default="France", max_length=128),
) -> list[AuchanOfferingContext]:
    from app.services.scrapers.auchan import (
        AuchanAuthError,
        list_auchan_offering_contexts,
    )

    try:
        contexts = await list_auchan_offering_contexts(
            zipcode=zipcode,
            city=city,
            latitude=latitude,
            longitude=longitude,
            country=country,
            cookies=_auchan_cookies(session, user_id=user.id),
        )
    except AuchanAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [AuchanOfferingContext(**context) for context in contexts]


@router.get("/auchan/selected-store", response_model=SupermarketStoreSelectionRead | None)
def get_auchan_selected_store(session: SessionDep) -> SupermarketStoreSelectionRead | None:
    selection = get_selected_store(session, SupermarketStore.AUCHAN)
    if selection is None:
        return None
    return SupermarketStoreSelectionRead(
        external_store_id=selection.external_store_id,
        store_label=selection.store_label,
        location_label=selection.location_label,
        updated_at=selection.updated_at,
    )


@router.post("/auchan/selected-store", response_model=SupermarketStoreSelectionRead)
async def select_auchan_store_endpoint(
    payload: AuchanStoreSelectionRequest,
    session: SessionDep,
    user: CurrentOrOwnerUser,
) -> SupermarketStoreSelectionRead:
    from app.services.scrapers.auchan import (
        AuchanAuthError,
        AuchanStoreContext,
        select_auchan_store,
    )

    context = AuchanStoreContext(
        seller_id=payload.seller_id,
        store_reference=payload.store_reference,
        channel=payload.channel,
        zipcode=payload.zipcode,
        city=payload.city,
        country=payload.country,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    try:
        journey = await select_auchan_store(
            context, cookies=_auchan_cookies(session, user_id=user.id)
        )
    except AuchanAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    selection = upsert_selected_store(
        session,
        SupermarketStore.AUCHAN,
        external_store_id=payload.seller_id,
        store_label=payload.store_label,
        location_label=payload.location_label,
        raw_payload={
            "store_reference": payload.store_reference,
            "channel": payload.channel,
            "zipcode": payload.zipcode,
            "city": payload.city,
            "country": payload.country,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "journey_id": journey.get("id"),
        },
    )
    return SupermarketStoreSelectionRead(
        external_store_id=selection.external_store_id,
        store_label=selection.store_label,
        location_label=selection.location_label,
        updated_at=selection.updated_at,
    )


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
