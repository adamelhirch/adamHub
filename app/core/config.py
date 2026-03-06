from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ADAMHUB_", extra="ignore")

    api_key: str = "change-me"
    db_url: str = "postgresql+psycopg://adamhub:adamhub@localhost:5432/adamhub"
    db_connect_retries: int = 20
    db_connect_retry_delay: float = 1.5
    public_base_url: str = "http://localhost:8000"
    allow_origins: str = "*"
    linear_api_token: str | None = None
    linear_team_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
