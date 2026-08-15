from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

# Intermarché serves search as a JSON API:
#   GET https://www.intermarche.com/api/products?query={json}&ref={pdv}
# with `query` carrying the keyword, pagination, sort and the promotions-only
# flag. Prices are embedded in the response (`prices.productPrice`) and are
# store-specific: the `ref` query param (and the `itm_pdv` cookie) scope the
# results to the selected store. The endpoint sits behind DataDome, which
# requires browser-like headers but not a login — prices are public.
INTERMARCHE_BASE_URL = "https://www.intermarche.com"
INTERMARCHE_COOKIES_PATH = Path(__file__).resolve().parents[3] / "data" / "cookies_intermarche.json"

# sort_by values (API contract) -> JSON `sort` field. `pertinence` is the
# default relevance order used by the site when no trier/ordre is given.
INTERMARCHE_SORT_TYPES: dict[str, tuple[str, str | None]] = {
    "price_asc": ("prix", "croissant"),
    "price_desc": ("prix", "decroissant"),
    "unit_price_asc": ("prixkg", "croissant"),
    "unit_price_desc": ("prixkg", "decroissant"),
}

# The /api/products endpoint is behind DataDome: it answers 403 with a JS
# challenge when the request does not look like a real browser. These headers
# (a coherent Chrome profile, verified against the live endpoint) are required.
_CHROME_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "fr,en;q=0.9",
    "sec-ch-ua": '"Chromium";v="151", "Not=A?Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "priority": "u=1, i",
}

INTERMARCHE_DEFAULT_REFERER = f"{INTERMARCHE_BASE_URL}/recherche/"


class IntermarcheAuthError(RuntimeError):
    """Intermarché rejected the current session (DataDome / auth)."""


def get_intermarche_proxy_url() -> str | None:
    for key in ("ADAMHUB_INTERMARCHE_PROXY_URL", "INTERMARCHE_PROXY_URL"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return normalize_proxy_url(value)
    return None


def normalize_proxy_url(proxy_url: str) -> str:
    normalized = proxy_url.strip()
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    return normalized


def load_intermarche_cookies(path: Path | None = None) -> list[dict[str, Any]]:
    cookies_path = path or INTERMARCHE_COOKIES_PATH
    if not cookies_path.exists():
        return []

    with cookies_path.open("r", encoding="utf-8") as handle:
        raw_cookies = json.load(handle)

    normalized: list[dict[str, Any]] = []
    for raw_cookie in raw_cookies:
        cookie: dict[str, Any] = {
            key: raw_cookie[key]
            for key in ("name", "value", "domain", "path", "httpOnly", "secure", "sameSite", "url")
            if key in raw_cookie
        }

        expiration = raw_cookie.get("expires")
        if expiration is None:
            expiration = raw_cookie.get("expirationDate")
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


def build_intermarche_cookie_jar(cookies: list[dict[str, Any]]) -> httpx.Cookies:
    jar = httpx.Cookies()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        jar.set(name, value, domain=cookie.get("domain"), path=cookie.get("path", "/"))
    return jar


def extract_pdv_ref_from_cookies(cookies: list[dict[str, Any]]) -> str | None:
    """Recover the selected store id (`ref`) from the session cookies.

    The browser stores the selection in the `itm_pdv` cookie as URL-encoded
    JSON (`{"ref":"11131",...}`); `novaParams` carries the same id under
    `pdvRef`. Returns None when no store is selected — the API still answers,
    but from the default catalog instead of the user's store.
    """
    for cookie_name, ref_key in (("itm_pdv", "ref"), ("novaParams", "pdvRef")):
        for cookie in cookies:
            if cookie.get("name") != cookie_name:
                continue
            value = (cookie.get("value") or "").strip()
            if not value:
                continue
            try:
                payload = json.loads(urllib.parse.unquote(value))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                ref = payload.get(ref_key)
                if ref:
                    return str(ref)
    return None


def build_search_query(
    keyword: str,
    page: int = 1,
    per_page: int = 40,
    sort_by: str | None = None,
    promotions_only: bool = False,
) -> dict[str, Any]:
    """Compose the JSON `query` payload expected by /api/products.

    The site encodes the search UI (keyword, page, sort `trier`/`ordre`,
    promotions-only switch) in this single JSON document.
    """
    if sort_by in INTERMARCHE_SORT_TYPES:
        sort_type, sort_direction = INTERMARCHE_SORT_TYPES[sort_by]
    else:
        sort_type, sort_direction = "pertinence", None

    return {
        "keyword": keyword,
        "slugs": [],
        "categoryId": "",
        "page": page,
        "perPage": per_page,
        "filters": [],
        "apiFilters": [],
        "sort": {"type": sort_type, "direction": sort_direction},
        "headingId": "-1",
        "catalogs": ["PDV"],
        "isPromo": bool(promotions_only),
        "type": "SEARCH",
    }


def _product_price(product: dict[str, Any]) -> str | None:
    prices = product.get("prices") if isinstance(product.get("prices"), dict) else None
    if not prices:
        return None
    product_price = prices.get("productPrice")
    if not isinstance(product_price, dict):
        return None
    concatenated = product_price.get("concatenated")
    if concatenated:
        return str(concatenated)
    value = product_price.get("value")
    currency = product_price.get("currency") or "€"
    if value is None:
        return None
    rendered = str(value).replace(".", ",")
    return f"{rendered}{currency}"


def _product_image(informations: dict[str, Any]) -> str | None:
    image = informations.get("image")
    if isinstance(image, dict) and image.get("src"):
        return str(image["src"])
    all_images = informations.get("allImages")
    if isinstance(all_images, list):
        for entry in all_images:
            if isinstance(entry, dict) and entry.get("src"):
                return str(entry["src"])
    return None


def _category_id_for(product: dict[str, Any]) -> int | None:
    """Deepest non-zero category id: subFamily > family > department."""
    for key in ("subFamillyId", "famillyId", "departmentId"):
        value = product.get(key)
        if value:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None


def extract_category_from_tracking_code(tracking_code: str | None) -> str | None:
    if not tracking_code:
        return None
    try:
        decoded = base64.b64decode(tracking_code + "===").decode("utf-8", "ignore")
    except Exception:
        return None

    family_markers = [
        "sous-famille",
        "sous-familles",
        "famille",
        "familles",
        "rayon",
        "rayons",
    ]
    lower = decoded.lower()
    for marker in family_markers:
        idx = lower.find(marker)
        if idx == -1:
            continue
        tail = decoded[idx: idx + 300]
        for stop_marker in [" pour la requête ", " dans la requête "]:
            stop_idx = tail.lower().find(stop_marker)
            if stop_idx != -1:
                tail = tail[:stop_idx]
                break
        labels = re.findall(r'"([^"]+)"', tail)
        labels = [label.strip() for label in labels if label.strip()]
        if labels:
            return " / ".join(dict.fromkeys(labels))
    return None


def _product_category(
    product: dict[str, Any],
    category_lookup: dict[int, str] | None,
) -> str | None:
    if category_lookup:
        category_id = _category_id_for(product)
        if category_id is not None and category_id in category_lookup:
            return category_lookup[category_id]
    return extract_category_from_tracking_code(product.get("trackingCode"))


def parse_intermarche_products(
    payload: dict[str, Any] | list[dict[str, Any]],
    max_results: int = 10,
    category_lookup: dict[int, str] | None = None,
) -> list[dict[str, str | None]]:
    """Map a /api/products payload to the raw-item format of normalize_search_result.

    Skips editorial tiles (recipes/ads mixed into the results) that carry no
    product identifier. The category is resolved from the /api/categories tree
    when available, falling back to the base64 `trackingCode` label.
    """
    products = payload.get("products") if isinstance(payload, dict) else payload
    if not isinstance(products, list):
        return []

    results: list[dict[str, str | None]] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        external_id = str(product.get("ean") or product.get("id") or "").strip() or None
        if external_id is None:
            continue

        informations = product.get("informations") if isinstance(product.get("informations"), dict) else {}
        name = (informations.get("title") or "").strip() or "Produit inconnu"
        brand = (informations.get("brand") or "").strip() or None
        packaging = (informations.get("packaging") or "").strip() or None

        product_url = None
        url = product.get("url")
        if url:
            product_url = (
                url if str(url).startswith("http") else f"{INTERMARCHE_BASE_URL}{url}"
            )

        results.append(
            {
                "id": external_id,
                "name": name,
                "brand": brand,
                "category": _product_category(product, category_lookup),
                "packaging": packaging,
                "price": _product_price(product),
                "image": _product_image(informations),
                "product_url": product_url,
                "store": "Intermarché",
            }
        )
        if len(results) >= max_results:
            break
    return results


def _walk_category_tree(nodes: list[dict[str, Any]], path: list[str], lookup: dict[int, str]) -> None:
    for node in nodes:
        title = node.get("title")
        node_path = path + ([title] if title else [])
        try:
            node_id = int(node["id"])
        except (KeyError, TypeError, ValueError):
            node_id = None
        if node_id is not None and node_path:
            lookup[node_id] = " / ".join(node_path)
        children = node.get("children") if isinstance(node.get("children"), list) else []
        _walk_category_tree(children, node_path, lookup)


def parse_intermarche_category_tree(tree: list[dict[str, Any]]) -> dict[int, str]:
    """Flatten the /api/categories tree into a category id -> path lookup."""
    lookup: dict[int, str] = {}
    _walk_category_tree(tree, [], lookup)
    return lookup


async def fetch_intermarche_categories(
    client: httpx.AsyncClient,
    pdv_ref: str | None = None,
) -> dict[int, str]:
    """Fetch the store's category tree (/api/categories) as an id -> path map."""
    params: dict[str, Any] = {"maxDepth": 4}
    if pdv_ref:
        params["pdvRef"] = pdv_ref
    response = await client.get(
        f"{INTERMARCHE_BASE_URL}/api/categories",
        params=params,
        headers={**_CHROME_HEADERS, "Referer": INTERMARCHE_DEFAULT_REFERER},
    )
    response.raise_for_status()
    tree = response.json().get("tree")
    if not isinstance(tree, list):
        return {}
    return parse_intermarche_category_tree(tree)


def is_intermarche_bot_challenge(content: str) -> bool:
    lowered = content.lower()
    return (
        "geo.captcha-delivery.com/interstitial" in lowered
        or "datadome device check" in lowered
        or "captcha-delivery.com" in lowered
    )


async def _fetch_products_page(
    client: httpx.AsyncClient,
    query: str,
    pdv_ref: str | None,
    page: int = 1,
    per_page: int = 40,
    sort_by: str | None = None,
    promotions_only: bool = False,
) -> list[dict[str, Any]]:
    search_query = build_search_query(
        query, page=page, per_page=per_page, sort_by=sort_by, promotions_only=promotions_only
    )
    params = {"query": json.dumps(search_query, separators=(",", ":"), ensure_ascii=False)}
    if pdv_ref:
        params["ref"] = pdv_ref
    url = f"{INTERMARCHE_BASE_URL}/api/products"
    headers = {**_CHROME_HEADERS, "Referer": f"{INTERMARCHE_DEFAULT_REFERER}{urllib.parse.quote(query)}"}

    # The API occasionally returns an empty result set or a transient DataDome
    # challenge (intermittent for cookie-less sessions); retry a couple of
    # times before giving up on a query.
    last_error: Exception | None = None
    for _ in range(3):
        try:
            response = await client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            last_error = exc
            await asyncio.sleep(0.5)
            continue
        if response.status_code in {401, 403} or is_intermarche_bot_challenge(response.text):
            last_error = IntermarcheAuthError(
                "Intermarché rejected the current session (DataDome or expired cookies). "
                "Refresh `data/cookies_intermarche.json` from a browser session "
                "with a store selected."
            )
            await asyncio.sleep(1.0)
            continue
        response.raise_for_status()
        try:
            products = response.json().get("products")
        except ValueError:
            last_error = IntermarcheAuthError(
                "Intermarché returned an unexpected response (DataDome). "
                "Refresh `data/cookies_intermarche.json` from a browser session "
                "with a store selected."
            )
            await asyncio.sleep(0.5)
            continue
        if isinstance(products, list) and products:
            return products
        await asyncio.sleep(0.5)
    if last_error is not None:
        raise last_error
    return []


async def search_intermarche(
    queries: list[str],
    max_results: int = 10,
    sort_by: str | None = None,
    promotions_only: bool = False,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    """Search the Intermarché JSON API (/api/products) for each query.

    The store id is recovered from the session cookies (``itm_pdv``) and passed
    as the ``ref`` query param; without a selected store the API still returns
    results from its default catalog. ``sort_by`` and ``promotions_only`` map to
    the JSON ``sort`` and ``isPromo`` fields of the query payload.
    """
    if cookies is None:
        cookies = load_intermarche_cookies()
    proxy_url = get_intermarche_proxy_url()
    pdv_ref = extract_pdv_ref_from_cookies(cookies)

    results: dict[str, list[dict[str, str | None]]] = {}
    async with httpx.AsyncClient(
        follow_redirects=True,
        cookies=build_intermarche_cookie_jar(cookies),
        proxy=proxy_url,
        timeout=httpx.Timeout(30.0),
        trust_env=not proxy_url,
    ) as client:
        try:
            category_lookup = await fetch_intermarche_categories(client, pdv_ref)
        except Exception:
            category_lookup = {}

        for query in queries:
            products = await _fetch_products_page(
                client,
                query,
                pdv_ref,
                per_page=max_results,
                sort_by=sort_by,
                promotions_only=promotions_only,
            )
            results[query] = parse_intermarche_products(
                products, max_results=max_results, category_lookup=category_lookup
            )
    return results


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "lait"
    print(
        json.dumps(
            asyncio.run(search_intermarche(queries=[query], max_results=10)),
            indent=2,
            ensure_ascii=False,
        )
    )
