from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from sqlmodel import Session, select

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
    assert body["user"]["email_verified"] is False


def test_verify_email_with_correct_token_marks_verified(client, test_engine, monkeypatch):
    captured: dict = {}

    async def fake_send(session, user, token):
        captured["token"] = token
        return True

    monkeypatch.setattr("app.api.auth.send_verification_email", fake_send)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "verify@example.com", "password": "secret-123", "display_name": "Verify"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["email_verified"] is False
    token = captured["token"]
    assert token

    bad = client.post("/api/v1/auth/verify-email", json={"token": "not-the-token"})
    assert bad.status_code == 400

    good = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert good.status_code == 200
    assert good.json()["email_verified"] is True

    with Session(test_engine) as session:
        user = session.exec(select(User).where(User.email == "verify@example.com")).first()
        assert user.email_verified is True
        assert user.email_verification_token_hash is None

    reuse = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert reuse.status_code == 400


def test_resend_verification_rotates_token(client, test_engine, monkeypatch):
    captured: list[str] = []

    async def fake_send(session, user, token):
        captured.append(token)
        return True

    monkeypatch.setattr("app.api.auth.send_verification_email", fake_send)

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "resend@example.com", "password": "secret-123", "display_name": "Resend"},
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    assert len(captured) == 1
    first_token = captured[0]

    resent = client.post("/api/v1/auth/resend-verification", headers=headers)
    assert resent.status_code == 200
    assert len(captured) == 2
    second_token = captured[1]
    assert second_token != first_token

    old = client.post("/api/v1/auth/verify-email", json={"token": first_token})
    assert old.status_code == 400
    new = client.post("/api/v1/auth/verify-email", json={"token": second_token})
    assert new.status_code == 200
    assert new.json()["email_verified"] is True


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
