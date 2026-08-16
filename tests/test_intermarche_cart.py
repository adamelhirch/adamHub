"""Offline tests for the Intermarché cart adapter.

The fixtures under ``tests/fixtures/intermarche/`` are reduced from the cart
traffic captured in the connected-session HAR (``intermarche.har``): the
``POST /api/service/panier/v1/stores/{store}/carts`` request/response pairs and
the session cookies. No network access is required — the adapter is exercised
through an ``httpx.AsyncClient`` built on ``httpx.MockTransport``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.services.scrapers.intermarche_cart import (
    INTERMARCHE_CART_BASE_URL,
    IntermarcheCartAuthError,
    IntermarcheCartClient,
    IntermarcheCartConflictError,
    IntermarcheCartError,
    IntermarcheCartItem,
    IntermarcheCartNotFoundError,
    IntermarcheCartState,
    build_cart_request_body,
    build_intermarche_cart_client,
    build_last_synchronized_cart,
    build_quantity_event,
    extract_customer_uuid_from_cookies,
    parse_cart_items,
    parse_cart_response,
)
from app.services.scrapers.intermarche import extract_pdv_ref_from_cookies

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "intermarche"

CUSTOMER_UUID = "515ffd9e-538e-447a-983e-69ca17363fac"
STORE_ID = "11131"


def _load(name: str):
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _cookies() -> list[dict]:
    return _load("cookies.json")


def _response(name: str) -> dict:
    return _load(name)


def _state(name: str = "cart_response_2_items.json") -> IntermarcheCartState:
    return parse_cart_response(_response(name), store_id=STORE_ID)


# ── Cookie / session identifier extraction ─────────────────────────────────────


def test_store_id_recovered_from_pdv_cookies():
    assert extract_pdv_ref_from_cookies(_cookies()) == STORE_ID


def test_extract_customer_uuid_returns_none_when_absent():
    # The observed session does not store the customer uuid in a cookie.
    assert extract_customer_uuid_from_cookies(_cookies()) is None


def test_extract_customer_uuid_finds_uuid_cookie():
    cookies = [
        {"name": "itm_session", "value": "7d190132-e690-4e5f-91b0-60f1f5ffac30"},
        {"name": "itm_customer", "value": CUSTOMER_UUID},
    ]
    assert extract_customer_uuid_from_cookies(cookies) == CUSTOMER_UUID


def test_extract_customer_uuid_from_json_cookie():
    cookies = [{"name": "novaParams", "value": f'{{"customerId":"{CUSTOMER_UUID}"}}'}]
    assert extract_customer_uuid_from_cookies(cookies) == CUSTOMER_UUID


def test_extract_customer_uuid_ignores_session_and_device_uuids():
    cookies = [
        {"name": "itm_session", "value": "7d190132-e690-4e5f-91b0-60f1f5ffac30"},
        {"name": "itm_device_id", "value": '{"id":"59c028d5-ac1a-45b3-9b82-54a65bdf29de"}'},
    ]
    assert extract_customer_uuid_from_cookies(cookies) is None


# ── Event & body construction ──────────────────────────────────────────────────


def test_build_quantity_event_add():
    event = build_quantity_event(
        "37731", 1, date_time="2026-08-15T03:02:26+02:00", tracking_code="bmF2"
    )
    assert event == {
        "catalog": "PDV",
        "itemId": "37731",
        "quantity": 1,
        "dateTime": "2026-08-15T03:02:26+02:00",
        "type": "QUANTITY",
        "trackingCode": "bmF2",
    }


def test_build_quantity_event_accept_substitution():
    event = build_quantity_event(
        "37731", 2, date_time="2026-08-15T03:02:26+02:00", accept_substitution=True
    )
    assert event["quantity"] == 2
    assert event["acceptSubstitution"] is True
    assert "trackingCode" not in event


def test_build_cart_request_body_replays_last_sync():
    state = _state()
    body = build_cart_request_body(
        events=[],
        last_sync=state,
        customer_date_time="2026-08-15T03:02:50+02:00",
    )
    assert body["customerDateTime"] == "2026-08-15T03:02:50+02:00"
    assert body["events"] == []
    replay = body["lastSynchronizedCart"]
    assert replay["synchronizeDateTime"].startswith("2026-08-15T03:02:28")
    # The replay keeps one PDV cart with the two trimmed line items.
    assert len(replay["carts"]) == 1
    cart = replay["carts"][0]
    assert cart["catalog"] == "PDV"
    assert cart["seller"] == {"id": "ITM", "name": "Intermarché"}
    assert [(i["id"], i["quantity"]) for i in cart["items"]] == [
        ("37731", 1),
        ("30490", 1),
    ]
    # The trimmed item echoes the product id (itemId), not the EAN, in idProduit.
    assert cart["items"][0]["item"]["itemId"] == "37731"
    assert cart["items"][0]["item"]["idProduit"] == "37731"
    assert cart["items"][0]["item"]["produitEan13"] == "2449185000000"


def test_build_cart_request_body_empty_cart_state():
    body = build_cart_request_body(
        events=[],
        last_sync=None,
        customer_date_time="2026-08-15T03:00:47+02:00",
    )
    assert body["events"] == []
    assert body["lastSynchronizedCart"] == {"carts": [], "synchronizeDateTime": None}


def test_build_last_synchronized_cart_trims_full_response():
    payload = _response("cart_response_2_items.json")
    replay = build_last_synchronized_cart(payload, "2026-08-15T03:02:28+02:00")
    assert replay["synchronizeDateTime"] == "2026-08-15T03:02:28+02:00"
    cart = replay["carts"][0]
    item = cart["items"][0]
    # Top-level trimmed line keeps id/quantity/price/amount/acceptSubstitution.
    assert set(item.keys()) == {
        "id",
        "quantity",
        "price",
        "amount",
        "acceptSubstitution",
        "item",
    }
    # The inner item is trimmed to the client's replay subset.
    assert set(item["item"].keys()) == {
        "itemId",
        "idProduit",
        "produitEan13",
        "pviIncrement",
        "prix",
        "privateData",
        "poidsMinimum",
        "substituable",
        "dispoCataloguePdv",
        "stock",
        "catalog",
        "libelle",
        "compatibleConsigne",
        "marque",
        "conditionnement",
        "qteMaxPanier",
        "isPresentAlcoholProduct",
    }


# ── Response → normalized items mapping ────────────────────────────────────────


def test_parse_cart_items_maps_response():
    items = parse_cart_items(_response("cart_response_2_items.json"))
    assert len(items) == 2
    first, second = items

    assert isinstance(first, IntermarcheCartItem)
    assert first.id == "37731"
    assert first.item_id == "37731"
    assert first.name == "Parmigiano reggiano AOP sous film au lait cru de vache 28,4% de mg"
    assert first.quantity == 1
    assert first.price == 5.07
    assert first.price_text == "5,07 €"
    assert first.ean == "2449185000000"
    assert first.image == (
        "https://driveimg1.intermarche.com/fr/Content/images/boitmal/produit/zoom/"
        "AD52786BE12402207CAAF5BE13DE2FCE.jpg"
    )

    assert second.id == "30490"
    assert second.item_id == "30490"
    assert second.name == "Beaufort AOP au lait cru"
    assert second.price == 6.3
    assert second.quantity == 1


def test_parse_cart_items_empty_cart():
    assert parse_cart_items(_response("cart_response_empty.json")) == []


def test_parse_cart_items_missing_image_is_none():
    payload = _response("cart_response_1_item.json")
    # Drop the images array to exercise the "image si dispo" fallback.
    payload["carts"][0]["items"][0]["item"]["images"] = []
    items = parse_cart_items(payload)
    assert items[0].image is None


def test_parse_cart_response_builds_state():
    state = parse_cart_response(
        _response("cart_response_2_items.json"), store_id=STORE_ID
    )
    assert state.customer_id == CUSTOMER_UUID
    assert state.store_id == STORE_ID
    assert state.items_number == 2
    assert state.amount == 11.37
    assert len(state.items) == 2
    assert state.item_quantity("37731") == 1


# ── Adapter actions (mocked httpx) ─────────────────────────────────────────────


def _mock_client(handler, **kwargs) -> IntermarcheCartClient:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return IntermarcheCartClient(
        client,
        customer_uuid=CUSTOMER_UUID,
        store_id=STORE_ID,
        **kwargs,
    )


def _ok_cart_response(name: str = "cart_response_2_items.json"):
    return httpx.Response(
        200, json=_response(name), headers={"content-type": "application/json"}
    )


def test_get_or_read_cart_posts_empty_events():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok_cart_response()

    client = _mock_client(handler)
    state = asyncio.run(client.get_or_read_cart())

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == (
        f"{INTERMARCHE_CART_BASE_URL}/stores/{STORE_ID}/carts?customerId={CUSTOMER_UUID}"
    )
    body = json.loads(request.content)
    assert body["events"] == []
    assert body["lastSynchronizedCart"]["carts"] == []
    assert isinstance(state, IntermarcheCartState)
    assert len(state.items) == 2


def test_add_item_sends_quantity_event():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok_cart_response("cart_response_1_item.json")

    client = _mock_client(handler)
    state = asyncio.run(client.add_item("37731", quantity=1))

    body = json.loads(seen[0].content)
    assert len(body["events"]) == 1
    event = body["events"][0]
    assert event["type"] == "QUANTITY"
    assert event["itemId"] == "37731"
    assert event["quantity"] == 1
    assert event["catalog"] == "PDV"
    assert state.item_quantity("37731") == 1


def test_update_item_quantity_sends_delta():
    # A first read seeds the local state (item at quantity 1); update to 3.
    responses = iter(
        [_ok_cart_response("cart_response_1_item.json"), _ok_cart_response()]
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return next(responses)

    client = _mock_client(handler)
    first = asyncio.run(client.get_or_read_cart())
    assert first.item_quantity("37731") == 1

    state = asyncio.run(client.update_item_quantity("37731", quantity=3))

    event = json.loads(seen[1].content)["events"][0]
    assert event["quantity"] == 2  # 3 - 1
    assert state.item_quantity("37731") == 1  # response fixture has qty 1


def test_remove_item_sends_minus_one():
    responses = iter(
        [_ok_cart_response("cart_response_1_item.json"), _ok_cart_response("cart_response_empty.json")]
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return next(responses)

    client = _mock_client(handler)
    asyncio.run(client.get_or_read_cart())
    state = asyncio.run(client.remove_item("37731"))

    event = json.loads(seen[1].content)["events"][0]
    assert event["quantity"] == -1
    assert state.items_number == 0


def test_remove_item_unknown_item_is_noop():
    responses = iter([_ok_cart_response("cart_response_1_item.json")])
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return next(responses)

    client = _mock_client(handler)
    asyncio.run(client.get_or_read_cart())
    asyncio.run(client.remove_item("does-not-exist"))
    assert len(seen) == 1  # only the initial read; no mutation was sent


def test_clear_cart_deletes_customer_cart():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    client = _mock_client(handler)
    result = asyncio.run(client.clear_cart())

    assert result is None
    assert len(seen) == 1
    assert seen[0].method == "DELETE"
    assert str(seen[0].url) == (
        f"{INTERMARCHE_CART_BASE_URL}/customers/{CUSTOMER_UUID}/carts?sellerId=ITM"
    )


def test_actions_replay_last_synchronized_cart():
    """A second action replays the previous response as lastSynchronizedCart."""
    responses = iter(
        [_ok_cart_response("cart_response_1_item.json"), _ok_cart_response()]
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return next(responses)

    client = _mock_client(handler)
    asyncio.run(client.add_item("37731", quantity=1))
    asyncio.run(client.add_item("30490", quantity=1))

    second_body = json.loads(seen[1].content)
    replay_items = second_body["lastSynchronizedCart"]["carts"][0]["items"]
    assert [i["id"] for i in replay_items] == ["37731"]


# ── Error handling ─────────────────────────────────────────────────────────────


def test_session_error_raises_auth_on_401():
    client = _mock_client(lambda request: httpx.Response(401, text="unauthorized"))
    with pytest.raises(IntermarcheCartAuthError):
        asyncio.run(client.get_or_read_cart())


def test_session_error_raises_auth_on_403():
    client = _mock_client(lambda request: httpx.Response(403, text="forbidden"))
    with pytest.raises(IntermarcheCartAuthError):
        asyncio.run(client.get_or_read_cart())


def test_not_found_raises_not_found():
    client = _mock_client(lambda request: httpx.Response(404, text="not found"))
    with pytest.raises(IntermarcheCartNotFoundError):
        asyncio.run(client.get_or_read_cart())


def test_conflict_raises_conflict():
    client = _mock_client(lambda request: httpx.Response(409, text="stale"))
    with pytest.raises(IntermarcheCartConflictError):
        asyncio.run(client.get_or_read_cart())


def test_unexpected_error_raises_cart_error():
    client = _mock_client(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(IntermarcheCartError) as exc_info:
        asyncio.run(client.get_or_read_cart())
    assert "500" in str(exc_info.value)


def test_non_json_response_raises_cart_error():
    client = _mock_client(
        lambda request: httpx.Response(200, text="<html>captcha</html>")
    )
    with pytest.raises(IntermarcheCartError):
        asyncio.run(client.get_or_read_cart())


def test_build_client_requires_store_selection():
    cookies = [{"name": "itm_session", "value": "x"}]
    with pytest.raises(IntermarcheCartError, match="store"):
        build_intermarche_cart_client(cookies, customer_uuid=CUSTOMER_UUID)
