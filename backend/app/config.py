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


def _csv(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


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

    # Comma-separated in the environment, e.g.
    #   CORS_ORIGINS=https://your-site.netlify.app,http://localhost:3000
    cors_origins: list[str] = _csv("CORS_ORIGINS", "http://localhost:3000")

    pool_min: int = int(os.getenv("POOL_MIN", "1"))
    pool_max: int = int(os.getenv("POOL_MAX", "10"))
    environment: str = os.getenv("ENVIRONMENT", "development")

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
            raise RuntimeError("JWT_SECRET must be set in production.")
        if "calcapp_dev_pw" in s.database_url or "localhost" in s.database_url:
            raise RuntimeError("DATABASE_URL must point at the production database.")
    return s
