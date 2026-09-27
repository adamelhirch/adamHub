"""Unit tests for Carrefour cart adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.services.scrapers.carrefour_cart import (
    CARREFOUR_CART_BASE_URL,
    CarrefourCartAuthError,
    CarrefourCartError,
    CarrefourCartNotFoundError,
    build_carrefour_cart_client,
    parse_carrefour_cart_response,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "carrefour"


def _load_fixture() -> dict:
    with (FIXTURES / "cart_response.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_parse_carrefour_cart_response():
    data = _load_fixture()
    state = parse_carrefour_cart_response(data)
    assert state.cart_id == "cart-carrefour-12345"
    assert state.amount == 14.50
    assert state.items_count == 2
    assert len(state.items) == 2
    assert state.items[0].item_id == "32452"
    assert state.items[0].quantity == 2
    assert state.items[0].price == 1.10
    assert state.items[1].item_id == "89201"
    assert state.items[1].quantity == 3


def test_carrefour_cart_read_success():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == CARREFOUR_CART_BASE_URL
        return httpx.Response(200, json=payload)

    client = build_carrefour_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.get_or_read_cart()
            assert state.amount == 14.50
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_carrefour_cart_add_item():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{CARREFOUR_CART_BASE_URL}/items"
        body = json.loads(request.content.decode("utf-8"))
        assert body["productId"] == "32452"
        assert body["quantity"] == 2
        return httpx.Response(200, json=payload)

    client = build_carrefour_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.add_item("32452", quantity=2)
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_carrefour_cart_update_quantity():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert str(request.url) == f"{CARREFOUR_CART_BASE_URL}/items/32452"
        body = json.loads(request.content.decode("utf-8"))
        assert body["quantity"] == 5
        return httpx.Response(200, json=payload)

    client = build_carrefour_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.update_item_quantity("32452", quantity=5)
            assert state.amount == 14.50
        finally:
            await client.aclose()

    asyncio.run(run())


def test_carrefour_cart_remove_item():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert str(request.url) == f"{CARREFOUR_CART_BASE_URL}/items/32452"
        return httpx.Response(200, json=payload)

    client = build_carrefour_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.remove_item("32452")
            assert state.items_count == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_carrefour_cart_clear():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert str(request.url) == CARREFOUR_CART_BASE_URL
        return httpx.Response(204)

    client = build_carrefour_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            await client.clear_cart()
        finally:
            await client.aclose()

    asyncio.run(run())


def test_carrefour_cart_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Cloudflare challenge")

    client = build_carrefour_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            with pytest.raises(CarrefourCartAuthError) as exc_info:
                await client.get_or_read_cart()
            assert "Session Carrefour expirée" in str(exc_info.value)
        finally:
            await client.aclose()

    asyncio.run(run())


def test_carrefour_cart_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Cart not found")

    client = build_carrefour_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            with pytest.raises(CarrefourCartNotFoundError):
                await client.get_or_read_cart()
        finally:
            await client.aclose()

    asyncio.run(run())
