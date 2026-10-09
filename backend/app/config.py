"""Application settings loaded from environment / .env file.

The settings object is a singleton (``settings``). Database URLs, secrets and
the INPI base URL are never hardcoded: they always come from the environment.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = .../intelliinpi  (this file is backend/app/config.py)
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database -----------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/intelliinpi_app",
        alias="DATABASE_URL",
    )

    # --- Security -----------------------------------------------------------
    jwt_secret: str = Field(default="dev-secret-change-me", alias="JWT_SECRET")
    jwt_refresh_secret: str = Field(
        default="dev-refresh-secret-change-me", alias="JWT_REFRESH_SECRET"
    )
    jwt_access_ttl_minutes: int = Field(default=30, alias="JWT_ACCESS_TTL_MINUTES")
    jwt_refresh_ttl_days: int = Field(default=14, alias="JWT_REFRESH_TTL_DAYS")
    jwt_algorithm: str = "HS256"
    password_hash_scheme: str = Field(default="argon2", alias="PASSWORD_HASH_SCHEME")

    # --- Master admin -------------------------------------------------------
    master_admin_email: str = Field(
        default="master@intelliinpi.com.br", alias="MASTER_ADMIN_EMAIL"
    )
    master_admin_password: str = Field(
        default="ChangeMe_MasterAdmin_123!", alias="MASTER_ADMIN_PASSWORD"
    )
    master_admin_name: str = Field(default="Master Admin", alias="MASTER_ADMIN_NAME")

    # --- Default tenant -----------------------------------------------------
    # The default tenant created by the seed/migration to which users without a
    # tenant (e.g. the existing master admin) are linked for data isolation.
    default_tenant_name: str = Field(
        default="Matriz", alias="DEFAULT_TENANT_NAME"
    )

    # --- INPI ---------------------------------------------------------------
    inpi_base_url: str = Field(
        default="https://dadosabertos.inpi.gov.br", alias="INPI_BASE_URL"
    )
    data_dir: str = Field(default="./data", alias="DATA_DIR")

    # --- DeepSeek (IA) ------------------------------------------------------
    # Real DeepSeek integration. When the API key is empty the feature degrades
    # explicitly (HTTP 503) instead of returning fabricated analyses.
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    deepseek_temperature: float = Field(
        default=0.2, alias="DEEPSEEK_TEMPERATURE"
    )
    deepseek_max_tokens: int = Field(default=2000, alias="DEEPSEEK_MAX_TOKENS")
    deepseek_timeout_seconds: float = Field(
        default=60.0, alias="DEEPSEEK_TIMEOUT_SECONDS"
    )

    # --- CORS ---------------------------------------------------------------
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # --- Login rate limiting ------------------------------------------------
    login_rate_limit_attempts: int = Field(
        default=10, alias="LOGIN_RATE_LIMIT_ATTEMPTS"
    )
    login_rate_limit_window_seconds: int = Field(
        default=300, alias="LOGIN_RATE_LIMIT_WINDOW_SECONDS"
    )

    @field_validator("database_url")
    @classmethod
    def _ensure_psycopg_driver(cls, value: str) -> str:
        # Normalise plain postgresql:// URLs to the psycopg (v3) driver.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        return p

    @property
    def reports_path(self) -> Path:
        return PROJECT_ROOT / "reports"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
