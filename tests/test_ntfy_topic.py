from tests.conftest import register_user


# ── Per-user ntfy topic: read / update via /auth/notifications ─────────────

def test_ntfy_topic_get_put_lifecycle(client, jwt_headers):
    assert client.get("/api/v1/auth/notifications", headers=jwt_headers).json() == {
        "ntfy_topic": None,
    }

    updated = client.put(
        "/api/v1/auth/notifications",
        headers=jwt_headers,
        json={"ntfy_topic": "mon-topic-ntfy"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"ntfy_topic": "mon-topic-ntfy"}

    read_back = client.get("/api/v1/auth/notifications", headers=jwt_headers)
    assert read_back.json() == {"ntfy_topic": "mon-topic-ntfy"}

    # A topic is only visible to its owner, never to another user.
    other = register_user(client, "other-topic-user@adamelhirch.com")
    other_read = client.get("/api/v1/auth/notifications", headers=other["headers"])
    assert other_read.json() == {"ntfy_topic": None}

    cleared = client.put(
        "/api/v1/auth/notifications",
        headers=jwt_headers,
        json={"ntfy_topic": None},
    )
    assert cleared.json() == {"ntfy_topic": None}


def test_ntfy_topic_normalizes_blank_to_none(client, jwt_headers):
    response = client.put(
        "/api/v1/auth/notifications",
        headers=jwt_headers,
        json={"ntfy_topic": "   "},
    )
    assert response.status_code == 200
    assert response.json() == {"ntfy_topic": None}


def test_ntfy_topic_requires_login(client):
    assert client.get("/api/v1/auth/notifications").status_code == 401
    assert (
        client.put(
            "/api/v1/auth/notifications",
            json={"ntfy_topic": "some-topic"},
        ).status_code
        == 401
    )