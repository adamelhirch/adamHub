"""Auchan cart adapter.

Communicates with Auchan's checkout cart API using authenticated session cookies
and store/seller context.
"""

from __future__ import annotations

import json
import re
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

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

from app.services.cart_exceptions import (
    SupermarketCartAuthError,
    SupermarketCartError,
    SupermarketCartNotFoundError,
    SupermarketCartStoreContextError,
)
from app.services.scrapers.auchan import build_auchan_cookie_jar

AUCHAN_CART_BASE_URL = "https://api.auchan.fr/checkout/v1/carts"

_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://www.auchan.fr",
    "referer": "https://www.auchan.fr/",
    "user-agent": _CHROME_USER_AGENT,
    "x-requested-with": "XMLHttpRequest",
}


class AuchanCartError(SupermarketCartError):
    """Base error for Auchan cart adapter."""


class AuchanCartAuthError(SupermarketCartAuthError, AuchanCartError):
    """Session expired or cookies rejected by Auchan."""


class AuchanCartStoreContextError(SupermarketCartStoreContextError, AuchanCartError):
    """Store location / seller context missing or invalid."""


class AuchanCartNotFoundError(SupermarketCartNotFoundError, AuchanCartError):
    """Cart or item not found on Auchan."""


@dataclass(frozen=True, slots=True)
class AuchanCartItem:
    id: str
    item_id: str
    offer_id: str | None
    name: str
    quantity: int
    price: float | None
    price_text: str | None
    image: str | None
    ean: str | None = None


@dataclass(frozen=True, slots=True)
class AuchanCartState:
    cart_id: str
    amount: float
    items_count: int
    seller_id: str | None
    items: tuple[AuchanCartItem, ...]
    raw_payload: dict = field(repr=False, compare=False, default_factory=dict)


def parse_auchan_cart_response(payload: dict[str, Any]) -> AuchanCartState:
    cart_data = payload.get("data", payload)
    cart_id = str(cart_data.get("cartId") or cart_data.get("id") or "")
    amount = float(cart_data.get("totalAmount") or cart_data.get("amount") or cart_data.get("total") or 0.0)

    seller_info = cart_data.get("seller") or {}
    seller_id = str(seller_info.get("id") or "") or None

    raw_items = cart_data.get("items") or []
    items: list[AuchanCartItem] = []
    for raw in raw_items:
        line_id = str(raw.get("id") or "")
        product_id = str(raw.get("productId") or raw.get("product_id") or raw.get("id") or "")
        offer_id = str(raw.get("offerId") or raw.get("offer_id") or "") or None
        name = str(raw.get("productTitle") or raw.get("title") or raw.get("name") or "Article Auchan")
        qty = int(raw.get("quantity") or raw.get("desiredQuantity") or 0)
        price_val = raw.get("unitPrice") or raw.get("price")
        price = float(price_val) if price_val is not None else None
        price_text = f"{price:.2f} €" if price is not None else None
        image = raw.get("imageUrl") or raw.get("image")
        ean = raw.get("ean")

        if qty > 0:
            items.append(
                AuchanCartItem(
                    id=line_id,
                    item_id=product_id,
                    offer_id=offer_id,
                    name=name,
                    quantity=qty,
                    price=price,
                    price_text=price_text,
                    image=image,
                    ean=ean,
                )
            )

    items_count = int(cart_data.get("itemCount") or len(items))

    return AuchanCartState(
        cart_id=cart_id,
        amount=amount,
        items_count=items_count,
        seller_id=seller_id,
        items=tuple(items),
        raw_payload=payload,
    )


class AuchanCartClient:
    """Client for interacting with Auchan's checkout cart API."""

    def __init__(
        self,
        client: Any,
        consent_id: str | None = None,
        seller_id: str | None = None,
    ) -> None:
        self._client = client
        self._consent_id = consent_id
        self._seller_id = seller_id
        self._cart_id: str | None = None

    async def aclose(self) -> None:
        if hasattr(self._client, "close"):
            await self._client.close()
        elif hasattr(self._client, "aclose"):
            await self._client.aclose()

    def _raise_for_status(self, response: Any, action_label: str) -> None:
        if response.status_code in (401, 403):
            raise AuchanCartAuthError(
                f"Session Auchan expirée ou non autorisée lors de {action_label} "
                f"(HTTP {response.status_code}). Veuillez reconnecter votre compte Auchan."
            )
        if response.status_code == 404:
            raise AuchanCartNotFoundError(f"Ressource non trouvée lors de {action_label} (HTTP 404).")
        if response.status_code in (400, 422):
            try:
                err_json = response.json()
                msg = err_json.get("message") or err_json.get("detail") or str(err_json)
            except Exception:
                msg = response.text[:200]
            raise AuchanCartStoreContextError(
                f"Contexte de magasin Auchan invalide lors de {action_label}: {msg}"
            )
        if response.status_code >= 400:
            raise AuchanCartError(
                f"Échec de l'opération Auchan ({action_label}): HTTP {response.status_code} - {response.text[:200]}"
            )

    def _get_cart_url(self, path: str = "") -> str:
        if self._cart_id:
            base = f"{AUCHAN_CART_BASE_URL}/{self._cart_id}"
        else:
            base = f"{AUCHAN_CART_BASE_URL}/mine"
        return f"{base}{path}" if path else base

    async def get_or_read_cart(self) -> AuchanCartState:
        url = f"{AUCHAN_CART_BASE_URL}/mine"
        params: dict[str, str] = {}
        if self._consent_id:
            params["consentId"] = self._consent_id

        try:
            response = await self._client.get(
                url,
                params=params,
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise AuchanCartError(f"Échec de la connexion à l'API panier Auchan: {exc}") from exc

        self._raise_for_status(response, "la lecture du panier")
        state = parse_auchan_cart_response(response.json())
        if state.cart_id:
            self._cart_id = state.cart_id
        return state

    async def add_item(
        self,
        item_id: str,
        quantity: int = 1,
        offer_id: str | None = None,
        seller_id: str | None = None,
    ) -> AuchanCartState:
        if not self._cart_id:
            try:
                await self.get_or_read_cart()
            except Exception:
                pass

        url = self._get_cart_url("/items")
        payload = {
            "productId": item_id,
            "offerId": offer_id or item_id,
            "sellerId": seller_id or self._seller_id or "",
            "desiredQuantity": quantity,
        }

        try:
            response = await self._client.post(
                url,
                json=payload,
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise AuchanCartError(f"Échec de l'ajout du produit {item_id} au panier Auchan: {exc}") from exc

        self._raise_for_status(response, f"l'ajout du produit {item_id}")
        if response.content:
            try:
                state = parse_auchan_cart_response(response.json())
                if state.cart_id:
                    self._cart_id = state.cart_id
                return state
            except Exception:
                pass
        return await self.get_or_read_cart()

    async def update_item_quantity(self, item_id: str, quantity: int) -> AuchanCartState:
        if quantity <= 0:
            return await self.remove_item(item_id)

        if not self._cart_id:
            await self.get_or_read_cart()

        url = self._get_cart_url(f"/items/{item_id}")
        payload = {"desiredQuantity": quantity}

        try:
            response = await self._client.patch(
                url,
                json=payload,
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise AuchanCartError(f"Échec de la mise à jour de quantité pour {item_id}: {exc}") from exc

        self._raise_for_status(response, f"la mise à jour de quantité pour {item_id}")
        if response.content:
            try:
                state = parse_auchan_cart_response(response.json())
                if state.cart_id:
                    self._cart_id = state.cart_id
                return state
            except Exception:
                pass
        return await self.get_or_read_cart()

    async def remove_item(self, item_id: str) -> AuchanCartState:
        if not self._cart_id:
            await self.get_or_read_cart()

        url = self._get_cart_url(f"/items/{item_id}")
        try:
            response = await self._client.delete(
                url,
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise AuchanCartError(f"Échec de la suppression du produit {item_id}: {exc}") from exc

        self._raise_for_status(response, f"la suppression du produit {item_id}")
        if response.content:
            try:
                state = parse_auchan_cart_response(response.json())
                if state.cart_id:
                    self._cart_id = state.cart_id
                return state
            except Exception:
                pass
        return await self.get_or_read_cart()

    async def clear_cart(self) -> None:
        if not self._cart_id:
            try:
                await self.get_or_read_cart()
            except Exception:
                pass

        url = self._get_cart_url()
        params: dict[str, str] = {}
        if self._consent_id:
            params["consentId"] = self._consent_id

        try:
            response = await self._client.delete(
                url,
                params=params,
                headers=_DEFAULT_HEADERS,
            )
        except Exception as exc:
            raise AuchanCartError(f"Échec du vidage du panier Auchan: {exc}") from exc

        self._raise_for_status(response, "le vidage du panier")


def build_auchan_cart_client(
    cookies: list[dict[str, Any]],
    consent_id: str | None = None,
    seller_id: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AuchanCartClient:
    # Best effort extraction of consentId and sellerId if not explicitly provided
    if not consent_id:
        for cookie in cookies:
            name = cookie.get("name") or ""
            val = cookie.get("value") or ""
            if name in ("lark-consentId", "consentId", "lark-consent-id"):
                consent_id = val
                break
        if not consent_id:
            for cookie in cookies:
                name = (cookie.get("name") or "").lower()
                val = cookie.get("value") or ""
                if "consent" in name and _UUID_RE.search(val):
                    match = _UUID_RE.search(val)
                    if match:
                        consent_id = match.group(0)
                        break

    if not seller_id:
        for cookie in cookies:
            name = (cookie.get("name") or "").lower()
            val = cookie.get("value") or ""
            if "seller" in name or name == "lark-journey":
                seller_id = val
                break

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
        cookie_jar = build_auchan_cookie_jar(cookies)
        client = httpx.AsyncClient(
            cookies=cookie_jar,
            transport=transport,
            timeout=15.0,
        )
    return AuchanCartClient(client, consent_id=consent_id, seller_id=seller_id)
