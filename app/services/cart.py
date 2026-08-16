"""Cart (panier) service.

The single seam through which callers manage a user's supermarket carts and
their line items. One cart exists per (user, store); items are snapshotted from
``SupermarketSearchCache`` rows (via ``cache_id``) and never from client input,
mirroring the catalog rule that store metadata is only ever trusted when it
comes from a cache row. Callers hold no knowledge of the cache table or of
which fields count as "store metadata".
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models import (
    CartStatus,
    SupermarketCart,
    SupermarketCartItem,
    SupermarketSearchCache,
    SupermarketStore,
)


def get_cart(
    session: Session, store: SupermarketStore, user_id: int | None = None
) -> SupermarketCart | None:
    statement = select(SupermarketCart).where(SupermarketCart.store == store)
    if user_id is not None:
        statement = statement.where(SupermarketCart.user_id == user_id)
    else:
        statement = statement.where(SupermarketCart.user_id.is_(None))
    return session.exec(statement).first()


def upsert_cart(
    session: Session,
    store: SupermarketStore,
    user_id: int | None = None,
    *,
    external_cart_ref: str | None = None,
) -> SupermarketCart:
    """Get or create the draft cart for a user + store.

    The (user, store) unique key means the existing cart is returned whatever
    its status; callers decide whether to move it back to draft themselves.
    """
    cart = get_cart(session, store, user_id=user_id)
    now = datetime.now(UTC)
    if cart is None:
        cart = SupermarketCart(
            user_id=user_id,
            store=store,
            status=CartStatus.DRAFT,
            external_cart_ref=external_cart_ref,
            created_at=now,
            updated_at=now,
        )
        session.add(cart)
        session.commit()
        session.refresh(cart)
        return cart
    if external_cart_ref is not None:
        cart.external_cart_ref = external_cart_ref
        cart.updated_at = now
        session.add(cart)
        session.commit()
        session.refresh(cart)
    return cart


def list_carts(session: Session, user_id: int | None = None) -> list[SupermarketCart]:
    statement = select(SupermarketCart)
    if user_id is not None:
        statement = statement.where(SupermarketCart.user_id == user_id)
    else:
        statement = statement.where(SupermarketCart.user_id.is_(None))
    return list(
        session.exec(statement.order_by(SupermarketCart.store, SupermarketCart.id)).all()
    )


def _snapshot_from_cache(cache_row: SupermarketSearchCache) -> dict:
    return {
        "external_id": cache_row.external_id,
        "name": cache_row.name,
        "brand": cache_row.brand,
        "packaging": cache_row.packaging,
        "price_amount": cache_row.price_amount,
        "price_text": cache_row.price_text,
        "image_url": cache_row.image_url,
        "product_url": cache_row.product_url,
    }


def _utcnow_naive() -> datetime:
    # SQLModel persists DateTime columns as naive UTC; compare like-for-like so
    # an aware `now` never clashes with a naive value read back from the DB.
    return datetime.now(UTC).replace(tzinfo=None)


def _load_fresh_cache(session: Session, cache_id: int) -> SupermarketSearchCache:
    cache_row = session.get(SupermarketSearchCache, cache_id)
    if cache_row is None:
        raise HTTPException(status_code=400, detail="Search cache entry not found")
    expires_at = cache_row.expires_at
    if expires_at is not None and expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(UTC).replace(tzinfo=None)
    if expires_at is None or expires_at < _utcnow_naive():
        raise HTTPException(status_code=400, detail="Search cache entry expired")
    return cache_row


def add_item(
    session: Session,
    cart: SupermarketCart,
    cache_id: int,
    quantity: int = 1,
) -> SupermarketCartItem:
    """Add (or merge) a line item to a cart, snapshotted from a cache row.

    The cache row is the only trusted source of the item's store metadata: an
    unknown or expired ``cache_id`` is a 400. Re-adding the same ``cache_id``
    merges into the existing line by bumping its quantity.
    """
    cache_row = _load_fresh_cache(session, cache_id)

    existing = session.exec(
        select(SupermarketCartItem).where(
            SupermarketCartItem.cart_id == cart.id,
            SupermarketCartItem.cache_id == cache_id,
        )
    ).first()
    if existing is not None:
        existing.quantity += quantity
        existing.updated_at = datetime.now(UTC)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    snapshot = _snapshot_from_cache(cache_row)
    now = datetime.now(UTC)
    item = SupermarketCartItem(
        cart_id=cart.id,
        cache_id=cache_id,
        quantity=quantity,
        created_at=now,
        updated_at=now,
        **snapshot,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def _get_cart_item(session: Session, cart: SupermarketCart, item_id: int) -> SupermarketCartItem:
    item = session.get(SupermarketCartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return item


def update_quantity(
    session: Session, cart: SupermarketCart, item_id: int, quantity: int
) -> SupermarketCartItem:
    item = _get_cart_item(session, cart, item_id)
    item.quantity = quantity
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def remove_item(session: Session, cart: SupermarketCart, item_id: int) -> None:
    item = _get_cart_item(session, cart, item_id)
    session.delete(item)
    session.commit()


def clear_cart(session: Session, cart: SupermarketCart) -> None:
    session.exec(
        delete(SupermarketCartItem)
        .where(SupermarketCartItem.cart_id == cart.id)
        .execution_options(synchronize_session=False)
    )
    cart.updated_at = datetime.now(UTC)
    session.add(cart)
    session.commit()


def set_status(
    session: Session, cart: SupermarketCart, status: CartStatus
) -> SupermarketCart:
    now = datetime.now(UTC)
    cart.status = status
    cart.validated_at = now if status is CartStatus.VALIDATED else None
    cart.updated_at = now
    session.add(cart)
    session.commit()
    session.refresh(cart)
    return cart
