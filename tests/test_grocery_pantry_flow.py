from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.models import SupermarketSearchCache, SupermarketStore


def _make_cache_row(test_engine, store=SupermarketStore.INTERMARCHE, **overrides) -> int:
    now = datetime.now(UTC)
    fields = {
        "store": store,
        "query": "milk",
        "external_id": "milk-123",
        "name": "Milk",
        "brand": "Candia",
        "category": "dairy",
        "packaging": "la bouteille de 2 L",
        "price_amount": 2.49,
        "price_text": "2,49 €",
        "image_url": "https://img.test/milk.png",
        "product_url": "https://shop.test/milk-123",
        "fetched_at": now,
        "expires_at": now + timedelta(days=1),
    }
    fields.update(overrides)
    with Session(test_engine) as session:
        row = SupermarketSearchCache(**fields)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def test_checking_grocery_item_updates_pantry(client, auth_headers, test_engine):
    cache_id = _make_cache_row(test_engine)

    created = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={
            "name": "Milk",
            "quantity": 2,
            "unit": "L",
            "category": "dairy",
            "cache_id": cache_id,
            "image_url": "https://img.test/milk.png",
            "store_label": "Intermarché",
            "external_id": "milk-123",
            "packaging": "la bouteille de 2 L",
            "price_text": "2,49 €",
            "product_url": "https://shop.test/milk-123",
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]
    assert created.json()["image_url"] == "https://img.test/milk.png"
    assert created.json()["price_text"] == "2,49 €"

    checked = client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": True})
    assert checked.status_code == 200
    assert checked.json()["checked"] is True

    pantry_rows = client.get("/api/v1/pantry/items", headers=auth_headers)
    assert pantry_rows.status_code == 200
    pantry = pantry_rows.json()
    assert len(pantry) == 1
    assert pantry[0]["name"] == "Milk"
    assert pantry[0]["quantity"] == 2.0
    assert pantry[0]["unit"] == "L"
    assert pantry[0]["image_url"] == "https://img.test/milk.png"
    assert pantry[0]["store_label"] == "Intermarché"
    assert pantry[0]["external_id"] == "milk-123"
    assert pantry[0]["packaging"] == "la bouteille de 2 L"
    assert pantry[0]["price_text"] == "2,49 €"
    assert pantry[0]["product_url"] == "https://shop.test/milk-123"

    # Checking again should not duplicate pantry sync.
    checked_again = client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": True})
    assert checked_again.status_code == 200
    pantry_rows_again = client.get("/api/v1/pantry/items", headers=auth_headers)
    assert pantry_rows_again.status_code == 200
    assert len(pantry_rows_again.json()) == 1
    assert pantry_rows_again.json()[0]["quantity"] == 2.0


def test_unchecking_grocery_item_reverses_pantry_restock(client, auth_headers):
    created = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={"name": "Milk", "quantity": 2, "unit": "L"},
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    checked = client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": True})
    assert checked.status_code == 200
    pantry = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    assert len(pantry) == 1
    assert pantry[0]["quantity"] == 2.0

    # Unchecking subtracts the previously added quantity.
    unchecked = client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": False})
    assert unchecked.status_code == 200
    pantry = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    assert len(pantry) == 1
    assert pantry[0]["quantity"] == 0.0

    # Re-checking restocks again (sync row was cleared on uncheck).
    rechecked = client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": True})
    assert rechecked.status_code == 200
    pantry = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    assert len(pantry) == 1
    assert pantry[0]["quantity"] == 2.0

    # Unchecking a second time is idempotent.
    unchecked_again = client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": False})
    assert unchecked_again.status_code == 200
    pantry = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    assert len(pantry) == 1
    assert pantry[0]["quantity"] == 0.0


def test_grocery_merge_converts_units(client, auth_headers):
    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Farine", "quantity": 2000, "unit": "g", "min_quantity": 0},
    )
    assert pantry.status_code == 200
    assert len(client.get("/api/v1/pantry/items", headers=auth_headers).json()) == 1

    grocery = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={"name": "Farine", "quantity": 2, "unit": "kg"},
    )
    assert grocery.status_code == 200
    item_id = grocery.json()["id"]

    checked = client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": True})
    assert checked.status_code == 200

    # "2 kg" merges into the existing "2000 g" row instead of duplicating it.
    pantry_rows = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    assert len(pantry_rows) == 1
    assert pantry_rows[0]["quantity"] == 4000.0
    assert pantry_rows[0]["unit"] == "g"

    # Unchecking reverses exactly the converted quantity.
    client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": False})
    pantry_rows = client.get("/api/v1/pantry/items", headers=auth_headers).json()
    assert len(pantry_rows) == 1
    assert pantry_rows[0]["quantity"] == 2000.0


def test_create_and_update_pantry_item_image_url(client, auth_headers):
    created = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={
            "name": "Yaourt",
            "quantity": 4,
            "unit": "item",
            "category": "Produits laitiers",
            "image_url": "https://img.test/yaourt.png",
            "min_quantity": 1,
        },
    )
    assert created.status_code == 200
    assert created.json()["image_url"] == "https://img.test/yaourt.png"

    pantry_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/pantry/items/{pantry_id}",
        headers=auth_headers,
        json={"image_url": "https://img.test/yaourt-new.png"},
    )
    assert updated.status_code == 200
    assert updated.json()["image_url"] == "https://img.test/yaourt-new.png"


def test_grocery_and_pantry_resolve_store_metadata_from_cache(client, auth_headers, test_engine):
    cache_id = _make_cache_row(
        test_engine,
        external_id="3533630097654",
        name="Sauce soja",
        packaging="la bouteille de 125 ml",
        price_amount=1.89,
        price_text="1,89 €",
        product_url="https://shop.test/soy",
    )

    grocery = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={
            "name": "Sauce soja",
            "quantity": 1,
            "unit": "item",
            "cache_id": cache_id,
            # Fabricated values are ignored in favor of the cache row.
            "store_label": "Fake Store",
            "external_id": "fake-id",
            "price_text": "0,00 €",
            "product_url": "https://fake.test/soy",
        },
    )
    assert grocery.status_code == 200
    body = grocery.json()
    assert body["store_label"] == "Intermarché"
    assert body["external_id"] == "3533630097654"
    assert body["packaging"] == "la bouteille de 125 ml"
    assert body["price_text"] == "1,89 €"
    assert body["product_url"] == "https://shop.test/soy"

    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={
            "name": "Sauce soja",
            "quantity": 1,
            "unit": "item",
            "cache_id": cache_id,
        },
    )
    assert pantry.status_code == 200
    pantry_id = pantry.json()["id"]
    assert pantry.json()["store_label"] == "Intermarché"
    assert pantry.json()["external_id"] == "3533630097654"

    updated = client.patch(
        f"/api/v1/pantry/items/{pantry_id}",
        headers=auth_headers,
        json={"cache_id": cache_id},
    )
    assert updated.status_code == 200
    assert updated.json()["price_text"] == "1,89 €"
    assert updated.json()["packaging"] == "la bouteille de 125 ml"


def test_store_metadata_without_cache_id_is_rejected(client, auth_headers):
    grocery = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={
            "name": "Sauce soja",
            "quantity": 1,
            "unit": "item",
            "store_label": "Intermarché",
            "external_id": "3533630097654",
            "price_text": "1,89 €",
            "product_url": "https://shop.test/soy",
        },
    )
    assert grocery.status_code == 422

    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={
            "name": "Sauce soja",
            "quantity": 1,
            "unit": "item",
            "store_label": "Intermarché",
            "external_id": "3533630097654",
        },
    )
    assert pantry.status_code == 422

    # A plain item without store metadata is still accepted.
    plain = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={"name": "Pain", "quantity": 1, "unit": "item"},
    )
    assert plain.status_code == 200


def test_store_metadata_with_invalid_cache_id_is_rejected(client, auth_headers):
    grocery = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={"name": "Sauce soja", "quantity": 1, "unit": "item", "cache_id": 999999},
    )
    assert grocery.status_code == 404


def test_grocery_and_pantry_items_allow_editing_name_fields(client, auth_headers):
    grocery = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={
            "name": "Pain",
            "quantity": 1,
            "unit": "item",
        },
    )
    assert grocery.status_code == 200
    grocery_id = grocery.json()["id"]

    updated_grocery = client.patch(
        f"/api/v1/groceries/{grocery_id}",
        headers=auth_headers,
        json={
            "name": "Pain complet",
            "quantity": 2,
            "category": "Boulangerie",
        },
    )
    assert updated_grocery.status_code == 200
    assert updated_grocery.json()["name"] == "Pain complet"
    assert updated_grocery.json()["quantity"] == 2.0
    assert updated_grocery.json()["category"] == "Boulangerie"

    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={
            "name": "Lait",
            "quantity": 1,
            "unit": "L",
            "min_quantity": 2,
        },
    )
    assert pantry.status_code == 200
    pantry_id = pantry.json()["id"]

    updated_pantry = client.patch(
        f"/api/v1/pantry/items/{pantry_id}",
        headers=auth_headers,
        json={
            "name": "Lait entier",
            "min_quantity": 3,
            "location": "Frigo",
        },
    )
    assert updated_pantry.status_code == 200
    assert updated_pantry.json()["name"] == "Lait entier"
    assert updated_pantry.json()["min_quantity"] == 3.0
    assert updated_pantry.json()["location"] == "Frigo"


def test_negative_quantities_are_rejected(client, auth_headers):
    grocery = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={"name": "Pain", "quantity": -1, "unit": "item"},
    )
    assert grocery.status_code == 422

    grocery_ok = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={"name": "Pain", "quantity": 0, "unit": "item"},
    )
    assert grocery_ok.status_code == 200
    grocery_id = grocery_ok.json()["id"]

    bad_update = client.patch(
        f"/api/v1/groceries/{grocery_id}",
        headers=auth_headers,
        json={"quantity": -5},
    )
    assert bad_update.status_code == 422

    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Lait", "quantity": -1, "unit": "L"},
    )
    assert pantry.status_code == 422

    pantry_ok = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Lait", "quantity": 1, "unit": "L", "min_quantity": 0},
    )
    assert pantry_ok.status_code == 200
    pantry_id = pantry_ok.json()["id"]

    bad_min = client.patch(
        f"/api/v1/pantry/items/{pantry_id}",
        headers=auth_headers,
        json={"min_quantity": -2},
    )
    assert bad_min.status_code == 422
