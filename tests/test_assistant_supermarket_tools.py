from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, select

from app.models import (
    GroceryItem,
    GroceryPantrySync,
    PantryItem,
    SupermarketSearchCache,
    SupermarketStore,
)
from app.schemas.supermarket import SupermarketStoreLocationRead
from tests.conftest import register_user


def _seed_cache(
    session: Session,
    *,
    store: SupermarketStore = SupermarketStore.LECLERC,
    name: str = "Beurre doux Marque Repère",
    query: str = "beurre",
    price_amount: float = 2.10,
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
        fetched_at=now,
        expires_at=now + timedelta(days=2),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_assistant_supermarket_search_and_set_favorite_store(client, auth_headers):
    # 1. supermarket.search_stores
    with patch(
        "app.services.supermarket.store_locator.SupermarketStoreLocator.search_stores",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = [
            SupermarketStoreLocationRead(
                store=SupermarketStore.LECLERC,
                external_store_id="0123",
                name="E.Leclerc Toulouse Blagnac",
                address="2 Allée Émile Zola",
                zipcode="31700",
                city="Blagnac",
                pickup_type="quai",
            )
        ]

        res = client.post(
            "/api/v1/skill/execute",
            headers=auth_headers,
            json={
                "action": "supermarket.search_stores",
                "input": {"store": "leclerc", "zipcode": "31700", "city": "Blagnac"},
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["ok"] is True
        assert len(data["data"]["stores"]) == 1
        assert data["data"]["stores"][0]["name"] == "E.Leclerc Toulouse Blagnac"

    # 2. supermarket.set_favorite_store
    set_res = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "supermarket.set_favorite_store",
            "input": {
                "store": "leclerc",
                "external_store_id": "0123",
                "store_label": "E.Leclerc Blagnac",
                "pickup_type": "quai",
                "optimization_strategy": "mdd",
            },
        },
    )
    assert set_res.status_code == 200, set_res.text
    set_data = set_res.json()
    assert set_data["ok"] is True
    assert set_data["data"]["preference"]["store"] == "leclerc"
    assert set_data["data"]["preference"]["external_store_id"] == "0123"


def test_assistant_supermarket_cart_lifecycle(client, test_engine, owner_id, auth_headers):
    with Session(test_engine) as session:
        g = GroceryItem(user_id=owner_id, name="Beurre", quantity=1, unit="item")
        session.add(g)
        session.commit()
        session.refresh(g)
        g_id = g.id

        _seed_cache(session, store=SupermarketStore.LECLERC, name="Beurre Repère", price_amount=2.20)

    # 1. supermarket.prepare_cart
    prep_res = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "supermarket.prepare_cart",
            "input": {
                "store": "leclerc",
                "optimization_strategy": "mdd",
            },
        },
    )
    assert prep_res.status_code == 200, prep_res.text
    prep_data = prep_res.json()
    assert prep_data["ok"] is True
    job = prep_data["data"]["job"]
    assert job["store"] == "leclerc"
    assert job["items_count"] == 1
    job_id = job["id"]

    # 2. supermarket.confirm_cart_sync
    sync_res = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "supermarket.confirm_cart_sync",
            "input": {"job_id": job_id},
        },
    )
    assert sync_res.status_code == 200, sync_res.text
    sync_data = sync_res.json()
    assert sync_data["ok"] is True
    assert sync_data["data"]["sync"]["status"] == "synced"

    # Constitution Principle III: in_cart = True, checked = False
    with Session(test_engine) as session:
        refreshed_g = session.get(GroceryItem, g_id)
        assert refreshed_g.in_cart is True
        assert refreshed_g.checked is False

    # 3. supermarket.confirm_pickup
    pickup_res = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={
            "action": "supermarket.confirm_pickup",
            "input": {"job_id": job_id},
        },
    )
    assert pickup_res.status_code == 200, pickup_res.text
    pickup_data = pickup_res.json()
    assert pickup_data["ok"] is True
    assert pickup_data["data"]["pickup"]["status"] == "completed"

    # Constitution Principle III: checked = True, pantry item restocked
    with Session(test_engine) as session:
        refreshed_g = session.get(GroceryItem, g_id)
        assert refreshed_g.checked is True
        sync_record = session.exec(select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == g_id)).first()
        assert sync_record is not None


def test_mcp_supermarket_tools_exposure():
    from app.mcp.server import _ACTION_BY_NAME, _informal_schema_to_json_schema

    expected_actions = [
        "supermarket.search_stores",
        "supermarket.set_favorite_store",
        "supermarket.prepare_cart",
        "supermarket.confirm_cart_sync",
        "supermarket.confirm_pickup",
    ]

    for act in expected_actions:
        assert act in _ACTION_BY_NAME, f"Action {act} missing from MCP _ACTION_BY_NAME"
        entry = _ACTION_BY_NAME[act]
        schema = _informal_schema_to_json_schema(entry["input_schema"])
        assert schema["type"] == "object"

