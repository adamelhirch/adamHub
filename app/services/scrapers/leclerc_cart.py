"""Leclerc Drive cart adapter.

Communicates with Leclerc Drive's panier.aspx endpoint using form-urlencoded
JSON payloads.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from html import unescape
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
from app.services.scrapers.leclerc import (
    _resolve_store_base_url,
    build_leclerc_cookie_jar,
)

_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_PANIER_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "user-agent": _CHROME_USER_AGENT,
    "x-requested-with": "XMLHttpRequest",
    "zcwb": "ajax-manager",
}


class LeclercCartError(SupermarketCartError):
    """Base error for Leclerc Drive cart adapter."""


class LeclercCartAuthError(SupermarketCartAuthError, LeclercCartError):
    """Session expired or cookies rejected by Leclerc Drive."""


class LeclercCartStoreContextError(SupermarketCartStoreContextError, LeclercCartError):
    """Store Drive base URL or point de livraison missing."""


class LeclercCartNotFoundError(SupermarketCartNotFoundError, LeclercCartError):
    """Cart or item not found on Leclerc Drive."""


@dataclass(frozen=True, slots=True)
class LeclercCartItem:
    id: str
    item_id: str
    name: str
    quantity: int
    price: float | None
    price_text: str | None
    image: str | None


@dataclass(frozen=True, slots=True)
class LeclercCartState:
    store_id: str
    amount: float
    items_count: int
    items: tuple[LeclercCartItem, ...]
    raw_payload: dict = field(repr=False, compare=False, default_factory=dict)


def extract_plid_from_url(base_url: str) -> str:
    match = re.search(r"magasin-(\d+)", base_url)
    if match:
        return match.group(1)
    return "123111"


def parse_leclerc_cart_response(payload: dict[str, Any]) -> LeclercCartState:
    panier = payload.get("objPanier") or payload
    store_id = str(panier.get("sNoPointLivraison") or "")
    amount = float(panier.get("nrMontantTotalTTC") or panier.get("total") or 0.0)

    raw_items = panier.get("lstLignes") or panier.get("items") or []
    items: list[LeclercCartItem] = []
    for raw in raw_items:
        line_id = str(raw.get("iIdLigne") or raw.get("id") or "")
        product_id = str(raw.get("iIdProduit") or raw.get("productId") or line_id)
        name = str(raw.get("sLibelle") or raw.get("name") or "Article Leclerc")
        qty = int(raw.get("iQuantite") or raw.get("quantity") or 0)
        price_val = raw.get("nrPrixUnitaireTTC") or raw.get("price")
        price = float(price_val) if price_val is not None else None
        price_text = f"{price:.2f} €" if price is not None else None
        image = raw.get("sUrlVignette") or raw.get("image")

        if qty > 0:
            items.append(
                LeclercCartItem(
                    id=line_id,
                    item_id=product_id,
                    name=name,
                    quantity=qty,
                    price=price,
                    price_text=price_text,
                    image=image,
                )
            )

    items_count = int(panier.get("iNombreArticles") or len(items))
    return LeclercCartState(
        store_id=store_id,
        amount=amount,
        items_count=items_count,
        items=tuple(items),
        raw_payload=payload,
    )


def parse_leclerc_detail_panier_html(html: str, plid: str = "") -> LeclercCartState:
    match = re.search(
        r"initOptions\([\"'][^\"']*ucDetailPanier_pnlDetailPanier[\"']\s*,\s*(\{.*?\})\);",
        html,
        re.DOTALL,
    )
    if not match:
        return LeclercCartState(store_id=plid, amount=0.0, items_count=0, items=())

    try:
        data = json.loads(match.group(1))
    except Exception:
        return LeclercCartState(store_id=plid, amount=0.0, items_count=0, items=())

    obj_contenu = data.get("objContenu", {})
    lst_elements = obj_contenu.get("lstElements", [])
    total = 0.0
    items_count = 0
    if lst_elements and isinstance(lst_elements, list):
        obj_elem = lst_elements[0].get("objElement", {})
        total_str = str(obj_elem.get("sTotalAPayer") or "0")
        m_tot = re.search(r"([0-9]+[,\.][0-9]+)", total_str)
        if m_tot:
            total = float(m_tot.group(1).replace(",", "."))
        items_count = int(obj_elem.get("iQuantitePanier", 0))

    def find_products(obj: Any) -> list[dict[str, Any]]:
        prods: list[dict[str, Any]] = []
        if isinstance(obj, dict):
            if obj.get("sType") == "Produit" and "iIdProduit" in obj:
                prods.append(obj)
            for v in obj.values():
                prods.extend(find_products(v))
        elif isinstance(obj, list):
            for v in obj:
                prods.extend(find_products(v))
        return prods

    items: list[LeclercCartItem] = []
    seen_ids: set[str] = set()
    for p in find_products(data):
        pid = str(p.get("iIdProduit") or p.get("sId") or "")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        name1 = unescape(str(p.get("sLibelleLigne1") or ""))
        name2 = unescape(str(p.get("sLibelleLigne2") or ""))
        name = f"{name1} {name2}".strip() or "Article Leclerc"
        qty = int(p.get("iQuantitePanier") or p.get("iQtePanier") or 1)
        price_val = p.get("nrPVUnitaireTTC") or p.get("price")
        price = float(price_val) if price_val is not None else None
        price_text = p.get("sPrixUnitaire") or (f"{price:.2f} €" if price is not None else None)
        image = p.get("sUrlVignetteProduit")
        items.append(
            LeclercCartItem(
                id=pid,
                item_id=pid,
                name=name,
                quantity=qty,
                price=price,
                price_text=price_text,
                image=image,
            )
        )

    if items_count == 0 and items:
        items_count = sum(it.quantity for it in items)

    return LeclercCartState(
        store_id=plid,
        amount=total,
        items_count=items_count,
        items=tuple(items),
        raw_payload=data,
    )


class LeclercCartClient:
    def __init__(self, http_client: Any, base_url: str, plid: str | None = None):
        self._client = http_client
        self._base_url = base_url.rstrip("/")
        self._plid = plid or extract_plid_from_url(self._base_url)

        parsed = urllib.parse.urlparse(self._base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
        if origin:
            self._ajax_cart_url = f"{origin}/magasin-{self._plid}/panier.aspx"
        else:
            self._ajax_cart_url = f"{self._base_url}/panier.aspx"

        self._detail_url = f"{self._base_url}/detail-panier.aspx"
        self._referer = f"{self._base_url}.aspx" if not self._base_url.endswith(".aspx") else self._base_url

    async def aclose(self) -> None:
        if hasattr(self._client, "close"):
            await self._client.close()
        elif hasattr(self._client, "aclose"):
            await self._client.aclose()

    def _raise_for_status(self, response: Any, action_desc: str) -> None:
        body = getattr(response, "text", "") or ""
        status = getattr(response, "status_code", 0)
        headers = getattr(response, "headers", {}) or {}

        is_datadome_challenge = status in (401, 403) and (
            "datadome" in body.lower()[:4000]
            or "var dd=" in body
            or "Please enable JS" in body[:500]
            or headers.get("x-datadome-response") is not None
            or str(headers.get("x-datadome", "")).lower() == "blocked"
        )
        if status in (401, 403) or is_datadome_challenge:
            raise LeclercCartAuthError(
                f"Session Leclerc expirée ou bloquée par l'anti-bot DataDome (HTTP {status}) lors de {action_desc}. "
                "Ré-importe tes cookies via l'extension depuis un onglet Leclerc actif."
            )
        if status == 404:
            raise LeclercCartNotFoundError(f"Panier ou article Leclerc introuvable lors de {action_desc}.")
        if status >= 400:
            raise LeclercCartError(f"Erreur Leclerc {status} lors de {action_desc}: {body[:200]}")

    async def _post_panier(self, data_dict: dict[str, Any], query_op: str | None = None) -> Any:
        url = self._ajax_cart_url
        if query_op:
            url += f"?op={query_op}"
        encoded_payload = urllib.parse.urlencode({"d": json.dumps(data_dict)})
        headers = {**_PANIER_HEADERS, "referer": self._referer}
        try:
            if isinstance(self._client, httpx.AsyncClient):
                response = await self._client.post(url, content=encoded_payload, headers=headers)
            else:
                response = await self._client.post(url, data=encoded_payload, headers=headers)
        except Exception as exc:
            raise LeclercCartError(f"Échec de connexion au panier Leclerc: {exc}") from exc
        self._raise_for_status(response, "l'opération panier")
        try:
            return response.json()
        except Exception:
            return {}

    async def get_or_read_cart(self) -> LeclercCartState:
        data = await self._post_panier({"sNoPointLivraison": self._plid}, query_op="12")
        if isinstance(data, dict) and ("objPanier" in data or "items" in data or "lstLignes" in data):
            return parse_leclerc_cart_response(data)

        elem: dict[str, Any] = {}
        if isinstance(data, list):
            for entry in data:
                obj = entry.get("objElement") if isinstance(entry, dict) else None
                if isinstance(obj, dict) and (obj.get("sType") == "Panier" or str(obj.get("sNoPointLivraison")) == self._plid):
                    elem = obj
                    break
            if not elem and data and isinstance(data[0], dict):
                elem = data[0].get("objElement", {})

        is_empty = elem.get("fEstVide", True) if elem else True
        prods_light = elem.get("lstProduitsLight", []) if elem else []
        if is_empty or not prods_light:
            return LeclercCartState(
                store_id=self._plid,
                amount=0.0,
                items_count=0,
                items=(),
                raw_payload={"op12": data},
            )

        try:
            headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "user-agent": _CHROME_USER_AGENT,
                "referer": self._referer,
            }
            if isinstance(self._client, httpx.AsyncClient):
                resp = await self._client.get(self._detail_url, headers=headers)
            else:
                resp = await self._client.get(self._detail_url, headers=headers)
            self._raise_for_status(resp, "la récupération du détail panier")
            detailed = parse_leclerc_detail_panier_html(resp.text, plid=self._plid)
            if detailed.items:
                return detailed
        except Exception:
            pass

        total_str = str(elem.get("sTotalAPayer") or "0")
        m_tot = re.search(r"([0-9]+[,\.][0-9]+)", total_str)
        amount = float(m_tot.group(1).replace(",", ".")) if m_tot else 0.0
        fallback_items: list[LeclercCartItem] = []
        for p in prods_light:
            pid = str(p.get("iIdProduit") or "")
            qty = int(p.get("iQtePanier") or 1)
            pr = float(p.get("rTotalAPayer") or 0.0)
            fallback_items.append(
                LeclercCartItem(
                    id=pid,
                    item_id=pid,
                    name=f"Article Leclerc {pid}",
                    quantity=qty,
                    price=pr,
                    price_text=f"{pr:.2f} €",
                    image=None,
                )
            )
        return LeclercCartState(
            store_id=self._plid,
            amount=amount,
            items_count=int(elem.get("iQuantitePanier") or len(fallback_items)),
            items=tuple(fallback_items),
            raw_payload={"op12": data},
        )

    async def add_item(self, item_id: str, quantity: int = 1) -> LeclercCartState:
        payload = {
            "eTypeAction": 1,
            "iIdProduit": str(item_id),
            "iQuantite": quantity,
            "sNoPointLivraison": self._plid,
        }
        data = await self._post_panier(payload, query_op="1")
        if isinstance(data, dict) and ("objPanier" in data or "items" in data):
            return parse_leclerc_cart_response(data)
        return await self.get_or_read_cart()

    async def update_item_quantity(self, item_id: str, quantity: int) -> LeclercCartState:
        if quantity <= 0:
            return await self.remove_item(item_id)
        payload = {
            "eTypeAction": 2,
            "iIdProduit": str(item_id),
            "iQuantite": quantity,
            "sNoPointLivraison": self._plid,
        }
        data = await self._post_panier(payload, query_op="1")
        if isinstance(data, dict) and ("objPanier" in data or "items" in data):
            return parse_leclerc_cart_response(data)
        return await self.get_or_read_cart()

    async def remove_item(self, item_id: str) -> LeclercCartState:
        payload = {
            "eTypeAction": 2,
            "iIdProduit": str(item_id),
            "iQuantite": 0,
            "sNoPointLivraison": self._plid,
        }
        data = await self._post_panier(payload, query_op="1")
        if isinstance(data, dict) and ("objPanier" in data or "items" in data):
            return parse_leclerc_cart_response(data)
        return await self.get_or_read_cart()

    async def clear_cart(self) -> None:
        await self._post_panier({"sNoPointLivraison": self._plid}, query_op="3")


def build_leclerc_cart_client(
    cookies: list[dict[str, Any]],
    store_base_url: str | None = None,
    base_url: str | None = None,
    plid: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LeclercCartClient:
    effective_url = base_url or store_base_url
    try:
        resolved_url = _resolve_store_base_url(effective_url, cookies=cookies)
    except Exception as exc:
        raise LeclercCartStoreContextError(str(exc)) from exc

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
        cookie_jar = build_leclerc_cookie_jar(cookies)
        client = httpx.AsyncClient(
            cookies=cookie_jar,
            transport=transport,
            timeout=15.0,
        )
    return LeclercCartClient(client, resolved_url, plid=plid)
