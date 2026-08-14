from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from sqlmodel import Session

from app.core.auth import _jwt_secret, hash_password, verify_password
from app.models import User


def test_register_happy_path(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "NewUser@Example.com", "password": "secret-123", "display_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == "newuser@example.com"
    assert body["user"]["display_name"] == "New User"
    assert body["user"]["is_active"] is True


def test_login_happy_path(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "secret-123", "display_name": "Login User"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "secret-123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == "login@example.com"


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "login-wrong@example.com", "password": "secret-123", "display_name": "Login User"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login-wrong@example.com", "password": "not-the-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou mot de passe incorrect"


def test_me_returns_current_user(client, jwt_headers):
    response = client.get("/api/v1/auth/me", headers=jwt_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "jwt-user@adamelhirch.com"
    assert body["is_active"] is True


def test_me_requires_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_register_duplicate_email_returns_409(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "secret-123", "display_name": "Dup"},
    )
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "secret-123", "display_name": "Dup"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Cet email est déjà inscrit"


def test_register_duplicate_email_race_returns_409(client, test_engine, monkeypatch):
    with Session(test_engine) as session:
        session.add(
            User(
                email="race@example.com",
                password_hash=hash_password("secret-123"),
                display_name="Race",
            )
        )
        session.commit()

    import app.api.auth as auth_module

    real_select = auth_module.select
    always_empty = lambda *args, **kwargs: real_select(User).where(User.email == "__never__")
    monkeypatch.setattr(auth_module, "select", always_empty)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "race@example.com", "password": "secret-123", "display_name": "Race"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Cet email est déjà inscrit"


def test_me_rejects_expired_token(client, owner_id):
    token = pyjwt.encode(
        {
            "sub": str(owner_id),
            "email": "expired@example.com",
            "display_name": "Expired",
            "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
        },
        _jwt_secret(),
        algorithm="HS256",
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_me_rejects_tampered_token(client, jwt_headers):
    tampered = jwt_headers["Authorization"][:-1] + ("x" if jwt_headers["Authorization"][-1] != "x" else "y")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_me_rejects_malformed_token(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt-token"})
    assert response.status_code == 401


def test_me_rejects_token_with_bad_subject(client, owner_id):
    token = pyjwt.encode(
        {
            "sub": "not-an-integer",
            "email": "bad-sub@example.com",
            "display_name": "Bad Sub",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        _jwt_secret(),
        algorithm="HS256",
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("secret-123")
    assert hashed != "secret-123"
    assert verify_password("secret-123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_hash_password_rejects_short_password():
    import pytest

    with pytest.raises(ValueError):
        hash_password("12345")
