from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ADAMHUB_", extra="ignore")

    api_keys: str = "change-me"
    
    @property
    def api_keys_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    # Email of the single legacy "owner" user that API-key-only requests (the
    # personal web frontend) resolve to. Must be set for the shared X-API-Key
    # path to scope data to a real user; no default on purpose.
    owner_email: str | None = None

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

    # Cookies-at-rest encryption. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Falls back to a development-only key if unset.
    cookie_encryption_key: str | None = None

    # JWT for user auth. Pick a long random secret in prod.
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 30  # 30 days


@lru_cache
def get_settings() -> Settings:
    return Settings()
