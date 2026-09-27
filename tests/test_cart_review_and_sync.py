from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app.models import (
    GroceryItem,
    GroceryPantrySync,
    GroceryToCartJob,
    MatchedCartItem,
    PantryItem,
    SubstituteProposal,
    SupermarketSearchCache,
    SupermarketStore,
)
from app.services.supermarket.cart_job_service import CartJobService
from tests.conftest import register_user


def _seed_cache(
    session: Session,
    *,
    store: SupermarketStore = SupermarketStore.LECLERC,
    name: str,
    brand: str | None = None,
    query: str = "beurre",
    price_amount: float = 2.10,
    packaging: str = "250g",
    external_id: str = "sku-1",
) -> SupermarketSearchCache:
    now = datetime.now(UTC)
    row = SupermarketSearchCache(
        store=store,
        query=query,
        external_id=external_id,
        name=name,
        brand=brand,
        packaging=packaging,
        price_amount=price_amount,
        price_text=f"{price_amount:.2f} €",
        image_url="https://img.test/p.png",
        product_url="https://store.test/p",
        fetched_at=now,
        expires_at=now + timedelta(days=2),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_update_cart_item_and_remove(client, test_engine):
    user = register_user(client, "cart-review-user@adamelhirch.com")

    with Session(test_engine) as session:
        g1 = GroceryItem(user_id=user["user"]["id"], name="Beurre doux", quantity=1, unit="item")
        g2 = GroceryItem(user_id=user["user"]["id"], name="Lait demi-écrémé", quantity=2, unit="item")
        session.add_all([g1, g2])
        session.commit()
        session.refresh(g1)
        session.refresh(g2)

        cache1 = _seed_cache(
            session,
            name="Beurre doux Marque Repère",
            price_amount=2.00,
            external_id="sku-b-1",
            query="beurre doux",
        )
        cache2 = _seed_cache(
            session,
            name="Lait demi-écrémé 1L",
            price_amount=1.10,
            external_id="sku-l-1",
            query="lait demi-écrémé",
        )

        now = datetime.now(UTC)
        job = GroceryToCartJob(
            user_id=user["user"]["id"],
            store=SupermarketStore.LECLERC,
            external_store_id="drive-1",
            status="reviewing",
            items_count=2,
            matched_count=2,
            estimated_total_cents=420,  # 200 + 2*110
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

        it1 = MatchedCartItem(
            job_id=job.id,
            grocery_item_id=g1.id,
            cache_id=cache1.id,
            external_id="sku-b-1",
            name="Beurre doux Marque Repère",
            quantity=1,
            unit_price_cents=200,
            total_price_cents=200,
            status="staged",
        )
        it2 = MatchedCartItem(
            job_id=job.id,
            grocery_item_id=g2.id,
            cache_id=cache2.id,
            external_id="sku-l-1",
            name="Lait demi-écrémé 1L",
            quantity=2,
            unit_price_cents=110,
            total_price_cents=220,
            status="staged",
        )
        session.add_all([it1, it2])
        session.commit()
        session.refresh(it1)
        session.refresh(it2)
        it1_id = it1.id
        it2_id = it2.id

    # 1. Update item 1: mark to_modify with custom note
    res1 = client.patch(
        f"/api/v1/supermarket/cart/jobs/{job_id}/items/{it1_id}",
        headers=user["headers"],
        json={"status": "to_modify", "custom_note": "Préférer demi-sel"},
    )
    assert res1.status_code == 200, res1.text
    assert res1.json()["status"] == "to_modify"
    assert res1.json()["custom_note"] == "Préférer demi-sel"

    # 2. Update item 2: mark removed (swipe left)
    res2 = client.patch(
        f"/api/v1/supermarket/cart/jobs/{job_id}/items/{it2_id}",
        headers=user["headers"],
        json={"status": "removed"},
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()["status"] == "removed"

    # 3. Read back job to verify updated estimated total (only active items counted)
    res_job = client.get(f"/api/v1/supermarket/cart/jobs/{job_id}", headers=user["headers"])
    assert res_job.status_code == 200
    job_data = res_job.json()
    assert job_data["estimated_total_cents"] == 200


def test_refine_job_batch(client, test_engine):
    user = register_user(client, "cart-refine-user@adamelhirch.com")

    with Session(test_engine) as session:
        g = GroceryItem(user_id=user["user"]["id"], name="Beurre", quantity=1, unit="item")
        session.add(g)
        session.commit()
        session.refresh(g)

        c1 = _seed_cache(
            session,
            name="Beurre doux standard",
            price_amount=2.00,
            external_id="sku-b-doux",
            query="beurre",
        )
        c2 = _seed_cache(
            session,
            name="Beurre demi-sel Bio Repère",
            brand="Marque Repère",
            price_amount=2.40,
            external_id="sku-b-demi-sel",
            query="beurre demi-sel bio",
        )

        now = datetime.now(UTC)
        job = GroceryToCartJob(
            user_id=user["user"]["id"],
            store=SupermarketStore.LECLERC,
            external_store_id="drive-1",
            status="reviewing",
            items_count=1,
            matched_count=1,
            estimated_total_cents=200,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

        it = MatchedCartItem(
            job_id=job.id,
            grocery_item_id=g.id,
            cache_id=c1.id,
            external_id="sku-b-doux",
            name="Beurre doux standard",
            quantity=1,
            unit_price_cents=200,
            total_price_cents=200,
            status="to_modify",
            custom_note="Prendre du beurre demi-sel bio",
        )
        session.add(it)
        session.commit()
        session.refresh(it)

    # Trigger refinement
    refine_res = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_id}/refine",
        headers=user["headers"],
        json={"adjustments": []},
    )
    assert refine_res.status_code == 200, refine_res.text
    data = refine_res.json()
    assert data["status"] == "reviewing"
    assert data["estimated_total_cents"] == 240
    refreshed_item = data["items"][0]
    assert refreshed_item["name"] == "Beurre demi-sel Bio Repère"
    assert refreshed_item["status"] == "staged"


def test_sync_remote_cart_principle_iii(client, test_engine):
    user = register_user(client, "cart-sync-user@adamelhirch.com")

    with Session(test_engine) as session:
        g1 = GroceryItem(user_id=user["user"]["id"], name="Pâtes Penne", quantity=2, unit="item", in_cart=False, checked=False)
        session.add(g1)
        session.commit()
        session.refresh(g1)
        g1_id = g1.id

        cache1 = _seed_cache(
            session,
            name="Pâtes Penne Rigate 500g",
            price_amount=1.15,
            external_id="sku-penne",
            query="pâtes",
        )

        now = datetime.now(UTC)
        job = GroceryToCartJob(
            user_id=user["user"]["id"],
            store=SupermarketStore.LECLERC,
            external_store_id="drive-1",
            status="reviewing",
            items_count=1,
            matched_count=1,
            estimated_total_cents=230,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

        it1 = MatchedCartItem(
            job_id=job.id,
            grocery_item_id=g1.id,
            cache_id=cache1.id,
            external_id="sku-penne",
            name="Pâtes Penne Rigate 500g",
            quantity=2,
            unit_price_cents=115,
            total_price_cents=230,
            status="staged",
        )
        session.add(it1)
        session.commit()
        session.refresh(it1)

    # Sync to remote cart
    sync_res = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_id}/sync",
        headers=user["headers"],
    )
    assert sync_res.status_code == 200, sync_res.text
    sync_data = sync_res.json()
    assert sync_data["status"] == "synced"
    assert sync_data["items_synced_count"] == 1

    # Constitution Principle III: in_cart is True, checked is False, pantry is NOT restocked
    with Session(test_engine) as session:
        g_refreshed = session.get(GroceryItem, g1_id)
        assert g_refreshed.in_cart is True
        assert g_refreshed.checked is False

        pantry_count = session.exec(select(PantryItem).where(PantryItem.user_id == user["user"]["id"])).all()
        assert len(pantry_count) == 0

        sync_rows = session.exec(select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == g1_id)).all()
        assert len(sync_rows) == 0


def test_confirm_pickup_principle_iii(client, test_engine):
    user = register_user(client, "cart-pickup-user@adamelhirch.com")

    with Session(test_engine) as session:
        g1 = GroceryItem(user_id=user["user"]["id"], name="Pâtes Penne", quantity=2, unit="item", in_cart=True, checked=False)
        session.add(g1)
        session.commit()
        session.refresh(g1)
        g1_id = g1.id

        cache1 = _seed_cache(
            session,
            name="Pâtes Penne Rigate 500g",
            price_amount=1.15,
            external_id="sku-penne",
            query="pâtes",
        )

        now = datetime.now(UTC)
        job = GroceryToCartJob(
            user_id=user["user"]["id"],
            store=SupermarketStore.LECLERC,
            external_store_id="drive-1",
            status="synced",
            items_count=1,
            matched_count=1,
            estimated_total_cents=230,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

        it1 = MatchedCartItem(
            job_id=job.id,
            grocery_item_id=g1.id,
            cache_id=cache1.id,
            external_id="sku-penne",
            name="Pâtes Penne Rigate 500g",
            quantity=2,
            unit_price_cents=115,
            total_price_cents=230,
            status="staged",
        )
        session.add(it1)
        session.commit()
        session.refresh(it1)

    # Confirm pickup
    pickup_res = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_id}/confirm-pickup",
        headers=user["headers"],
    )
    assert pickup_res.status_code == 200, pickup_res.text
    pickup_data = pickup_res.json()
    assert pickup_data["status"] == "completed"
    assert pickup_data["restocked_items_count"] == 1

    # Constitution Principle III: checked is True, pantry restocked via GroceryPantrySync
    with Session(test_engine) as session:
        g_refreshed = session.get(GroceryItem, g1_id)
        assert g_refreshed.checked is True

        pantry_items = session.exec(select(PantryItem).where(PantryItem.user_id == user["user"]["id"])).all()
        assert len(pantry_items) == 1
        assert pantry_items[0].name == "Pâtes Penne"
        assert pantry_items[0].quantity == 2.0

        sync_rows = session.exec(select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == g1_id)).all()
        assert len(sync_rows) == 1
        assert sync_rows[0].pantry_item_id == pantry_items[0].id
        assert sync_rows[0].added_quantity == 2.0


def test_cross_user_isolation_review_and_sync(client, test_engine):
    user_a = register_user(client, "sync-user-a@adamelhirch.com")
    user_b = register_user(client, "sync-user-b@adamelhirch.com")

    with Session(test_engine) as session:
        job = GroceryToCartJob(
            user_id=user_a["user"]["id"],
            store=SupermarketStore.LECLERC,
            external_store_id="drive-1",
            status="reviewing",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

        it = MatchedCartItem(
            job_id=job.id,
            name="Test item",
            quantity=1,
            unit_price_cents=100,
            total_price_cents=100,
            status="staged",
        )
        session.add(it)
        session.commit()
        session.refresh(it)
        it_id = it.id

    # User B cannot patch item
    p_res = client.patch(
        f"/api/v1/supermarket/cart/jobs/{job_id}/items/{it_id}",
        headers=user_b["headers"],
        json={"status": "removed"},
    )
    assert p_res.status_code == 404

    # User B cannot refine
    r_res = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_id}/refine",
        headers=user_b["headers"],
        json={"adjustments": []},
    )
    assert r_res.status_code == 404

    # User B cannot sync
    s_res = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_id}/sync",
        headers=user_b["headers"],
    )
    assert s_res.status_code == 404

    # User B cannot confirm pickup
    c_res = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_id}/confirm-pickup",
        headers=user_b["headers"],
    )
    assert c_res.status_code == 404

    # User B cannot delete User A's job
    del_b = client.delete(
        f"/api/v1/supermarket/cart/jobs/{job_id}",
        headers=user_b["headers"],
    )
    assert del_b.status_code == 404

    # User A can delete the job
    del_a = client.delete(
        f"/api/v1/supermarket/cart/jobs/{job_id}",
        headers=user_a["headers"],
    )
    assert del_a.status_code == 204

    # Job is gone
    get_res = client.get(
        f"/api/v1/supermarket/cart/jobs/{job_id}",
        headers=user_a["headers"],
    )
    assert get_res.status_code == 404

    # Active job is now None
    active_res = client.get(
        "/api/v1/supermarket/cart/jobs/active",
        headers=user_a["headers"],
    )
    assert active_res.status_code == 200
    assert active_res.json() is None

