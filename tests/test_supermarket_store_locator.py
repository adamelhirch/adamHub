from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, select

from app.models import SupermarketStore, UserStorePreference
from app.schemas.supermarket import SupermarketStoreLocationRead
from tests.conftest import register_user


def test_store_preferences_crud_and_isolation(client, test_engine):
    user_a = register_user(client, "store-a@adamelhirch.com")
    user_b = register_user(client, "store-b@adamelhirch.com")

    # User A starts with no preferences
    res = client.get("/api/v1/supermarket/stores/preferences", headers=user_a["headers"])
    assert res.status_code == 200
    assert res.json() == []

    # User A sets Leclerc preference
    put_data = {
        "external_store_id": "0123_TAPE_1",
        "store_label": "Borne TAPE Leclerc Cornebarrieu",
        "location_label": "Route de Colomiers, 31700 Cornebarrieu",
        "pickup_type": "tape",
        "optimization_strategy": "mdd",
        "channel": "tape",
        "raw_context": {"terminal_id": "TAPE-1"},
    }
    put_res = client.put(
        "/api/v1/supermarket/stores/preferences/leclerc",
        headers=user_a["headers"],
        json=put_data,
    )
    assert put_res.status_code == 200
    pref = put_res.json()
    assert pref["store"] == "leclerc"
    assert pref["external_store_id"] == "0123_TAPE_1"
    assert pref["pickup_type"] == "tape"
    assert pref["optimization_strategy"] == "mdd"

    # User A retrieves preferences
    get_res = client.get("/api/v1/supermarket/stores/preferences", headers=user_a["headers"])
    assert get_res.status_code == 200
    items = get_res.json()
    assert len(items) == 1
    assert items[0]["external_store_id"] == "0123_TAPE_1"

    # Multi-tenant isolation: User B still has empty preferences
    b_res = client.get("/api/v1/supermarket/stores/preferences", headers=user_b["headers"])
    assert b_res.status_code == 200
    assert b_res.json() == []

    # User A updates Leclerc preference to quai drive (upsert)
    update_data = {
        "external_store_id": "0123",
        "store_label": "E.Leclerc Drive Blagnac",
        "location_label": "Zone Commerciale Grand Noble",
        "pickup_type": "quai",
        "optimization_strategy": "bio",
        "channel": "drive",
        "raw_context": {},
    }
    put_res2 = client.put(
        "/api/v1/supermarket/stores/preferences/leclerc",
        headers=user_a["headers"],
        json=update_data,
    )
    assert put_res2.status_code == 200
    pref2 = put_res2.json()
    assert pref2["external_store_id"] == "0123"
    assert pref2["pickup_type"] == "quai"
    assert pref2["optimization_strategy"] == "bio"

    # Verify only 1 row exists for User A + Leclerc
    with Session(test_engine) as session:
        rows = session.exec(
            select(UserStorePreference).where(
                UserStorePreference.user_id == user_a["user"]["id"],
                UserStorePreference.store == SupermarketStore.LECLERC,
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].external_store_id == "0123"


def test_store_search_endpoint(client, auth_headers):
    mock_locations = [
        SupermarketStoreLocationRead(
            store=SupermarketStore.LECLERC,
            external_store_id="0123",
            name="E.Leclerc Drive Blagnac",
            address="Zone Commerciale Grand Noble",
            zipcode="31700",
            city="Blagnac",
            pickup_type="quai",
            distance_km=2.4,
            channel="drive",
        ),
        SupermarketStoreLocationRead(
            store=SupermarketStore.LECLERC,
            external_store_id="0123_TAPE_1",
            name="Borne TAPE Leclerc Cornebarrieu",
            address="Route de Colomiers",
            zipcode="31700",
            city="Cornebarrieu",
            pickup_type="tape",
            distance_km=4.8,
            channel="tape",
        ),
    ]

    with patch(
        "app.services.supermarket.store_locator.SupermarketStoreLocator.search_stores",
        new=AsyncMock(return_value=mock_locations),
    ):
        res = client.get(
            "/api/v1/supermarket/stores/search",
            headers=auth_headers,
            params={"store": "leclerc", "zipcode": "31700"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert len(data) == 2
        assert data[0]["external_store_id"] == "0123"
        assert data[0]["pickup_type"] == "quai"
        assert data[1]["pickup_type"] == "tape"


def test_store_search_carrefour_compiegne_fallback():
    import asyncio
    from app.services.supermarket.store_locator import SupermarketStoreLocator

    # Test searching for Carrefour in Compiègne
    results = asyncio.run(
        SupermarketStoreLocator.search_stores(
            store=SupermarketStore.CARREFOUR,
            city="Carrefour Compiègne",
        )
    )
    assert len(results) >= 1
    # Ensure retailer name is stripped from city and drives are properly formed
    compiegne_results = [r for r in results if "Compiègne" in r.city or "60200" in (r.zipcode or "") or "Venette" in r.name]
    assert len(compiegne_results) >= 1
    assert compiegne_results[0].store == SupermarketStore.CARREFOUR


def test_store_search_carrefour_compans():
    import asyncio
    from app.services.supermarket.store_locator import SupermarketStoreLocator

    # Test searching for Carrefour in Compans (Toulouse)
    results = asyncio.run(
        SupermarketStoreLocator.search_stores(
            store=SupermarketStore.CARREFOUR,
            city="Compans",
        )
    )
    assert len(results) >= 1
    compans_matches = [r for r in results if "compans" in r.name.lower() or "compans" in (r.address or "").lower()]
    assert len(compans_matches) >= 1
    assert compans_matches[0].store == SupermarketStore.CARREFOUR
    assert compans_matches[0].external_store_id == "1509"


