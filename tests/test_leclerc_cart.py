"""Unit tests for Leclerc Drive cart adapter."""

from __future__ import annotations

import asyncio
import json
import urllib.parse
from pathlib import Path

import httpx
import pytest

from app.services.scrapers.leclerc_cart import (
    LeclercCartAuthError,
    LeclercCartError,
    LeclercCartNotFoundError,
    LeclercCartStoreContextError,
    build_leclerc_cart_client,
    parse_leclerc_cart_response,
    parse_leclerc_detail_panier_html,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "leclerc"
BASE_URL = "https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran"


def _load_fixture() -> dict:
    with (FIXTURES / "cart_response.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_parse_leclerc_cart_response():
    data = _load_fixture()
    state = parse_leclerc_cart_response(data)
    assert state.store_id == "123111"
    assert state.amount == 18.20
    assert state.items_count == 2
    assert len(state.items) == 2
    assert state.items[0].item_id == "32452"
    assert state.items[0].quantity == 2
    assert state.items[0].price == 1.15
    assert state.items[1].item_id == "129009"
    assert state.items[1].quantity == 4


def test_leclerc_cart_missing_base_url():
    with pytest.raises(LeclercCartStoreContextError) as exc_info:
        build_leclerc_cart_client([], store_base_url="")
    assert "Leclerc store base URL is not configured" in str(exc_info.value)


def test_leclerc_cart_read():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "panier.aspx?op=12" in str(request.url)
        return httpx.Response(200, json=payload)

    client = build_leclerc_cart_client([], store_base_url=BASE_URL, transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.get_or_read_cart()
            assert state.amount == 18.20
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_leclerc_cart_add_item():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = request.content.decode("utf-8")
        parsed_body = urllib.parse.parse_qs(body)
        d_val = json.loads(parsed_body["d"][0])
        assert d_val["eTypeAction"] == 1
        assert d_val["iIdProduit"] == "32452"
        assert d_val["iQuantite"] == 2
        return httpx.Response(200, json=payload)

    client = build_leclerc_cart_client([], store_base_url=BASE_URL, transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.add_item("32452", quantity=2)
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_leclerc_cart_update_quantity():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = request.content.decode("utf-8")
        parsed_body = urllib.parse.parse_qs(body)
        d_val = json.loads(parsed_body["d"][0])
        assert d_val["eTypeAction"] == 2
        assert d_val["iIdProduit"] == "32452"
        assert d_val["iQuantite"] == 5
        return httpx.Response(200, json=payload)

    client = build_leclerc_cart_client([], store_base_url=BASE_URL, transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.update_item_quantity("32452", quantity=5)
            assert state.amount == 18.20
        finally:
            await client.aclose()

    asyncio.run(run())


def test_leclerc_cart_remove_item():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = request.content.decode("utf-8")
        parsed_body = urllib.parse.parse_qs(body)
        d_val = json.loads(parsed_body["d"][0])
        assert d_val["eTypeAction"] == 2
        assert d_val["iIdProduit"] == "32452"
        assert d_val["iQuantite"] == 0
        return httpx.Response(200, json=payload)

    client = build_leclerc_cart_client([], store_base_url=BASE_URL, transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.remove_item("32452")
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_leclerc_cart_clear():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "op=3" in str(request.url)
        return httpx.Response(200, text='{"bSucces": true}')

    client = build_leclerc_cart_client([], store_base_url=BASE_URL, transport=httpx.MockTransport(handler))

    async def run():
        try:
            await client.clear_cart()
        finally:
            await client.aclose()

    asyncio.run(run())


def test_leclerc_cart_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="DataDome challenge")

    client = build_leclerc_cart_client([], store_base_url=BASE_URL, transport=httpx.MockTransport(handler))

    async def run():
        try:
            with pytest.raises(LeclercCartAuthError) as exc_info:
                await client.get_or_read_cart()
            assert "Session Leclerc expirée" in str(exc_info.value)
        finally:
            await client.aclose()

    asyncio.run(run())


def test_parse_leclerc_detail_panier_html():
    html_sample = """
    <html>
    <head></head>
    <body>
    <script>
    Utilitaires.widget.initOptions('ctl00_ctl00_mainMutiUnivers_main_ctl00_ucDetailPanier_pnlDetailPanier',{"objContenu":{"lstElements":[{"objElement":{"sTotalAPayer":"5,49 €","iQuantitePanier":2,"lstPanier":[],"lstEnfants":[{"objElement":{"sType":"Produit","iIdProduit":1010,"sLibelleLigne1":"Cr&#232;me enti&#232;re","sLibelleLigne2":"40cl","iQuantitePanier":2,"nrPVUnitaireTTC":2.99,"sPrixUnitaire":"2,99 €","sUrlVignetteProduit":"https://img.leclerc.fr/1010.webp"}}]}}]}});
    </script>
    </body>
    </html>
    """
    state = parse_leclerc_detail_panier_html(html_sample, plid="123111")
    assert state.store_id == "123111"
    assert state.amount == 5.49
    assert state.items_count == 2
    assert len(state.items) == 1
    assert state.items[0].id == "1010"
    assert state.items[0].name == "Crème entière 40cl"
    assert state.items[0].quantity == 2
    assert state.items[0].price == 2.99
    assert state.items[0].price_text == "2,99 €"
    assert state.items[0].image == "https://img.leclerc.fr/1010.webp"

