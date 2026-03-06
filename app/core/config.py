from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ADAMHUB_", extra="ignore")

    api_keys: str = "change-me"
    
    @property
    def api_keys_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    db_url: str = "postgresql+psycopg://adamhub:adamhub@localhost:5432/adamhub"
    db_connect_retries: int = 20
    db_connect_retry_delay: float = 1.5
    public_base_url: str = "http://localhost:8000"
    allow_origins: str = "*"

    # Notifications (NTFY)
    ntfy_topic: str | None = None
    ntfy_server: str = "https://ntfy.sh"

    linear_api_token: str | None = None
    linear_team_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
