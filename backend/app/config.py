"""Application settings loaded from environment / .env file.

The settings object is a singleton (``settings``). Database URLs, secrets and
the INPI base URL are never hardcoded: they always come from the environment.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = .../intelliinpi  (this file is backend/app/config.py)
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Known insecure defaults shipped in code/.env.example. Starting a non-local
# environment with any of these values is refused (see ``_reject_insecure``).
INSECURE_JWT_SECRETS: frozenset[str] = frozenset(
    {
        "dev-secret-change-me",
        "dev-refresh-secret-change-me",
        "change-me-in-production-please-use-a-long-random-string-32chars+",
        "change-me-too-in-production-please-use-a-long-random-string-32chars+",
    }
)
INSECURE_ADMIN_PASSWORDS: frozenset[str] = frozenset(
    {"ChangeMe_MasterAdmin_123!"}
)
# Environments considered "local" where the dev defaults above are tolerated.
LOCAL_ENVIRONMENTS: frozenset[str] = frozenset({"local", "dev", "development", "test"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Environment --------------------------------------------------------
    # Selects the strictness of the startup validation. ``local`` (default)
    # tolerates the development defaults; anything else refuses them.
    environment: str = Field(default="local", alias="ENVIRONMENT")

    # --- Database -----------------------------------------------------------
    # No credentials or hosts are hardcoded here: the real value always comes
    # from the environment (local .env or, in deploy, the platform's env vars).
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
    # pePI (busca.inpi.gov.br) serves the marca logotipos through an anonymous
    # session. Kept separate from ``inpi_base_url`` (open-data portal) because
    # they are different hosts with different authentication semantics.
    pepi_base_url: str = Field(
        default="https://busca.inpi.gov.br/pePI", alias="INPI_PEPI_BASE_URL"
    )
    # Logotipo fetching is done by the offline worker (``python -m
    # ingestion.logos``). The API is DB-first and, by default, READ-ONLY: it
    # serves whatever the worker already stored and shows a placeholder when the
    # image is absent. Set to ``True`` only to allow the old on-demand fetch from
    # INPI during an API request (not recommended; blocks a request/worker).
    logo_fetch_enabled: bool = Field(default=False, alias="LOGO_FETCH_ENABLED")
    logo_http_timeout_seconds: int = Field(
        default=120, alias="LOGO_HTTP_TIMEOUT_SECONDS"
    )
    logo_http_retries: int = Field(default=2, alias="LOGO_HTTP_RETRIES")

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

    # --- NIT document storage (decision D2) ---------------------------------
    # Backend: "local" (private directory, development/pilot) or "s3" (private
    # object storage — inert until STORAGE_BUCKET + credentials are configured).
    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    storage_bucket: str = Field(default="", alias="STORAGE_BUCKET")
    # Physical directory for the local private backend. MUST be outside any
    # directory served by the web server. Default: backend/var/documents.
    document_storage_dir: str = Field(
        default="backend/var/documents", alias="DOCUMENT_STORAGE_DIR"
    )
    # Upload ceiling (default 25 MB — decision A5).
    document_max_size_mb: int = Field(default=25, alias="DOCUMENT_MAX_SIZE_MB")

    @field_validator("database_url")
    @classmethod
    def _ensure_psycopg_driver(cls, value: str) -> str:
        # Normalise plain postgresql:// URLs to the psycopg (v3) driver.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def _reject_insecure_defaults(self) -> "Settings":
        """Refuse to start a non-local environment with known weak defaults.

        Development (``ENVIRONMENT=local``) keeps working with the shipped
        defaults so local runs and the test-suite are unaffected. Any other
        environment (staging, production, ...) must supply real secrets.
        """
        if self.environment.strip().lower() in LOCAL_ENVIRONMENTS:
            return self

        problems: list[str] = []
        if self.jwt_secret in INSECURE_JWT_SECRETS:
            problems.append("JWT_SECRET")
        if self.jwt_refresh_secret in INSECURE_JWT_SECRETS:
            problems.append("JWT_REFRESH_SECRET")
        if self.jwt_secret == self.jwt_refresh_secret:
            problems.append("JWT_SECRET == JWT_REFRESH_SECRET (must differ)")
        if self.master_admin_password in INSECURE_ADMIN_PASSWORDS:
            problems.append("MASTER_ADMIN_PASSWORD")
        for name, value in (
            ("JWT_SECRET", self.jwt_secret),
            ("JWT_REFRESH_SECRET", self.jwt_refresh_secret),
        ):
            if value and len(value) < 32:
                problems.append(f"{name} (deve ter ao menos 32 caracteres)")
        if problems:
            raise ValueError(
                "Configuração insegura para ENVIRONMENT="
                f"'{self.environment}': {', '.join(problems)}. "
                "Defina segredos reais antes de iniciar este ambiente."
            )
        return self

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
    def logos_path(self) -> Path:
        """Where marca logotipo images are stored on disk.

        Mirrors ``ingestion.config.IngestionConfig.logos_dir`` so the on-demand
        resolver and the offline downloader share the exact same layout
        (``<data>/raw/marcas/logos/<2 primeiros dígitos>/<codigo>.<ext>``).
        """
        return self.data_path / "raw" / "marcas" / "logos"

    @property
    def reports_path(self) -> Path:
        return PROJECT_ROOT / "reports"

    @property
    def document_storage_path(self) -> Path:
        """Absolute path of the private document storage directory.

        Relative values are resolved against the project root; the directory is
        NOT under the Next.js/public tree, so it is never served as a static file.
        """
        p = Path(self.document_storage_dir)
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        return p

    @property
    def document_max_size_bytes(self) -> int:
        return max(1, int(self.document_max_size_mb)) * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
