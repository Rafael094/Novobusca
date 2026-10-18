"""Ingestion-pipeline configuration.

Resolves the database URL, data directory and INPI base URL from the backend
``app.config.settings`` when the backend is importable, falling back to
environment variables / sane defaults when the pipeline is run standalone.

This keeps a single source of truth (the backend ``.env``) while still allowing
the pipeline to run in an environment where ``app`` is not on ``sys.path``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _backend_settings() -> object | None:
    try:  # pragma: no cover - depends on import environment
        from app.config import settings  # type: ignore

        return settings
    except Exception:  # noqa: BLE001 - config is best-effort
        return None


def _first(*values: str | None, default: str = "") -> str:
    for value in values:
        if value:
            return value
    return default


@dataclass(frozen=True)
class IngestionConfig:
    """Frozen configuration snapshot for a pipeline run."""

    database_url: str
    data_dir: Path
    inpi_base_url: str
    pePI_base_url: str = "https://busca.inpi.gov.br/pePI"
    # Portal das Revistas (RPI) — publicação semanal de terça-feira.
    rpi_base_url: str = "https://revistas.inpi.gov.br"
    http_timeout_seconds: int = 120
    http_retries: int = 4
    chunk_size: int = 50_000
    verify_ssl: bool = True
    user_agent: str = "IntelliINPI-Ingestion/1.0 (+https://localhost)"
    logo_concurrency: int = 4
    logo_delay_seconds: float = 0.15
    # Petições do pePI (página de detalhe) — knobs separados dos logotipos.
    pepi_concurrency: int = 4
    pepi_delay_seconds: float = 0.25

    @property
    def psycopg_dsn(self) -> str:
        """Return a libpq DSN suitable for psycopg/COPY (no SQLAlchemy driver)."""
        url = self.database_url
        # Strip the SQLAlchemy driver suffix: postgresql+psycopg:// -> postgresql://
        if "+" in url.split("://", 1)[0]:
            scheme, rest = url.split("://", 1)
            url = "postgresql://" + rest
        return url

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def extracted_dir(self) -> Path:
        return self.data_dir / "extracted"

    @property
    def logos_dir(self) -> Path:
        """Where marca logotipo images are stored on disk."""
        return self.data_dir / "raw" / "marcas" / "logos"

    @property
    def rpi_dir(self) -> Path:
        """Where downloaded RPI editions (weekly ZIPs) are kept on disk."""
        return self.data_dir / "raw" / "rpi"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir.parent / "reports"


def load_config() -> IngestionConfig:
    """Build an :class:`IngestionConfig` from the backend settings or env."""
    settings = _backend_settings()

    database_url = _first(
        getattr(settings, "database_url", None) if settings else None,
        os.environ.get("DATABASE_URL"),
        default="postgresql+psycopg://postgres:postgres@localhost:5432/intelliinpi_app",
    )
    data_dir = _first(
        getattr(settings, "data_dir", None) if settings else None,
        os.environ.get("DATA_DIR"),
        default="./data",
    )
    base_url = _first(
        getattr(settings, "inpi_base_url", None) if settings else None,
        os.environ.get("INPI_BASE_URL"),
        default="https://dadosabertos.inpi.gov.br",
    )
    pepi_base_url = _first(
        os.environ.get("INPI_PEPI_BASE_URL"),
        default="https://busca.inpi.gov.br/pePI",
    )
    rpi_base_url = _first(
        os.environ.get("INPI_RPI_BASE_URL"),
        default="https://revistas.inpi.gov.br",
    )

    # Resolve the data dir relative to the repository root (project root), not
    # the current working directory, so CLI and server both land in the same spot.
    data_path = Path(data_dir)
    if not data_path.is_absolute():
        repo_root = Path(__file__).resolve().parent.parent
        data_path = (repo_root / data_dir).resolve()

    cfg = IngestionConfig(
        database_url=database_url,
        data_dir=data_path,
        inpi_base_url=base_url.rstrip("/"),
        pePI_base_url=pepi_base_url.rstrip("/"),
        rpi_base_url=rpi_base_url.rstrip("/"),
        http_timeout_seconds=int(os.environ.get("INPI_HTTP_TIMEOUT", "120")),
        http_retries=int(os.environ.get("INPI_HTTP_RETRIES", "4")),
        chunk_size=int(os.environ.get("INPI_IMPORT_CHUNK_SIZE", "50000")),
        verify_ssl=os.environ.get("INPI_VERIFY_SSL", "true").lower() != "false",
        logo_concurrency=int(os.environ.get("INPI_LOGO_CONCURRENCY", "4")),
        logo_delay_seconds=float(os.environ.get("INPI_LOGO_DELAY", "0.15")),
        pepi_concurrency=int(os.environ.get("INPI_PEPI_CONCURRENCY", "4")),
        pepi_delay_seconds=float(os.environ.get("INPI_PEPI_DELAY", "0.25")),
    )
    return cfg


CONFIG = load_config()
