from __future__ import annotations

import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup


CARREFOUR_BASE_URL = "https://www.carrefour.fr"
CARREFOUR_COOKIES_PATH = Path(__file__).resolve().parents[3] / "data" / "cookies_carrefour.json"

DEFAULT_IMAGE_FORMAT = "200x200"

# Inferred from `attributes.flags` and `attributes.topCategoryName` when present.
FLAG_CATEGORY_HINTS: dict[str, str] = {
    "flag.common.organic": "Bio",
    "flag.common.fresh": "Frais",
    "flag.common.frozen": "Surgelés",
    "flag.common.local": "Local",
    "flag.common.eco": "Éco-responsable",
}


class CarrefourAuthError(RuntimeError):
    """Cookies are missing or rejected by Carrefour."""


def get_carrefour_proxy_url() -> str | None:
    for key in ("ADAMHUB_CARREFOUR_PROXY_URL", "CARREFOUR_PROXY_URL"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return _normalize_proxy_url(value)
    return None


def _normalize_proxy_url(proxy_url: str) -> str:
    normalized = proxy_url.strip()
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    return normalized


def load_carrefour_cookies(path: Path | None = None) -> list[dict[str, Any]]:
    cookies_path = path or CARREFOUR_COOKIES_PATH
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


def build_carrefour_cookie_jar(cookies: list[dict[str, Any]]) -> httpx.Cookies:
    jar = httpx.Cookies()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        jar.set(name, value, domain=cookie.get("domain"), path=cookie.get("path", "/"))
    return jar


def _resolve_image_url(images: dict[str, Any] | None, fmt: str = DEFAULT_IMAGE_FORMAT) -> str | None:
    if not isinstance(images, dict):
        return None
    paths = images.get("paths") or []
    if not paths:
        return None
    raw = paths[0]
    if not isinstance(raw, str):
        return None
    return raw.replace("FORMAT", fmt)


def _resolve_category(attributes: dict[str, Any]) -> str | None:
    top = attributes.get("topCategoryName")
    if isinstance(top, str) and top.strip():
        return top.strip()
    flags = attributes.get("flags") or []
    if isinstance(flags, list):
        for flag in flags:
            label = FLAG_CATEGORY_HINTS.get(flag)
            if label:
                return label
    return None


def _resolve_offer(attributes: dict[str, Any]) -> dict[str, Any] | None:
    """Return the canonical Carrefour offer (skipping marketplace sellers)."""
    offers_map = attributes.get("offers") or {}
    if not isinstance(offers_map, dict):
        return None
    for ean_offers in offers_map.values():
        if not isinstance(ean_offers, dict):
            continue
        for offer in ean_offers.values():
            if not isinstance(offer, dict):
                continue
            sub_type = (offer.get("subType") or "").lower()
            attrs = offer.get("attributes") or {}
            availability = attrs.get("availability") or {}
            if sub_type == "carrefour" and availability.get("purchasable", True):
                return attrs
    # Fallback: first offer (regardless of subType) so we still surface the title.
    for ean_offers in offers_map.values():
        if not isinstance(ean_offers, dict):
            continue
        for offer in ean_offers.values():
            if isinstance(offer, dict) and offer.get("attributes"):
                return offer["attributes"]
    return None


def _format_price(value: float | int | None) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return f"{value:.2f} €".replace(".", ",")


_BRAND_TAIL_RE = re.compile(r"\b([A-ZÀ-Ý][A-ZÀ-Ý0-9' &-]{2,}(?:\s+[A-ZÀ-Ý0-9' &-]+)*)\s*$")


def _extract_initial_state(html: str) -> dict[str, Any] | None:
    """Pull `window.__INITIAL_STATE__ = {...}` out of the SSR HTML.

    Returns the parsed object or None if the marker isn't present.
    """
    marker = "__INITIAL_STATE__="
    start = html.find(marker)
    if start == -1:
        return None
    start += len(marker)
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(html[start:], start=start):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start: i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _devalue(arr: list[Any], idx: int, _seen: frozenset[int] | None = None) -> Any:
    """Resolve a Devalue (Rich Harris) flat-array reference.

    Carrefour's `routeData` is serialized this way: index 0 holds the root,
    integer values inside dicts/lists are themselves indices into `arr`.
    """
    if _seen is None:
        _seen = frozenset()
    if not isinstance(idx, int) or idx < 0 or idx >= len(arr):
        return None
    if idx in _seen:
        return None
    val = arr[idx]
    if not isinstance(val, (dict, list)):
        return val
    seen = _seen | {idx}
    if isinstance(val, list):
        return [_devalue(arr, x, seen) if isinstance(x, int) else x for x in val]
    return {
        k: (_devalue(arr, v, seen) if isinstance(v, int) else v)
        for k, v in val.items()
    }


def _resolve_route_data_products(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = state.get("routeData")
    if not isinstance(raw, str) or not raw:
        return []
    try:
        flat = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(flat, list) or not flat:
        return []
    root = _devalue(flat, 0)
    if not isinstance(root, dict):
        return []
    data = root.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _resolve_attribute_price(attributes: dict[str, Any]) -> dict[str, Any] | None:
    """Find the canonical Carrefour price object inside attributes.offers.*.*.attributes.price."""
    offers_map = attributes.get("offers") or {}
    if not isinstance(offers_map, dict):
        return None
    for ean_offers in offers_map.values():
        if not isinstance(ean_offers, dict):
            continue
        for offer in ean_offers.values():
            if not isinstance(offer, dict):
                continue
            sub_type = (offer.get("subType") or "").lower()
            attrs = offer.get("attributes") or {}
            avail = attrs.get("availability") or {}
            if sub_type == "carrefour" and avail.get("purchasable", True):
                price = attrs.get("price")
                if isinstance(price, dict):
                    return price
    # Fallback: first available price even if marketplace.
    for ean_offers in offers_map.values():
        if not isinstance(ean_offers, dict):
            continue
        for offer in ean_offers.values():
            if isinstance(offer, dict):
                price = (offer.get("attributes") or {}).get("price")
                if isinstance(price, dict):
                    return price
    return None


def _format_eur(amount: float | int | None) -> str | None:
    if not isinstance(amount, (int, float)) or amount <= 0:
        return None
    return f"{amount:.2f} €".replace(".", ",")


def parse_carrefour_state_products(
    state: dict[str, Any], max_results: int
) -> list[dict[str, str | None]]:
    """Build normalized search results from the SSR routeData payload."""
    products = _resolve_route_data_products(state)
    results: dict[str, dict[str, str | None]] = {}
    for product in products:
        if not isinstance(product, dict):
            continue
        attrs = product.get("attributes") or {}
        ean = attrs.get("ean") or ""
        title = attrs.get("title") or ""
        if not ean or not title or ean in results:
            continue

        price_obj = _resolve_attribute_price(attrs) or {}
        price_text = _format_eur(price_obj.get("price"))
        per_unit_label = price_obj.get("perUnitLabel")
        if per_unit_label and price_text:
            price_text = f"{price_text} ({per_unit_label})"

        slug = attrs.get("slug") or ""
        product_url = (
            f"{CARREFOUR_BASE_URL}/p/{urllib.parse.quote(slug)}-{ean}" if slug else None
        )

        images = attrs.get("images") or {}
        image_url = None
        if isinstance(images, dict):
            paths = images.get("paths") or []
            if paths:
                first = paths[0]
                if isinstance(first, str):
                    image_url = first.replace("FORMAT", DEFAULT_IMAGE_FORMAT)

        category = attrs.get("topCategoryName") or _resolve_category(attrs)

        results[ean] = {
            "id": ean,
            "name": title,
            "brand": attrs.get("brand") or _infer_brand(title),
            "category": category,
            "packaging": attrs.get("packaging") or attrs.get("format"),
            "price": price_text,
            "image": image_url,
            "product_url": product_url,
            "store": "Carrefour",
        }
        if len(results) >= max_results:
            break
    return list(results.values())


def _infer_brand(title: str) -> str | None:
    """Carrefour titles end with the brand in uppercase (e.g. 'Lait UHT LACTEL').
    Pull out the trailing all-caps run when present.
    """
    if not title:
        return None
    cleaned = title.strip()
    m = _BRAND_TAIL_RE.search(cleaned)
    if not m:
        return None
    candidate = m.group(1).strip()
    if len(candidate) < 3 or candidate in {"BIO", "BD"}:
        return None
    return candidate


def parse_carrefour_search_html(html: str, max_results: int) -> list[dict[str, str | None]]:
    """Parse the SSR product cards from /s?q=…. Returns up to `max_results` items.

    Each <article data-testid="<EAN>"> card carries: title, slug, price, packaging.
    Brand and image are missing from the static HTML (image is lazy-loaded).
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select('article[data-testid]')
    results: dict[str, dict[str, str | None]] = {}
    for card in cards:
        ean = card.get("data-testid") or ""
        if not ean.isdigit() or ean in results:
            continue

        title_anchor = card.select_one('a[data-testid="product-card-title"]')
        if title_anchor is None:
            continue
        href = title_anchor.get("href") or ""
        title_node = title_anchor.find("h3") or title_anchor
        title = title_node.get_text(strip=True)
        if not title:
            continue

        # Price node — base price text plus a nested currency span.
        price_node = card.select_one(
            ".product-list-card-plp-grid__shimmer-base-price, "
            ".product-list-card-plp-grid__current-price, "
            ".product-list-card-plp-grid__price"
        )
        price_text: str | None = None
        if price_node is not None:
            raw = price_node.get_text(" ", strip=True)
            # "1,58 €" or "1,58€" → keep formatted FR notation
            if raw:
                # Normalize whitespace and currency.
                price_text = re.sub(r"\s+", " ", raw).strip()
                if not price_text.endswith("€"):
                    if "€" in price_text:
                        price_text = re.sub(r"\s*€", " €", price_text)

        packaging_node = card.select_one(".product-list-card-plp-grid__packaging")
        packaging = packaging_node.get_text(strip=True) if packaging_node else None

        product_url = (
            href if href.startswith("http") else f"{CARREFOUR_BASE_URL}{href}"
        )

        results[ean] = {
            "id": ean,
            "name": title,
            "brand": _infer_brand(title),
            "category": None,
            "packaging": packaging,
            "price": price_text,
            "image": None,  # lazy-loaded; not in static HTML
            "product_url": product_url,
            "store": "Carrefour",
        }
        if len(results) >= max_results:
            break
    return list(results.values())


def parse_carrefour_search(payload: list[dict[str, Any]] | dict[str, Any], max_results: int) -> list[dict[str, str | None]]:
    """Parse a /api/marketing/search response (list of groups)."""
    if isinstance(payload, dict):
        # Defensive: some envelopes wrap the list under "data".
        payload = payload.get("data") or []
    if not isinstance(payload, list):
        return []

    results: dict[str, dict[str, str | None]] = {}
    for group in payload:
        if not isinstance(group, dict):
            continue
        for product in group.get("products") or []:
            if not isinstance(product, dict):
                continue
            attrs = product.get("attributes") or {}
            ean = attrs.get("ean") or product.get("id")
            title = attrs.get("title")
            if not ean or not title or ean in results:
                continue

            offer = _resolve_offer(attrs)
            price_obj = (offer or {}).get("price") or {}
            price_amount = price_obj.get("price") if isinstance(price_obj, dict) else None
            price_text = _format_price(price_amount)
            per_unit_label = price_obj.get("perUnitLabel") if isinstance(price_obj, dict) else None
            if per_unit_label and price_text:
                price_text = f"{price_text} ({per_unit_label})"

            slug = attrs.get("slug") or ""
            product_url = (
                f"{CARREFOUR_BASE_URL}/p/{urllib.parse.quote(slug)}-{ean}" if slug else None
            )

            brand = attrs.get("brand")
            packaging = attrs.get("packaging") or attrs.get("format")

            results[ean] = {
                "id": ean,
                "name": title,
                "brand": brand,
                "category": _resolve_category(attrs),
                "packaging": packaging,
                "price": price_text,
                "image": _resolve_image_url(attrs.get("images")),
                "product_url": product_url,
                "store": "Carrefour",
            }
            if len(results) >= max_results:
                return list(results.values())
    return list(results.values())


# Carrefour gates the API behind Cloudflare + a User-Agent / sec-ch-ua coherence
# check. Sending a vintage UA returns 404 + invalidates the session cookies. The
# values below match a real Chrome 147 macOS request from a recent HAR.
_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)
_SEC_CH_UA = '"Chromium";v="147", "Not.A/Brand";v="8"'


def _build_headers(referer: str, *, json_request: bool = True) -> dict[str, str]:
    headers: dict[str, str] = {
        "User-Agent": _CHROME_USER_AGENT,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "fr,en;q=0.9",
        "Origin": CARREFOUR_BASE_URL,
        "Referer": referer,
        "priority": "u=1, i",
        "sec-ch-ua": _SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
    if json_request:
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Content-Type"] = "application/json"
        headers["sec-fetch-dest"] = "empty"
        headers["x-requested-with"] = "XMLHttpRequest"
    else:
        headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
            "image/webp,image/apng,*/*;q=0.8"
        )
        headers["sec-fetch-dest"] = "document"
        headers["sec-fetch-site"] = "none"
        headers["sec-fetch-user"] = "?1"
        headers["upgrade-insecure-requests"] = "1"
    return headers


def _raise_for_auth(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise CarrefourAuthError(
            "Carrefour rejected the current session. "
            "Refresh `data/cookies_carrefour.json` from a logged-in browser session."
        )


async def search_carrefour(
    queries: list[str],
    max_results: int = 30,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    if cookies is None:
        cookies = load_carrefour_cookies()
    if not cookies:
        raise CarrefourAuthError(
            "No Carrefour cookies on disk. Provide `data/cookies_carrefour.json` "
            "exported from a logged-in browser session with a Drive store selected."
        )

    proxy_url = get_carrefour_proxy_url()
    results: dict[str, list[dict[str, str | None]]] = {}
    async with httpx.AsyncClient(
        base_url=CARREFOUR_BASE_URL,
        cookies=build_carrefour_cookie_jar(cookies),
        proxy=proxy_url,
        timeout=httpx.Timeout(30.0),
        trust_env=not proxy_url,
        follow_redirects=False,
    ) as client:
        for query in queries:
            encoded = urllib.parse.quote(query)
            referer = f"{CARREFOUR_BASE_URL}/"

            # The real catalog search results are SSR-rendered into /s?q=…. The
            # rich data (price, packaging, image, category) lives inside
            # `__INITIAL_STATE__.routeData`, serialized in Devalue format. The
            # plain HTML cards are a fallback that drops images and category.
            response = await client.get(
                f"/s?q={encoded}",
                headers=_build_headers(referer, json_request=False),
            )
            _raise_for_auth(response)
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                raise CarrefourAuthError(
                    "Carrefour returned a non-HTML response for the search page. "
                    "Cookies are likely stale — re-export `data/cookies_carrefour.json`."
                )
            response.raise_for_status()

            html = response.text
            state = _extract_initial_state(html)
            items: list[dict[str, str | None]] = []
            if state is not None:
                items = parse_carrefour_state_products(state, max_results=max_results)
            if not items:
                items = parse_carrefour_search_html(html, max_results=max_results)
            results[query] = items
    return results
