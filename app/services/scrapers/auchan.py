from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

# Auchan serves search as server-rendered HTML at /recherche?text={query}.
# Product cards are `<article class="product-thumbnail" data-id="{uuid}">`
# carrying name (itemprop name description), brand (itemprop brand), packaging
# (product-attribute), image (meta itemprop=image) and the product URL.
#
# The PRICE is NOT in the search HTML: it is lazy-loaded via a "Afficher le
# prix" button that calls
#   GET api.auchan.fr/xsell/v0/cross-sell/availability/{productId}?activeContexts=GROCERY--{sellerId}__PICK_UP
# with the selected store context. Without a store context, no price is shown.
# This scraper therefore returns products without price; wiring the price
# requires persisting the selected store context (see docs).
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


def get_auchan_proxy_url() -> str | None:
    for key in ("ADAMHUB_AUCHAN_PROXY_URL", "AUCHAN_PROXY_URL"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return _normalize_proxy_url(value)
    return None


def _normalize_proxy_url(proxy_url: str) -> str:
    normalized = proxy_url.strip()
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    return normalized


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


def parse_auchan_search_html(html: str, max_results: int) -> list[dict[str, str | None]]:
    """Parse product cards out of a `/recherche` response page."""
    soup = BeautifulSoup(html, "html.parser")

    results: dict[str, dict[str, str | None]] = {}
    for article in soup.find_all("article", class_="product-thumbnail"):
        product_id = article.get("data-id")
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

        if not name:
            continue
        key = product_id or name
        if key in results:
            continue
        results[key] = {
            "id": product_id,
            "name": name,
            "brand": brand,
            "category": None,
            "packaging": packaging,
            "price": None,  # lazy-loaded; not present in the search HTML
            "image": image,
            "product_url": product_url,
        }
        if len(results) >= max_results:
            break
    return list(results.values())


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


def _raise_for_auth(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise AuchanAuthError(
            "Auchan rejected the current session. "
            "Refresh `data/cookies_auchan.json` from a logged-in browser session "
            "with a store selected."
        )


async def search_auchan(
    queries: list[str],
    max_results: int = 30,
    sort_by: str | None = None,
    promotions_only: bool = False,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    """Search Auchan by scraping `/recherche` and parsing product cards.

    Returns products without price (the price is lazy-loaded per product and
    requires a selected store context). ``promotions_only`` is accepted for
    interface parity and ignored (Auchan has no such query flag).
    """
    del promotions_only
    if cookies is None:
        cookies = load_auchan_cookies()
    if not cookies:
        raise AuchanAuthError(
            "No Auchan cookies on disk. Provide `data/cookies_auchan.json` "
            "exported from a logged-in browser session with a store selected."
        )

    sort_key = AUCHAN_SORT_KEYS.get(sort_by) if sort_by else None

    proxy_url = get_auchan_proxy_url()
    results: dict[str, list[dict[str, str | None]]] = {}
    async with httpx.AsyncClient(
        cookies=build_auchan_cookie_jar(cookies),
        proxy=proxy_url,
        timeout=httpx.Timeout(30.0),
        trust_env=not proxy_url,
        follow_redirects=True,
    ) as client:
        for query in queries:
            params: dict[str, Any] = {"text": query}
            if sort_key:
                params["sort"] = sort_key
            response = await client.get(
                f"{AUCHAN_BASE_URL}/recherche",
                params=params,
                headers=_build_headers(f"{AUCHAN_BASE_URL}/"),
            )
            _raise_for_auth(response)
            response.raise_for_status()
            results[query] = parse_auchan_search_html(
                response.text, max_results=max_results
            )
    return results
