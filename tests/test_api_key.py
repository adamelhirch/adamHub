from tests.conftest import register_user


# ── Per-user API key: generate / read / revoke ───────────────────────────────

def test_api_key_lifecycle(client, jwt_headers):
    assert client.get("/api/v1/auth/api-key", headers=jwt_headers).json() == {
        "api_key": None,
        "created_at": None,
    }

    created = client.post("/api/v1/auth/api-key", headers=jwt_headers)
    assert created.status_code == 200, created.text
    raw_key = created.json()["api_key"]
    assert raw_key and raw_key.startswith("ahub_")
    assert created.json()["created_at"] is not None

    read_back = client.get("/api/v1/auth/api-key", headers=jwt_headers)
    assert read_back.json()["api_key"] == raw_key

    regenerated = client.post("/api/v1/auth/api-key", headers=jwt_headers)
    new_key = regenerated.json()["api_key"]
    assert new_key != raw_key

    revoked = client.delete("/api/v1/auth/api-key", headers=jwt_headers)
    assert revoked.status_code == 204
    assert client.get("/api/v1/auth/api-key", headers=jwt_headers).json()["api_key"] is None


def test_api_key_requires_login_not_itself(client):
    # Bootstrapping a key needs a JWT session, not a pre-existing key.
    assert client.get("/api/v1/auth/api-key").status_code == 401
    assert client.post("/api/v1/auth/api-key").status_code == 401


# ── A per-user key resolves like a JWT on the MVP routers, and never on owner-only ones ──

def test_per_user_api_key_reaches_mvp_routes(client, jwt_headers):
    raw_key = client.post("/api/v1/auth/api-key", headers=jwt_headers).json()["api_key"]
    key_headers = {"X-API-Key": raw_key}

    assert client.get("/api/v1/groceries", headers=key_headers).status_code == 200
    assert client.get("/api/v1/pantry/items", headers=key_headers).status_code == 200
    assert client.get("/api/v1/recipes", headers=key_headers).status_code == 200
    assert client.get("/api/v1/meal-plans", headers=key_headers).status_code == 200
    assert client.get("/api/v1/supermarket/connections", headers=key_headers).status_code == 200


def test_per_user_api_key_reaches_scoped_domains_but_not_owner_only_gate(client, jwt_headers):
    raw_key = client.post("/api/v1/auth/api-key", headers=jwt_headers).json()["api_key"]
    key_headers = {"X-API-Key": raw_key}

    # Tenant-scoped domains resolve the per-user key to its owner (finances
    # scoped in t1, tasks in t6, events in t7, subscriptions in t8, fitness
    # in t9, habits in t10, calendar items in t11, calendar feeds in t12)…
    assert client.get("/api/v1/finances/transactions", headers=key_headers).status_code == 200
    assert client.get("/api/v1/tasks", headers=key_headers).status_code == 200
    assert client.get("/api/v1/events", headers=key_headers).status_code == 200
    assert client.get("/api/v1/subscriptions", headers=key_headers).status_code == 200
    assert client.get("/api/v1/fitness/sessions", headers=key_headers).status_code == 200
    assert client.get("/api/v1/calendar/items", headers=key_headers).status_code == 200
    assert client.get("/api/v1/calendar/feeds", headers=key_headers).status_code == 200

    # …while the still-unscoped owner-only domains keep rejecting it.
    assert client.get("/api/v1/skill/manifest", headers=key_headers).status_code == 401


def test_per_user_api_key_is_scoped_to_its_owner(client, jwt_headers):
    """Two SaaS users' groceries stay isolated through a per-user key, same as through a JWT."""
    other = register_user(client, "other-key-user@adamelhirch.com")
    other_key = client.post("/api/v1/auth/api-key", headers=other["headers"]).json()["api_key"]

    created = client.post(
        "/api/v1/groceries",
        headers=jwt_headers,
        json={"name": "Lait"},
    )
    assert created.status_code == 200, created.text

    other_list = client.get("/api/v1/groceries", headers={"X-API-Key": other_key})
    assert other_list.status_code == 200
    assert other_list.json() == []


def test_invalid_api_key_is_rejected(client):
    assert client.get("/api/v1/groceries", headers={"X-API-Key": "ahub_not-a-real-key"}).status_code == 401
