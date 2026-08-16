"""Intermarché cart adapter — read/write the store's real shopping cart.

Intermarché does not expose a plain REST cart resource; instead the cart is
synchronised through a single POST endpoint that replays the client's last known
cart and applies a list of delta ``events`` on top of it (the response is the
new cart state). The endpoints and payloads below were recovered from a
connected-session HAR capture (``data/live-capture/intermarche.har``) and are
documented in ``docs/supermarket-reverse-engineering.md``.

Endpoints (``https://www.intermarche.com/api/service/panier/v1``):

- ``POST /stores/{store_id}/carts?customerId={uuid}``
  Body ``{customerDateTime, events: [...], lastSynchronizedCart: {...}}``.
  ``events`` is empty for a pure read; each mutation is a ``QUANTITY`` event
  whose ``quantity`` is a *signed delta* applied on top of the replayed
  ``lastSynchronizedCart`` (add = ``+n``, remove = ``-n``). The response is the
  full new cart state.
- ``DELETE /customers/{uuid}/carts?sellerId=ITM`` → 204 (clears the cart).

The ``store_id`` is the selected store id recovered from the session cookies via
``extract_pdv_ref_from_cookies`` (the ``itm_pdv`` / ``novaParams`` cookies). The
``customer_uuid`` identifies the connected customer and is *not* reliably stored
in a cookie: the OAuth flow hands it back through the ``/loading?userId=…``
redirect. Callers therefore pass it explicitly; ``extract_customer_uuid_from_cookies``
is a best-effort helper that only recovers it when a session cookie happens to
carry it.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from app.services.scrapers.intermarche import (
    build_intermarche_cookie_jar,
    extract_pdv_ref_from_cookies,
    is_intermarche_bot_challenge,
)

INTERMARCHE_CART_BASE_URL = "https://www.intermarche.com/api/service/panier/v1"

# Chrome UA matching the browser the cart API is served to (same profile as the
# search scraper); the cart endpoint additionally requires `x-oauth` when the
# session is connected (customerId in the query string).
_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

_CART_HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "origin": "https://www.intermarche.com",
    "referer": "https://www.intermarche.com/",
    "user-agent": _CHROME_USER_AGENT,
    "x-oauth": "true",
    "x-service-name": "panier",
    "x-red-device": "red_fo_desktop",
    "x-red-version": "3",
}

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# Cookie names that, when present, unambiguously hold the *customer* uuid. The
# generic session/device cookies (itm_session, itm_device_id) carry their own
# uuids and are deliberately not scanned.
_CUSTOMER_UUID_COOKIE_NAMES = frozenset(
    {"itm_customer", "itm_customer_id", "itm_customer_uuid", "customerId", "customer_id"}
)
_CUSTOMER_UUID_JSON_KEYS = ("customerId", "customer_id", "customerUuid", "userId")


class IntermarcheCartError(RuntimeError):
    """Base error for the Intermarché cart adapter."""


class IntermarcheCartAuthError(IntermarcheCartError):
    """Intermarché rejected the session (401/403/DataDome) — the cookies are dead."""


class IntermarcheCartNotFoundError(IntermarcheCartError):
    """The cart (or customer) was not found (404)."""


class IntermarcheCartConflictError(IntermarcheCartError):
    """The replayed ``lastSynchronizedCart`` was out of sync with the server (409)."""


@dataclass(frozen=True, slots=True)
class IntermarcheCartItem:
    """A normalized cart line, mapped from the site's ``carts[].items[]`` shape.

    ``id`` is the cart line id, ``item_id`` the product/item id (``item.itemId``)
    used as the key for the ``QUANTITY`` events.
    """

    id: str
    item_id: str
    name: str
    quantity: int
    price: float | None
    price_text: str | None
    image: str | None
    ean: str | None


@dataclass(frozen=True, slots=True)
class IntermarcheCartState:
    """The last cart state synchronised from the server.

    ``raw_payload`` keeps the full response so the next request can replay a
    faithfully trimmed ``lastSynchronizedCart``.
    """

    customer_id: str
    store_id: str
    synchronize_date_time: str
    amount: float
    items_number: int
    items: tuple[IntermarcheCartItem, ...]
    raw_payload: dict = field(repr=False, compare=False, default_factory=dict)

    def item_quantity(self, item_id: str) -> int:
        total = 0
        for item in self.items:
            if item.item_id == str(item_id):
                total += item.quantity
        return total

    def to_last_synchronized_cart(self) -> dict:
        return build_last_synchronized_cart(
            self.raw_payload, _truncate_to_seconds(self.synchronize_date_time)
        )


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _truncate_to_seconds(iso: str) -> str:
    if not iso:
        return iso
    try:
        return datetime.fromisoformat(iso).isoformat(timespec="seconds")
    except ValueError:
        return iso


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_price(price: float | None) -> str | None:
    if price is None:
        return None
    return f"{str(price).replace('.', ',')} €"


def extract_customer_uuid_from_cookies(cookies: list[dict[str, Any]] | None) -> str | None:
    """Best-effort recovery of the connected customer uuid from session cookies.

    The connected-session HAR does not store the customer uuid in a cookie (it
    arrives via the ``/loading?userId=…`` OAuth redirect), so this usually
    returns ``None`` and the caller supplies the uuid explicitly. It only returns
    a value when a cookie is unambiguously the customer id (a known name or a
    JSON cookie carrying ``customerId``/``userId``).
    """
    for cookie in cookies or []:
        name = cookie.get("name")
        value = (cookie.get("value") or "").strip()
        if not value:
            continue
        if name in _CUSTOMER_UUID_COOKIE_NAMES:
            match = _UUID_RE.search(value)
            if match:
                return match.group(0)
            continue
        try:
            payload = json.loads(urllib.parse.unquote(value))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(payload, dict):
            for key in _CUSTOMER_UUID_JSON_KEYS:
                raw = payload.get(key)
                if raw:
                    match = _UUID_RE.search(str(raw))
                    if match:
                        return match.group(0)
    return None


def build_quantity_event(
    item_id: str | int,
    quantity: int,
    *,
    catalog: str = "PDV",
    date_time: str | None = None,
    tracking_code: str | None = None,
    accept_substitution: bool | None = None,
) -> dict[str, Any]:
    """Compose a ``QUANTITY`` delta event (add = ``+n``, remove = ``-n``)."""
    event: dict[str, Any] = {
        "catalog": catalog,
        "itemId": str(item_id),
        "quantity": int(quantity),
        "dateTime": date_time or _now_iso(),
        "type": "QUANTITY",
    }
    if tracking_code is not None:
        event["trackingCode"] = tracking_code
    if accept_substitution is not None:
        event["acceptSubstitution"] = accept_substitution
    return event


def build_last_synchronized_cart(
    payload: dict[str, Any], synchronize_date_time: str | None
) -> dict[str, Any]:
    """Trim a full cart response into the ``lastSynchronizedCart`` replay shape.

    The client only replays a subset of each item (``itemId``/``idProduit``,
    the EAN, price, stock and the labels the server needs to reconcile); this
    mirrors the observed ``lastSynchronizedCart`` exactly, including the quirk
    that ``idProduit`` echoes the ``itemId`` rather than the EAN.
    """
    carts: list[dict[str, Any]] = []
    for cart in payload.get("carts") or []:
        if not isinstance(cart, dict):
            continue
        lines = cart.get("items") or []
        if not lines:
            continue
        carts.append(
            {
                "items": [_trim_cart_item(line) for line in lines],
                "catalog": cart.get("catalog"),
                "amount": cart.get("amount"),
                "seller": {
                    "id": (cart.get("seller") or {}).get("id"),
                    "name": (cart.get("seller") or {}).get("name"),
                },
                "acceptSubstitution": cart.get("acceptSubstitution"),
            }
        )
    return {"carts": carts, "synchronizeDateTime": synchronize_date_time}


def _trim_cart_item(line: dict[str, Any]) -> dict[str, Any]:
    item = line.get("item") if isinstance(line.get("item"), dict) else {}
    price = line.get("price")
    trimmed: dict[str, Any] = {
        "id": line.get("id"),
        "quantity": line.get("quantity"),
        "price": price,
        "amount": line.get("amount"),
        "acceptSubstitution": line.get("acceptSubstitution"),
        "item": {
            "itemId": item.get("itemId"),
            "idProduit": item.get("itemId"),
            "produitEan13": item.get("produitEan13"),
            "pviIncrement": item.get("pviIncrement"),
            "prix": price if price is not None else item.get("prix"),
            "privateData": item.get("privateData"),
            "poidsMinimum": item.get("poidsMinimum"),
            "substituable": item.get("substituable"),
            "dispoCataloguePdv": item.get("dispoCataloguePdv"),
            "stock": item.get("stock"),
            "catalog": item.get("catalog"),
            "libelle": item.get("libelle"),
            "compatibleConsigne": item.get("compatibleConsigne"),
            "marque": item.get("marque"),
            "conditionnement": item.get("conditionnement"),
            "qteMaxPanier": item.get("qteMaxPanier"),
            "isPresentAlcoholProduct": item.get("isPresentAlcoholProduct"),
        },
    }
    if line.get("itemParentId") is not None:
        trimmed["itemParentId"] = line["itemParentId"]
    if line.get("comment") is not None:
        trimmed["comment"] = line["comment"]
    return trimmed


def build_cart_request_body(
    *,
    events: list[dict[str, Any]],
    last_sync: IntermarcheCartState | None,
    customer_date_time: str | None = None,
) -> dict[str, Any]:
    """Compose the sync request body (customerDateTime + events + replay)."""
    return {
        "customerDateTime": customer_date_time or _now_iso(),
        "events": events,
        "lastSynchronizedCart": (
            last_sync.to_last_synchronized_cart()
            if last_sync is not None
            else {"carts": [], "synchronizeDateTime": None}
        ),
    }


def _first_image(item: dict[str, Any]) -> str | None:
    images = item.get("images")
    if isinstance(images, list) and images and images[0]:
        return str(images[0])
    return None


def parse_cart_items(payload: dict[str, Any]) -> list[IntermarcheCartItem]:
    """Map the site's cart response into normalized ``IntermarcheCartItem`` lines."""
    items: list[IntermarcheCartItem] = []
    carts = payload.get("carts") if isinstance(payload, dict) else None
    for cart in carts or []:
        if not isinstance(cart, dict):
            continue
        for line in cart.get("items") or []:
            if not isinstance(line, dict):
                continue
            item = line.get("item") if isinstance(line.get("item"), dict) else {}
            line_id = str(line.get("id") or "").strip()
            item_id = str(item.get("itemId") or line_id or "").strip()
            if not item_id:
                continue
            price = _as_float(line.get("price"))
            items.append(
                IntermarcheCartItem(
                    id=line_id or item_id,
                    item_id=item_id,
                    name=(item.get("libelle") or "").strip() or "Produit inconnu",
                    quantity=int(line.get("quantity") or 0),
                    price=price,
                    price_text=_format_price(price),
                    image=_first_image(item),
                    ean=str(item.get("produitEan13") or "") or None,
                )
            )
    return items


def parse_cart_response(
    payload: dict[str, Any],
    *,
    store_id: str,
    customer_uuid: str | None = None,
) -> IntermarcheCartState:
    """Normalize a full cart response into an ``IntermarcheCartState``."""
    return IntermarcheCartState(
        customer_id=str(payload.get("id") or customer_uuid or ""),
        store_id=str(store_id),
        synchronize_date_time=str(payload.get("synchronizeDateTime") or ""),
        amount=_as_float(payload.get("amount")) or 0.0,
        items_number=int(payload.get("itemsNumber") or 0),
        items=tuple(parse_cart_items(payload)),
        raw_payload=payload,
    )


class IntermarcheCartClient:
    """Talks to the Intermarché cart API with a connected session's cookies.

    The client holds the last synchronised state so each mutation replays the
    correct ``lastSynchronizedCart``. ``client`` is an injected
    ``httpx.AsyncClient`` (built on the session cookies); the caller owns its
    lifecycle.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        customer_uuid: str,
        store_id: str,
        catalog: str = "PDV",
        seller_id: str = "ITM",
    ) -> None:
        self._client = client
        self._customer_uuid = customer_uuid
        self._store_id = store_id
        self._catalog = catalog
        self._seller_id = seller_id
        self._last_sync: IntermarcheCartState | None = None

    @property
    def last_sync(self) -> IntermarcheCartState | None:
        return self._last_sync

    def _carts_url(self) -> str:
        return f"{INTERMARCHE_CART_BASE_URL}/stores/{self._store_id}/carts"

    def _clear_url(self) -> str:
        return f"{INTERMARCHE_CART_BASE_URL}/customers/{self._customer_uuid}/carts"

    def _raise_for_cart_error(self, response: httpx.Response) -> None:
        if response.status_code == 204:
            return
        if response.status_code in {401, 403} or is_intermarche_bot_challenge(response.text):
            raise IntermarcheCartAuthError(
                "Intermarché rejected the current cart session (401/403 or DataDome). "
                "Re-import the connection cookies from a fresh browser session."
            )
        if response.status_code == 404:
            raise IntermarcheCartNotFoundError(
                "Intermarché cart/customer not found (404). The session's customer "
                "uuid or selected store may be wrong."
            )
        if response.status_code == 409:
            raise IntermarcheCartConflictError(
                "Intermarché cart out of sync (409): the replayed lastSynchronizedCart "
                "did not match the server state. Re-read the cart before mutating."
            )
        if response.status_code >= 400:
            snippet = (response.text or "")[:200]
            raise IntermarcheCartError(
                f"Intermarché cart API error {response.status_code}: {snippet}"
            )

    async def _sync(self, events: list[dict[str, Any]]) -> IntermarcheCartState:
        body = build_cart_request_body(
            events=events,
            last_sync=self._last_sync,
            customer_date_time=_now_iso(),
        )
        response = await self._client.post(
            self._carts_url(),
            params={"customerId": self._customer_uuid},
            json=body,
            headers=_CART_HEADERS,
        )
        self._raise_for_cart_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise IntermarcheCartError(
                "Intermarché cart API returned a non-JSON response (likely a "
                "DataDome challenge or dead session)."
            ) from exc
        state = parse_cart_response(
            payload, store_id=self._store_id, customer_uuid=self._customer_uuid
        )
        self._last_sync = state
        return state

    async def get_or_read_cart(
        self, last_sync: IntermarcheCartState | None = None
    ) -> IntermarcheCartState:
        """Read the current cart (empty events + replayed ``lastSynchronizedCart``).

        ``last_sync`` optionally seeds the replay state (e.g. after a 409); by
        default the previous response is replayed.
        """
        if last_sync is not None:
            self._last_sync = last_sync
        return await self._sync([])

    async def add_item(
        self,
        item_id: str | int,
        quantity: int = 1,
        *,
        tracking_code: str | None = None,
        accept_substitution: bool | None = None,
    ) -> IntermarcheCartState:
        """Add ``quantity`` of ``item_id`` (a ``+quantity`` QUANTITY event)."""
        event = build_quantity_event(
            item_id,
            quantity,
            catalog=self._catalog,
            date_time=_now_iso(),
            tracking_code=tracking_code,
            accept_substitution=accept_substitution,
        )
        return await self._sync([event])

    async def update_item_quantity(
        self, item_id: str | int, quantity: int
    ) -> IntermarcheCartState:
        """Set the line's quantity to ``quantity`` (sends the signed delta)."""
        current = self._last_sync.item_quantity(item_id) if self._last_sync else 0
        delta = int(quantity) - current
        if delta == 0:
            return self._last_sync if self._last_sync is not None else await self._sync([])
        event = build_quantity_event(item_id, delta, catalog=self._catalog, date_time=_now_iso())
        return await self._sync([event])

    async def remove_item(self, item_id: str | int) -> IntermarcheCartState:
        """Remove the line (a ``-current_quantity`` QUANTITY event; -1 for qty 1)."""
        current = self._last_sync.item_quantity(item_id) if self._last_sync else 0
        if current <= 0:
            return self._last_sync if self._last_sync is not None else await self._sync([])
        event = build_quantity_event(item_id, -current, catalog=self._catalog, date_time=_now_iso())
        return await self._sync([event])

    async def clear_cart(self) -> None:
        """Clear the cart (DELETE customers/{uuid}/carts?sellerId=ITM → 204)."""
        response = await self._client.delete(
            self._clear_url(),
            params={"sellerId": self._seller_id},
            headers=_CART_HEADERS,
        )
        self._raise_for_cart_error(response)
        self._last_sync = None


def build_intermarche_cart_client(
    cookies: list[dict[str, Any]],
    *,
    customer_uuid: str,
    proxy_url: str | None = None,
    catalog: str = "PDV",
    seller_id: str = "ITM",
) -> IntermarcheCartClient:
    """Build a cart client from a connected session's cookies.

    The selected store id is recovered from the cookies (``itm_pdv`` /
    ``novaParams``); without a selected store the cart cannot be scoped and this
    raises. ``customer_uuid`` must be supplied by the caller (it is not stored
    in the cookies).
    """
    store_id = extract_pdv_ref_from_cookies(cookies)
    if not store_id:
        raise IntermarcheCartError(
            "No Intermarché store selected in the session cookies (itm_pdv / "
            "novaParams). Select a store in the browser before importing the "
            "connection."
        )
    client = httpx.AsyncClient(
        follow_redirects=True,
        cookies=build_intermarche_cookie_jar(cookies),
        proxy=proxy_url,
        timeout=httpx.Timeout(30.0),
        trust_env=not proxy_url,
    )
    return IntermarcheCartClient(
        client,
        customer_uuid=customer_uuid,
        store_id=store_id,
        catalog=catalog,
        seller_id=seller_id,
    )
