from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import OptionalUser, SessionDep
from app.core.security import require_api_key
from app.models import (
    GroceryItem,
    SupermarketConnection,
    SupermarketSearchCache,
    SupermarketStore,
    SupermarketTargetType,
)
from app.schemas import (
    SupermarketConnectionImport,
    SupermarketConnectionRead,
    SupermarketMappingCreate,
    SupermarketMappingRead,
    SupermarketSearchRequest,
    SupermarketSearchResult,
    SupermarketStoreRead,
    UbereatsAddressCreate,
    UbereatsAddressRead,
    UbereatsAddressUpdate,
    UbereatsCartAddRequest,
    UbereatsCartItem,
    UbereatsCartRead,
    UbereatsCartSummary,
    UbereatsCartSummaryEntry,
    UbereatsGeocodeResult,
    UbereatsImportedItem,
    UbereatsImportRequest,
    UbereatsImportResult,
    UbereatsLocationRead,
    UbereatsPastOrder,
    UbereatsStoreOption,
    UbereatsStoreSelectionRead,
    UbereatsStoreSelectionRequest,
)
from app.services.connections import (
    activate_connection as activate_supermarket_connection,
    delete_connection as delete_supermarket_connection,
    list_connections as list_supermarket_connections,
    upsert_connection as upsert_supermarket_connection,
)
from app.services.scraper_service import (
    fetch_search_results,
    get_selected_store,
    load_active_cookies,
    upsert_search_cache,
    upsert_selected_store,
)
from app.services.geocoder import GeocoderError, search_addresses as geocoder_search
from app.services.scrapers.ubereats import (
    UbereatsAuthError,
    UbereatsLocationError,
    decode_uev2_loc,
    get_current_address_label,
    list_grocery_stores,
    load_ubereats_cookies,
    set_delivery_location,
)
from app.services.ubereats_addresses import (
    activate_address as activate_ubereats_address,
    create_address as create_ubereats_address,
    delete_address as delete_ubereats_address,
    list_addresses as list_ubereats_addresses,
)
from app.services.ubereats_cart import (
    UbereatsCartError,
    add_item_to_cart as add_to_ubereats_cart,
    fetch_cart_summary as fetch_ubereats_cart_summary,
)
from app.services.ubereats_orders import (
    UbereatsOrderError,
    extract_order_uuid,
    import_order_to_pantry as import_ubereats_order_to_pantry,
    list_past_orders as list_ubereats_past_orders,
)
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
        )
        for definition in list_store_definitions()
    ]


@router.get("/connections", response_model=list[SupermarketConnectionRead])
def list_connections_endpoint(
    session: SessionDep,
    user: OptionalUser,
    store: SupermarketStore | None = Query(default=None),
) -> list[SupermarketConnectionRead]:
    user_id = user.id if user else None
    return [
        _connection_to_read(row)
        for row in list_supermarket_connections(session, store, user_id=user_id)
    ]


@router.post("/connections/import", response_model=SupermarketConnectionRead)
def import_connection_endpoint(
    payload: SupermarketConnectionImport,
    session: SessionDep,
    user: OptionalUser,
) -> SupermarketConnectionRead:
    if not payload.cookies:
        raise HTTPException(status_code=400, detail="cookies must be a non-empty list")
    user_id = user.id if user else None
    # If the caller is authenticated, pin the connection to them and use their
    # display name as the label by default.
    label = payload.label.strip()
    if not label:
        label = (user.display_name if user else f"{payload.store.value}-connection").strip()
    connection = upsert_supermarket_connection(
        session,
        store=payload.store,
        label=label,
        cookies=payload.cookies,
        activate=payload.activate,
        connection_id=payload.connection_id,
        user_id=user_id,
    )
    return _connection_to_read(connection)


@router.put("/connections/{connection_id}/activate", response_model=SupermarketConnectionRead)
def activate_connection_endpoint(
    connection_id: int, session: SessionDep, user: OptionalUser
) -> SupermarketConnectionRead:
    connection = activate_supermarket_connection(session, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if user and connection.user_id and connection.user_id != user.id:
        raise HTTPException(status_code=403, detail="Cette connexion appartient à un autre compte")
    return _connection_to_read(connection)


@router.delete("/connections/{connection_id}", response_model=SupermarketConnectionRead)
def delete_connection_endpoint(
    connection_id: int, session: SessionDep, user: OptionalUser
) -> SupermarketConnectionRead:
    if user:
        existing = session.get(SupermarketConnection, connection_id)
        if existing and existing.user_id and existing.user_id != user.id:
            raise HTTPException(status_code=403, detail="Cette connexion appartient à un autre compte")
    connection = delete_supermarket_connection(session, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _connection_to_read(connection)


@router.post("/search", response_model=list[SupermarketSearchResult])
async def run_search(
    payload: SupermarketSearchRequest, session: SessionDep, user: OptionalUser
) -> list[SupermarketSearchResult]:
    try:
        normalized = await fetch_search_results(
            store=payload.store,
            queries=payload.queries,
            max_results=payload.max_results,
            promotions_only=payload.promotions_only,
            sort_by=payload.sort_by,
            session=session,
            user_id=user.id if user else None,
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


@router.get("/ubereats/location", response_model=UbereatsLocationRead)
def get_ubereats_location() -> UbereatsLocationRead:
    cookies = load_ubereats_cookies()
    payload = decode_uev2_loc(cookies)
    if not payload:
        return UbereatsLocationRead(
            label=None, title=None, formatted_address=None, latitude=None, longitude=None
        )
    address = payload.get("address") or {}
    return UbereatsLocationRead(
        label=get_current_address_label(cookies),
        title=address.get("title"),
        formatted_address=address.get("eaterFormattedAddress") or address.get("address1"),
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
    )


@router.put("/ubereats/location", response_model=UbereatsLocationRead)
async def update_ubereats_location(payload: UbereatsAddressUpdate) -> UbereatsLocationRead:
    new_payload = {
        "address": {
            "title": payload.title,
            "subtitle": payload.subtitle or "",
            "eaterFormattedAddress": payload.formatted_address or payload.title,
            "address1": payload.formatted_address or payload.title,
        },
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "reference": payload.reference or "",
        "referenceType": payload.reference_type,
    }
    await set_delivery_location(new_payload)
    cookies = load_ubereats_cookies()
    return UbereatsLocationRead(
        label=get_current_address_label(cookies),
        title=payload.title,
        formatted_address=payload.formatted_address or payload.title,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )


@router.get("/ubereats/stores", response_model=list[UbereatsStoreOption])
async def list_ubereats_stores(
    session: SessionDep, limit: int = Query(default=25, ge=1, le=50)
) -> list[UbereatsStoreOption]:
    cookies = load_active_cookies(session, SupermarketStore.UBEREATS)
    try:
        stores = await list_grocery_stores(max_results=limit, cookies=cookies)
    except UbereatsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except UbereatsLocationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [UbereatsStoreOption(**store) for store in stores]


@router.get("/ubereats/selected-store", response_model=UbereatsStoreSelectionRead | None)
def get_ubereats_selected_store(session: SessionDep) -> UbereatsStoreSelectionRead | None:
    selection = get_selected_store(session, SupermarketStore.UBEREATS)
    if selection is None:
        return None
    return UbereatsStoreSelectionRead(
        external_store_id=selection.external_store_id,
        store_label=selection.store_label,
        location_label=selection.location_label,
        updated_at=selection.updated_at,
    )


@router.put("/ubereats/selected-store", response_model=UbereatsStoreSelectionRead)
def select_ubereats_store(
    payload: UbereatsStoreSelectionRequest, session: SessionDep
) -> UbereatsStoreSelectionRead:
    cookies = load_ubereats_cookies()
    selection = upsert_selected_store(
        session,
        SupermarketStore.UBEREATS,
        external_store_id=payload.external_store_id,
        store_label=payload.store_label,
        location_label=payload.location_label or get_current_address_label(cookies),
    )
    return UbereatsStoreSelectionRead(
        external_store_id=selection.external_store_id,
        store_label=selection.store_label,
        location_label=selection.location_label,
        updated_at=selection.updated_at,
    )


@router.get("/ubereats/geocode", response_model=list[UbereatsGeocodeResult])
async def geocode_address(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(default=6, ge=1, le=10),
) -> list[UbereatsGeocodeResult]:
    try:
        results = await geocoder_search(q, limit=limit)
    except GeocoderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [UbereatsGeocodeResult(**result) for result in results]


@router.get("/ubereats/addresses", response_model=list[UbereatsAddressRead])
def list_addresses(session: SessionDep) -> list[UbereatsAddressRead]:
    return [
        UbereatsAddressRead.model_validate(address, from_attributes=True)
        for address in list_ubereats_addresses(session)
    ]


@router.post("/ubereats/addresses", response_model=UbereatsAddressRead)
async def create_address(payload: UbereatsAddressCreate, session: SessionDep) -> UbereatsAddressRead:
    address = create_ubereats_address(
        session,
        label=payload.label,
        formatted_address=payload.formatted_address,
        subtitle=payload.subtitle,
        latitude=payload.latitude,
        longitude=payload.longitude,
        reference=payload.reference,
        reference_type=payload.reference_type,
    )
    if payload.activate:
        activated = await activate_ubereats_address(session, address.id)
        if activated is not None:
            address = activated
    return UbereatsAddressRead.model_validate(address, from_attributes=True)


@router.put("/ubereats/addresses/{address_id}/activate", response_model=UbereatsAddressRead)
async def activate_address(address_id: int, session: SessionDep) -> UbereatsAddressRead:
    address = await activate_ubereats_address(session, address_id)
    if address is None:
        raise HTTPException(status_code=404, detail="Address not found")
    return UbereatsAddressRead.model_validate(address, from_attributes=True)


@router.delete("/ubereats/addresses/{address_id}", response_model=UbereatsAddressRead)
def remove_address(address_id: int, session: SessionDep) -> UbereatsAddressRead:
    address = delete_ubereats_address(session, address_id)
    if address is None:
        raise HTTPException(status_code=404, detail="Address not found")
    return UbereatsAddressRead.model_validate(address, from_attributes=True)


@router.get("/ubereats/orders", response_model=list[UbereatsPastOrder])
async def list_past_orders(
    session: SessionDep, limit: int = Query(default=10, ge=1, le=50)
) -> list[UbereatsPastOrder]:
    cookies = load_active_cookies(session, SupermarketStore.UBEREATS)
    try:
        orders = await list_ubereats_past_orders(limit=limit, cookies=cookies)
    except UbereatsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [UbereatsPastOrder(**order) for order in orders]


@router.post("/ubereats/orders/import-to-pantry", response_model=UbereatsImportResult)
async def import_ubereats_order(
    payload: UbereatsImportRequest, session: SessionDep
) -> UbereatsImportResult:
    order_uuid = extract_order_uuid(payload.tracking_url_or_uuid)
    if not order_uuid:
        raise HTTPException(
            status_code=400,
            detail="Could not extract an order UUID from the input.",
        )
    cookies = load_active_cookies(session, SupermarketStore.UBEREATS)
    try:
        result = await import_ubereats_order_to_pantry(session, order_uuid, cookies=cookies)
    except UbereatsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except UbereatsOrderError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return UbereatsImportResult(
        order_uuid=result["order_uuid"],
        store_label=result.get("store_label"),
        items_imported=result["items_imported"],
        items_updated=result["items_updated"],
        items=[UbereatsImportedItem(**it) for it in result["items"]],
    )


def _serialize_cart(cart: dict | None) -> UbereatsCartRead | None:
    if cart is None:
        return None
    items: list[UbereatsCartItem] = []
    for raw in cart.get("items") or []:
        items.append(
            UbereatsCartItem(
                item_uuid=raw.get("uuid") or "",
                cart_item_uuid=raw.get("shoppingCartItemUuid") or "",
                title=raw.get("title") or "",
                quantity=raw.get("quantity") or 0,
                price_cents=raw.get("price"),
                image_url=raw.get("imageURL"),
            )
        )
    return UbereatsCartRead(
        draft_order_uuid=cart.get("draft_order_uuid"),
        cart_uuid=cart.get("cart_uuid"),
        store_uuid=cart.get("store_uuid"),
        items=items,
    )


@router.get("/ubereats/cart", response_model=UbereatsCartSummary)
async def get_ubereats_cart(
    session: SessionDep,
    store_uuid: str | None = Query(default=None),
    include_details: bool = Query(default=False),
) -> UbereatsCartSummary:
    target_store = store_uuid
    if target_store is None:
        selection = get_selected_store(session, SupermarketStore.UBEREATS)
        target_store = selection.external_store_id if selection else None

    cookies = load_active_cookies(session, SupermarketStore.UBEREATS)
    try:
        summary = await fetch_ubereats_cart_summary(
            target_store, include_details=include_details, cookies=cookies
        )
    except UbereatsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except UbereatsCartError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    entries: list[UbereatsCartSummaryEntry] = []
    for raw in summary.get("carts") or []:
        details = raw.pop("details", None)
        entries.append(
            UbereatsCartSummaryEntry(
                **raw,
                details=_serialize_cart(details) if details else None,
            )
        )
    return UbereatsCartSummary(carts=entries, focused=_serialize_cart(summary.get("focused")))


def _upsert_grocery_item_for_cache(
    session: SessionDep, cache_row: SupermarketSearchCache, quantity: int
) -> None:
    """Mirror a cached UE product into the local grocery list.

    If a row with the same `external_id` already exists, increments quantity.
    Otherwise creates a new GroceryItem with the cache metadata.
    """
    now = datetime.now(UTC)
    existing: GroceryItem | None = None
    if cache_row.external_id:
        statement = select(GroceryItem).where(GroceryItem.external_id == cache_row.external_id)
        existing = session.exec(statement).first()

    if existing is not None:
        existing.quantity = (existing.quantity or 0) + quantity
        existing.checked = False
        existing.updated_at = now
        session.add(existing)
        session.commit()
        return

    note_parts = [
        "Uber Eats",
        cache_row.price_text or None,
        cache_row.packaging or None,
    ]
    note = " · ".join(part for part in note_parts if part) or None
    item = GroceryItem(
        name=cache_row.name,
        quantity=quantity,
        unit="item",
        category=cache_row.category,
        image_url=cache_row.image_url,
        store_label="Uber Eats",
        external_id=cache_row.external_id,
        packaging=cache_row.packaging,
        price_text=cache_row.price_text,
        product_url=cache_row.product_url,
        priority=3,
        note=note,
        created_at=now,
        updated_at=now,
    )
    session.add(item)
    session.commit()


@router.post("/ubereats/cart/items", response_model=UbereatsCartRead)
async def add_ubereats_cart_item(
    payload: UbereatsCartAddRequest, session: SessionDep
) -> UbereatsCartRead:
    cache_row = session.get(SupermarketSearchCache, payload.cache_id)
    if cache_row is None or cache_row.store != SupermarketStore.UBEREATS:
        raise HTTPException(status_code=404, detail="Cached Uber Eats product not found")

    raw = cache_row.payload_json or {}
    item_uuid = raw.get("id")
    section_uuid = raw.get("section_uuid")
    subsection_uuid = raw.get("subsection_uuid")
    store_uuid = raw.get("store_uuid")
    if not (item_uuid and section_uuid and subsection_uuid and store_uuid):
        raise HTTPException(
            status_code=409,
            detail=(
                "Cached payload is missing the Uber Eats UUIDs. "
                "Re-run the search to refresh the cache."
            ),
        )

    price_cents = raw.get("price_cents")
    if not isinstance(price_cents, int) or price_cents <= 0:
        if cache_row.price_amount and cache_row.price_amount > 0:
            price_cents = int(round(cache_row.price_amount * 100))
        else:
            raise HTTPException(
                status_code=409,
                detail="Cached product has no resolvable price. Re-run the search.",
            )

    cookies = load_active_cookies(session, SupermarketStore.UBEREATS)
    try:
        cart = await add_to_ubereats_cart(
            store_uuid=store_uuid,
            item_uuid=item_uuid,
            section_uuid=section_uuid,
            subsection_uuid=subsection_uuid,
            title=cache_row.name,
            price_cents=price_cents,
            image_url=cache_row.image_url,
            quantity=payload.quantity,
            cookies=cookies,
        )
    except UbereatsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except UbereatsCartError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Mirror the item into the local grocery list so the hub stays in sync.
    _upsert_grocery_item_for_cache(session, cache_row, payload.quantity)

    return _serialize_cart(cart)
