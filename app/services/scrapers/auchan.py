from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.services.scrapers.proxy_session import ProxySession

# Auchan serves search as server-rendered HTML at /recherche?text={query}.
# Product cards are `<article class="product-thumbnail" data-id="{uuid}">`
# carrying name (itemprop name description), brand (itemprop brand), packaging
# (product-attribute), image (meta itemprop=image) and the product URL.
#
# The PRICE is rendered server-side inside the card's ``itemprop="offers"``
# block ONLY when a store context is selected for the session; without one the
# card shows a "Afficher le prix" button instead. Store context is selected via
# POST /journey/update and the search page reads it back from a ``lark-journey``
# cookie carrying the journey id. This flow works WITHOUT login (any valid
# session cookie, see data/live-capture/auchan-paslogin.har); the cart
# endpoints (checkout/v1/carts + consentId) are out of scope.
#
# Wiring the price therefore requires (1) persisting the selected store and
# (2) applying it to the live session before scraping: ``search_auchan`` takes
# an optional ``AuchanStoreContext`` and re-applies it (journey/update +
# lark-journey cookie) whenever the session's current journey does not match.
AUCHAN_BASE_URL = "https://www.auchan.fr"
AUCHAN_COOKIES_PATH = Path(__file__).resolve().parents[3] / "data" / "cookies_auchan.json"

# `sort` query param values observed in the wild.
AUCHAN_SORT_KEYS = {
    "default": None,
    "price_asc": "asc_price_pos",
    "price_desc": "desc_price_pos",
    "unit_price_asc": "asc_unitprice_pos",
    "unit_price_desc": "desc_unitprice_pos",
    "discount_desc": "desc_discountpercent_pos",
    "rating_desc": "desc_averageoverallrating",
}


class AuchanAuthError(RuntimeError):
    """Cookies are missing or rejected by Auchan."""


class AuchanStoreSelectionError(ValueError):
    """No store context selected (or selectable) for the Auchan session."""


@dataclass(frozen=True, slots=True)
class AuchanStoreContext:
    """A selected Auchan store, as carried by POST /journey/update.

    ``seller_id`` is the GROCERY context's seller UUID (e.g.
    ``4c663296-54a8-45f6-b385-0be86b4dfe98``); ``store_reference`` is the
    ``storeReference`` id (e.g. ``6007``). The address/location fields feed the
    journey update payload and default to the reference capture (Toulouse).
    """

    seller_id: str
    store_reference: str
    channel: str = "PICK_UP"
    zipcode: str | None = None
    city: str | None = None
    country: str | None = "France"
    latitude: float | None = None
    longitude: float | None = None


def _journey_update_payload(context: AuchanStoreContext, journey_id: str) -> dict[str, str]:
    """Compose the form-urlencoded payload for POST /journey/update."""
    payload: dict[str, str] = {
        "offeringContext.seller.id": context.seller_id,
        "offeringContext.channels[0]": context.channel,
        "offeringContext.storeReference": context.store_reference,
        "address.zipcode": context.zipcode or "",
        "address.city": context.city or "",
        "address.country": context.country or "France",
        "location.latitude": str(context.latitude or ""),
        "location.longitude": str(context.longitude or ""),
        "accuracy": "MUNICIPALITY",
        "position": "1",
        "journeyId": journey_id,
    }
    return payload


def load_auchan_cookies(path: Path | None = None) -> list[dict[str, Any]]:
    cookies_path = path or AUCHAN_COOKIES_PATH
    if not cookies_path.exists():
        return []

    with cookies_path.open("r", encoding="utf-8") as handle:
        raw_cookies = json.load(handle)

    normalized: list[dict[str, Any]] = []
    for raw in raw_cookies:
        cookie: dict[str, Any] = {
            key: raw[key]
            for key in ("name", "value", "domain", "path", "httpOnly", "secure", "sameSite", "url")
            if key in raw
        }

        expiration = raw.get("expires") if raw.get("expires") is not None else raw.get("expirationDate")
        if expiration is not None:
            cookie["expires"] = int(expiration)

        same_site = cookie.get("sameSite")
        if same_site == "lax":
            cookie["sameSite"] = "Lax"
        elif same_site == "strict":
            cookie["sameSite"] = "Strict"
        elif same_site in {"none", "no_restriction"}:
            cookie["sameSite"] = "None"
        elif same_site is None and "sameSite" in cookie:
            del cookie["sameSite"]

        normalized.append(cookie)
    return normalized


def build_auchan_cookie_jar(cookies: list[dict[str, Any]]) -> httpx.Cookies:
    jar = httpx.Cookies()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        jar.set(name, value, domain=cookie.get("domain"), path=cookie.get("path", "/"))
    return jar


def _format_price(amount: str, currency: str) -> str | None:
    """Format a schema.org Offer price + currency into a French price string."""
    if not amount:
        return None
    amount = amount.strip().replace(".", ",")
    symbol = "€" if currency in {"EUR", "eur", "€"} else currency
    return f"{amount} {symbol}".strip()


def parse_auchan_search_html(html: str, max_results: int) -> list[dict[str, str | None]]:
    """Parse product cards out of a `/recherche` response page.

    With a store context selected the price is rendered server-side inside the
    card's ``itemprop="offers"`` block (``meta itemprop="price"`` +
    ``meta itemprop="priceCurrency"``); without a store it is absent and left
    as ``None``. The cart identifiers (``offer_id``, ``seller_id``) are exposed
    from the card's data attributes for the add-to-cart flow.
    """
    soup = BeautifulSoup(html, "html.parser")

    results: dict[str, dict[str, str | None]] = {}
    for article in soup.find_all("article", class_="product-thumbnail"):
        product_id = article.get("data-id")
        offer_id = article.get("data-current-offer-id")
        link = article.find("a", class_="product-thumbnail__details-wrapper")
        product_url = link.get("href") if link else None
        if product_url and product_url.startswith("/"):
            product_url = f"{AUCHAN_BASE_URL}{product_url}"

        description = article.find("p", class_="product-thumbnail__description")
        name = None
        brand = None
        if description:
            brand_el = description.find("strong", itemprop="brand")
            if brand_el:
                brand = (brand_el.get_text(strip=True) or None)
            # name = description text minus the brand prefix.
            full = description.get_text(" ", strip=True)
            if brand and full.startswith(brand):
                name = full[len(brand):].strip() or None
            else:
                name = full or None

        packaging = None
        attrs = article.find("div", class_="product-thumbnail__attributes")
        if attrs:
            spans = [s.get_text(strip=True) for s in attrs.find_all("span", class_="product-attribute")]
            packaging = " · ".join(spans) or None

        image = None
        image_meta = article.find("meta", itemprop="image")
        if image_meta:
            image = image_meta.get("content")

        price = None
        offer_block = article.find("div", itemprop="offers")
        if offer_block:
            price_meta = offer_block.find("meta", itemprop="price")
            currency_meta = offer_block.find("meta", itemprop="priceCurrency")
            if price_meta and price_meta.get("content"):
                price = _format_price(
                    price_meta["content"],
                    currency_meta.get("content", "EUR") if currency_meta else "EUR",
                )

        seller_id = None
        qty = article.find("div", class_="quantity-selector")
        if qty:
            seller_id = qty.get("data-seller-id")

        if not name:
            continue
        key = product_id or name
        if key in results:
            continue
        results[key] = {
            "id": product_id,
            "offer_id": offer_id,
            "seller_id": seller_id,
            "name": name,
            "brand": brand,
            "category": None,
            "packaging": packaging,
            "price": price,
            "image": image,
            "product_url": product_url,
            "store": "Auchan",
        }
        if len(results) >= max_results:
            break
    return list(results.values())


def parse_auchan_offering_contexts(html: str) -> list[dict[str, str | None]]:
    """Parse the store cards of a `/offering-contexts` response page.

    Each store is a ``div.journey-offering-context__wrapper`` carrying a
    ``form.journey-offering-contexts__form.journeyChoice`` whose hidden inputs
    expose the ``sellerId`` / ``storeReference`` / ``channels`` that feed
    ``POST /journey/update``, plus human-facing name/address/distance.
    """
    soup = BeautifulSoup(html, "html.parser")
    contexts: list[dict[str, str | None]] = []
    for wrapper in soup.find_all("div", class_="journey-offering-context__wrapper"):
        pos_id = wrapper.get("data-id")
        pos_type = wrapper.get("data-type")

        form = wrapper.find("form", class_="journey-offering-contexts__form")
        seller_id = None
        store_reference = None
        channel = None
        if form:
            seller_id = form.find("input", attrs={"name": "sellerId"})
            store_reference = form.find("input", attrs={"name": "storeReference"})
            channel = form.find("input", attrs={"name": "channels"})
            seller_id = seller_id.get("value") if seller_id else None
            store_reference = store_reference.get("value") if store_reference else None
            channel = channel.get("value") if channel else None
        if not seller_id:
            continue

        name_el = wrapper.find("span", class_="place-pos__name")
        address_el = wrapper.find("div", class_="place-pos__address")
        distance_el = wrapper.find("div", class_="journey-offering-context__pos-distance")

        contexts.append(
            {
                "pos_id": pos_id,
                "pos_type": pos_type,
                "seller_id": seller_id,
                "store_reference": store_reference,
                "channel": channel,
                "name": name_el.get_text(" ", strip=True) if name_el else None,
                "address": address_el.get_text(" ", strip=True) if address_el else None,
                "distance": distance_el.get_text(" ", strip=True) if distance_el else None,
            }
        )
    return contexts


_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)


def _build_headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": _CHROME_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr,en;q=0.9",
        "Referer": referer,
    }


def _build_json_headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": _CHROME_USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "fr,en;q=0.9",
        "Referer": referer,
        "x-requested-with": "XMLHttpRequest",
    }


def _build_client(cookies: list[dict[str, Any]], proxy_url: str | None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        cookies=build_auchan_cookie_jar(cookies),
        proxy=proxy_url,
        timeout=httpx.Timeout(30.0),
        trust_env=not proxy_url,
        follow_redirects=True,
    )


def _raise_for_auth(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise AuchanAuthError(
            "Auchan rejected the current session. "
            "Refresh `data/cookies_auchan.json` from a non-expired browser session."
        )


def _journey_grocery_seller(journey: dict[str, Any]) -> str | None:
    """Return the GROCERY context's seller id from a /journey response."""
    for context in journey.get("activeContexts") or []:
        if context.get("type") != "GROCERY":
            continue
        inner = context.get("context") or {}
        seller = inner.get("seller") or {}
        return seller.get("id")
    return None


async def get_auchan_journey(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    """Fetch the current journey (selected store context) for the session."""
    if not cookies:
        raise AuchanAuthError("No Auchan cookies on disk.")
    scope = "auchan:journey"
    session = ProxySession(scope, lambda proxy_url: _build_client(cookies, proxy_url))
    try:
        response = await session.client.get(
            f"{AUCHAN_BASE_URL}/journey",
            headers=_build_json_headers(f"{AUCHAN_BASE_URL}/"),
        )
        _raise_for_auth(response)
        response.raise_for_status()
        payload = response.json()
        session.release(ok=True)
        return payload
    except Exception:
        session.release(ok=False)
        raise
    finally:
        await session.aclose()


async def select_auchan_store(
    context: AuchanStoreContext,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Select the store in the live session via POST /journey/update.

    Returns the updated journey JSON. The session keeps the store context
    server-side; ``search_auchan`` re-applies it when needed.
    """
    if cookies is None:
        cookies = load_auchan_cookies()
    if not cookies:
        raise AuchanAuthError("No Auchan cookies on disk.")
    scope = "auchan:select-store"
    session = ProxySession(scope, lambda proxy_url: _build_client(cookies, proxy_url))
    try:
        result = await _apply_auchan_store_context(session.client, context)
        session.release(ok=True)
        return result
    except Exception:
        session.release(ok=False)
        raise
    finally:
        await session.aclose()


async def _apply_auchan_store_context(
    client: httpx.AsyncClient,
    context: AuchanStoreContext,
) -> dict[str, Any]:
    """Ensure the session has ``context`` selected and the lark-journey cookie set.

    The search SSR reads the selected store from the ``lark-journey`` cookie
    (a journey id the browser stores after a successful /journey/update), so the
    journey update alone is not enough for server-rendered prices.
    """
    journey_response = await client.get(
        f"{AUCHAN_BASE_URL}/journey",
        headers=_build_json_headers(f"{AUCHAN_BASE_URL}/"),
    )
    _raise_for_auth(journey_response)
    journey_response.raise_for_status()
    current_journey = journey_response.json()

    if _journey_grocery_seller(current_journey) == context.seller_id:
        journey = current_journey
    else:
        journey_id = current_journey.get("id")
        if not journey_id:
            raise AuchanStoreSelectionError(
                "Could not read the current journey id from /journey."
            )
        update_response = await client.post(
            f"{AUCHAN_BASE_URL}/journey/update",
            data=_journey_update_payload(context, journey_id),
            headers=_build_json_headers(f"{AUCHAN_BASE_URL}/"),
        )
        _raise_for_auth(update_response)
        update_response.raise_for_status()
        journey = update_response.json()

    journey_id = journey.get("id")
    if journey_id:
        client.cookies.set("lark-journey", journey_id, domain="www.auchan.fr", path="/")
        client.cookies.set("lark-history", "true", domain="www.auchan.fr", path="/")
    return journey


async def list_auchan_offering_contexts(
    *,
    zipcode: str,
    city: str,
    latitude: float,
    longitude: float,
    country: str = "France",
    cookies: list[dict[str, Any]] | None = None,
) -> list[dict[str, str | None]]:
    """List selectable store contexts (GET /offering-contexts) for an address."""
    if cookies is None:
        cookies = load_auchan_cookies()
    if not cookies:
        raise AuchanAuthError("No Auchan cookies on disk.")

    params: dict[str, str] = {
        "address.zipcode": zipcode,
        "address.city": city,
        "address.country": country,
        "location.latitude": str(latitude),
        "location.longitude": str(longitude),
        "accuracy": "MUNICIPALITY",
        "position": "1",
        "sellerType": "GROCERY",
        "filters.pos": "",
        "filters.slots": "",
        "filters.validStoreReferences": "",
        "channels": "PICK_UP,SHIPPING",
    }
    headers = {
        **_build_json_headers(f"{AUCHAN_BASE_URL}/"),
        "Accept": "application/crest",
        "x-crest-renderer": "journey-renderer",
    }
    scope = f"auchan:offering-contexts:{zipcode}"
    session = ProxySession(scope, lambda proxy_url: _build_client(cookies, proxy_url))
    try:
        response = await session.client.get(
            f"{AUCHAN_BASE_URL}/offering-contexts",
            params=params,
            headers=headers,
        )
        _raise_for_auth(response)
        response.raise_for_status()
        payload = parse_auchan_offering_contexts(response.text)
        session.release(ok=True)
        return payload
    except Exception:
        session.release(ok=False)
        raise
    finally:
        await session.aclose()


async def search_auchan(
    queries: list[str],
    max_results: int = 30,
    sort_by: str | None = None,
    promotions_only: bool = False,
    cookies: list[dict[str, Any]] | None = None,
    store_selection: AuchanStoreContext | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    """Search Auchan by scraping `/recherche` and parsing product cards.

    Prices are rendered in the HTML only when a store context is selected for
    the session. When ``store_selection`` is provided it is applied to the
    session first (POST /journey/update + ``lark-journey`` cookie) so the
    returned products carry prices. ``promotions_only`` is accepted for
    interface parity and ignored (Auchan has no such query flag).
    """
    del promotions_only
    if cookies is None:
        cookies = load_auchan_cookies()
    if not cookies:
        raise AuchanAuthError(
            "No Auchan cookies on disk. Provide `data/cookies_auchan.json` "
            "exported from a valid browser session."
        )

    sort_key = AUCHAN_SORT_KEYS.get(sort_by) if sort_by else None

    scope = f"auchan:{json.dumps(queries, ensure_ascii=False)}"
    session = ProxySession(scope, lambda proxy_url: _build_client(cookies, proxy_url))
    results: dict[str, list[dict[str, str | None]]] = {}
    try:
        if store_selection is not None:
            await _apply_auchan_store_context(session.client, store_selection)
        for query in queries:
            params: dict[str, Any] = {"text": query}
            if sort_key:
                params["sort"] = sort_key
            response = await session.client.get(
                f"{AUCHAN_BASE_URL}/recherche",
                params=params,
                headers=_build_headers(f"{AUCHAN_BASE_URL}/"),
            )
            _raise_for_auth(response)
            response.raise_for_status()
            results[query] = parse_auchan_search_html(
                response.text, max_results=max_results
            )
        session.release(ok=True)
    except Exception:
        session.release(ok=False)
        raise
    finally:
        await session.aclose()
    return results
