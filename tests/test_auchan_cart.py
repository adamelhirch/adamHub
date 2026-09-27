"""Unit tests for Auchan cart adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.services.scrapers.auchan_cart import (
    AUCHAN_CART_BASE_URL,
    AuchanCartAuthError,
    AuchanCartError,
    AuchanCartNotFoundError,
    AuchanCartStoreContextError,
    build_auchan_cart_client,
    parse_auchan_cart_response,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "auchan"


def _load_fixture() -> dict:
    with (FIXTURES / "cart_response.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_parse_auchan_cart_response():
    data = _load_fixture()
    state = parse_auchan_cart_response(data)
    assert state.cart_id == "14382b45-6789-abcd-ef01-23456789abcd"
    assert state.amount == 16.75
    assert state.items_count == 2
    assert state.seller_id == "4c663296-54a8-45f6-b385-0be86b4dfe98"
    assert len(state.items) == 2
    assert state.items[0].id == "line-auchan-1"
    assert state.items[0].item_id == "e7ab4048-1234-abcd-5678-abcdef012345"
    assert state.items[0].offer_id == "c21f64ea-5678-abcd-1234-fedcba543210"
    assert state.items[0].quantity == 3
    assert state.items[0].price == 1.05
    assert state.items[1].id == "line-auchan-2"
    assert state.items[1].item_id == "f8bc5159-2345-bcde-6789-bcdef0123456"
    assert state.items[1].quantity == 4
    assert state.items[1].price == 3.40


def test_auchan_cart_read_success():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url).startswith(f"{AUCHAN_CART_BASE_URL}/mine")
        return httpx.Response(200, json=payload)

    client = build_auchan_cart_client([], consent_id="test-consent", transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.get_or_read_cart()
            assert state.amount == 16.75
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_auchan_cart_add_item():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=payload)
        assert request.method == "POST"
        assert "items" in str(request.url)
        body = json.loads(request.content.decode("utf-8"))
        assert body["productId"] == "e7ab4048-1234-abcd-5678-abcdef012345"
        assert body["desiredQuantity"] == 3
        return httpx.Response(200, json=payload)

    client = build_auchan_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            state = await client.add_item("e7ab4048-1234-abcd-5678-abcdef012345", quantity=3)
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_auchan_cart_update_quantity():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=payload)
        assert request.method == "PATCH"
        assert "items/line-auchan-1" in str(request.url)
        body = json.loads(request.content.decode("utf-8"))
        assert body["desiredQuantity"] == 5
        return httpx.Response(200, json=payload)

    client = build_auchan_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            # initialize cart_id
            await client.get_or_read_cart()
            state = await client.update_item_quantity("line-auchan-1", quantity=5)
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_auchan_cart_remove_item():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=payload)
        assert request.method == "DELETE"
        assert "items/line-auchan-1" in str(request.url)
        return httpx.Response(200, json=payload)

    client = build_auchan_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            await client.get_or_read_cart()
            state = await client.remove_item("line-auchan-1")
            assert len(state.items) == 2
        finally:
            await client.aclose()

    asyncio.run(run())


def test_auchan_cart_clear():
    payload = _load_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=payload)
        assert request.method == "DELETE"
        assert str(request.url).startswith(f"{AUCHAN_CART_BASE_URL}/14382b45-6789-abcd-ef01-23456789abcd")
        return httpx.Response(204)

    client = build_auchan_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            await client.get_or_read_cart()
            await client.clear_cart()
        finally:
            await client.aclose()

    asyncio.run(run())


def test_auchan_cart_auth_error_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    client = build_auchan_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            with pytest.raises(AuchanCartAuthError):
                await client.get_or_read_cart()
        finally:
            await client.aclose()

    asyncio.run(run())


def test_auchan_cart_store_context_error_422():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "Invalid seller context"})

    client = build_auchan_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            with pytest.raises(AuchanCartStoreContextError):
                await client.get_or_read_cart()
        finally:
            await client.aclose()

    asyncio.run(run())


def test_auchan_cart_not_found_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Cart not found"})

    client = build_auchan_cart_client([], transport=httpx.MockTransport(handler))

    async def run():
        try:
            with pytest.raises(AuchanCartNotFoundError):
                await client.get_or_read_cart()
        finally:
            await client.aclose()

    asyncio.run(run())
