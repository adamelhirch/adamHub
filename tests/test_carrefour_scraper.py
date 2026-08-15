"""Offline tests for the Carrefour JSON scraper.

Fixtures under `tests/fixtures/carrefour/` are derived from the bodies captured
in `data/live-capture/carrefourr-recherche.har` (the `/s?q=lait` SSR body and
the POST `/api/marketing/search` body). No network access is required.
"""

import asyncio
import json
from pathlib import Path

import pytest

from app.models import SupermarketStore
from app.services.scrapers.carrefour import (
    CARREFOUR_BASE_URL,
    CARREFOUR_SORT_KEYS,
    build_carrefour_cookie_jar,
    load_carrefour_cookies,
    parse_carrefour_search,
    parse_carrefour_search_json,
    search_carrefour,
)
from app.services.store_catalog import normalize_search_result

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "carrefour"


def _load(name: str):
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_parse_carrefour_search_json_maps_full_product():
    payload = _load("search_page1.json")
    items = parse_carrefour_search_json(payload, max_results=30)

    assert len(items) == 30
    first = next(item for item in items if item["id"] == "3428272950057")
    assert first["name"] == "Lait Demi-Ecrémé UHT Bio LACTEL"
    assert first["brand"] == "LACTEL"
    assert first["category"] == "Crèmerie et Produits laitiers"
    assert first["packaging"] == "la bouteille 1L"
    assert first["price"] == "1,58 € (1.58 € / L)"
    assert first["image"].startswith("https://media.carrefour.fr/medias/")
    assert "p_200x200" in first["image"]
    assert first["product_url"] == (
        f"{CARREFOUR_BASE_URL}/p/lait-demi-ecreme-uht-bio-lactel-3428272950057"
    )
    assert first["store"] == "Carrefour"


def test_parse_carrefour_search_json_normalize_contract():
    payload = _load("search_page1.json")
    items = parse_carrefour_search_json(payload, max_results=5)

    normalized = [
        normalize_search_result(SupermarketStore.CARREFOUR, "lait", item)
        for item in items
    ]
    assert len(normalized) == 5
    first = normalized[0]
    assert first["external_id"] == "3428272950057"
    assert first["price_amount"] == 1.58
    assert first["price_text"] == "1,58 € (1.58 € / L)"
    assert first["image_url"].startswith("https://media.carrefour.fr/medias/")
    assert first["product_url"].endswith("-3428272950057")


def test_parse_carrefour_search_json_respects_max_results_and_dedupes():
    payload = _load("search_page1.json")
    items = parse_carrefour_search_json(payload, max_results=10)
    assert len(items) == 10
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))


def test_parse_carrefour_search_json_promotions_only():
    payload = _load("search_page1.json")
    all_items = parse_carrefour_search_json(payload, max_results=30)
    promo_items = parse_carrefour_search_json(
        payload, max_results=30, promotions_only=True
    )

    assert 0 < len(promo_items) < len(all_items)
    for item in promo_items:
        assert item["id"] in {p["id"] for p in all_items}


def test_parse_carrefour_search_json_skips_invalid_products():
    payload = {
        "data": [
            {"attributes": {"ean": "123", "title": "Bon"}},
            {"attributes": {"title": "pas d'ean"}},
            {"attributes": {"ean": "456"}},
            "not-a-product",
            None,
            {"attributes": {"ean": "123", "title": "doublon"}},
        ]
    }
    items = parse_carrefour_search_json(payload, max_results=10)
    assert len(items) == 1
    assert items[0]["id"] == "123"


def test_parse_carrefour_search_marketing_groups():
    payload = _load("marketing_search.json")
    items = parse_carrefour_search(payload, max_results=30)

    assert len(items) >= 10
    first = next(item for item in items if item["id"] == "3428272950057")
    assert first["name"] == "Lait Demi-Ecrémé UHT Bio LACTEL"
    assert first["price"].startswith("1,58 €")
    assert first["product_url"].startswith(CARREFOUR_BASE_URL)


def test_parse_carrefour_search_marketing_groups_promotions_only():
    payload = _load("marketing_search.json")
    all_items = parse_carrefour_search(payload, max_results=30)
    promo_items = parse_carrefour_search(
        payload, max_results=30, promotions_only=True
    )

    assert len(promo_items) > 0
    assert len(promo_items) <= len(all_items)


def test_carrefour_sort_keys_are_observed_values():
    expected = {
        "price_asc": "offers.prices.effective_price",
        "price_desc": "-offers.prices.effective_price",
        "price_per_unit_asc": "offers.prices.standard_price_per_unit.price_per_unit_value",
        "price_per_unit_desc": "-offers.prices.standard_price_per_unit.price_per_unit_value",
        "best_rated": "-product.customer_review.average",
    }
    assert CARREFOUR_SORT_KEYS == expected


def test_carrefour_cookie_helpers_roundtrip():
    cookies = load_carrefour_cookies()
    jar = build_carrefour_cookie_jar(cookies)
    assert jar is not None
    # Loading without a file on disk returns an empty list (no crash).
    assert load_carrefour_cookies(FIXTURES / "does-not-exist.json") == []


def test_search_carrefour_raises_without_cookies_offline():
    with pytest.raises(RuntimeError):
        asyncio.run(search_carrefour(queries=["lait"], cookies=[]))


def _monkeypatch_transport(monkeypatch, handler) -> None:
    """Route the scraper's httpx.AsyncClient onto a MockTransport.

    Patches the module-level `httpx` module so the scraper's AsyncClient call
    gets a transport, while keeping the rest of httpx intact.
    """
    import httpx as real_httpx

    class _MockClient(real_httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = real_httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("app.services.scrapers.carrefour.httpx", real_httpx)
    monkeypatch.setattr("app.services.scrapers.carrefour.httpx.AsyncClient", _MockClient)


def test_search_carrefour_wires_sort_param_and_parses_offline(monkeypatch, tmp_path):
    import asyncio as _asyncio

    payload = _load("search_page1.json")
    seen: list[str] = []

    def handler(request):
        seen.append(str(request.url))
        return _handler_response(payload)

    _monkeypatch_transport(monkeypatch, handler)
    _monkeypatch_cookie_file(monkeypatch, tmp_path)

    results = _asyncio.run(
        search_carrefour(queries=["lait"], max_results=10, sort_by="price_desc")
    )

    assert len(seen) == 1
    assert "sort=-offers.prices.effective_price" in seen[0]
    assert "q=lait" in seen[0]
    assert len(results["lait"]) == 10
    assert results["lait"][0]["store"] == "Carrefour"


def test_search_carrefour_follows_next_page_links_offline(monkeypatch, tmp_path):
    import asyncio as _asyncio
    import httpx

    page1 = _load("search_page1.json")
    page2 = json.loads(json.dumps(page1))
    page1["links"]["next"] = "/s?q=lait&page=2"
    # Trim page 1 to a handful so pagination is exercised.
    page1["data"] = page1["data"][:5]
    page2["data"] = page2["data"][5:12]
    page2["links"]["next"] = None

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        body = page2 if "page=2" in str(request.url) else page1
        return httpx.Response(200, json=body, headers={"content-type": "application/json"})

    _monkeypatch_transport(monkeypatch, handler)
    _monkeypatch_cookie_file(monkeypatch, tmp_path)

    results = _asyncio.run(search_carrefour(queries=["lait"], max_results=12))

    assert len(seen) == 2
    assert any("page=2" in url for url in seen)
    assert len(results["lait"]) == 12


def _handler_response(payload: dict):
    import httpx

    return httpx.Response(200, json=payload, headers={"content-type": "application/json"})


def _monkeypatch_cookie_file(monkeypatch, tmp_path) -> None:
    """Point the scraper at a throwaway cookie file so no real file is needed."""
    fake_cookie_file = tmp_path / "cookies.json"
    fake_cookie_file.write_text(
        json.dumps([{"name": "FRO_SESSION_ID", "value": "x", "domain": ".carrefour.fr", "path": "/"}])
    )
    monkeypatch.setattr(
        "app.services.scrapers.carrefour.CARREFOUR_COOKIES_PATH", fake_cookie_file
    )
