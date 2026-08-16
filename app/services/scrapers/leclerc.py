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

from app.services.scrapers.proxy_session import ProxySession

try:  # pragma: no cover - exercised via CURL_CFFI_AVAILABLE flag in tests
    from curl_cffi.requests import AsyncSession as CurlCffiAsyncSession
    from curl_cffi.requests.cookies import Cookies as CurlCffiCookies

    CURL_CFFI_AVAILABLE = True
except ImportError:
    CurlCffiAsyncSession = None  # type: ignore[assignment]
    CurlCffiCookies = None  # type: ignore[assignment]
    CURL_CFFI_AVAILABLE = False

# curl_cffi impersonation target. DataDome fingerprints the TLS/HTTP2
# handshake, not just the User-Agent: curl_cffi's `chrome` profile reproduces a
# real Chrome handshake, which defeats the 403 challenge that plain httpx hits
# even with fresh cookies (confirmed empirically: impersonate=chrome on
# recherche.aspx returns 200 while httpx gets the DataDome probe).
CURL_IMPERSONATE = "chrome"

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


def _build_curl_cookie_jar(cookies: list[dict[str, Any]]) -> CurlCffiCookies:
    jar = CurlCffiCookies()
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        jar.set(name, value, domain=cookie.get("domain"), path=cookie.get("path", "/"))
    return jar


def _resolve_store_base_url(store_base_url: str | None) -> str:
    """Return the store base URL, from the explicit arg or the env var.

    The env var is read at call time (not module import time): the value lives
    in the local `.env` (docker-compose `env_file` exports it into the process
    env) or in the operator's shell, and a long-running worker must pick it up
    when it appears after the module was first imported.
    """
    configured = (
        os.environ.get("ADAMHUB_LECLERC_BASE_URL") or LECLERC_DEFAULT_BASE_URL
    )
    base = (store_base_url or configured or "").rstrip("/")
    if not base:
        raise LeclercAuthError(
            "Leclerc store base URL is not configured. Set ADAMHUB_LECLERC_BASE_URL "
            "to the store subdomain + magasin path (e.g. "
            "https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran) "
            "obtained after selecting a Drive store."
        )
    return base


def _clean_text(value: Any) -> str | None:
    """Normalize an HTML-escaped product field (collapse runs of whitespace)."""
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", unescape(str(value)))
    return cleaned.strip() or None


# Matches `Utilitaires.widget.initOptions('...pnlElementProduit', {..});` and
# captures the JSON payload. The `.*?` (non-greedy) scan is safe on the live
# page: the first `})` after the opening `{` is the call's own close.
_INIT_OPTIONS_PRODUCTS_RE = re.compile(
    r"initOptions\(['\"][^'\"]*pnlElementProduit['\"],\s*(\{.*?\})\);",
    re.DOTALL,
)


def _iter_product_blobs(html: str) -> list[dict[str, Any]]:
    """Parse every `pnlElementProduit` initOptions payload in the page.

    The search page can embed several product-list widgets (main results,
    suggestion carousels...). The empirical curl_cffi capture showed the first
    blob in document order can be a names-only carousel whose entries carry no
    price or id, shadowing the main list — so every blob is parsed and merged
    downstream (see `parse_leclerc_search_html`).
    """
    payloads: list[dict[str, Any]] = []
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if "pnlElementProduit" not in text:
            continue
        for match in _INIT_OPTIONS_PRODUCTS_RE.finditer(text):
            try:
                payload = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


def _iter_product_objects(elements: list[Any]) -> list[dict[str, Any]]:
    """Yield `objElement` dicts from `lstElements` entries.

    Descends into `lstEnfants` (declinaison/variant groups): a grouped card can
    have a label-only `objElement` while the full product (id + price) lives on
    the child, so children are walked recursively and their objects collected
    too.
    """
    products: list[dict[str, Any]] = []
    for entry in elements:
        if not isinstance(entry, dict):
            continue
        obj = entry.get("objElement")
        if isinstance(obj, dict):
            products.append(obj)
        children = entry.get("lstEnfants")
        if isinstance(children, list):
            products.extend(_iter_product_objects(children))
    return products


def _extract_product_id(product: dict[str, Any]) -> str | None:
    """Leclerc product id from `iIdProduit` / `sId` / `sIdUnique`.

    `sIdUnique` is a display key of the form `Produit{id}` (confirmed in the
    live capture); the numeric id is what the cart APIs consume.
    """
    raw = product.get("iIdProduit")
    if raw is None:
        raw = product.get("sId")
    if raw is None:
        raw = product.get("sIdUnique")
        if isinstance(raw, str) and raw.startswith("Produit"):
            raw = raw[len("Produit") :]
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _format_leclerc_price(amount: Any) -> str | None:
    """Format a numeric TTC amount the way the site displays it ("6,72 €")."""
    if not isinstance(amount, (int, float)) or amount <= 0:
        return None
    return f"{amount:.2f}".replace(".", ",") + " €"


def _extract_product_price(product: dict[str, Any]) -> str | None:
    """Displayed price from `sPrixUnitaire`, falling back to the numeric amount.

    The live capture can serve an entry whose displayed string is empty while
    `nrPVUnitaireTTC` still carries the amount — the numeric fallback keeps the
    price from being dropped.
    """
    price = _clean_text(product.get("sPrixUnitaire"))
    if price:
        return price
    return _format_leclerc_price(product.get("nrPVUnitaireTTC"))


def _product_to_search_result(product: dict[str, Any]) -> dict[str, str | None] | None:
    name = _clean_text(product.get("sLibelleLigne1"))
    if not name:
        return None
    ext_id = _extract_product_id(product)
    category = product.get("sCategorie")
    return {
        "id": ext_id,
        "name": name,
        "brand": None,
        "category": str(category) if category is not None else None,
        "packaging": _clean_text(product.get("sLibelleLigne2")),
        "price": _extract_product_price(product),
        "price_per_unit": _clean_text(product.get("sPrixParUniteDeMesure")),
        "image": product.get("sUrlVignetteProduit"),
        "product_url": product.get("sUrlPageProduit"),
        "store": "Leclerc",
    }


def parse_leclerc_search_html(html: str, max_results: int) -> list[dict[str, str | None]]:
    """Parse the embedded product JSON out of a `recherche.aspx` response.

    The product list lives in `initOptions('...pnlElementProduit', {..})` whose
    JSON has `objContenu.lstElements[].objElement` entries with the fields:
    iIdProduit, sLibelleLigne1 (name), sLibelleLigne2 (format), sPrixUnitaire,
    sPrixParUniteDeMesure, sUrlVignetteProduit, sUrlPageProduit, sCategorie.
    The selector was confirmed against the live `fd7-courses.leclercdrive.fr`
    capture (data/live-capture/fd7-courses.leclercdrive.fr.har, 936 KB HTML).

    Every `pnlElementProduit` blob is merged (a names-only suggestion carousel
    must not shadow the main list) and `lstEnfants` children are walked so a
    grouped card's full product (id + price) is never dropped.
    """
    collected: dict[str, dict[str, str | None]] = {}
    # name -> key in `collected`: lets an id-ed product evict the earlier
    # name-only placeholder for the same product (grouped card / shadow blob).
    name_to_key: dict[str, str] = {}
    for payload in _iter_product_blobs(html):
        elements = (payload.get("objContenu") or {}).get("lstElements") or []
        if not isinstance(elements, list):
            continue
        for product in _iter_product_objects(elements):
            item = _product_to_search_result(product)
            if item is None:
                continue
            name = item["name"]
            if item["id"] is not None:
                key = item["id"]
                stale_key = name_to_key.get(name)
                if (
                    stale_key is not None
                    and stale_key != key
                    and collected.get(stale_key, {}).get("id") is None
                ):
                    # Evict the label-only placeholder (grouped parent /
                    # names-only carousel) once the full product appears.
                    del collected[stale_key]
                    del name_to_key[name]
            else:
                if name_to_key.get(name) is not None:
                    # A full or placeholder entry already covers this name.
                    continue
                key = name
            previous = collected.get(key)
            if previous is None or (
                (previous["price"] is None and item["price"] is not None)
                or (previous["id"] is None and item["id"] is not None)
            ):
                collected[key] = item
                name_to_key[name] = key
    return list(collected.values())[:max_results]


# Leclerc Drive is server-rendered; a coherent Chrome UA and the cookie-bearing
# session are required. Some actions are gated behind DataDome/hCaptcha.
_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)


def _build_headers(referer: str, *, impersonated: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr,en;q=0.9",
        "Referer": referer,
    }
    if not impersonated:
        # Only the plain-httpx path sets its own User-Agent. When curl_cffi
        # impersonates, it fills User-Agent + sec-ch-ua from its own Chrome
        # profile — sending our hardcoded UA would desync the fingerprint.
        headers["User-Agent"] = _CHROME_USER_AGENT
    return headers


def _raise_for_auth(response: httpx.Response) -> None:
    # DataDome answers 403 with a JS probe page (`var dd={...}`, "Please enable
    # JS and disable any ad blocker") — detect it before the generic 403 branch
    # so the operator knows a fresh cookie session is required. Confirmed live:
    # both a bare request and the captured (stale) session get this challenge.
    body = response.text or ""
    if response.status_code == 403 and (
        "var dd=" in body or "datadome" in body.lower()[:4000] or "Please enable JS" in body[:500]
    ):
        raise LeclercAuthError(
            "Leclerc returned an anti-bot challenge (DataDome). A fresh cookie "
            "session is required."
        )
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
    *,
    store_base_url: str | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    """Search Leclerc Drive by scraping `recherche.aspx` and parsing its JSON.

    The request runs through a curl_cffi session impersonating Chrome
    (``impersonate=chrome``) when curl_cffi is installed — DataDome fingerprints
    the TLS/HTTP2 handshake and 403s plain httpx even with fresh cookies —
    falling back to httpx when curl_cffi is unavailable. ``_raise_for_auth``
    still detects the DataDome challenge on both transports.

    ``store_base_url`` is the store subdomain + magasin path (or the
    ``ADAMHUB_LECLERC_BASE_URL`` env var). ``sort_by`` maps through
    ``LECLERC_SORT_IDS`` to the site's ``tri`` query param (datasource ids
    1..6 confirmed in the live capture). ``promotions_only`` is accepted for
    interface parity and ignored: Leclerc has no promotions-only query flag on
    `recherche.aspx` (promos live on a separate page), so the store definition
    exposes ``supports_promotions`` so callers can skip the flag.
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

    scope = f"leclerc:{json.dumps(queries, ensure_ascii=False)}"

    def _build_httpx_client(proxy_url: str | None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            cookies=build_leclerc_cookie_jar(cookies),
            proxy=proxy_url,
            timeout=httpx.Timeout(30.0),
            trust_env=not proxy_url,
            follow_redirects=True,
        )

    def _build_curl_cffi_client(proxy_url: str | None) -> CurlCffiAsyncSession:
        # DataDome flags the pool's shared egress IPs even with impersonation
        # (same as Cloudflare for Carrefour) — the direct connection with the
        # impersonated handshake clears the challenge, so the proxy is
        # intentionally ignored on this path.
        del proxy_url
        return CurlCffiAsyncSession(
            impersonate=CURL_IMPERSONATE,
            base_url=base,
            cookies=_build_curl_cookie_jar(cookies),
            timeout=30.0,
        )

    def _build_leclerc_client(proxy_url: str | None) -> Any:
        if CURL_CFFI_AVAILABLE:
            return _build_curl_cffi_client(proxy_url)
        return _build_httpx_client(proxy_url)

    session = ProxySession(scope, _build_leclerc_client)
    results: dict[str, list[dict[str, str | None]]] = {}
    try:
        for query in queries:
            params: dict[str, Any] = {"TexteRecherche": query}
            if tri is not None:
                params["tri"] = tri
            response = await session.client.get(
                f"{base}/recherche.aspx",
                params=params,
                headers=_build_headers(f"{base}/", impersonated=CURL_CFFI_AVAILABLE),
            )
            _raise_for_auth(response)
            response.raise_for_status()
            results[query] = parse_leclerc_search_html(
                response.text, max_results=max_results
            )
        session.release(ok=True)
    except Exception:
        session.release(ok=False)
        raise
    finally:
        await session.aclose()
    return results
