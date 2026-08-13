from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select

from app.core import db as db_module
from app.core.auth import create_token, hash_password
from app.core.config import get_settings
from app.main import app
from app.models import User

# Ensure SQLModel metadata is populated.
from app import models as _models  # noqa: F401

OWNER_EMAIL = "owner@adamelhirch.com"
OWNER_PASSWORD = "owner-password-123"


@pytest.fixture(autouse=True)
def disable_app_lifespan_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.setup_scheduler", lambda: None)
    monkeypatch.setattr("app.main.shutdown_scheduler", lambda: None)


@pytest.fixture()
def test_engine(tmp_path):
    db_path = tmp_path / "adamhub-test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


def _seed_owner_user(engine) -> User:
    with Session(engine) as session:
        owner = session.exec(select(User).where(User.email == OWNER_EMAIL)).first()
        if owner is None:
            owner = User(
                email=OWNER_EMAIL,
                password_hash=hash_password(OWNER_PASSWORD),
                display_name="Owner",
            )
            session.add(owner)
            session.commit()
            session.refresh(owner)
        return owner


@pytest.fixture()
def client(test_engine, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("ADAMHUB_API_KEYS", "change-me")
    monkeypatch.setenv("ADAMHUB_OWNER_EMAIL", OWNER_EMAIL)
    get_settings.cache_clear()
    _seed_owner_user(test_engine)

    def override_get_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[db_module.get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": "change-me"}


@pytest.fixture()
def owner_id(client, test_engine) -> int:
    """DB id of the ADAMHUB_OWNER_EMAIL user (used to seed rows owned by the legacy path)."""
    return _seed_owner_user(test_engine).id


def register_user(client: TestClient, email: str, password: str = "password-123", display_name: str = "User") -> dict:
    """Register a user via the API and return the JWT auth headers + user dict."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "token": body["token"],
        "user": body["user"],
        "headers": {"Authorization": f"Bearer {body['token']}"},
    }


@pytest.fixture()
def jwt_headers(client: TestClient):
    """Auth headers for a freshly-registered JWT user (distinct from the owner)."""
    return register_user(client, "jwt-user@adamelhirch.com")["headers"]


@pytest.fixture()
def owner_headers(client: TestClient):
    """JWT auth headers for the ADAMHUB_OWNER_EMAIL user."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}
