from tests.conftest import register_user


def _import_connection(client, headers, *, label="Mon drive", store="intermarche", cookies=None, activate=True, credentials=None):
    payload = {
        "store": store,
        "label": label,
        "cookies": cookies if cookies is not None else [{"name": "session", "value": "abc"}],
        "activate": activate,
    }
    if credentials is not None:
        payload["credentials"] = credentials
    response = client.post(
        "/api/v1/supermarket/connections/import",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_connection_import_list_activate_delete_flow(client, auth_headers):
    # Importing a second active connection for the same store deactivates the first.
    first = _import_connection(client, auth_headers, label="Drive principal")
    assert first["is_active"] is True
    assert first["cookies_count"] == 1

    second = _import_connection(client, auth_headers, label="Drive secondaire")
    assert second["is_active"] is True

    listed = client.get("/api/v1/supermarket/connections", headers=auth_headers).json()
    assert {c["id"] for c in listed} == {first["id"], second["id"]}
    by_id = {c["id"]: c for c in listed}
    assert by_id[first["id"]]["is_active"] is False
    assert by_id[second["id"]]["is_active"] is True

    # Activating the first one deactivates the second again.
    activated = client.put(
        f"/api/v1/supermarket/connections/{first['id']}/activate", headers=auth_headers
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    listed = client.get("/api/v1/supermarket/connections", headers=auth_headers).json()
    by_id = {c["id"]: c for c in listed}
    assert by_id[first["id"]]["is_active"] is True
    assert by_id[second["id"]]["is_active"] is False

    # Deleting one connection leaves the other untouched.
    deleted = client.delete(f"/api/v1/supermarket/connections/{second['id']}", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json()["id"] == second["id"]

    remaining = client.get("/api/v1/supermarket/connections", headers=auth_headers).json()
    assert [c["id"] for c in remaining] == [first["id"]]


def test_connection_list_filters_by_store(client, auth_headers):
    intermarche = _import_connection(client, auth_headers, label="Intermarché", store="intermarche")
    leclerc = _import_connection(client, auth_headers, label="Leclerc", store="leclerc")

    all_rows = client.get("/api/v1/supermarket/connections", headers=auth_headers).json()
    assert {c["id"] for c in all_rows} == {intermarche["id"], leclerc["id"]}

    intermarche_rows = client.get(
        "/api/v1/supermarket/connections", headers=auth_headers, params={"store": "intermarche"}
    ).json()
    assert [c["id"] for c in intermarche_rows] == [intermarche["id"]]


def test_connection_import_requires_cookies_or_credentials(client, auth_headers):
    response = client.post(
        "/api/v1/supermarket/connections/import",
        headers=auth_headers,
        json={"store": "intermarche", "label": "Vide", "activate": True},
    )
    assert response.status_code == 400
    assert "cookies or credentials" in response.json()["detail"]


def test_connection_import_with_credentials_stores_encrypted(client, auth_headers):
    body = _import_connection(
        client,
        auth_headers,
        label="Leclerc creds",
        store="leclerc",
        cookies=[],
        credentials={"username": "user@example.com", "password": "s3cret"},
        activate=False,
    )
    assert body["label"] == "Leclerc creds"
    assert body["cookies_count"] == 0
    assert body["is_active"] is False


def test_connection_import_label_falls_back_to_display_name(client, jwt_headers):
    # register_user uses display_name="User" by default; a blank label is
    # replaced by the acting user's display name.
    body = _import_connection(client, jwt_headers, label="   ")
    assert body["label"] == "User"


def test_non_owner_activate_and_delete_are_404_without_side_effects(client):
    owner = register_user(client, "conn-side-owner@adamelhirch.com")
    intruder = register_user(client, "conn-side-intruder@adamelhirch.com")

    owner_active = _import_connection(client, owner["headers"], label="Owner drive")
    intruder_active = _import_connection(client, intruder["headers"], label="Intruder drive")
    intruder_inactive = _import_connection(
        client, intruder["headers"], label="Intruder spare", activate=False
    )

    # Activate / delete of another user's connection is a plain 404.
    assert client.put(
        f"/api/v1/supermarket/connections/{owner_active['id']}/activate", headers=intruder["headers"]
    ).status_code == 404
    assert client.delete(
        f"/api/v1/supermarket/connections/{owner_active['id']}", headers=intruder["headers"]
    ).status_code == 404

    # No side effects: the owner's connection is still active, and the
    # intruder's own connections were not touched by the failed attempt.
    owner_rows = client.get("/api/v1/supermarket/connections", headers=owner["headers"]).json()
    assert [c["is_active"] for c in owner_rows if c["id"] == owner_active["id"]] == [True]

    intruder_rows = client.get("/api/v1/supermarket/connections", headers=intruder["headers"]).json()
    by_id = {c["id"]: c for c in intruder_rows}
    assert by_id[intruder_active["id"]]["is_active"] is True
    assert by_id[intruder_inactive["id"]]["is_active"] is False
