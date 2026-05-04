from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path
from typing import Any

import httpx


UBEREATS_BASE_URL = "https://www.ubereats.com"
UBEREATS_COOKIES_PATH = Path(__file__).resolve().parents[3] / "data" / "cookies_ubereats.json"
UBEREATS_LOC_COOKIE_NAME = "uev2.loc"
GROCERY_FEED_TYPE = "GROCERY"

# Sort filter UUIDs from getInStoreSearchV1 response.
SORT_FILTER_UUID = "55ff3403-48b8-46fe-9d7d-229f04cb82ad"
SORT_OPTION_PRICE_ASC = ("6d19f03e-656a-4a58-b467-b6925cbad1c7", "Price low to high")
SORT_OPTION_PRICE_DESC = ("29611a74-5cec-455b-8cb3-10f64fbe09a2", "Price high to low")

# Uber Eats does not expose a server-side grocery filter on getFeedV1, so we filter
# client-side by matching store names against this brand list. Extend as needed.
GROCERY_BRAND_KEYWORDS: tuple[str, ...] = (
    "carrefour",
    "monoprix",
    "franprix",
    "casino shop",
    "petit casino",
    "vival",
    "spar",
    "picard",
    "auchan",
    "lidl",
    "aldi",
    "naturalia",
    "bio c'bon",
    "bio c bon",
    "biocoop",
    "intermarch",
    "leclerc",
    "coccinelle",
    "proxi",
    "g20",
    "marche u",
    "u express",
    "match",
    "sherpa",
    "naturéo",
    "natureo",
    "day by day",
    "paul",
    "marie blachère",
    "marie blachere",
    "grand frais",
    "thiriet",
)


class UbereatsAuthError(RuntimeError):
    """Cookies are missing or rejected by Uber Eats."""


class UbereatsLocationError(RuntimeError):
    """No delivery location is set on the current session."""


def get_ubereats_proxy_url() -> str | None:
    for key in ("ADAMHUB_UBEREATS_PROXY_URL", "UBEREATS_PROXY_URL"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return _normalize_proxy_url(value)
    return None


def _normalize_proxy_url(proxy_url: str) -> str:
    normalized = proxy_url.strip()
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    return normalized


def load_ubereats_cookies(path: Path | None = None) -> list[dict[str, Any]]:
    cookies_path = path or UBEREATS_COOKIES_PATH
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


def save_ubereats_cookies(cookies: list[dict[str, Any]], path: Path | None = None) -> None:
    cookies_path = path or UBEREATS_COOKIES_PATH
    cookies_path.parent.mkdir(parents=True, exist_ok=True)
    with cookies_path.open("w", encoding="utf-8") as handle:
        json.dump(cookies, handle, ensure_ascii=False, indent=2)


def build_ubereats_cookie_jar(cookies: list[dict[str, Any]]) -> httpx.Cookies:
    jar = httpx.Cookies()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        jar.set(name, value, domain=cookie.get("domain"), path=cookie.get("path", "/"))
    return jar


def find_cookie(cookies: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for cookie in cookies:
        if cookie.get("name") == name:
            return cookie
    return None


def decode_uev2_loc(cookies: list[dict[str, Any]]) -> dict[str, Any] | None:
    cookie = find_cookie(cookies, UBEREATS_LOC_COOKIE_NAME)
    if not cookie:
        return None
    raw_value = cookie.get("value") or ""
    if not raw_value:
        return None
    try:
        decoded = urllib.parse.unquote(raw_value)
        return json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None


def encode_uev2_loc(payload: dict[str, Any]) -> str:
    return urllib.parse.quote(json.dumps(payload, separators=(",", ":")), safe="")


def get_current_address_label(cookies: list[dict[str, Any]]) -> str | None:
    payload = decode_uev2_loc(cookies)
    if not payload:
        return None
    address = payload.get("address") or {}
    formatted = address.get("eaterFormattedAddress") or address.get("address1")
    title = address.get("title")
    if formatted and title and formatted != title:
        return f"{title} — {formatted}"
    return formatted or title


def update_uev2_loc(cookies: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    encoded = encode_uev2_loc(payload)
    cookie = find_cookie(cookies, UBEREATS_LOC_COOKIE_NAME)
    if cookie:
        cookie["value"] = encoded
        return cookies

    cookies.append(
        {
            "name": UBEREATS_LOC_COOKIE_NAME,
            "value": encoded,
            "domain": ".ubereats.com",
            "path": "/",
            "secure": True,
            "sameSite": "Lax",
        }
    )
    return cookies


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "Origin": UBEREATS_BASE_URL,
        "Referer": f"{UBEREATS_BASE_URL}/fr/",
        "x-csrf-token": "x",
    }


def _build_client(cookies: list[dict[str, Any]]) -> httpx.AsyncClient:
    proxy_url = get_ubereats_proxy_url()
    return httpx.AsyncClient(
        base_url=UBEREATS_BASE_URL,
        follow_redirects=True,
        headers=_build_headers(),
        cookies=build_ubereats_cookie_jar(cookies),
        proxy=proxy_url,
        timeout=httpx.Timeout(30.0),
        trust_env=not proxy_url,
    )


def _raise_for_auth(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise UbereatsAuthError(
            "Uber Eats rejected the current session. "
            "Refresh `data/cookies_ubereats.json` from a logged-in browser session."
        )


def _walk(node: Any):
    """Yield every dict node in a nested structure."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _looks_like_grocery(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in GROCERY_BRAND_KEYWORDS)


def _extract_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("text") or value.get("accessibilityText")
    return None


def _first_image_url(image: Any) -> str | None:
    if isinstance(image, str):
        return image
    if isinstance(image, dict):
        items = image.get("items")
        if isinstance(items, list) and items:
            return items[0].get("url")
        return image.get("url")
    return None


def _parse_rating(value: Any) -> float | None:
    text = _extract_text(value)
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def parse_grocery_stores(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract grocery stores from a getFeedV1 response.

    The feed mixes restaurants and groceries with no server-side vertical filter,
    so we keep only stores whose title matches a known grocery brand keyword.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    feed_items = (data or {}).get("feedItems") or []

    stores: dict[str, dict[str, Any]] = {}
    for item in feed_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in {"REGULAR_STORE", "STORE_WITH_INLINE_ITEMS"}:
            continue

        store = item.get("store") or {}
        if not isinstance(store, dict):
            continue
        uuid = store.get("storeUuid") or store.get("uuid")
        name = _extract_text(store.get("title"))
        if not uuid or not name or not isinstance(uuid, str):
            continue
        if not _looks_like_grocery(name):
            continue
        if uuid in stores:
            continue

        # Find a useful subtitle: ETD badge or similar.
        subtitle = None
        for badge in store.get("meta") or []:
            if isinstance(badge, dict) and badge.get("badgeType") in {"ETD", "PRIORITY_DELIVERY"}:
                subtitle = badge.get("text")
                break

        action_url = store.get("actionUrl") or ""
        full_url = (
            action_url
            if action_url.startswith("http")
            else f"{UBEREATS_BASE_URL}{action_url}"
            if action_url
            else None
        )

        stores[uuid] = {
            "uuid": uuid,
            "name": name,
            "subtitle": subtitle,
            "address": full_url,
            "rating": _parse_rating(store.get("rating")),
            "image_url": _first_image_url(store.get("image")),
        }
    return list(stores.values())


def _format_price_eur(cents: int | None) -> str | None:
    if cents is None or cents <= 0:
        return None
    return f"{cents / 100:.2f} €".replace(".", ",")


def parse_search_results(
    payload: dict[str, Any],
    max_results: int,
    store_uuid: str | None = None,
) -> list[dict[str, str | None]]:
    """Extract products from a getInStoreSearchV1 response.

    The new shape is `data.catalogSectionsMap[<sectionUuid>][0].payload
    .standardItemsPayload.catalogItems[]`. Each item has a numeric price in
    `purchaseInfo.purchaseOptions[0].purchasePriceV2.base.low` (cents).
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    catalog_sections_map = (data or {}).get("catalogSectionsMap") or {}

    results: dict[str, dict[str, str | None]] = {}
    for sections in catalog_sections_map.values():
        if not isinstance(sections, list):
            continue
        for section in sections:
            section_payload = (section or {}).get("payload") or {}
            standard = section_payload.get("standardItemsPayload") or {}
            for node in standard.get("catalogItems") or []:
                if not isinstance(node, dict):
                    continue
                uuid = node.get("uuid")
                name = node.get("title")
                if not uuid or not name or uuid in results:
                    continue
                if node.get("isSoldOut") or not node.get("isAvailable", True):
                    continue

                # Price in cents
                price_cents: int | None = None
                if isinstance(node.get("price"), (int, float)) and node["price"] > 0:
                    price_cents = int(node["price"])
                else:
                    purchase_options = (node.get("purchaseInfo") or {}).get("purchaseOptions") or []
                    if purchase_options:
                        ppv2 = (purchase_options[0] or {}).get("purchasePriceV2") or {}
                        base = ppv2.get("base") or {}
                        low = base.get("low")
                        if isinstance(low, (int, float)) and low > 0:
                            price_cents = int(low)

                price_text = _extract_text(node.get("priceTagline")) or _format_price_eur(price_cents)
                if not price_text:
                    continue

                image_url = node.get("imageUrl")

                results[uuid] = {
                    "id": uuid,
                    "name": name,
                    "brand": None,
                    "category": None,
                    "packaging": None,
                    "price": price_text,
                    "price_cents": price_cents,
                    "image": image_url,
                    "product_url": None,
                    "store": "Uber Eats",
                    "section_uuid": node.get("sectionUuid"),
                    "subsection_uuid": node.get("subsectionUuid"),
                    "store_uuid": store_uuid,
                }
                if len(results) >= max_results:
                    return list(results.values())

    return list(results.values())


async def list_grocery_stores(
    max_results: int = 25, cookies: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    if cookies is None:
        cookies = load_ubereats_cookies()
    if not cookies:
        raise UbereatsAuthError(
            "No Uber Eats cookies on disk. Provide `data/cookies_ubereats.json` "
            "exported from a logged-in browser session."
        )
    if not decode_uev2_loc(cookies):
        raise UbereatsLocationError(
            "Uber Eats session has no delivery location. "
            "Add the `uev2.loc` cookie or call `PUT /supermarket/ubereats/location`."
        )

    body = {
        "feedType": GROCERY_FEED_TYPE,
        "diningMode": "DELIVERY",
        "userQuery": "",
        "date": "",
        "startTime": 0,
        "endTime": 0,
        "sortAndFilters": [],
        "marketingFeedType": "",
        "billboardUuid": "",
        "feedProvider": "",
        "promotionUuid": "",
        "targetingStoreTag": "",
        "venueUUID": "",
        "selectedSectionUUID": "",
        "favorites": "",
        "searchSource": "",
        "keyName": "",
    }
    async with _build_client(cookies) as client:
        response = await client.post("/api/getFeedV1", json=body)
        _raise_for_auth(response)
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            raise RuntimeError(
                f"Uber Eats getFeedV1 returned an error: {payload.get('data')}"
            )

    stores = parse_grocery_stores(payload)
    return stores[:max_results]


def _build_target_location(target: dict[str, Any] | None, cookies: list[dict[str, Any]]) -> dict[str, Any]:
    """Compose a UE-compatible targetLocation from a saved address (preferred)
    or the decoded uev2.loc cookie as a fallback. Empty fields are accepted.
    """
    if target:
        return target

    payload = decode_uev2_loc(cookies) or {}
    address = payload.get("address") or {}
    components = payload.get("addressComponents") or {}
    formatted = (
        address.get("eaterFormattedAddress")
        or address.get("address1")
        or address.get("title")
        or ""
    )
    return {
        "address": formatted,
        "streetAddress": address.get("address1") or formatted,
        "city": components.get("city") or "",
        "country": components.get("countryCode") or "FR",
        "postalCode": components.get("postalCode") or "",
        "region": components.get("firstLevelSubdivisionCode") or "",
        "latitude": payload.get("latitude") or 0.0,
        "longitude": payload.get("longitude") or 0.0,
        "geo": {"city": "", "country": "fr", "region": ""},
        "locationType": "GROCERY_STORE",
    }


def _build_sort_filter(sort_by: str | None) -> list[dict[str, Any]] | None:
    if sort_by == "price_asc":
        opt_uuid, value = SORT_OPTION_PRICE_ASC
    elif sort_by == "price_desc":
        opt_uuid, value = SORT_OPTION_PRICE_DESC
    else:
        return None
    return [
        {
            "uuid": SORT_FILTER_UUID,
            "minPermitted": 1,
            "maxPermitted": 1,
            "options": [{"uuid": opt_uuid, "selected": True, "value": value}],
            "type": "sort",
        }
    ]


async def search_in_store(
    store_uuid: str,
    queries: list[str],
    max_results: int = 50,
    target_location: dict[str, Any] | None = None,
    sort_by: str | None = None,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    if cookies is None:
        cookies = load_ubereats_cookies()
    if not cookies:
        raise UbereatsAuthError(
            "No Uber Eats cookies on disk. Provide `data/cookies_ubereats.json` "
            "exported from a logged-in browser session."
        )

    target = _build_target_location(target_location, cookies)
    sort_filter = _build_sort_filter(sort_by)

    results: dict[str, list[dict[str, str | None]]] = {}
    async with _build_client(cookies) as client:
        for query in queries:
            body: dict[str, Any] = {
                "diningMode": "DELIVERY",
                "sectionUUIDs": None,
                "storeUUIDs": [store_uuid],
                "userQuery": query,
                "isGrocery": True,
                "targetLocation": target,
                "entrypointContext": "IN_STORE_SEARCH",
            }
            if sort_filter is not None:
                body["sortAndFilters"] = sort_filter
            response = await client.post("/_p/api/getInStoreSearchV1?localeCode=fr", json=body)
            _raise_for_auth(response)
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "success":
                raise RuntimeError(
                    f"Uber Eats getInStoreSearchV1 returned an error: {payload.get('data')}"
                )
            results[query] = parse_search_results(
                payload, max_results=max_results, store_uuid=store_uuid
            )
    return results


async def set_delivery_location(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a new delivery location into the cookie file.

    Expected payload mirrors the structure stored in `uev2.loc`:
        {
          "address": {"title": "...", "subtitle": "...", "eaterFormattedAddress": "..."},
          "latitude": 48.8566,
          "longitude": 2.3522,
          "reference": "ChIJ...",
          "referenceType": "GOOGLE_PLACES"
        }
    """
    cookies = load_ubereats_cookies()
    cookies = update_uev2_loc(cookies, payload)
    save_ubereats_cookies(cookies)
    return payload
