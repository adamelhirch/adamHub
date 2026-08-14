from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path
from typing import Any

import httpx


# Leclerc Drive is a client-side SPA at www.leclercdrive.fr: the real search
# endpoint is only visible in the network traffic of a logged-in session (with a
# Drive store selected, so prices are store-specific). This module follows the
# same plumbing contract as `carrefour.py` — JSON API + cookies — and is
# defensive about the payload shape. The search path below is a placeholder that
# must be replaced once the real endpoint is captured (see the live-capture
# wizard in scripts/).
LECLERC_BASE_URL = "https://www.leclercdrive.fr"
LECLERC_API_VERSION = "v1"
LECLERC_COOKIES_PATH = Path(__file__).resolve().parents[3] / "data" / "cookies_leclerc.json"


class LeclercAuthError(RuntimeError):
    """Cookies are missing or rejected by Leclerc Drive."""


def get_leclerc_proxy_url() -> str | None:
    for key in ("ADAMHUB_LECLERC_PROXY_URL", "LECLERC_PROXY_URL"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return _normalize_proxy_url(value)
    return None


def _normalize_proxy_url(proxy_url: str) -> str:
    normalized = proxy_url.strip()
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    return normalized


def load_leclerc_cookies(path: Path | None = None) -> list[dict[str, Any]]:
    cookies_path = path or LECLERC_COOKIES_PATH
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


def build_leclerc_cookie_jar(cookies: list[dict[str, Any]]) -> httpx.Cookies:
    jar = httpx.Cookies()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        jar.set(name, value, domain=cookie.get("domain"), path=cookie.get("path", "/"))
    return jar


def _extract_price(raw: dict[str, Any]) -> str | None:
    """Normalize the many price shapes Leclerc has returned over time."""
    price_raw = raw.get("price")
    if price_raw is None:
        price_raw = raw.get("salePrice") or raw.get("prix")
    if price_raw is None:
        return None

    if isinstance(price_raw, str):
        text = price_raw.strip()
        return text or None
    if isinstance(price_raw, (int, float)):
        if price_raw <= 0:
            return None
        return f"{price_raw:.2f} €".replace(".", ",")

    if isinstance(price_raw, dict):
        amount = price_raw.get("amount")
        if amount is None:
            amount = price_raw.get("value")
        if not isinstance(amount, (int, float)) or amount <= 0:
            return None
        currency = price_raw.get("currency") or "€"
        currency_symbol = {"EUR": "€"}.get(str(currency).upper(), str(currency))
        price = f"{amount:.2f} {currency_symbol}".replace(".", ",")
        per_unit = price_raw.get("perUnitLabel") or price_raw.get("perUnit")
        if per_unit:
            price = f"{price} ({per_unit})"
        return price
    return None


def _resolve_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Unwrap the nested product/offer object when the API wraps it."""
    for key in ("product", "offer", "item"):
        nested = raw.get(key)
        if isinstance(nested, dict):
            merged = dict(nested)
            for extra in ("price", "salePrice", "stock", "availability"):
                if extra not in merged and extra in raw:
                    merged[extra] = raw[extra]
            return merged
    return raw


def parse_leclerc_search(payload: Any, max_results: int) -> list[dict[str, str | None]]:
    """Parse a Leclerc Drive search response into normalized result dicts.

    Defensive on purpose: the real envelope is only confirmable with a live
    session, so this accepts a top-level list or a wrapping dict whose key is
    one of the known containers. Items without a name are skipped.
    """
    if isinstance(payload, dict):
        for key in ("results", "data", "products", "items", "searchResults"):
            container = payload.get(key)
            if isinstance(container, list):
                payload = container
                break
        else:
            payload = []
    if not isinstance(payload, list):
        return []

    results: dict[str, dict[str, str | None]] = {}
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        product = _resolve_product(raw)
        name = (product.get("name") or "").strip()
        if not name:
            continue
        ext_id = (
            str(product.get("id") or product.get("productId") or product.get("ean") or "")
            .strip()
        )
        key = ext_id or name
        if key in results:
            continue

        slug = product.get("slug") or product.get("urlKey")
        product_url = None
        if slug:
            product_url = (
                f"https://www.leclercdrive.fr/produit/{urllib.parse.quote(str(slug))}"
            )

        image_url = None
        image = product.get("image") or product.get("imageUrl")
        if isinstance(image, str):
            image_url = image
        elif isinstance(product.get("images"), list):
            for candidate in product["images"]:
                if isinstance(candidate, str):
                    image_url = candidate
                    break
                if isinstance(candidate, dict):
                    url = candidate.get("url") or candidate.get("src")
                    if isinstance(url, str):
                        image_url = url
                        break

        results[key] = {
            "id": ext_id or None,
            "name": name,
            "brand": product.get("brand"),
            "category": product.get("category") or product.get("categoryName"),
            "packaging": product.get("packaging") or product.get("format"),
            "price": _extract_price(product),
            "image": image_url,
            "product_url": product_url,
            "store": "Leclerc",
        }
        if len(results) >= max_results:
            break
    return list(results.values())


# The API is gated behind Cloudflare-style checks; a coherent Chrome UA and the
# cookie-bearing session are required, mirroring the Carrefour scraper.
_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)
_SEC_CH_UA = '"Chromium";v="147", "Not.A/Brand";v="8"'


def _build_headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": _CHROME_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "fr,en;q=0.9",
        "Origin": "https://www.leclercdrive.fr",
        "Referer": referer,
        "sec-ch-ua": _SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    }


def _raise_for_auth(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise LeclercAuthError(
            "Leclerc rejected the current session. "
            "Refresh `data/cookies_leclerc.json` from a logged-in browser session "
            "with a Drive store selected."
        )


async def search_leclerc(
    queries: list[str],
    max_results: int = 30,
    sort_by: str | None = None,
    promotions_only: bool = False,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    """Best-effort Leclerc Drive search following the `search_carrefour` contract.

    NOTE: this plumbing is not live-validated yet. The exact endpoint, headers
    and response envelope are reverse-engineered from public knowledge and need
    confirmation against a real session (cookies from a logged-in Drive account
    with a store selected). Sorting and promotions filtering are not wired to
    the request yet.
    """
    del sort_by, promotions_only
    if cookies is None:
        cookies = load_leclerc_cookies()
    if not cookies:
        raise LeclercAuthError(
            "No Leclerc Drive cookies on disk. Provide `data/cookies_leclerc.json` "
            "exported from a logged-in browser session with a Drive store selected."
        )

    proxy_url = get_leclerc_proxy_url()
    results: dict[str, list[dict[str, str | None]]] = {}
    async with httpx.AsyncClient(
        base_url=LECLERC_BASE_URL,
        cookies=build_leclerc_cookie_jar(cookies),
        proxy=proxy_url,
        timeout=httpx.Timeout(30.0),
        trust_env=not proxy_url,
        follow_redirects=False,
    ) as client:
        for query in queries:
            encoded = urllib.parse.quote(query)
            response = await client.get(
                f"/{LECLERC_API_VERSION}/search",
                params={"q": query},
                headers=_build_headers(f"{LECLERC_BASE_URL}/"),
            )
            _raise_for_auth(response)
            response.raise_for_status()
            try:
                payload = response.json()
            except json.JSONDecodeError:
                raise RuntimeError(
                    "Leclerc returned a non-JSON response for the search API. "
                    "The endpoint may have changed — live validation is required."
                )
            results[query] = parse_leclerc_search(payload, max_results=max_results)
    return results
