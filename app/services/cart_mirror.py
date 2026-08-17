"""Intermarché cart mirror — drive the store's real cart from /supermarket/carts*.

Run 1 shipped local-only carts. For Intermarché the cart endpoints now act as a
true mirror: each mutation is first applied to the store's cart through the b1
adapter (``app/services/scrapers/intermarche_cart.py``) and the local
``SupermarketCart`` is rewritten from the server's response; every failure (dead
session, missing connection, out-of-sync, …) is rejected with a clear HTTP error
WITHOUT touching the local cart. PUT status stays a local, manual operation and
the three other stores keep the local behavior.

Public surface (all throw ``fastapi.HTTPException`` directly, like the rest of the
cart service layer):

- ``read_cart``              → adapter ``get_or_read_cart`` (empty events)
- ``add_item``               → cache row → adapter ``add_item``
- ``update_item_quantity``   → local line → read + adapter ``update_item_quantity``
- ``remove_item``            → local line → read + adapter ``remove_item``
- ``clear_cart``             → adapter ``clear_cart``

The adapter seam for tests is ``build_intermarche_cart_client`` (monkeypatched in
``tests/test_supermarket_cart_mirror.py``); the mirrored local rewrite goes
through ``cart.replace_items``.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from fastapi import HTTPException
from sqlmodel import Session

from app.models import SupermarketCart, SupermarketCartItem, SupermarketStore
from app.services.cart import (
    get_cart,
    load_cache_row,
    replace_items,
    upsert_cart,
)
from app.services.connections import decrypt_cookies, touch_connection
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
from app.services.store_catalog import load_active_connection

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
    "La ligne n'a pas d'identifiant Intermarché exploitable : impossible de la "
    "modifier sur le site."
)


def _state_to_items(state: IntermarcheCartState) -> list[dict[str, Any]]:
    """Normalize an adapter response into ``cart.replace_items`` snapshots.

    Lines with a zero/negative quantity are dropped: a removed line disappears
    from the server response, and a kept 0-quantity line is not a cart line.
    """
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


def _as_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IntermarcheCartAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, IntermarcheCartNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, IntermarcheCartConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, IntermarcheCartError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=503, detail=f"Panier Intermarché indisponible : {exc}")


async def _run_with_client(
    session: Session,
    user_id: int,
    action: Callable[[IntermarcheCartClient], Awaitable[T]],
) -> T:
    """Build the mirror client for the user and run an adapter action.

    Resolves the active Intermarché connection and the customer uuid first (400
    with a clear message when either is missing), then delegates to the adapter.
    Every adapter error becomes a typed HTTP error, and the client (and its HTTP
    connection) is always released.

    The customer uuid is not reliably present in cookies (see
    ``extract_customer_uuid_from_cookies``), so a routine cookie-only re-sync
    from the extension would otherwise silently drop it: this falls back to
    the value persisted on the connection row, and self-heals that row when
    the cookies *do* carry a (possibly new) uuid so it survives future syncs.
    """
    connection = load_active_connection(session, SupermarketStore.INTERMARCHE, user_id=user_id)
    if connection is None:
        raise HTTPException(status_code=400, detail=_NO_CONNECTION_DETAIL)
    cookies = decrypt_cookies(connection)
    if not cookies:
        raise HTTPException(status_code=400, detail=_NO_CONNECTION_DETAIL)
    touch_connection(session, connection)
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
    try:
        return await action(client)
    except IntermarcheCartError as exc:
        raise _as_http_error(exc) from exc
    finally:
        await client.aclose()


def _commit_state(session: Session, user_id: int, state: IntermarcheCartState | None) -> SupermarketCart:
    """Write a successful server response into the local mirror cart.

    Called only after the adapter succeeded: the local cart (created on demand)
    is rewritten to mirror the server's response verbatim.
    """
    cart = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=user_id)
    replace_items(session, cart, _state_to_items(state) if state is not None else [])
    return cart


def _local_item(session: Session, user_id: int, item_id: int) -> SupermarketCartItem:
    """Load the user's mirror cart line, 404 when the cart or line is missing."""
    cart = get_cart(session, SupermarketStore.INTERMARCHE, user_id=user_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart item not found")
    item = session.get(SupermarketCartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return item


async def read_cart(session: Session, user_id: int) -> SupermarketCart:
    """GET mirror: re-read the site cart (empty events) and mirror it locally."""

    async def action(client: IntermarcheCartClient) -> IntermarcheCartState:
        return await client.get_or_read_cart()

    state = await _run_with_client(session, user_id, action)
    return _commit_state(session, user_id, state)


async def add_item(session: Session, user_id: int, cache_id: int, quantity: int) -> SupermarketCart:
    """POST mirror: send a +quantity event for the cache row's site id, then mirror.

    The cart API validates ``itemId`` as the catalog's own (short, numeric) id
    — an EAN barcode is rejected. ``external_id`` prefers the EAN (used for
    search/cross-store matching), so the raw catalog id captured separately
    at search time (``payload_json.site_item_id``) is used here when present,
    falling back to ``external_id`` for cache rows fetched before this field
    existed.
    """
    cache_row = load_cache_row(session, cache_id)  # 400 when unknown/expired
    item_id = (cache_row.payload_json or {}).get("site_item_id") or cache_row.external_id
    if not item_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Le produit n'a pas d'identifiant Intermarché exploitable : "
                "impossible de l'ajouter au panier du site."
            ),
        )

    async def action(client: IntermarcheCartClient) -> IntermarcheCartState:
        return await client.add_item(item_id, quantity=quantity)

    state = await _run_with_client(session, user_id, action)
    return _commit_state(session, user_id, state)


async def update_item_quantity(session: Session, user_id: int, item_id: int, quantity: int) -> SupermarketCart:
    """PATCH mirror: set the line's quantity on the site (delta protocol), then mirror."""
    item = _local_item(session, user_id, item_id)
    site_item_id = item.external_id
    if not site_item_id:
        raise HTTPException(status_code=400, detail=_NO_SITE_ITEM_ID_DETAIL)

    async def action(client: IntermarcheCartClient) -> IntermarcheCartState:
        # The delta protocol needs the current state: re-read the live cart so the
        # adapter computes quantity - current against the server, not against an
        # empty replay on a fresh client.
        await client.get_or_read_cart()
        return await client.update_item_quantity(site_item_id, quantity)

    state = await _run_with_client(session, user_id, action)
    return _commit_state(session, user_id, state)


async def remove_item(session: Session, user_id: int, item_id: int) -> SupermarketCart:
    """DELETE mirror: remove the line on the site (delta -current), then mirror."""
    item = _local_item(session, user_id, item_id)
    site_item_id = item.external_id
    if not site_item_id:
        raise HTTPException(status_code=400, detail=_NO_SITE_ITEM_ID_DETAIL)

    async def action(client: IntermarcheCartClient) -> IntermarcheCartState:
        # Same delta protocol as the quantity update: read first, then remove.
        await client.get_or_read_cart()
        return await client.remove_item(site_item_id)

    state = await _run_with_client(session, user_id, action)
    return _commit_state(session, user_id, state)


async def clear_cart(session: Session, user_id: int) -> SupermarketCart:
    """DELETE mirror: clear the site cart (204), then empty the local mirror."""

    async def action(client: IntermarcheCartClient) -> None:
        await client.clear_cart()

    await _run_with_client(session, user_id, action)
    return _commit_state(session, user_id, None)