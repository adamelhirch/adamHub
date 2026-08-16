import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Export the local .env into os.environ before any Settings read. pydantic-
# settings only consumes .env for its own model fields; other modules (e.g. the
# supermarket scrapers) read os.environ directly, so without this a value set
# in .env (Leclerc base URL, proxies file, …) would be invisible to them in
# local dev (`cp .env.example .env` + uvicorn, no docker env_file).
load_dotenv()


def current_env() -> str:
    """Return the explicit runtime environment from ADAMHUB_ENV.

    production is the default: an unset ADAMHUB_ENV must never silently
    downgrade the security posture, so dev/test mode is always an opt-in.
    """
    return (os.environ.get("ADAMHUB_ENV") or "production").strip().lower()


def is_dev_or_test() -> bool:
    """Single source of truth for "dev/test" contexts that may use dev defaults."""
    return current_env() in {"development", "test"}


class SecurityConfigError(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ADAMHUB_", extra="ignore")

    # Shared API key(s) for the legacy personal frontend. Must be set to a
    # non-default value outside dev/test; see validate_security_config().
    api_keys: str | None = None

    @property
    def api_keys_list(self) -> list[str]:
        return [k.strip() for k in (self.api_keys or "").split(",") if k.strip()]

    # Email of the single legacy "owner" user that API-key-only requests (the
    # personal web frontend) resolve to. Must be set for the shared X-API-Key
    # path to scope data to a real user; no default on purpose.
    owner_email: str | None = None

    db_url: str = "postgresql+psycopg://adamhub:adamhub@localhost:5432/adamhub"
    db_connect_retries: int = 20
    db_connect_retry_delay: float = 1.5
    public_base_url: str = "http://localhost:8000"
    # Default to the deployed frontend origin instead of "*". A wildcard remains
    # possible but only via an explicit opt-in in dev/test; see validate_security_config().
    allow_origins: str = "https://hub.adamelhirch.com"

    # Notifications (NTFY)
    ntfy_topic: str | None = None
    ntfy_server: str = "https://ntfy.sh"

    linear_api_token: str | None = None
    linear_team_id: str | None = None

    # Email verification via Resend. Without ADAMHUB_RESEND_API_KEY (dev/test)
    # sending is a logged no-op and registration is never blocked.
    resend_api_key: str | None = None
    email_from: str = "AdamHUB <onboarding@resend.dev>"

    # Cookies-at-rest encryption. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Required outside dev/test; see validate_security_config().
    cookie_encryption_key: str | None = None

    # JWT for user auth. Pick a long random secret in prod. Required outside
    # dev/test; see validate_security_config().
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 30  # 30 days

    # Shared supermarket proxy pool (app/services/proxy_pool.py). proxies_file
    # is the 1-proxy-per-line list (login:password@host:port), cooldown_seconds
    # is how long a blocked proxy stays paused before it can rotate back in.
    proxies_file: str = "data/proxies.txt"
    proxy_cooldown_seconds: int = 600


def validate_security_config(settings: Settings) -> None:
    """Refuse startup when secrets/CORS fall back to insecure defaults.

    Dev/test contexts (ADAMHUB_ENV=development|test) may keep the old silent
    fallbacks; every other context must be explicitly and securely configured.
    """
    if is_dev_or_test():
        return

    problems: list[str] = []

    api_key = (settings.api_keys or "").strip()
    if not api_key or api_key == "change-me":
        problems.append(
            "ADAMHUB_API_KEYS is missing or still the insecure default 'change-me'. "
            "Set it to a long random secret, or set ADAMHUB_ENV=development/test to "
            "opt into the insecure dev defaults."
        )

    if not (settings.jwt_secret or "").strip():
        problems.append(
            "ADAMHUB_JWT_SECRET is empty. Set it to a long random secret (e.g. "
            "`python -c \"import secrets; print(secrets.token_urlsafe(64))\"`), or set "
            "ADAMHUB_ENV=development/test to opt into the dev fallback."
        )

    if not (settings.cookie_encryption_key or "").strip():
        problems.append(
            "ADAMHUB_COOKIE_ENCRYPTION_KEY is empty. Generate a Fernet key with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`, "
            "or set ADAMHUB_ENV=development/test to opt into the dev fallback."
        )

    if settings.allow_origins == "*":
        problems.append(
            "ADAMHUB_ALLOW_ORIGINS='*' is only allowed in development/test. "
            "Set it to the deployed frontend origin (e.g. https://hub.adamelhirch.com)."
        )

    if problems:
        raise SecurityConfigError(
            "Insecure startup configuration:\n- " + "\n- ".join(problems)
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validate_security_config(settings)
    return settings
