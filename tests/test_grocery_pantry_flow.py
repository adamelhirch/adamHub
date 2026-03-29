def test_checking_grocery_item_updates_pantry(client, auth_headers):
    created = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={
            "name": "Milk",
            "quantity": 2,
            "unit": "L",
            "category": "dairy",
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


def test_grocery_and_pantry_support_store_metadata_fields(client, auth_headers):
    grocery = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={
            "name": "Sauce soja",
            "quantity": 1,
            "unit": "item",
            "store_label": "Intermarché",
            "external_id": "3533630097654",
            "packaging": "la bouteille de 125 ml",
            "price_text": "1,89 €",
            "product_url": "https://shop.test/soy",
        },
    )
    assert grocery.status_code == 200
    assert grocery.json()["store_label"] == "Intermarché"
    assert grocery.json()["packaging"] == "la bouteille de 125 ml"

    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={
            "name": "Sauce soja",
            "quantity": 1,
            "unit": "item",
            "store_label": "Intermarché",
            "external_id": "3533630097654",
            "packaging": "la bouteille de 125 ml",
            "price_text": "1,89 €",
            "product_url": "https://shop.test/soy",
        },
    )
    assert pantry.status_code == 200
    pantry_id = pantry.json()["id"]

    updated = client.patch(
        f"/api/v1/pantry/items/{pantry_id}",
        headers=auth_headers,
        json={
            "price_text": "1,79 €",
            "packaging": "la bouteille de 150 ml",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["price_text"] == "1,79 €"
    assert updated.json()["packaging"] == "la bouteille de 150 ml"


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
