from tests.conftest import register_user


# ── Off-MVP domains are Owner-only (#59) ─────────────────────────────────────
# The unscoped domains (tasks, events, …) must reject any JWT that does not
# belong to ADAMHUB_OWNER_EMAIL, while the legacy X-API-Key path and the
# Owner's own JWT keep working. Finances was tenant-scoped (t1: user_id on
# transactions/budgets) and moved to CurrentOrOwnerUser, so it is no longer
# part of this gate.

def test_owner_only_route_rejects_non_owner_jwt(client, jwt_headers):
    saas = register_user(client, "saas-user@adamelhirch.com")

    assert client.get("/api/v1/tasks", headers=jwt_headers).status_code == 401
    assert client.get("/api/v1/events", headers=jwt_headers).status_code == 401
    assert client.get("/api/v1/habits", headers=jwt_headers).status_code == 401

    # Write routes are gated the same way.
    assert (
        client.post(
            "/api/v1/tasks",
            headers=saas["headers"],
            json={"title": "Réunion", "due_at": "2026-09-01T09:00:00Z", "estimated_minutes": 30},
        ).status_code
        == 401
    )


def test_finances_router_accepts_any_authenticated_user(client, jwt_headers):
    # Tenant-scoped finances no longer gates on ownership: a plain JWT user
    # reaches it (and simply sees their own empty data).
    assert client.get("/api/v1/finances/transactions", headers=jwt_headers).status_code == 200
    assert client.get("/api/v1/finances/transactions", headers=jwt_headers).json() == []


def test_owner_only_route_accepts_api_key_and_owner_jwt(client, auth_headers, owner_headers):
    assert client.get("/api/v1/finances/transactions", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/tasks", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/finances/transactions", headers=owner_headers).status_code == 200
    assert client.get("/api/v1/tasks", headers=owner_headers).status_code == 200


def test_owner_only_gate_does_not_block_mvp_or_auth_routes(client, jwt_headers):
    saas = register_user(client, "saas-mvp@adamelhirch.com")

    # The same SaaS user still reaches its MVP routes and /auth/me.
    assert client.get("/api/v1/groceries", headers=saas["headers"]).status_code == 200
    assert client.get("/api/v1/auth/me", headers=saas["headers"]).status_code == 200
