"""Carrefour cart adapter.

Communicates with Carrefour's cart API using authenticated session cookies
and proxy pool support for Cloudflare-protected requests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

try:
    from curl_cffi.requests import AsyncSession as CurlCffiAsyncSession
    from curl_cffi.requests.cookies import Cookies as CurlCffiCookies
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CurlCffiAsyncSession = None  # type: ignore[assignment]
    CurlCffiCookies = None  # type: ignore[assignment]
    CURL_CFFI_AVAILABLE = False

CURL_IMPERSONATE = "chrome"

from app.services.cart_exceptions import (
    SupermarketCartAuthError,
    SupermarketCartError,
    SupermarketCartNotFoundError,
    SupermarketCartStoreContextError,
)
from app.services.scrapers.carrefour import build_carrefour_cookie_jar

CARREFOUR_CART_BASE_URL = "https://www.carrefour.fr/api/cart"

_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://www.carrefour.fr",
    "referer": "https://www.carrefour.fr/",
    "user-agent": _CHROME_USER_AGENT,
    "x-requested-with": "XMLHttpRequest",
}


class CarrefourCartError(SupermarketCartError):
    """Base error for Carrefour cart adapter."""


class CarrefourCartAuthError(SupermarketCartAuthError, CarrefourCartError):
    """Session expired or cookies rejected by Carrefour."""


class CarrefourCartStoreContextError(SupermarketCartStoreContextError, CarrefourCartError):
    """Store location / Drive context missing or invalid."""


class CarrefourCartNotFoundError(SupermarketCartNotFoundError, CarrefourCartError):
    """Cart or item not found on Carrefour."""


@dataclass(frozen=True, slots=True)
class CarrefourCartItem:
    id: str
    item_id: str
    name: str
    quantity: int
    price: float | None
    price_text: str | None
    image: str | None
    ean: str | None


@dataclass(frozen=True, slots=True)
class CarrefourCartState:
    cart_id: str
    amount: float
    items_count: int
    items: tuple[CarrefourCartItem, ...]
    raw_payload: dict = field(repr=False, compare=False, default_factory=dict)


def parse_carrefour_cart_response(payload: dict[str, Any]) -> CarrefourCartState:
    cart_data = payload.get("data", payload)
    cart_id = str(cart_data.get("id", ""))
    amount = float(cart_data.get("total") or cart_data.get("amount") or cart_data.get("total_amount") or 0.0)

    raw_items = cart_data.get("items") or []
    items: list[CarrefourCartItem] = []
    for raw in raw_items:
        line_id = str(raw.get("id") or "")
        product_id = str(raw.get("product_id") or raw.get("productId") or raw.get("id") or "")
        name = str(raw.get("title") or raw.get("name") or "Article Carrefour")
        qty = int(raw.get("quantity") or 0)
        price_val = raw.get("price") or raw.get("unitPrice")
        price = float(price_val) if price_val is not None else None
        price_text = f"{price:.2f} €" if price is not None else None
        image = raw.get("image") or raw.get("imageUrl")
        ean = raw.get("ean")

        if qty > 0:
            items.append(
                CarrefourCartItem(
                    id=line_id,
                    item_id=product_id,
                    name=name,
                    quantity=qty,
                    price=price,
                    price_text=price_text,
                    image=image,
                    ean=ean,
                )
            )

    items_count = int(cart_data.get("items_count") or len(items))
    return CarrefourCartState(
        cart_id=cart_id,
        amount=amount,
        items_count=items_count,
        items=tuple(items),
        raw_payload=payload,
    )


class CarrefourCartClient:
    def __init__(self, http_client: Any):
        self._client = http_client

    async def aclose(self) -> None:
        if hasattr(self._client, "close"):
            await self._client.close()
        elif hasattr(self._client, "aclose"):
            await self._client.aclose()

    def _raise_for_status(self, response: Any, action_desc: str) -> None:
        if response.status_code in (401, 403):
            raise CarrefourCartAuthError(
                f"Session Carrefour expirée ou rejetée (HTTP {response.status_code}) lors de {action_desc}. "
                "Ré-importe tes cookies via l'extension."
            )
        if response.status_code == 404:
            raise CarrefourCartNotFoundError(f"Panier ou article Carrefour introuvable lors de {action_desc}.")
        if response.status_code >= 400:
            raise CarrefourCartError(f"Erreur Carrefour {response.status_code} lors de {action_desc}: {response.text[:200]}")

    async def get_or_read_cart(self) -> CarrefourCartState:
        try:
            response = await self._client.get(CARREFOUR_CART_BASE_URL, headers=_DEFAULT_HEADERS)
        except Exception as exc:
            raise CarrefourCartError(f"Échec de connexion au panier Carrefour: {exc}") from exc
        self._raise_for_status(response, "la lecture du panier")
        return parse_carrefour_cart_response(response.json())

    async def add_item(self, item_id: str, quantity: int = 1) -> CarrefourCartState:
        payload = {"productId": item_id, "quantity": quantity}
        try:
            response = await self._client.post(
                f"{CARREFOUR_CART_BASE_URL}/items",
                json=payload,
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise CarrefourCartError(f"Échec de l'ajout au panier Carrefour: {exc}") from exc
        self._raise_for_status(response, f"l'ajout du produit {item_id}")
        return parse_carrefour_cart_response(response.json())

    async def update_item_quantity(self, item_id: str, quantity: int) -> CarrefourCartState:
        if quantity <= 0:
            return await self.remove_item(item_id)
        payload = {"quantity": quantity}
        try:
            response = await self._client.patch(
                f"{CARREFOUR_CART_BASE_URL}/items/{item_id}",
                json=payload,
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise CarrefourCartError(f"Échec de mise à jour quantité Carrefour: {exc}") from exc
        self._raise_for_status(response, f"la mise à jour de quantité pour {item_id}")
        return parse_carrefour_cart_response(response.json())

    async def remove_item(self, item_id: str) -> CarrefourCartState:
        try:
            response = await self._client.delete(
                f"{CARREFOUR_CART_BASE_URL}/items/{item_id}",
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise CarrefourCartError(f"Échec de suppression d'article Carrefour: {exc}") from exc
        self._raise_for_status(response, f"la suppression du produit {item_id}")
        if response.content:
            return parse_carrefour_cart_response(response.json())
        return await self.get_or_read_cart()

    async def clear_cart(self) -> None:
        try:
            response = await self._client.delete(
                CARREFOUR_CART_BASE_URL,
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise CarrefourCartError(f"Échec du vidage du panier Carrefour: {exc}") from exc
        self._raise_for_status(response, "le vidage du panier")


def build_carrefour_cart_client(
    cookies: list[dict[str, Any]],
    transport: httpx.AsyncBaseTransport | None = None,
) -> CarrefourCartClient:
    if CURL_CFFI_AVAILABLE and transport is None:
        jar = CurlCffiCookies()
        for c in cookies:
            jar.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))
        client = CurlCffiAsyncSession(
            impersonate=CURL_IMPERSONATE,
            cookies=jar,
            timeout=15.0,
        )
    else:
        cookie_jar = build_carrefour_cookie_jar(cookies)
        client = httpx.AsyncClient(
            cookies=cookie_jar,
            transport=transport,
            timeout=15.0,
        )
    return CarrefourCartClient(client)
