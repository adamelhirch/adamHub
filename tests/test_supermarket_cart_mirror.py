"""Endpoint-level tests for the Intermarché cart mirror on /supermarket/carts*.

Run 1 shipped local-only carts. For Intermarché the cart endpoints now act as a
real mirror: each mutation (add / quantity / remove / clear / read) is applied to
the store's cart through the b1 adapter first, and the local cart is rewritten
from the server's response; every failure is rejected with a clear error WITHOUT
touching the local cart. PUT status stays local (manual validation) and the 3
other stores keep the local behavior.

The adapter seam (``build_intermarche_cart_client``) is monkeypatched with a fake
client: these tests exercise cookie resolution, adapter invocation, local rewrite,
error mapping and client lifecycle with zero network access. The adapter itself is
covered by ``tests/test_intermarche_cart.py`` (mock httpx + .har fixtures).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models import (
    SupermarketCart,
    SupermarketCartItem,
    SupermarketSearchCache,
    SupermarketStore,
)
from app.services.cart import upsert_cart
from app.services.scrapers.intermarche_cart import (
    IntermarcheCartAuthError,
    IntermarcheCartConflictError,
    IntermarcheCartError,
    IntermarcheCartNotFoundError,
    IntermarcheCartState,
    parse_cart_response,
)
from tests.conftest import register_user

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "intermarche"

CUSTOMER_UUID = "515ffd9e-538e-447a-983e-69ca17363fac"
STORE_ID = "11131"

# Session cookies with a selected store (itm_pdv / novaParams, from the .har
# fixture) plus an explicit customer-uuid cookie so the mirror can resolve it.
SESSION_COOKIES = [
    {
        "name": "itm_pdv",
        "value": (
            "{%22ref%22:%2211131%22%2C%22isEcommerce%22:true%2C%22name%22:"
            "%22Super%2520Ramonville%2520Saint-Agne%22}"
        ),
    },
    {"name": "novaParams", "value": "{%22pdvRef%22:%2211131%22}"},
    {"name": "itm_customer", "value": CUSTOMER_UUID},
]


def _load_fixture(name: str) -> dict:
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _state(name: str = "cart_response_2_items.json") -> IntermarcheCartState:
    return parse_cart_response(_load_fixture(name), store_id=STORE_ID)


def _state_with(item_id: str, quantity: int, name: str = "Beaufort AOP au lait cru") -> IntermarcheCartState:
    payload = {
        "id": CUSTOMER_UUID,
        "synchronizeDateTime": "2026-08-15T03:02:28+02:00",
        "amount": 6.3 * quantity,
        "itemsNumber": 1,
        "carts": [
            {
                "items": [
                    {
                        "id": item_id,
                        "quantity": quantity,
                        "price": 6.3,
                        "amount": 6.3 * quantity,
                        "item": {
                            "itemId": item_id,
                            "libelle": name,
                            "images": ["https://img.test/beaufort.png"],
                        },
                    }
                ]
            }
        ],
    }
    return parse_cart_response(payload, store_id=STORE_ID)


class FakeCartClient:
    """Stands in for the real IntermarcheCartClient at the adapter seam.

    ``states`` (optional) is consumed one per adapter call, so a test can model
    a read-then-mutate sequence (e.g. remove returns an empty cart after the
    initial read showed one line). ``error`` short-circuits every call.
    """

    def __init__(
        self,
        state: IntermarcheCartState | None = None,
        *,
        error: Exception | None = None,
        states: list[IntermarcheCartState] | None = None,
    ):
        self.state = state
        self.error = error
        self.states = list(states) if states else []
        self.calls: list[tuple[str, tuple, dict]] = []
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def _call(self, name: str, args: tuple, kwargs: dict):
        self.calls.append((name, args, kwargs))
        if self.error is not None:
            raise self.error
        if self.states:
            return self.states.pop(0)
        return self.state

    async def get_or_read_cart(self, last_sync=None):
        return await self._call("get_or_read_cart", (last_sync,), {})

    async def add_item(self, item_id, quantity=1, **kwargs):
        return await self._call("add_item", (item_id,), {"quantity": quantity, **kwargs})

    async def update_item_quantity(self, item_id, quantity):
        return await self._call("update_item_quantity", (item_id,), {"quantity": quantity})

    async def remove_item(self, item_id):
        return await self._call("remove_item", (item_id,), {})

    async def clear_cart(self):
        return await self._call("clear_cart", (), {})


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _seed_cache_row(
    session,
    *,
    store=SupermarketStore.INTERMARCHE,
    external_id="30490",
    name="Beaufort AOP au lait cru",
    expires_at: datetime | None = None,
    **overrides,
) -> SupermarketSearchCache:
    now = datetime.now(UTC)
    row = SupermarketSearchCache(
        store=store,
        query="beaufort",
        external_id=external_id,
        name=name,
        brand="SAV",
        packaging="200 g",
        price_amount=6.3,
        price_text="6,30 €",
        image_url="https://img.test/beaufort.png",
        product_url="https://example.test/beaufort",
        fetched_at=now,
        expires_at=expires_at if expires_at is not None else now + timedelta(days=1),
        **overrides,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _cache_id_of(test_engine, external_id: str) -> int:
    with Session(test_engine) as session:
        row = session.exec(
            select(SupermarketSearchCache).where(
                SupermarketSearchCache.external_id == external_id
            )
        ).first()
        assert row is not None
        return row.id


def _import_connection(client, headers) -> dict:
    response = client.post(
        "/api/v1/supermarket/connections/import",
        headers=headers,
        json={
            "store": "intermarche",
            "label": "Intermarché session",
            "cookies": SESSION_COOKIES,
            "activate": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _seed_local_item(test_engine, user_id, *, external_id="37731", name="Parmigiano", quantity=1) -> int:
    """Seed one mirrored-style local line directly (mirror-off path)."""
    with Session(test_engine) as session:
        cart = session.exec(
            select(SupermarketCart).where(
                SupermarketCart.store == SupermarketStore.INTERMARCHE,
                SupermarketCart.user_id == user_id,
            )
        ).first()
        if cart is None:
            cart = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=user_id)
        item = SupermarketCartItem(
            cart_id=cart.id,
            external_id=external_id,
            name=name,
            quantity=quantity,
            price_amount=5.07,
            price_text="5,07 €",
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item.id


def _local_items(test_engine, user_id) -> list[dict]:
    with Session(test_engine) as session:
        cart = session.exec(
            select(SupermarketCart).where(
                SupermarketCart.store == SupermarketStore.INTERMARCHE,
                SupermarketCart.user_id == user_id,
            )
        ).first()
        if cart is None:
            return []
        rows = session.exec(
            select(SupermarketCartItem).where(SupermarketCartItem.cart_id == cart.id)
        ).all()
        return [
            {
                "id": row.id,
                "external_id": row.external_id,
                "name": row.name,
                "quantity": row.quantity,
            }
            for row in rows
        ]


def _cart_id(test_engine, user_id) -> int:
    with Session(test_engine) as session:
        cart = session.exec(
            select(SupermarketCart).where(
                SupermarketCart.store == SupermarketStore.INTERMARCHE,
                SupermarketCart.user_id == user_id,
            )
        ).first()
        assert cart is not None
        return cart.id


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeCartClient) -> list:
    """Monkeypatch the adapter seam; returns the list of build() invocations."""
    built: list = []

    def build(cookies, customer_uuid, **kwargs):
        built.append((cookies, customer_uuid))
        return fake

    monkeypatch.setattr("app.services.cart_mirror.build_intermarche_cart_client", build)
    return built


# ── GET /carts/intermarche — re-read from the site ─────────────────────────────


def test_mirror_get_reads_site_and_rewrites_local(client, auth_headers, owner_id, test_engine, monkeypatch):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state())
    _patch_client(monkeypatch, fake)
    # A stale local cart must be overwritten by the site state.
    _seed_local_item(test_engine, owner_id, external_id="999", name="Ancien local")

    response = client.get("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 200, response.text
    cart = response.json()
    assert cart["store"] == "intermarche"
    assert cart["status"] == "draft"
    assert [call[0] for call in fake.calls] == ["get_or_read_cart"]
    assert fake.calls[0][1] == (None,)  # fresh client, nothing to replay
    assert fake.closed is True

    items = cart["items"]
    assert {item["external_id"] for item in items} == {"37731", "30490"}

    local = _local_items(test_engine, owner_id)
    assert {item["external_id"] for item in local} == {"37731", "30490"}
    by_ext = {item["external_id"]: item for item in local}
    assert by_ext["37731"]["name"].startswith("Parmigiano")
    assert by_ext["37731"]["quantity"] == 1
    assert by_ext["30490"]["quantity"] == 1
    # A successful mirror read stamps the local cart as refreshed.
    with Session(test_engine) as session:
        saved = session.get(SupermarketCart, cart["id"])
        assert saved.updated_at is not None
        assert saved.updated_at > saved.created_at


def test_mirror_get_empty_site_cart_clears_local(client, auth_headers, owner_id, test_engine, monkeypatch):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state("cart_response_empty.json"))
    _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)

    response = client.get("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    assert _local_items(test_engine, owner_id) == []


def test_mirror_get_skips_zero_quantity_lines(client, auth_headers, owner_id, test_engine, monkeypatch):
    _import_connection(client, auth_headers)
    # A response keeping a resolved-away 0-quantity line must not pollute the
    # local mirror: only real (quantity > 0) lines are rewritten.
    payload = {
        "id": CUSTOMER_UUID,
        "synchronizeDateTime": "2026-08-15T03:02:28+02:00",
        "amount": 12.6,
        "itemsNumber": 1,
        "carts": [
            {
                "items": [
                    {
                        "id": "30490",
                        "quantity": 2,
                        "price": 6.3,
                        "item": {"itemId": "30490", "libelle": "Beaufort"},
                    },
                    {
                        "id": "37731",
                        "quantity": 0,
                        "price": 5.07,
                        "item": {"itemId": "37731", "libelle": "Parmigiano"},
                    },
                ]
            }
        ],
    }
    fake = FakeCartClient(state=parse_cart_response(payload, store_id=STORE_ID))
    _patch_client(monkeypatch, fake)

    response = client.get("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert {item["external_id"] for item in response.json()["items"]} == {"30490"}
    assert [_["external_id"] for _ in _local_items(test_engine, owner_id)] == ["30490"]


def test_mirror_get_without_connection_rejects_without_touching_local(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    fake = FakeCartClient(state=_state())
    built = _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id, external_id="37731", name="Parmigiano")

    response = client.get("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 400, response.text
    assert "connexion Intermarché" in response.json()["detail"]
    assert built == []  # the adapter was never reached
    assert fake.closed is False  # nothing was built, nothing to close
    local = _local_items(test_engine, owner_id)
    assert len(local) == 1
    assert local[0]["external_id"] == "37731"
    assert local[0]["name"] == "Parmigiano"
    assert local[0]["quantity"] == 1


def test_mirror_get_dead_session_is_401_and_local_untouched(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state(), error=IntermarcheCartAuthError("session morte"))
    _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)

    response = client.get("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 401, response.text
    assert "session morte" in response.json()["detail"]
    assert fake.closed is True  # the client is always released, even on error
    local = _local_items(test_engine, owner_id)
    assert len(local) == 1 and local[0]["external_id"] == "37731" and local[0]["quantity"] == 1


def test_mirror_get_conflict_is_409(client, auth_headers, test_engine, monkeypatch):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state(), error=IntermarcheCartConflictError("out of sync"))
    _patch_client(monkeypatch, fake)

    response = client.get("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 409, response.text
    assert "out of sync" in response.json()["detail"]


def test_mirror_get_not_found_is_404(client, auth_headers, test_engine, monkeypatch):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state(), error=IntermarcheCartNotFoundError("no customer"))
    _patch_client(monkeypatch, fake)

    response = client.get("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 404, response.text
    assert "no customer" in response.json()["detail"]


def test_mirror_get_generic_error_is_503(client, auth_headers, test_engine, monkeypatch):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state(), error=IntermarcheCartError("API 500"))
    _patch_client(monkeypatch, fake)

    response = client.get("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 503, response.text
    assert "API 500" in response.json()["detail"]


# ── POST /carts/intermarche/items — mirror add ─────────────────────────────────


def test_mirror_add_calls_adapter_and_rewrites_local(client, auth_headers, owner_id, test_engine, monkeypatch):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state_with("30490", quantity=3))
    _patch_client(monkeypatch, fake)
    with Session(test_engine) as session:
        _seed_cache_row(session)  # external_id = 30490

    response = client.post(
        "/api/v1/supermarket/carts/intermarche/items",
        headers=auth_headers,
        json={"cache_id": _cache_id_of(test_engine, "30490"), "quantity": 2},
    )

    assert response.status_code == 200, response.text
    assert fake.calls == [("add_item", ("30490",), {"quantity": 2})]
    assert fake.closed is True
    cart = response.json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["external_id"] == "30490"
    assert cart["items"][0]["quantity"] == 3  # rewritten from the adapter response
    local = _local_items(test_engine, owner_id)
    assert local[0]["name"] == "Beaufort AOP au lait cru"


def test_mirror_add_unknown_cache_rejects_before_any_site_call(client, auth_headers, test_engine, monkeypatch):
    fake = FakeCartClient(state=_state())
    built = _patch_client(monkeypatch, fake)

    response = client.post(
        "/api/v1/supermarket/carts/intermarche/items",
        headers=auth_headers,
        json={"cache_id": 999999, "quantity": 1},
    )

    assert response.status_code == 400, response.text
    assert "Search cache entry not found" in response.json()["detail"]
    assert built == []
    assert fake.calls == []


def test_mirror_add_expired_cache_rejects(client, auth_headers, test_engine, monkeypatch):
    fake = FakeCartClient(state=_state())
    _patch_client(monkeypatch, fake)
    with Session(test_engine) as session:
        cache_id = _seed_cache_row(
            session, expires_at=datetime.now(UTC) - timedelta(hours=1)
        ).id

    response = client.post(
        "/api/v1/supermarket/carts/intermarche/items",
        headers=auth_headers,
        json={"cache_id": cache_id, "quantity": 1},
    )

    assert response.status_code == 400, response.text
    assert "expired" in response.json()["detail"]
    assert fake.calls == []


def test_mirror_add_session_dead_401_without_touching_local(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state(), error=IntermarcheCartAuthError("session morte"))
    _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)
    with Session(test_engine) as session:
        cache_id = _seed_cache_row(session).id

    response = client.post(
        "/api/v1/supermarket/carts/intermarche/items",
        headers=auth_headers,
        json={"cache_id": cache_id, "quantity": 2},
    )

    assert response.status_code == 401, response.text
    assert "session morte" in response.json()["detail"]
    local = _local_items(test_engine, owner_id)
    assert len(local) == 1 and local[0]["external_id"] == "37731" and local[0]["quantity"] == 1


# ── PATCH /carts/intermarche/items/{id} — mirror quantity ──────────────────────


def test_mirror_update_quantity_reads_then_updates_and_rewrites(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state_with("37731", quantity=5))
    _patch_client(monkeypatch, fake)
    item_id = _seed_local_item(test_engine, owner_id, external_id="37731", quantity=1)

    response = client.patch(
        f"/api/v1/supermarket/carts/intermarche/items/{item_id}",
        headers=auth_headers,
        json={"quantity": 5},
    )

    assert response.status_code == 200, response.text
    # The delta protocol needs the current state: read first, then mutate.
    assert [call[0] for call in fake.calls] == ["get_or_read_cart", "update_item_quantity"]
    assert fake.calls[1] == ("update_item_quantity", ("37731",), {"quantity": 5})
    assert response.json()["items"][0]["quantity"] == 5
    assert _local_items(test_engine, owner_id)[0]["quantity"] == 5


def test_mirror_update_unknown_item_is_404_without_site_call(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    fake = FakeCartClient(state=_state())
    built = _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)

    response = client.patch(
        "/api/v1/supermarket/carts/intermarche/items/999999",
        headers=auth_headers,
        json={"quantity": 5},
    )

    assert response.status_code == 404, response.text
    assert "Cart item not found" in response.json()["detail"]
    assert built == [] and fake.calls == []


def test_mirror_update_without_connection_rejects_without_touching_local(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    fake = FakeCartClient(state=_state())
    built = _patch_client(monkeypatch, fake)
    item_id = _seed_local_item(test_engine, owner_id)

    response = client.patch(
        f"/api/v1/supermarket/carts/intermarche/items/{item_id}",
        headers=auth_headers,
        json={"quantity": 5},
    )

    assert response.status_code == 400, response.text
    assert "connexion Intermarché" in response.json()["detail"]
    assert built == []
    assert _local_items(test_engine, owner_id)[0]["quantity"] == 1


# ── DELETE /carts/intermarche/items/{id} — mirror remove ───────────────────────


def test_mirror_remove_item_rewrites_local(client, auth_headers, owner_id, test_engine, monkeypatch):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(
        states=[_state("cart_response_2_items.json"), _state("cart_response_empty.json")]
    )
    _patch_client(monkeypatch, fake)
    item_id = _seed_local_item(test_engine, owner_id)

    response = client.delete(
        f"/api/v1/supermarket/carts/intermarche/items/{item_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert [call[0] for call in fake.calls] == ["get_or_read_cart", "remove_item"]
    assert fake.calls[1] == ("remove_item", ("37731",), {})
    # The adapter answered with an empty cart: the local mirror follows.
    assert response.json()["items"] == []
    assert _local_items(test_engine, owner_id) == []


def test_mirror_remove_unknown_item_is_404_without_site_call(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    fake = FakeCartClient(state=_state())
    built = _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)

    response = client.delete(
        "/api/v1/supermarket/carts/intermarche/items/999999",
        headers=auth_headers,
    )

    assert response.status_code == 404, response.text
    assert built == [] and fake.calls == []


# ── DELETE /carts/intermarche — mirror clear ───────────────────────────────────


def test_mirror_clear_cart_calls_adapter_and_clears_local(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    _import_connection(client, auth_headers)
    fake = FakeCartClient()
    _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)

    response = client.delete("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert fake.calls == [("clear_cart", (), {})]
    assert fake.closed is True
    assert response.json()["items"] == []
    # The local cart row survives (like the local clear), but empty.
    assert _cart_id(test_engine, owner_id) is not None
    assert _local_items(test_engine, owner_id) == []


def test_mirror_clear_cart_without_connection_rejects(client, auth_headers, owner_id, test_engine, monkeypatch):
    fake = FakeCartClient()
    built = _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)

    response = client.delete("/api/v1/supermarket/carts/intermarche", headers=auth_headers)

    assert response.status_code == 400, response.text
    assert built == []
    assert len(_local_items(test_engine, owner_id)) == 1


# ── PUT /carts/intermarche/status — unchanged, local only ──────────────────────


def test_mirror_status_put_stays_local_without_any_connection(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    fake = FakeCartClient(state=_state())
    built = _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)

    response = client.put(
        "/api/v1/supermarket/carts/intermarche/status",
        headers=auth_headers,
        json={"status": "validated"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "validated"
    assert built == [] and fake.calls == []  # the site was never contacted
    with Session(test_engine) as session:
        cart = session.get(SupermarketCart, response.json()["id"])
        assert cart.status.value == "validated"


# ── Tenant scoping ─────────────────────────────────────────────────────────────


def test_mirror_is_scoped_per_tenant_and_never_touches_other_users(
    client, auth_headers, owner_id, test_engine, monkeypatch
):
    _import_connection(client, auth_headers)
    fake = FakeCartClient(state=_state())
    _patch_client(monkeypatch, fake)
    _seed_local_item(test_engine, owner_id)
    intruder = register_user(client, "mirror-intruder@adamelhirch.com")["headers"]

    # The intruder has no Intermarché connection: the mirror rejects with 400
    # (their own call), and the owner's local cart is untouched.
    response = client.get("/api/v1/supermarket/carts/intermarche", headers=intruder)
    assert response.status_code == 400, response.text
    assert "connexion Intermarché" in response.json()["detail"]

    assert len(_local_items(test_engine, owner_id)) == 1
    assert client.get("/api/v1/supermarket/carts", headers=intruder).json() == []


# ── Non-regression: the 3 other stores stay local ──────────────────────────────


def test_local_cart_flow_unchanged_for_other_stores(client, auth_headers, test_engine):
    for store in ("carrefour", "leclerc", "auchan"):
        with Session(test_engine) as session:
            _seed_cache_row(session, store=store, external_id=f"sku-{store}")

        added = client.post(
            f"/api/v1/supermarket/carts/{store}/items",
            headers=auth_headers,
            json={"cache_id": _cache_id_of(test_engine, f"sku-{store}")},
        )
        assert added.status_code == 200, added.text
        assert added.json()["store"] == store
        assert added.json()["items"][0]["external_id"] == f"sku-{store}"
        item_id = added.json()["items"][0]["id"]

        read = client.get(f"/api/v1/supermarket/carts/{store}", headers=auth_headers)
        assert read.status_code == 200
        assert read.json()["id"] == added.json()["id"]

        patched = client.patch(
            f"/api/v1/supermarket/carts/{store}/items/{item_id}",
            headers=auth_headers,
            json={"quantity": 4},
        )
        assert patched.status_code == 200
        assert patched.json()["items"][0]["quantity"] == 4

        status = client.put(
            f"/api/v1/supermarket/carts/{store}/status",
            headers=auth_headers,
            json={"status": "validated"},
        )
        assert status.status_code == 200
        assert status.json()["status"] == "validated"

        removed = client.delete(
            f"/api/v1/supermarket/carts/{store}/items/{item_id}", headers=auth_headers
        )
        assert removed.status_code == 200
        assert removed.json()["items"] == []

        cleared = client.delete(f"/api/v1/supermarket/carts/{store}", headers=auth_headers)
        assert cleared.status_code == 200
        assert cleared.json()["items"] == []