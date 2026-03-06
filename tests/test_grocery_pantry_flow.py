def test_checking_grocery_item_updates_pantry(client, auth_headers):
    created = client.post(
        "/api/v1/groceries",
        headers=auth_headers,
        json={
            "name": "Milk",
            "quantity": 2,
            "unit": "L",
            "category": "dairy",
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

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

    # Checking again should not duplicate pantry sync.
    checked_again = client.patch(f"/api/v1/groceries/{item_id}", headers=auth_headers, json={"checked": True})
    assert checked_again.status_code == 200
    pantry_rows_again = client.get("/api/v1/pantry/items", headers=auth_headers)
    assert pantry_rows_again.status_code == 200
    assert len(pantry_rows_again.json()) == 1
    assert pantry_rows_again.json()[0]["quantity"] == 2.0
