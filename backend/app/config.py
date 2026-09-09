"""Runtime configuration.

Every value that differs between development and production comes from the
environment. The defaults here are development-only and are deliberately
obvious as such; nothing in this file is a production secret.
"""
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # The API must connect as an ordinary role. Connecting as a superuser (or
    # any role with BYPASSRLS) silently disables row-level security and every
    # tenant would see every other tenant's data.
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://calcapp:calcapp_dev_pw@localhost:5432/legal_rules_dev")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-secret-not-for-production-use-32b+")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
    refresh_token_days: int = int(os.getenv("REFRESH_TOKEN_DAYS", "14"))
    engine_version: str = "1.0.0"

    # Held as a plain string, not list[str]. pydantic-settings treats a list
    # field as "complex" and JSON-decodes the environment value before any
    # validator runs, so a comma-separated CORS_ORIGINS would crash the
    # process at startup. Parsing happens in the property below instead.
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")

    pool_min: int = int(os.getenv("POOL_MIN", "1"))
    pool_max: int = int(os.getenv("POOL_MAX", "10"))
    environment: str = os.getenv("ENVIRONMENT", "development")

    @property
    def cors_origins(self) -> list[str]:
        """Allowed browser origins, comma-separated in the environment."""
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")


@lru_cache
def settings() -> Settings:
    s = Settings()
    # Fail loudly rather than serving production traffic on a known-public
    # secret or a superuser database connection.
    if s.is_production:
        if "dev-only-secret" in s.jwt_secret:
            raise RuntimeError(
                "JWT_SECRET is still the development default. Set a real secret.")
        # The check is for the development *credential*, not the hostname: a
        # production database may legitimately be on localhost, a unix socket
        # or a private network address.
        if "calcapp_dev_pw" in s.database_url:
            raise RuntimeError(
                "DATABASE_URL still carries the development password. "
                "Point it at the production database.")
    return s
