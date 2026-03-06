from collections.abc import Generator
from pathlib import Path
import time

from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

settings = get_settings()


def _ensure_sqlite_parent_dir(db_url: str) -> None:
    prefix = "sqlite:///"
    if not db_url.startswith(prefix):
        return

    raw_path = db_url[len(prefix):]
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent_dir(settings.db_url)
connect_args = {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
engine = create_engine(settings.db_url, connect_args=connect_args, pool_pre_ping=True)


def init_db() -> None:
    # Alembic handles migrations now, we just ensure we can connect
    retries = max(settings.db_connect_retries, 0)
    for attempt in range(retries + 1):
        try:
            with engine.connect():
                pass
            return
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(settings.db_connect_retry_delay)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
