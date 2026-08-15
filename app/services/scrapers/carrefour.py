from __future__ import annotations

import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

import httpx


CARREFOUR_BASE_URL = "https://www.carrefour.fr"
CARREFOUR_COOKIES_PATH = Path(__file__).resolve().parents[3] / "data" / "cookies_carrefour.json"

DEFAULT_IMAGE_FORMAT = "200x200"

# `sort` query param values observed in live HAR captures (`carrefour.har`).
CARREFOUR_SORT_KEYS: dict[str, str | None] = {
    "price_asc": "offers.prices.effective_price",
    "price_desc": "-offers.prices.effective_price",
    "price_per_unit_asc": "offers.prices.standard_price_per_unit.price_per_unit_value",
    "price_per_unit_desc": "-offers.prices.standard_price_per_unit.price_per_unit_value",
    "best_rated": "-product.customer_review.average",
}

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


def _has_promotion(offer: dict[str, Any] | None) -> bool:
    """True when the canonical offer carries a live promotion.

    A product is considered "on promotion" when the offer exposes a `promotion`
    block or a non-empty `promotions` list.
    """
    if not offer:
        return False
    promotion = offer.get("promotion")
    promotions = offer.get("promotions") or []
    return bool(promotion) or (isinstance(promotions, list) and len(promotions) > 0)


_BRAND_TAIL_RE = re.compile(r"\b([A-ZÀ-Ý][A-ZÀ-Ý0-9' &-]{2,}(?:\s+[A-ZÀ-Ý0-9' &-]+)*)\s*$")


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


def _product_to_search_result(product: dict[str, Any]) -> dict[str, str | None] | None:
    """Map one product object from the /s?q= JSON payload to a search result."""
    if not isinstance(product, dict):
        return None
    attrs = product.get("attributes") or {}
    if not isinstance(attrs, dict):
        return None

    ean = attrs.get("ean") or ""
    title = attrs.get("title") or ""
    if not ean or not title:
        return None

    offer = _resolve_offer(attrs)
    price_obj = (offer or {}).get("price") or {}
    price_amount = price_obj.get("price") if isinstance(price_obj, dict) else None
    price_text = _format_price(price_amount)
    per_unit_label = price_obj.get("perUnitLabel") if isinstance(price_obj, dict) else None
    if per_unit_label and price_text:
        price_text = f"{price_text} ({per_unit_label})"

    links = product.get("links") or {}
    self_link = links.get("self") if isinstance(links, dict) else None
    if isinstance(self_link, str) and self_link:
        product_url = self_link if self_link.startswith("http") else f"{CARREFOUR_BASE_URL}{self_link}"
    else:
        slug = attrs.get("slug") or ""
        product_url = (
            f"{CARREFOUR_BASE_URL}/p/{urllib.parse.quote(slug)}-{ean}" if slug else None
        )

    return {
        "id": ean,
        "name": title,
        "brand": attrs.get("brand") or _infer_brand(title),
        "category": _resolve_category(attrs),
        "packaging": attrs.get("packaging") or attrs.get("format"),
        "price": price_text,
        "image": _resolve_image_url(attrs.get("images")),
        "product_url": product_url,
        "store": "Carrefour",
    }


def parse_carrefour_search_json(
    payload: dict[str, Any] | list[Any],
    max_results: int,
    promotions_only: bool = False,
) -> list[dict[str, str | None]]:
    """Parse the /s?q=… JSON search payload (array of product objects).

    The endpoint returns `{"data": [...], "links": ..., "meta": ...}`; `data`
    is the product list. A bare list (defensive) is also accepted.
    """
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            data = data.get("catalogPlpResponse") or data.get("products") or []
    else:
        data = payload
    if not isinstance(data, list):
        return []

    results: dict[str, dict[str, str | None]] = {}
    for product in data:
        if not isinstance(product, dict):
            continue
        attrs = product.get("attributes") or {}
        ean = attrs.get("ean") or product.get("id")
        title = attrs.get("title")
        if not ean or not title or ean in results:
            continue
        if promotions_only and not _has_promotion(_resolve_offer(attrs)):
            continue

        result = _product_to_search_result(product)
        if result is None:
            continue
        results[ean] = result
        if len(results) >= max_results:
            break
    return list(results.values())


def parse_carrefour_search(
    payload: list[dict[str, Any]] | dict[str, Any],
    max_results: int,
    promotions_only: bool = False,
) -> list[dict[str, str | None]]:
    """Parse a /api/marketing/search response (list of groups).

    Kept as a secondary parser for the marketing search body; the primary
    scraper path uses `parse_carrefour_search_json`.
    """
    if isinstance(payload, dict):
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
            if promotions_only and not _has_promotion(_resolve_offer(attrs)):
                continue

            result = _product_to_search_result(product)
            if result is None:
                continue
            results[ean] = result
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
    sort_by: str | None = None,
    promotions_only: bool = False,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    if cookies is None:
        cookies = load_carrefour_cookies()
    if not cookies:
        raise CarrefourAuthError(
            "No Carrefour cookies on disk. Provide `data/cookies_carrefour.json` "
            "exported from a logged-in browser session with a Drive store selected."
        )

    sort_key = CARREFOUR_SORT_KEYS.get(sort_by) if sort_by else None

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
            referer = f"{CARREFOUR_BASE_URL}/"

            params: dict[str, str] = {"q": query}
            if sort_key:
                params["sort"] = sort_key

            # The catalog search endpoint is served as JSON when requested with
            # XHR headers (observed in HAR: pages 2-19 + sort variants return
            # application/json). The JSON payload carries the full product data
            # (price, packaging, image, category) directly.
            response = await client.get(
                "/s",
                params=params,
                headers=_build_headers(referer, json_request=True),
            )
            _raise_for_auth(response)
            response.raise_for_status()

            try:
                payload = response.json()
            except json.JSONDecodeError as exc:
                raise CarrefourAuthError(
                    "Carrefour returned a non-JSON response for the search query. "
                    "Cookies are likely stale — re-export `data/cookies_carrefour.json`."
                ) from exc

            items = parse_carrefour_search_json(
                payload, max_results=max_results, promotions_only=promotions_only
            )

            # Follow pagination (up to max_results) via the links.next chain.
            collected: dict[str, dict[str, str | None]] = {item["id"]: item for item in items}
            page = 2
            while len(collected) < max_results and page <= 20:
                if isinstance(payload, dict):
                    links = payload.get("links") or {}
                    next_link = links.get("next") if isinstance(links, dict) else None
                else:
                    next_link = None
                if not isinstance(next_link, str) or not next_link:
                    break

                next_params = dict(params)
                parsed = urllib.parse.urlparse(next_link)
                next_page = urllib.parse.parse_qs(parsed.query).get("page")
                if next_page:
                    page = int(next_page[0])
                else:
                    break
                next_params["page"] = str(page)
                response = await client.get(
                    "/s",
                    params=next_params,
                    headers=_build_headers(referer, json_request=True),
                )
                _raise_for_auth(response)
                response.raise_for_status()
                try:
                    payload = response.json()
                except json.JSONDecodeError as exc:
                    raise CarrefourAuthError(
                        "Carrefour returned a non-JSON response for the search page. "
                        "Cookies are likely stale — re-export `data/cookies_carrefour.json`."
                    ) from exc

                page_items = parse_carrefour_search_json(
                    payload, max_results=max_results, promotions_only=promotions_only
                )
                for item in page_items:
                    if item["id"] not in collected:
                        collected[item["id"]] = item
                        if len(collected) >= max_results:
                            break
                page += 1

            results[query] = list(collected.values())[:max_results]
    return results
