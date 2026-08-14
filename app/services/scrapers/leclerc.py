from __future__ import annotations

import json
import os
import re
import urllib.parse
from html import unescape
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

# Leclerc Drive serves search as server-rendered HTML on a store-specific
# subdomain (e.g. fd7-courses.leclercdrive.fr) once a point de livraison is
# selected. The product list is embedded in the page as a JSON blob inside a
# call to `Utilitaires.widget.initOptions('...pnlElementProduit', {..})`.
#
# The subdomain + `magasin-{plid}-{plid}-{slug}` path are store-specific; the
# operator must set ADAMHUB_LECLERC_BASE_URL to that store base (see the store
# selection flow: api-recherchemagasins.leclercdrive.fr). Without it the scraper
# cannot know which store to hit and raises a clear error.
LECLERC_DEFAULT_BASE_URL = os.environ.get(
    "ADAMHUB_LECLERC_BASE_URL", ""
).rstrip("/")

LECLERC_COOKIES_PATH = Path(__file__).resolve().parents[3] / "data" / "cookies_leclerc.json"

# `tri` query param -> Leclerc sort id (from the page's embedded sort widget).
LECLERC_SORT_IDS = {
    "default": 1,
    "price_asc": 2,
    "price_desc": 3,
    "price_per_unit_asc": 4,
    "price_per_unit_desc": 5,
    "best_rated": 6,
}


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


def _resolve_store_base_url(store_base_url: str | None) -> str:
    """Return the store base URL, from the explicit arg or the env var."""
    base = (store_base_url or LECLERC_DEFAULT_BASE_URL or "").rstrip("/")
    if not base:
        raise LeclercAuthError(
            "Leclerc store base URL is not configured. Set ADAMHUB_LECLERC_BASE_URL "
            "to the store subdomain + magasin path (e.g. "
            "https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran) "
            "obtained after selecting a Drive store."
        )
    return base


def parse_leclerc_search_html(html: str, max_results: int) -> list[dict[str, str | None]]:
    """Parse the embedded product JSON out of a `recherche.aspx` response.

    The product list lives in `initOptions('...pnlElementProduit', {..})` whose
    JSON has `objContenu.lstElements[].objElement` entries with the fields:
    iIdProduit, sLibelleLigne1 (name), sLibelleLigne2 (format), sPrixUnitaire,
    sPrixParUniteDeMesure, sUrlVignetteProduit, sUrlPageProduit, sCategorie.
    """
    soup = BeautifulSoup(html, "html.parser")

    # The JSON blob is inside a <script> whose text contains
    # initOptions('...pnlElementProduit', {...});
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if "pnlElementProduit" not in text:
            continue
        match = re.search(
            r"initOptions\(['\"][^'\"]*pnlElementProduit['\"],\s*(\{.*?\})\);",
            text,
            re.DOTALL,
        )
        if not match:
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        elements = (
            payload.get("objContenu", {}).get("lstElements", [])
            if isinstance(payload, dict)
            else []
        )
        results: list[dict[str, str | None]] = []
        for entry in elements:
            product = entry.get("objElement") if isinstance(entry, dict) else None
            if not isinstance(product, dict):
                continue
            name = (unescape(product.get("sLibelleLigne1") or "")).strip()
            if not name:
                continue
            ext_id = product.get("iIdProduit") or product.get("sId")
            results.append(
                {
                    "id": str(ext_id) if ext_id is not None else None,
                    "name": name,
                    "brand": None,
                    "category": str(product["sCategorie"]) if product.get("sCategorie") is not None else None,
                    "packaging": unescape(product.get("sLibelleLigne2") or "").strip() or None,
                    "price": unescape(product.get("sPrixUnitaire") or "").strip() or None,
                    "price_per_unit": unescape(product.get("sPrixParUniteDeMesure") or "").strip() or None,
                    "image": product.get("sUrlVignetteProduit"),
                    "product_url": product.get("sUrlPageProduit"),
                }
            )
            if len(results) >= max_results:
                break
        return results

    return []


# Leclerc Drive is server-rendered; a coherent Chrome UA and the cookie-bearing
# session are required. Some actions are gated behind DataDome/hCaptcha.
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
        raise LeclercAuthError(
            "Leclerc rejected the current session. "
            "Refresh `data/cookies_leclerc.json` from a logged-in browser session "
            "with a Drive store selected."
        )
    # DataDome blocks with a 403 challenge page; surface it clearly.
    if response.status_code == 403 or "datadome" in response.text.lower()[:2000]:
        raise LeclercAuthError(
            "Leclerc returned an anti-bot challenge (DataDome). A fresh cookie "
            "session is required."
        )


async def search_leclerc(
    queries: list[str],
    max_results: int = 30,
    sort_by: str | None = None,
    promotions_only: bool = False,
    cookies: list[dict[str, Any]] | None = None,
    *,
    store_base_url: str | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    """Search Leclerc Drive by scraping `recherche.aspx` and parsing its JSON.

    ``store_base_url`` is the store subdomain + magasin path (or the
    ``ADAMHUB_LECLERC_BASE_URL`` env var). ``promotions_only`` is not wired to
    the request (Leclerc has no promotions-only query flag); it is accepted for
    interface parity and ignored.
    """
    del promotions_only
    base = _resolve_store_base_url(store_base_url)

    if cookies is None:
        cookies = load_leclerc_cookies()
    if not cookies:
        raise LeclercAuthError(
            "No Leclerc Drive cookies on disk. Provide `data/cookies_leclerc.json` "
            "exported from a logged-in browser session with a Drive store selected."
        )

    tri = LECLERC_SORT_IDS.get(sort_by) if sort_by else None

    proxy_url = get_leclerc_proxy_url()
    results: dict[str, list[dict[str, str | None]]] = {}
    async with httpx.AsyncClient(
        cookies=build_leclerc_cookie_jar(cookies),
        proxy=proxy_url,
        timeout=httpx.Timeout(30.0),
        trust_env=not proxy_url,
        follow_redirects=True,
    ) as client:
        for query in queries:
            params: dict[str, Any] = {"TexteRecherche": query}
            if tri is not None:
                params["tri"] = tri
            response = await client.get(
                f"{base}/recherche.aspx",
                params=params,
                headers=_build_headers(f"{base}/"),
            )
            _raise_for_auth(response)
            response.raise_for_status()
            results[query] = parse_leclerc_search_html(
                response.text, max_results=max_results
            )
    return results
