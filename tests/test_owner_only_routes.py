from tests.conftest import register_user


# ── Off-MVP domains are Owner-only ──────────────────────────────────────────
# The unscoped domain (skill) rejects any JWT that does not belong to
# ADAMHUB_OWNER_EMAIL, while the legacy X-API-Key path and the Owner's own JWT
# keep working.

def test_owner_only_route_rejects_non_owner_jwt(client, jwt_headers):
    saas = register_user(client, "saas-user@adamelhirch.com")

    assert client.get("/api/v1/skill/manifest", headers=jwt_headers).status_code == 401

    # Write routes are gated the same way.
    assert (
        client.post(
            "/api/v1/skill/execute",
            headers=saas["headers"],
            json={"action": "grocery.list_items", "input": {}},
        ).status_code
        == 401
    )


def test_owner_only_route_accepts_api_key_and_owner_jwt(client, auth_headers, owner_headers):
    assert client.get("/api/v1/skill/manifest", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/skill/manifest", headers=owner_headers).status_code == 200


def test_owner_only_gate_does_not_block_mvp_or_auth_routes(client, jwt_headers):
    saas = register_user(client, "saas-mvp@adamelhirch.com")

    # The same SaaS user reaches its MVP routes and /auth/me.
    assert client.get("/api/v1/groceries", headers=saas["headers"]).status_code == 200
    assert client.get("/api/v1/auth/me", headers=saas["headers"]).status_code == 200
    assert client.get("/api/v1/recipes", headers=saas["headers"]).status_code == 200
    assert client.get("/api/v1/pantry/items", headers=saas["headers"]).status_code == 200