"""Offline tests proving the scrapers talk to the shared proxy pool.

Each scraper builds its httpx client through `proxy_session.ProxySession`,
which acquires a proxy for the whole search (sticky per scope) and releases it
at the end (ok=True on success, ok=False on failure). An empty pool yields a
direct connection. Intermarché's retry loop rotates the proxy on a block
signal (403 / DataDome / timeout): the failed proxy is released as blocked and
the next healthy one is acquired. All requests run through httpx.MockTransport
— no network access.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.services import proxy_pool

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _pool(monkeypatch, proxies: list[str], cooldown_seconds: int = 600) -> proxy_pool.ProxyPool:
    normalized = [p if p.startswith("http://") else f"http://{p}" for p in proxies]
    pool = proxy_pool.ProxyPool(normalized, cooldown_seconds=cooldown_seconds)
    monkeypatch.setattr(proxy_pool, "_pool", pool)
    return pool


def _empty_pool(monkeypatch) -> proxy_pool.ProxyPool:
    pool = proxy_pool.ProxyPool([], cooldown_seconds=600)
    monkeypatch.setattr(proxy_pool, "_pool", pool)
    return pool


def _handler_response(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, headers={"content-type": "application/json"})


def _intermarche_cookie() -> list[dict]:
    return [{"name": "itm_pdv", "value": '{"ref":"11131"}', "domain": ".intermarche.com", "path": "/"}]


def _monkeypatch_transport(monkeypatch, module: str, handler) -> None:
    """Route a scraper's httpx.AsyncClient onto a MockTransport.

    The real network is fully mocked, so the proxy argument is dropped from the
    client kwargs — with a proxy set, httpx wraps MockTransport in a
    ProxyTransport that would try a real TCP connect to the proxy host.
    For carrefour the httpx fallback path is forced (curl_cffi is preferred
    when installed) so the transport mock is actually exercised.
    """
    import httpx as real_httpx

    class _MockClient(real_httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.pop("proxy", None)
            kwargs.pop("trust_env", None)
            kwargs["transport"] = real_httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(f"app.services.scrapers.{module}.httpx.AsyncClient", _MockClient)
    if module == "carrefour":
        monkeypatch.setattr("app.services.scrapers.carrefour.CURL_CFFI_AVAILABLE", False)


# ---------------------------------------------------------------------------
# Intermarché: pool consulted + rotation on 403
# ---------------------------------------------------------------------------

def test_intermarche_acquires_and_releases_on_success(monkeypatch):
    from app.services.scrapers.intermarche import search_intermarche

    pool = _pool(monkeypatch, ["u:p@proxy-a.example:8000", "u:p@proxy-b.example:8001"])
    products = json.loads((FIXTURES / "intermarche_products.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/categories" in str(request.url):
            return _handler_response({"tree": []})
        return _handler_response(products)

    _monkeypatch_transport(monkeypatch, "intermarche", handler)

    results = asyncio.run(search_intermarche(queries=["lait"], cookies=_intermarche_cookie()))

    assert results["lait"]
    # The proxy is sticky per scope and stays healthy (release ok=True).
    assert pool.acquire('intermarche:["lait"]') == "http://u:p@proxy-a.example:8000"


def test_intermarche_rotates_proxy_on_403(monkeypatch):
    from app.services.scrapers.intermarche import search_intermarche

    pool = _pool(monkeypatch, ["u:p@proxy-a.example:8000", "u:p@proxy-b.example:8001"])
    products = json.loads((FIXTURES / "intermarche_products.json").read_text(encoding="utf-8"))
    calls = {"products": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/categories" in str(request.url):
            return _handler_response({"tree": []})
        calls["products"] += 1
        if calls["products"] == 1:
            return httpx.Response(403, text="datadome device check")
        return _handler_response(products)

    _monkeypatch_transport(monkeypatch, "intermarche", handler)

    results = asyncio.run(search_intermarche(queries=["lait"], cookies=_intermarche_cookie()))

    assert calls["products"] == 2  # 403 then success
    assert results["lait"]
    # The blocked proxy is in cooldown; a fresh scope now gets the next one.
    assert pool.acquire("other") == "http://u:p@proxy-b.example:8001"


def test_intermarche_empty_pool_runs_direct(monkeypatch):
    from app.services.scrapers.intermarche import search_intermarche

    _empty_pool(monkeypatch)
    products = json.loads((FIXTURES / "intermarche_products.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/categories" in str(request.url):
            return _handler_response({"tree": []})
        return _handler_response(products)

    _monkeypatch_transport(monkeypatch, "intermarche", handler)

    results = asyncio.run(search_intermarche(queries=["lait"], cookies=_intermarche_cookie()))
    assert results["lait"]


# ---------------------------------------------------------------------------
# Carrefour: pool consulted + releases as failed on auth error
# ---------------------------------------------------------------------------

def test_carrefour_acquires_and_releases_on_success(monkeypatch, tmp_path):
    from app.services.scrapers.carrefour import search_carrefour

    pool = _pool(monkeypatch, ["u:p@proxy-a.example:8000", "u:p@proxy-b.example:8001"])
    page1 = json.loads((FIXTURES / "carrefour" / "search_page1.json").read_text(encoding="utf-8"))
    page1["links"]["next"] = None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page1, headers={"content-type": "application/json"})

    _monkeypatch_transport(monkeypatch, "carrefour", handler)

    results = asyncio.run(
        search_carrefour(
            queries=["lait"],
            max_results=5,
            cookies=[{"name": "FRO_SESSION_ID", "value": "x", "domain": ".carrefour.fr", "path": "/"}],
        )
    )

    assert results["lait"]
    assert pool.acquire('carrefour:["lait"]') == "http://u:p@proxy-a.example:8000"


def test_carrefour_releases_failed_proxy_on_403(monkeypatch):
    from app.services.scrapers.carrefour import search_carrefour

    pool = _pool(monkeypatch, ["u:p@proxy-a.example:8000", "u:p@proxy-b.example:8001"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    _monkeypatch_transport(monkeypatch, "carrefour", handler)

    with pytest.raises(Exception, match="rejected the current session"):
        asyncio.run(
            search_carrefour(
                queries=["lait"],
                cookies=[{"name": "FRO_SESSION_ID", "value": "x", "domain": ".carrefour.fr", "path": "/"}],
            )
        )

    # The failed proxy went into cooldown; the next scope gets the other one.
    assert pool.acquire("other") == "http://u:p@proxy-b.example:8001"


# ---------------------------------------------------------------------------
# Leclerc / Auchan: pool consulted, empty pool runs direct
# ---------------------------------------------------------------------------

def test_leclerc_acquires_pool_proxy(monkeypatch):
    from app.services.scrapers.leclerc import search_leclerc

    pool = _pool(monkeypatch, ["u:p@proxy-a.example:8000"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html></html>")

    _monkeypatch_transport(monkeypatch, "leclerc", handler)

    results = asyncio.run(
        search_leclerc(
            queries=["lait"],
            cookies=[{"name": "x", "value": "y", "domain": ".leclercdrive.fr"}],
            store_base_url="https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran",
        )
    )
    assert results["lait"] == []
    assert pool.acquire('leclerc:["lait"]') == "http://u:p@proxy-a.example:8000"


def test_auchan_empty_pool_runs_direct(monkeypatch):
    from app.services.scrapers.auchan import search_auchan

    _empty_pool(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/journey" in str(request.url):
            return httpx.Response(200, json={"id": "j1", "activeContexts": []})
        if "/recherche" in str(request.url):
            return httpx.Response(200, text="<html><body></body></html>")
        return httpx.Response(200, text="")

    _monkeypatch_transport(monkeypatch, "auchan", handler)

    results = asyncio.run(
        search_auchan(
            queries=["lait"],
            cookies=[{"name": "x", "value": "y", "domain": ".auchan.fr"}],
        )
    )
    assert results["lait"] == []
