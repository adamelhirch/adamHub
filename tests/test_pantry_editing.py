from datetime import date
from sqlmodel import Session, select
from app.models import PantryItem

def test_pantry_item_creation_and_full_update(client, auth_headers, test_engine):
    # 1. Create item
    res = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={
            "name": "Saumon",
            "quantity": 250.0,
            "unit": "g",
            "category": "Poisson",
            "location": "Réfrigérateur",
            "note": "pavé",
        },
    )
    assert res.status_code == 200
    created = res.json()
    item_id = created["id"]
    assert created["name"] == "Saumon"
    assert created["quantity"] == 250.0

    # 2. Update with all fields
    update_res = client.patch(
        f"/api/v1/pantry/items/{item_id}",
        headers=auth_headers,
        json={
            "name": "Saumon frais",
            "quantity": 300.0,
            "unit": "g",
            "category": "Poisson",
            "location": "Réfrigérateur",
            "expires_at": "2026-09-30",
            "note": "2 pavés de 150 g",
            "min_quantity": 100.0,
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["id"] == item_id
    assert updated["name"] == "Saumon frais"
    assert updated["quantity"] == 300.0
    assert updated["unit"] == "g"
    assert updated["category"] == "Poisson"
    assert updated["location"] == "Réfrigérateur"
    assert updated["expires_at"] == "2026-09-30"
    assert updated["note"] == "2 pavés de 150 g"
    assert updated["min_quantity"] == 100.0

    # 3. Verify in list
    list_res = client.get("/api/v1/pantry/items", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()
    match = next(i for i in items if i["id"] == item_id)
    assert match["name"] == "Saumon frais"
    assert match["quantity"] == 300.0
    assert match["expires_at"] == "2026-09-30"


def test_pantry_update_negative_quantity_fails(client, auth_headers):
    # 1. Create item
    res = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Pâtes", "quantity": 500.0, "unit": "g"},
    )
    assert res.status_code == 200
    item_id = res.json()["id"]

    # 2. Try updating to negative quantity
    update_res = client.patch(
        f"/api/v1/pantry/items/{item_id}",
        headers=auth_headers,
        json={"quantity": -50.0},
    )
    assert update_res.status_code == 422


def test_pantry_cross_tenant_protection(client, auth_headers, test_engine):
    from tests.conftest import register_user

    # Create item under owner user
    res = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Secret Pasta", "quantity": 250.0, "unit": "g"},
    )
    assert res.status_code == 200
    item_id = res.json()["id"]

    # Register another SaaS user
    other = register_user(client, "otheruser@test.com", "otherpassword123", "Other")

    # Other user attempts to update item -> 404 (existence hiding)
    patch_res = client.patch(
        f"/api/v1/pantry/items/{item_id}",
        headers=other["headers"],
        json={"quantity": 999.0},
    )
    assert patch_res.status_code == 404

