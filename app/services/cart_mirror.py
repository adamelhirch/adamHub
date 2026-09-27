"""Multi-store cart mirror — drive real supermarket carts from /supermarket/carts*.

Synchronizes shopping carts across supported supermarket retailers (Intermarché,
Carrefour, Leclerc, Auchan). Each mutation is first applied to the retailer's cart
API through its store adapter, and the local SupermarketCart is rewritten from
the server's response. Every failure (expired session, missing connection, out of sync)
is rejected with a typed HTTP error without corrupting the local cart data.

Public surface:
- `read_cart`              → adapter `get_or_read_cart`
- `add_item`               → cache row → adapter `add_item` (with duplicate accumulation)
- `update_item_quantity`   → local line → adapter `update_item_quantity`
- `remove_item`            → local line → adapter `remove_item`
- `clear_cart`             → adapter `clear_cart`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import SupermarketCart, SupermarketCartItem, SupermarketStore
from app.services.cart import (
    get_cart,
    load_cache_row,
    replace_items,
    upsert_cart,
)
from app.services.connections import decrypt_cookies, touch_connection
from app.services.scrapers.auchan_cart import (
    AuchanCartAuthError,
    AuchanCartClient,
    AuchanCartError,
    AuchanCartNotFoundError,
    AuchanCartState,
    AuchanCartStoreContextError,
    build_auchan_cart_client,
)
from app.services.scrapers.carrefour_cart import (
    CarrefourCartAuthError,
    CarrefourCartClient,
    CarrefourCartError,
    CarrefourCartNotFoundError,
    CarrefourCartState,
    CarrefourCartStoreContextError,
    build_carrefour_cart_client,
)
from app.services.scrapers.intermarche_cart import (
    IntermarcheCartAuthError,
    IntermarcheCartClient,
    IntermarcheCartConflictError,
    IntermarcheCartError,
    IntermarcheCartNotFoundError,
    IntermarcheCartState,
    build_intermarche_cart_client,
    extract_customer_uuid_from_cookies,
)
from app.services.scrapers.leclerc_cart import (
    LeclercCartAuthError,
    LeclercCartClient,
    LeclercCartError,
    LeclercCartNotFoundError,
    LeclercCartState,
    LeclercCartStoreContextError,
    build_leclerc_cart_client,
)
from app.services.cart_exceptions import (
    SupermarketCartAuthError,
    SupermarketCartConflictError,
    SupermarketCartError,
    SupermarketCartNotFoundError,
    SupermarketCartStoreContextError,
)
from app.services.store_catalog import get_selected_store, load_active_connection

T = TypeVar("T")

_NO_CONNECTION_DETAIL = (
    "Aucune connexion Intermarché active pour ce compte. Importe et active une "
    "connexion (POST /supermarket/connections/import) avant d'utiliser le panier "
    "miroir."
)

_NO_CUSTOMER_UUID_DETAIL = (
    "Impossible de retrouver l'identifiant client Intermarché dans les cookies de "
    "session (userId reçu par le redirect OAuth /loading?userId=…). Ré-importe les "
    "cookies depuis une session connectée."
)

_NO_SITE_ITEM_ID_DETAIL = (
    "La ligne n'a pas d'identifiant exploitable : impossible de la modifier sur le site."
)


def _get_no_connection_detail(store: SupermarketStore) -> str:
    if store == SupermarketStore.INTERMARCHE:
        return _NO_CONNECTION_DETAIL
    label = store.value.capitalize()
    return (
        f"Aucune connexion {label} active pour ce compte. Importe et active une "
        f"connexion (POST /supermarket/connections/import) avant d'utiliser le panier "
        f"miroir."
    )


@dataclass(frozen=True, slots=True)
class CartItemSnapshot:
    external_id: str
    name: str
    quantity: int
    price_amount: float | None = None
    price_text: str | None = None
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class CartStateSnapshot:
    store: SupermarketStore
    amount: float
    items_count: int
    items: tuple[CartItemSnapshot, ...]


def _state_to_items(state: Any) -> list[dict[str, Any]]:
    """Normalize an adapter response into ``cart.replace_items`` snapshots.

    Lines with a zero/negative quantity are dropped: a removed line disappears
    from the server response, and a kept 0-quantity line is not a cart line.
    """
    if state is None or not hasattr(state, "items"):
        return []
    return [
        {
            "external_id": item.item_id,
            "name": item.name,
            "quantity": item.quantity,
            "price_amount": item.price,
            "price_text": item.price_text,
            "image_url": item.image,
        }
        for item in state.items
        if item.quantity > 0
    ]


def _as_http_error(exc: Exception, store_label: str = "Supermarché") -> HTTPException:
    if isinstance(
        exc,
        (
            SupermarketCartAuthError,
            IntermarcheCartAuthError,
            CarrefourCartAuthError,
            LeclercCartAuthError,
            AuchanCartAuthError,
        ),
    ):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(
        exc,
        (
            SupermarketCartStoreContextError,
            CarrefourCartStoreContextError,
            LeclercCartStoreContextError,
            AuchanCartStoreContextError,
        ),
    ):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(
        exc,
        (
            SupermarketCartNotFoundError,
            IntermarcheCartNotFoundError,
            CarrefourCartNotFoundError,
            LeclercCartNotFoundError,
            AuchanCartNotFoundError,
        ),
    ):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (SupermarketCartConflictError, IntermarcheCartConflictError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(
        exc,
        (
            SupermarketCartError,
            IntermarcheCartError,
            CarrefourCartError,
            LeclercCartError,
            AuchanCartError,
        ),
    ):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=503, detail=f"Panier {store_label} indisponible : {exc}")


async def _run_with_client(
    session: Session,
    user_id: int,
    store: SupermarketStore,
    action: Callable[[Any], Awaitable[T]],
) -> T:
    """Build the mirror client for the user and store, then run an adapter action."""
    connection = load_active_connection(session, store, user_id=user_id)
    if connection is None:
        raise HTTPException(status_code=400, detail=_get_no_connection_detail(store))
    cookies = decrypt_cookies(connection)
    if not cookies:
        raise HTTPException(status_code=400, detail=_get_no_connection_detail(store))
    touch_connection(session, connection)

    client: Any = None
    if store == SupermarketStore.INTERMARCHE:
        customer_uuid = extract_customer_uuid_from_cookies(cookies) or connection.customer_uuid
        if not customer_uuid:
            raise HTTPException(status_code=400, detail=_NO_CUSTOMER_UUID_DETAIL)
        if customer_uuid != connection.customer_uuid:
            connection.customer_uuid = customer_uuid
            session.add(connection)
            session.commit()
        try:
            client = build_intermarche_cart_client(cookies, customer_uuid=customer_uuid)
        except IntermarcheCartError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    elif store == SupermarketStore.CARREFOUR:
        try:
            client = build_carrefour_cart_client(cookies)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    elif store == SupermarketStore.LECLERC:
        selection = get_selected_store(session, SupermarketStore.LECLERC)
        base_url = None
        plid = None
        if selection and selection.payload_json:
            base_url = selection.payload_json.get("base_url")
            plid = selection.payload_json.get("plid")
        try:
            client = build_leclerc_cart_client(cookies, base_url=base_url, plid=plid)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    elif store == SupermarketStore.AUCHAN:
        selection = get_selected_store(session, SupermarketStore.AUCHAN)
        seller_id = None
        if selection and selection.payload_json:
            seller_id = selection.payload_json.get("seller_id") or selection.store_id
        try:
            client = build_auchan_cart_client(cookies, seller_id=seller_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail=f"Magasin non pris en charge : {store}")

    try:
        return await action(client)
    except HTTPException:
        raise
    except Exception as exc:
        raise _as_http_error(exc, store_label=store.value.capitalize()) from exc
    finally:
        if client is not None and hasattr(client, "aclose"):
            await client.aclose()


def _commit_state(
    session: Session,
    user_id: int,
    state: Any | None,
    store: SupermarketStore = SupermarketStore.INTERMARCHE,
) -> SupermarketCart:
    """Write a successful server response into the local mirror cart."""
    cart = upsert_cart(session, store, user_id=user_id)
    replace_items(session, cart, _state_to_items(state) if state is not None else [])
    return cart


def _local_item(
    session: Session,
    user_id: int,
    item_id: int,
    store: SupermarketStore | None = None,
) -> SupermarketCartItem:
    """Load the user's mirror cart line, 404 when the cart or line is missing."""
    item = session.get(SupermarketCartItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Cart item not found")
    cart = session.get(SupermarketCart, item.cart_id)
    if cart is None or cart.user_id != user_id:
        raise HTTPException(status_code=404, detail="Cart item not found")
    if store is not None and cart.store != store:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return item


async def read_cart(
    session: Session,
    user_id: int,
    store: SupermarketStore = SupermarketStore.INTERMARCHE,
) -> SupermarketCart:
    """GET mirror: re-read the site cart and mirror it locally."""

    async def action(client: Any) -> Any:
        return await client.get_or_read_cart()

    state = await _run_with_client(session, user_id, store, action)
    return _commit_state(session, user_id, state, store=store)


async def add_item(
    session: Session,
    user_id: int,
    cache_id: int,
    quantity: int,
    store: SupermarketStore | None = None,
) -> SupermarketCart:
    """POST mirror: add item to retailer cart with duplicate accumulation, then mirror."""
    cache_row = load_cache_row(session, cache_id)  # 400 when unknown/expired
    target_store = store or cache_row.store
    payload = cache_row.payload_json or {}
    item_id = payload.get("site_item_id") or cache_row.external_id
    if not item_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Le produit n'a pas d'identifiant {target_store.value.capitalize()} exploitable : "
                "impossible de l'ajouter au panier du site."
            ),
        )

    # Duplicate accumulation logic: check if already present in user's cart for this store
    cart = get_cart(session, target_store, user_id=user_id)
    existing_item = None
    if cart and cart.id is not None:
        items = session.exec(
            select(SupermarketCartItem).where(SupermarketCartItem.cart_id == cart.id)
        ).all()
        for it in items:
            if it.external_id == item_id or it.external_id == cache_row.external_id:
                existing_item = it
                break

    async def action(client: Any) -> Any:
        if target_store == SupermarketStore.INTERMARCHE:
            return await client.add_item(item_id, quantity=quantity)

        if existing_item is not None:
            accumulated_quantity = existing_item.quantity + quantity
            return await client.update_item_quantity(item_id, accumulated_quantity)

        offer_id = payload.get("offer_id")
        seller_id = payload.get("seller_id")
        if target_store == SupermarketStore.AUCHAN and (offer_id or seller_id):
            return await client.add_item(
                item_id,
                quantity=quantity,
                offer_id=offer_id,
                seller_id=seller_id,
            )
        return await client.add_item(item_id, quantity=quantity)

    state = await _run_with_client(session, user_id, target_store, action)
    return _commit_state(session, user_id, state, store=target_store)


async def update_item_quantity(
    session: Session,
    user_id: int,
    item_id: int,
    quantity: int,
    store: SupermarketStore | None = None,
) -> SupermarketCart:
    """PATCH mirror: set the line's quantity on the site, then mirror."""
    item = _local_item(session, user_id, item_id, store=store)
    cart = session.get(SupermarketCart, item.cart_id)
    target_store = cart.store if cart else (store or SupermarketStore.INTERMARCHE)
    site_item_id = item.external_id
    if not site_item_id:
        raise HTTPException(status_code=400, detail=_NO_SITE_ITEM_ID_DETAIL)

    async def action(client: Any) -> Any:
        if target_store == SupermarketStore.INTERMARCHE:
            await client.get_or_read_cart()
        return await client.update_item_quantity(site_item_id, quantity)

    state = await _run_with_client(session, user_id, target_store, action)
    return _commit_state(session, user_id, state, store=target_store)


async def remove_item(
    session: Session,
    user_id: int,
    item_id: int,
    store: SupermarketStore | None = None,
) -> SupermarketCart:
    """DELETE mirror: remove the line on the site, then mirror."""
    item = _local_item(session, user_id, item_id, store=store)
    cart = session.get(SupermarketCart, item.cart_id)
    target_store = cart.store if cart else (store or SupermarketStore.INTERMARCHE)
    site_item_id = item.external_id
    if not site_item_id:
        raise HTTPException(status_code=400, detail=_NO_SITE_ITEM_ID_DETAIL)

    async def action(client: Any) -> Any:
        if target_store == SupermarketStore.INTERMARCHE:
            await client.get_or_read_cart()
        return await client.remove_item(site_item_id)

    state = await _run_with_client(session, user_id, target_store, action)
    return _commit_state(session, user_id, state, store=target_store)


async def clear_cart(
    session: Session,
    user_id: int,
    store: SupermarketStore = SupermarketStore.INTERMARCHE,
) -> SupermarketCart:
    """DELETE mirror: clear the site cart, then empty the local mirror."""

    async def action(client: Any) -> None:
        await client.clear_cart()

    await _run_with_client(session, user_id, store, action)
    return _commit_state(session, user_id, None, store=store)
