from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app.models import (
    GroceryItem,
    GroceryToCartJob,
    MatchedCartItem,
    SupermarketSearchCache,
    SupermarketStore,
    User,
    UserStorePreference,
)
from app.services.supermarket.cart_job_service import CartJobService
from app.skill.actions import execute_action
from tests.conftest import register_user


def _seed_cache(
    session: Session,
    *,
    store: SupermarketStore = SupermarketStore.LECLERC,
    name: str,
    query: str,
    price_amount: float = 1.50,
    external_id: str = "sku-1",
) -> SupermarketSearchCache:
    now = datetime.now(UTC)
    row = SupermarketSearchCache(
        store=store,
        query=query,
        external_id=external_id,
        name=name,
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


def test_user_store_preferences_multi_tenant_isolation(client):
    user_a = register_user(client, "tenant-a@adamelhirch.com")
    user_b = register_user(client, "tenant-b@adamelhirch.com")

    # User A sets preferred store
    payload_a = {
        "external_store_id": "L-31000",
        "store_label": "E.Leclerc Roques",
        "location_label": "Allée de Fraixinet, 31120 Roques",
        "pickup_type": "quai",
        "optimization_strategy": "mdd",
    }
    resp = client.put("/api/v1/supermarket/stores/preferences/leclerc", headers=user_a["headers"], json=payload_a)
    assert resp.status_code == 200, resp.text

    # User B checks preferences -> should be empty
    resp_b = client.get("/api/v1/supermarket/stores/preferences", headers=user_b["headers"])
    assert resp_b.status_code == 200
    assert resp_b.json() == []

    # User B sets preferred store
    payload_b = {
        "external_store_id": "INT-31500",
        "store_label": "Intermarché Toulouse",
        "location_label": "31500 Toulouse",
        "pickup_type": "pieton",
        "optimization_strategy": "budget",
    }
    resp = client.put("/api/v1/supermarket/stores/preferences/intermarche", headers=user_b["headers"], json=payload_b)
    assert resp.status_code == 200

    # User A preferences still isolated
    resp_a = client.get("/api/v1/supermarket/stores/preferences", headers=user_a["headers"])
    assert resp_a.status_code == 200
    pref_a = resp_a.json()
    assert len(pref_a) == 1
    assert pref_a[0]["store"] == "leclerc"
    assert pref_a[0]["external_store_id"] == "L-31000"

    # User B preferences still isolated
    resp_b = client.get("/api/v1/supermarket/stores/preferences", headers=user_b["headers"])
    assert resp_b.status_code == 200
    pref_b = resp_b.json()
    assert len(pref_b) == 1
    assert pref_b[0]["store"] == "intermarche"
    assert pref_b[0]["external_store_id"] == "INT-31500"


def test_cart_jobs_cross_tenant_access_denied_404(client, test_engine):
    user_a = register_user(client, "tenant-cart-a@adamelhirch.com")
    user_b = register_user(client, "tenant-cart-b@adamelhirch.com")

    # Seed User A groceries and cache
    with Session(test_engine) as session:
        _seed_cache(session, store=SupermarketStore.LECLERC, name="Pain de mie complet", query="pain de mie")
        g_a = GroceryItem(user_id=user_a["user"]["id"], name="Pain de mie", quantity=1, unit="item")
        session.add(g_a)
        session.commit()
        session.refresh(g_a)

    resp_job = client.post(
        "/api/v1/supermarket/cart/jobs",
        headers=user_a["headers"],
        json={"store": "leclerc", "optimization_strategy": "mdd"},
    )
    assert resp_job.status_code == 201, resp_job.text
    job_a_id = resp_job.json()["id"]
    assert len(resp_job.json()["items"]) > 0
    item_a_id = resp_job.json()["items"][0]["id"]

    # 1. User B cannot GET User A's job
    resp = client.get(f"/api/v1/supermarket/cart/jobs/{job_a_id}", headers=user_b["headers"])
    assert resp.status_code == 404

    # 2. User B cannot PATCH an item in User A's job
    resp = client.patch(
        f"/api/v1/supermarket/cart/jobs/{job_a_id}/items/{item_a_id}",
        headers=user_b["headers"],
        json={"status": "removed"},
    )
    assert resp.status_code == 404

    # 3. User B cannot refine User A's job
    resp = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_a_id}/refine",
        headers=user_b["headers"],
    )
    assert resp.status_code == 404

    # 4. User B cannot sync User A's job
    resp = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_a_id}/sync",
        headers=user_b["headers"],
    )
    assert resp.status_code == 404

    # 5. User B cannot confirm pickup on User A's job
    resp = client.post(
        f"/api/v1/supermarket/cart/jobs/{job_a_id}/confirm-pickup",
        headers=user_b["headers"],
    )
    assert resp.status_code == 404


def test_cross_tenant_item_tampering_prevented(client, test_engine):
    user_a = register_user(client, "tamper-a@adamelhirch.com")
    user_b = register_user(client, "tamper-b@adamelhirch.com")

    with Session(test_engine) as session:
        _seed_cache(session, store=SupermarketStore.LECLERC, name="Pommes Gala 1kg", query="pommes gala", external_id="sku-a")
        _seed_cache(session, store=SupermarketStore.LECLERC, name="Poires Williams 1kg", query="poires williams", external_id="sku-b")
        ga = GroceryItem(user_id=user_a["user"]["id"], name="Pommes Gala", quantity=4, unit="item")
        gb = GroceryItem(user_id=user_b["user"]["id"], name="Poires Williams", quantity=2, unit="item")
        session.add_all([ga, gb])
        session.commit()

    resp_a = client.post(
        "/api/v1/supermarket/cart/jobs",
        headers=user_a["headers"],
        json={"store": "leclerc"},
    )
    assert resp_a.status_code == 201
    job_a_id = resp_a.json()["id"]
    assert len(resp_a.json()["items"]) > 0
    item_a_id = resp_a.json()["items"][0]["id"]

    resp_b = client.post(
        "/api/v1/supermarket/cart/jobs",
        headers=user_b["headers"],
        json={"store": "leclerc"},
    )
    assert resp_b.status_code == 201
    job_b_id = resp_b.json()["id"]

    # User B attempts to patch User A's item using User B's valid job_b_id
    resp = client.patch(
        f"/api/v1/supermarket/cart/jobs/{job_b_id}/items/{item_a_id}",
        headers=user_b["headers"],
        json={"status": "removed"},
    )
    assert resp.status_code == 404


def test_cart_matcher_service_strict_grocery_scoping(client, test_engine):
    user_a = register_user(client, "grocery-scope-a@adamelhirch.com")
    user_b = register_user(client, "grocery-scope-b@adamelhirch.com")

    with Session(test_engine) as session:
        ga = GroceryItem(user_id=user_a["user"]["id"], name="Fromage blanc", quantity=1, unit="item")
        session.add(ga)
        session.commit()
        session.refresh(ga)
        ga_id = ga.id

    # User B attempts to create a job requesting User A's grocery item id
    resp_b = client.post(
        "/api/v1/supermarket/cart/jobs",
        headers=user_b["headers"],
        json={"store": "leclerc", "item_ids": [ga_id]},
    )
    assert resp_b.status_code == 201
    # User A's item should NOT be included in User B's job items
    items_b = resp_b.json()["items"]
    assert len(items_b) == 0


def test_assistant_skill_actions_tenant_isolation(client, test_engine):
    user_a = register_user(client, "assistant-scope-a@adamelhirch.com")
    user_b = register_user(client, "assistant-scope-b@adamelhirch.com")

    with Session(test_engine) as session:
        ga = GroceryItem(user_id=user_a["user"]["id"], name="Pâtes coquillettes", quantity=2, unit="item")
        session.add(ga)
        session.commit()

    resp_a = client.post(
        "/api/v1/supermarket/cart/jobs",
        headers=user_a["headers"],
        json={"store": "leclerc"},
    )
    job_a_id = resp_a.json()["id"]

    with Session(test_engine) as session:
        user_obj_b = session.get(User, user_b["user"]["id"])
        # User B attempting to confirm cart sync on User A's job via skill action
        with pytest.raises(ValueError, match=r"introuvable|not found"):
            execute_action("supermarket.confirm_cart_sync", {"job_id": job_a_id}, session, user=user_obj_b)

        # User B attempting to confirm pickup on User A's job via skill action
        with pytest.raises(ValueError, match=r"introuvable|not found"):
            execute_action("supermarket.confirm_pickup", {"job_id": job_a_id}, session, user=user_obj_b)
