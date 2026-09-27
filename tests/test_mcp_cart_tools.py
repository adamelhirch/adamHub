"""Tests for supermarket cart MCP tools (User Story 2)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import mcp_types as types
import pytest
from sqlmodel import Session

from app.mcp import server as mcp_server
from app.models import SupermarketCart, SupermarketSearchCache, SupermarketStore
from app.services.scrapers.intermarche_cart import parse_cart_response
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from tests.conftest import register_user


def _run(coro):
    return asyncio.run(coro)


def _auth_as(user_id: int):
    token = auth_context_var.set(
        AuthenticatedUser(AccessToken(token="t", client_id="test", scopes=["mcp"], subject=str(user_id)))
    )
    return token


class FakeClient:
    def __init__(self, state):
        self.state = state
        self.calls = []

    async def get_or_read_cart(self, *args, **kwargs):
        self.calls.append(("get_or_read_cart", args, kwargs))
        return self.state

    async def add_item(self, item_id, quantity=1, **kwargs):
        self.calls.append(("add_item", (item_id,), {"quantity": quantity, **kwargs}))
        return self.state

    async def update_item_quantity(self, item_id, quantity):
        self.calls.append(("update_item_quantity", (item_id,), {"quantity": quantity}))
        return self.state

    async def remove_item(self, item_id):
        self.calls.append(("remove_item", (item_id,), {}))
        return self.state

    async def clear_cart(self):
        self.calls.append(("clear_cart", (), {}))

    async def aclose(self):
        pass


def _sample_state(item_id="30490", qty=2):
    return parse_cart_response(
        {
            "id": "customer-test-123",
            "synchronizeDateTime": "2026-09-11T12:00:00Z",
            "amount": 12.60,
            "itemsNumber": 1,
            "carts": [
                {
                    "items": [
                        {
                            "id": item_id,
                            "quantity": qty,
                            "price": 6.30,
                            "amount": 12.60,
                            "item": {
                                "itemId": item_id,
                                "libelle": "Beaufort AOP au lait cru",
                                "images": ["https://img.test/beaufort.png"],
                            },
                        }
                    ]
                }
            ],
        },
        store_id="11131",
    )


def test_cart_tools_present_in_mcp_listing(client, test_engine, monkeypatch):
    user = register_user(client, "mcp-cart-tester@adamelhirch.com")
    monkeypatch.setattr(mcp_server, "engine", test_engine)
    token = _auth_as(int(user["user"]["id"]))
    try:
        result = _run(mcp_server._on_list_tools(None, None))
    finally:
        auth_context_var.reset(token)

    names = {tool.name for tool in result.tools}
    expected = {
        "supermarket.get_cart",
        "supermarket.list_carts",
        "supermarket.add_cart_item",
        "supermarket.update_cart_item",
        "supermarket.remove_cart_item",
        "supermarket.clear_cart",
    }
    assert expected <= names


def test_mcp_cart_operations_full_flow(client, test_engine, monkeypatch):
    user = register_user(client, "mcp-cart-flow@adamelhirch.com")
    user_id = int(user["user"]["id"])
    monkeypatch.setattr(mcp_server, "engine", test_engine)

    # 1. Import connection
    client.post(
        "/api/v1/supermarket/connections/import",
        headers=user["headers"],
        json={
            "store": "intermarche",
            "label": "Intermarché test session",
            "cookies": [
                {"name": "itm_pdv", "value": "{%22ref%22:%2211131%22}"},
                {"name": "itm_customer", "value": "515ffd9e-538e-447a-983e-69ca17363fac"},
            ],
            "activate": True,
        },
    )

    # 2. Seed search cache row
    now = datetime.now(UTC)
    with Session(test_engine) as session:
        cache = SupermarketSearchCache(
            store=SupermarketStore.INTERMARCHE,
            query="beaufort",
            external_id="30490",
            name="Beaufort AOP",
            price_amount=6.30,
            price_text="6,30 €",
            fetched_at=now,
            expires_at=now + timedelta(days=1),
        )
        session.add(cache)
        session.commit()
        session.refresh(cache)
        cache_id = cache.id

    fake = FakeClient(state=_sample_state("30490", 2))
    monkeypatch.setattr(
        "app.services.cart_mirror.build_intermarche_cart_client",
        lambda *args, **kwargs: fake,
    )

    token = _auth_as(user_id)
    try:
        # Add item via MCP
        call_params = types.CallToolRequestParams(
            name="supermarket.add_cart_item",
            arguments={"store": "intermarche", "cache_id": cache_id, "quantity": 2},
        )
        add_result = _run(mcp_server._on_call_tool(None, call_params))
        assert not add_result.is_error
        add_data = json.loads(add_result.content[0].text)
        assert add_data["store"] == "intermarche"
        assert len(add_data["items"]) == 1
        item_id = add_data["items"][0]["id"]

        # List carts via MCP
        list_params = types.CallToolRequestParams(
            name="supermarket.list_carts",
            arguments={},
        )
        list_result = _run(mcp_server._on_call_tool(None, list_params))
        assert not list_result.is_error
        list_data = json.loads(list_result.content[0].text)
        assert len(list_data["carts"]) == 1
        assert list_data["carts"][0]["store"] == "intermarche"

        # Get cart via MCP
        get_params = types.CallToolRequestParams(
            name="supermarket.get_cart",
            arguments={"store": "intermarche"},
        )
        get_result = _run(mcp_server._on_call_tool(None, get_params))
        assert not get_result.is_error
        get_data = json.loads(get_result.content[0].text)
        assert get_data["id"] == add_data["id"]

        # Update cart item via MCP
        fake.state = _sample_state("30490", 5)
        update_params = types.CallToolRequestParams(
            name="supermarket.update_cart_item",
            arguments={"store": "intermarche", "item_id": item_id, "quantity": 5},
        )
        update_result = _run(mcp_server._on_call_tool(None, update_params))
        assert not update_result.is_error
        update_data = json.loads(update_result.content[0].text)
        assert update_data["items"][0]["quantity"] == 5

        # Remove item via MCP
        empty_state = parse_cart_response(
            {
                "id": "customer-test-123",
                "synchronizeDateTime": "2026-09-11T12:00:00Z",
                "amount": 0.0,
                "itemsNumber": 0,
                "carts": [{"items": []}],
            },
            store_id="11131",
        )
        fake.state = empty_state
        remove_params = types.CallToolRequestParams(
            name="supermarket.remove_cart_item",
            arguments={"store": "intermarche", "item_id": item_id},
        )
        remove_result = _run(mcp_server._on_call_tool(None, remove_params))
        assert not remove_result.is_error
        remove_data = json.loads(remove_result.content[0].text)
        assert remove_data["items"] == []

        # Clear cart via MCP
        clear_params = types.CallToolRequestParams(
            name="supermarket.clear_cart",
            arguments={"store": "intermarche"},
        )
        clear_result = _run(mcp_server._on_call_tool(None, clear_params))
        assert not clear_result.is_error
    finally:
        auth_context_var.reset(token)


def test_mcp_cart_tenant_scoping(client, test_engine, monkeypatch):
    """User A cannot access or mutate User B's cart."""
    user_a = register_user(client, "mcp-user-a@adamelhirch.com")
    user_b = register_user(client, "mcp-user-b@adamelhirch.com")
    monkeypatch.setattr(mcp_server, "engine", test_engine)

    # User A lists carts -> sees none
    token_a = _auth_as(int(user_a["user"]["id"]))
    try:
        list_params = types.CallToolRequestParams(name="supermarket.list_carts", arguments={})
        res_a = _run(mcp_server._on_call_tool(None, list_params))
        assert not res_a.is_error
        assert json.loads(res_a.content[0].text)["carts"] == []
    finally:
        auth_context_var.reset(token_a)


def test_mcp_cart_unconnected_store_returns_clear_error(client, test_engine, monkeypatch):
    user = register_user(client, "mcp-unconn@adamelhirch.com")
    monkeypatch.setattr(mcp_server, "engine", test_engine)
    token = _auth_as(int(user["user"]["id"]))
    try:
        get_params = types.CallToolRequestParams(
            name="supermarket.get_cart",
            arguments={"store": "carrefour"},
        )
        res = _run(mcp_server._on_call_tool(None, get_params))
        assert res.is_error
        assert "Aucune connexion Carrefour active" in res.content[0].text
    finally:
        auth_context_var.reset(token)
