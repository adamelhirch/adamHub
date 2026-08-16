from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import (
    CartStatus,
    SupermarketCart,
    SupermarketCartItem,
    SupermarketSearchCache,
    SupermarketStore,
)
from app.services.cart import (
    add_item,
    clear_cart,
    get_cart,
    list_carts,
    remove_item,
    set_status,
    update_quantity,
    upsert_cart,
)
from tests.conftest import register_user


# ── Helpers ────────────────────────────────────────────────────────────────────


def _seed_cache_row(
    session: Session,
    *,
    store=SupermarketStore.INTERMARCHE,
    name="Lait entier",
    external_id="sku-lait",
    expires_at: datetime | None = None,
    **overrides,
) -> SupermarketSearchCache:
    now = datetime.now(UTC)
    row = SupermarketSearchCache(
        store=store,
        query="lait",
        external_id=external_id,
        name=name,
        brand="Candia",
        packaging="1 L",
        price_amount=1.49,
        price_text="1,49 €",
        image_url="https://img.test/lait.png",
        product_url="https://example.test/lait",
        fetched_at=now,
        expires_at=expires_at if expires_at is not None else now + timedelta(days=1),
        **overrides,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _seed_cache(test_engine, **kwargs) -> int:
    with Session(test_engine) as session:
        return _seed_cache_row(session, **kwargs).id


# ── Model ──────────────────────────────────────────────────────────────────────


def test_cart_unique_per_user_and_store(test_engine):
    with Session(test_engine) as session:
        session.add(SupermarketCart(user_id=10, store=SupermarketStore.INTERMARCHE))
        session.commit()

        session.add(SupermarketCart(user_id=10, store=SupermarketStore.INTERMARCHE))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # The same user with a different store gets a distinct cart.
        session.add(SupermarketCart(user_id=10, store=SupermarketStore.LECLERC))
        session.commit()


def test_cart_item_fk_cascades_on_cart_delete():
    fk = next(
        fk for fk in SupermarketCartItem.__table__.foreign_keys if fk.parent.name == "cart_id"
    )
    assert fk.ondelete == "CASCADE"


def test_cart_status_enum_defaults_to_draft(test_engine):
    with Session(test_engine) as session:
        session.add(SupermarketCart(user_id=11, store=SupermarketStore.CARREFOUR))
        session.commit()
        cart = session.exec(select(SupermarketCart)).first()
        assert cart.status == CartStatus.DRAFT
        assert cart.validated_at is None
        assert cart.external_cart_ref is None


# ── Service: cart lifecycle ────────────────────────────────────────────────────


def test_upsert_and_get_cart_by_store(test_engine):
    with Session(test_engine) as session:
        assert get_cart(session, SupermarketStore.INTERMARCHE, user_id=1) is None

        created = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=1)
        assert created.id is not None
        assert created.status == CartStatus.DRAFT
        assert created.validated_at is None

        again = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=1)
        assert again.id == created.id

        other_store = upsert_cart(session, SupermarketStore.LECLERC, user_id=1)
        assert other_store.id != created.id

        carts = list_carts(session, user_id=1)
        assert {cart.store for cart in carts} == {
            SupermarketStore.INTERMARCHE,
            SupermarketStore.LECLERC,
        }


def test_add_item_snapshots_cache_and_merges_same_cache_id(test_engine):
    with Session(test_engine) as session:
        cache = _seed_cache_row(session)
        cart = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=1)

        first = add_item(session, cart, cache.id)
        assert first.quantity == 1
        assert first.name == "Lait entier"
        assert first.brand == "Candia"
        assert first.packaging == "1 L"
        assert first.price_amount == 1.49
        assert first.price_text == "1,49 €"
        assert first.external_id == "sku-lait"
        assert first.product_url == "https://example.test/lait"

        # The same cache_id merges by bumping quantity, no duplicate line.
        second = add_item(session, cart, cache.id, quantity=2)
        assert second.id == first.id
        assert second.quantity == 3

        # A different cache_id creates a distinct line.
        other = _seed_cache_row(session, name="Beurre", external_id="sku-beurre")
        third = add_item(session, cart, other.id)
        assert third.id != first.id

        items = session.exec(
            select(SupermarketCartItem).where(SupermarketCartItem.cart_id == cart.id)
        ).all()
        assert len(items) == 2


def test_add_item_rejects_unknown_cache_id(test_engine):
    with Session(test_engine) as session:
        cart = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=1)
        with pytest.raises(HTTPException) as exc_info:
            add_item(session, cart, cache_id=999999)
        assert exc_info.value.status_code == 400


def test_add_item_rejects_expired_cache_id(test_engine):
    with Session(test_engine) as session:
        cache = _seed_cache_row(
            session, expires_at=datetime.now(UTC) - timedelta(minutes=1)
        )
        cart = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=1)
        with pytest.raises(HTTPException) as exc_info:
            add_item(session, cart, cache.id)
        assert exc_info.value.status_code == 400


def test_update_quantity_remove_item_and_clear(test_engine):
    with Session(test_engine) as session:
        cache = _seed_cache_row(session)
        cart = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=1)
        item = add_item(session, cart, cache.id)

        updated = update_quantity(session, cart, item.id, quantity=7)
        assert updated.quantity == 7

        remove_item(session, cart, item.id)
        assert session.get(SupermarketCartItem, item.id) is None

        # clear wipes every item but keeps the cart row itself.
        add_item(session, cart, cache.id)
        clear_cart(session, cart)
        remaining = session.exec(
            select(SupermarketCartItem).where(SupermarketCartItem.cart_id == cart.id)
        ).all()
        assert remaining == []
        assert session.get(SupermarketCart, cart.id) is not None


def test_update_quantity_unknown_item_is_404(test_engine):
    with Session(test_engine) as session:
        cart = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=1)
        with pytest.raises(HTTPException) as exc_info:
            update_quantity(session, cart, 999999, 3)
        assert exc_info.value.status_code == 404


def test_set_status_sets_and_clears_validated_at(test_engine):
    with Session(test_engine) as session:
        cart = upsert_cart(session, SupermarketStore.INTERMARCHE, user_id=1)
        assert cart.status == CartStatus.DRAFT

        validated = set_status(session, cart, CartStatus.VALIDATED)
        assert validated.status == CartStatus.VALIDATED
        assert validated.validated_at is not None

        back_to_draft = set_status(session, cart, CartStatus.DRAFT)
        assert back_to_draft.status == CartStatus.DRAFT
        assert back_to_draft.validated_at is None


# ── Endpoints ──────────────────────────────────────────────────────────────────


def test_cart_endpoints_full_flow(client, auth_headers, test_engine):
    cache_id = _seed_cache(test_engine, store=SupermarketStore.CARREFOUR)

    # No carts yet.
    assert client.get("/api/v1/supermarket/carts", headers=auth_headers).json() == []

    # Adding an item creates the cart and snapshots the cache row.
    added = client.post(
        "/api/v1/supermarket/carts/carrefour/items",
        headers=auth_headers,
        json={"cache_id": cache_id},
    )
    assert added.status_code == 200, added.text
    cart = added.json()
    assert cart["store"] == "carrefour"
    assert cart["status"] == "draft"
    assert cart["validated_at"] is None
    assert len(cart["items"]) == 1
    assert cart["items"][0]["name"] == "Lait entier"
    item_id = cart["items"][0]["id"]

    # GET the cart by store.
    read = client.get("/api/v1/supermarket/carts/carrefour", headers=auth_headers)
    assert read.status_code == 200
    assert read.json()["id"] == cart["id"]

    # It is listed among the user's carts.
    listed = client.get("/api/v1/supermarket/carts", headers=auth_headers).json()
    assert [c["id"] for c in listed] == [cart["id"]]

    # Update quantity.
    patched = client.patch(
        f"/api/v1/supermarket/carts/carrefour/items/{item_id}",
        headers=auth_headers,
        json={"quantity": 5},
    )
    assert patched.status_code == 200
    assert patched.json()["items"][0]["quantity"] == 5

    # Validate the cart: status flips and validated_at is stamped.
    validated = client.put(
        "/api/v1/supermarket/carts/carrefour/status",
        headers=auth_headers,
        json={"status": "validated"},
    )
    assert validated.status_code == 200
    assert validated.json()["status"] == "validated"
    assert validated.json()["validated_at"] is not None

    # Back to draft clears validated_at.
    drafted = client.put(
        "/api/v1/supermarket/carts/carrefour/status",
        headers=auth_headers,
        json={"status": "draft"},
    )
    assert drafted.status_code == 200
    assert drafted.json()["status"] == "draft"
    assert drafted.json()["validated_at"] is None

    # Remove the item.
    removed = client.delete(
        f"/api/v1/supermarket/carts/carrefour/items/{item_id}",
        headers=auth_headers,
    )
    assert removed.status_code == 200
    assert removed.json()["items"] == []

    # Clear the cart (keeps the cart row).
    client.post(
        "/api/v1/supermarket/carts/carrefour/items",
        headers=auth_headers,
        json={"cache_id": cache_id},
    )
    cleared = client.delete("/api/v1/supermarket/carts/carrefour", headers=auth_headers)
    assert cleared.status_code == 200
    assert cleared.json()["items"] == []


def test_cart_add_rejects_unknown_cache(client, auth_headers):
    response = client.post(
        "/api/v1/supermarket/carts/carrefour/items",
        headers=auth_headers,
        json={"cache_id": 999999},
    )
    assert response.status_code == 400


def test_cart_add_rejects_expired_cache(client, auth_headers, test_engine):
    cache_id = _seed_cache(test_engine, store=SupermarketStore.CARREFOUR, expires_at=datetime.now(UTC) - timedelta(hours=1))
    response = client.post(
        "/api/v1/supermarket/carts/carrefour/items",
        headers=auth_headers,
        json={"cache_id": cache_id},
    )
    assert response.status_code == 400


def test_cart_cross_user_is_404_without_leak(client, test_engine):
    owner = register_user(client, "cart-owner@adamelhirch.com")
    intruder = register_user(client, "cart-intruder@adamelhirch.com")
    cache_id = _seed_cache(test_engine, store=SupermarketStore.CARREFOUR)

    added = client.post(
        "/api/v1/supermarket/carts/carrefour/items",
        headers=owner["headers"],
        json={"cache_id": cache_id},
    )
    item_id = added.json()["items"][0]["id"]

    # The intruder sees no carts and cannot touch the owner's item.
    assert client.get("/api/v1/supermarket/carts", headers=intruder["headers"]).json() == []
    assert client.patch(
        f"/api/v1/supermarket/carts/carrefour/items/{item_id}",
        headers=intruder["headers"],
        json={"quantity": 9},
    ).status_code == 404
    assert client.delete(
        f"/api/v1/supermarket/carts/carrefour/items/{item_id}",
        headers=intruder["headers"],
    ).status_code == 404

    # The owner's cart is untouched.
    cart = client.get("/api/v1/supermarket/carts/carrefour", headers=owner["headers"]).json()
    assert cart["items"][0]["quantity"] == 1


def test_cart_scoped_per_user_same_store(client, test_engine):
    user_a = register_user(client, "cart-a@adamelhirch.com")
    user_b = register_user(client, "cart-b@adamelhirch.com")
    cache_id = _seed_cache(test_engine, store=SupermarketStore.CARREFOUR)

    client.post(
        "/api/v1/supermarket/carts/carrefour/items",
        headers=user_a["headers"],
        json={"cache_id": cache_id},
    )
    client.post(
        "/api/v1/supermarket/carts/carrefour/items",
        headers=user_b["headers"],
        json={"cache_id": cache_id},
    )

    a_carts = client.get("/api/v1/supermarket/carts", headers=user_a["headers"]).json()
    b_carts = client.get("/api/v1/supermarket/carts", headers=user_b["headers"]).json()
    assert len(a_carts) == 1
    assert len(b_carts) == 1
    assert a_carts[0]["id"] != b_carts[0]["id"]
