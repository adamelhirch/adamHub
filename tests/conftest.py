from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from app.core import db as db_module
from app.core.config import get_settings
from app.main import app

# Ensure SQLModel metadata is populated.
from app import models as _models  # noqa: F401


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


@pytest.fixture()
def client(test_engine, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("ADAMHUB_API_KEYS", "change-me")
    get_settings.cache_clear()

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
