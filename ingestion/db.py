"""Lightweight database access for the ingestion pipeline.

The pipeline writes to the *tracking* tables (``inpi_dataset``, ``inpi_import``,
``inpi_import_error``, ``inpi_import_checkpoint``, ``inpi_rpi``) with raw SQL.
Using raw SQL keeps the pipeline independent of the backend ORM import path and
avoids session-lifecycle surprises during long COPY loads.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import psycopg

from ingestion.config import CONFIG


def connect() -> psycopg.Connection:
    """Open a new autocommit psycopg connection to the target database."""
    conn = psycopg.connect(CONFIG.psycopg_dsn, autocommit=True)
    return conn


@contextlib.contextmanager
def cursor() -> Iterator[psycopg.Cursor]:
    """Context manager yielding a server-side cursor on a fresh connection."""
    with connect() as conn:
        with conn.cursor() as cur:
            yield cur


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Dataset registry -------------------------------------------------------
def upsert_dataset(
    *,
    name: str,
    category: str,
    source_url: str,
    status: str = "DISCOVERED",
    file_name: str | None = None,
    file_size: int | None = None,
    sha256: str | None = None,
    raw_path: str | None = None,
    extracted_path: str | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Insert or update a dataset row; returns the dataset UUID as a string."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_dataset
                (id, name, category, source_url, status, file_name, file_size,
                 sha256, raw_path, extracted_path, metadata, created_at, updated_at)
            VALUES
                (%(id)s, %(name)s, %(category)s, %(source_url)s, %(status)s,
                 %(file_name)s, %(file_size)s, %(sha256)s, %(raw_path)s,
                 %(extracted_path)s, %(meta)s, %(now)s, %(now)s)
            ON CONFLICT (name) DO UPDATE SET
                category = EXCLUDED.category,
                source_url = EXCLUDED.source_url,
                status = EXCLUDED.status,
                file_name = EXCLUDED.file_name,
                file_size = EXCLUDED.file_size,
                sha256 = EXCLUDED.sha256,
                raw_path = EXCLUDED.raw_path,
                extracted_path = EXCLUDED.extracted_path,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """,
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "category": category,
                "source_url": source_url,
                "status": status,
                "file_name": file_name,
                "file_size": file_size,
                "sha256": sha256,
                "raw_path": raw_path,
                "extracted_path": extracted_path,
                "meta": _json(meta),
                "now": _now(),
            },
        )
        row = cur.fetchone()
        return str(row[0])


def set_dataset_status(
    name: str,
    status: str,
    *,
    file_size: int | None = None,
    sha256: str | None = None,
    raw_path: str | None = None,
    extracted_path: str | None = None,
    reference_date: datetime | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Update the mutable fields of a dataset row by name."""
    sets = ["status = %(status)s", "updated_at = %(now)s"]
    params: dict[str, Any] = {"name": name, "status": status, "now": _now()}
    if file_size is not None:
        sets.append("file_size = %(file_size)s")
        params["file_size"] = file_size
    if sha256 is not None:
        sets.append("sha256 = %(sha256)s")
        params["sha256"] = sha256
    if raw_path is not None:
        sets.append("raw_path = %(raw_path)s")
        params["raw_path"] = raw_path
        sets.append("downloaded_at = %(now)s")
    if extracted_path is not None:
        sets.append("extracted_path = %(extracted_path)s")
        params["extracted_path"] = extracted_path
    if reference_date is not None:
        sets.append("reference_date = %(reference_date)s")
        params["reference_date"] = reference_date
    if meta is not None:
        sets.append("metadata = %(meta)s")
        params["meta"] = _json(meta)
    with cursor() as cur:
        cur.execute(
            f"UPDATE inpi_dataset SET {', '.join(sets)} WHERE name = %(name)s",
            params,
        )


def _json(value: Any) -> Any:
    if value is None:
        return None
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


# --- Import runs ------------------------------------------------------------
def start_import(dataset_id: str, *, meta: dict[str, Any] | None = None) -> str:
    """Create a RUNNING import run and return its UUID string."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_import
                (id, dataset_id, started_at, status, rows_read, rows_inserted,
                 rows_updated, rows_skipped, rows_failed, error_count, metadata)
            VALUES
                (%(id)s, %(dataset_id)s, %(now)s, 'RUNNING', 0, 0, 0, 0, 0, 0, %(meta)s)
            RETURNING id
            """,
            {
                "id": str(uuid.uuid4()),
                "dataset_id": dataset_id,
                "now": _now(),
                "meta": _json(meta),
            },
        )
        return str(cur.fetchone()[0])


def finish_import(
    import_id: str,
    *,
    status: str,
    rows_read: int = 0,
    rows_inserted: int = 0,
    rows_updated: int = 0,
    rows_skipped: int = 0,
    rows_failed: int = 0,
    error_count: int = 0,
    error_message: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    with cursor() as cur:
        cur.execute(
            """
            UPDATE inpi_import SET
                finished_at = %(now)s,
                status = %(status)s,
                rows_read = %(rows_read)s,
                rows_inserted = %(rows_inserted)s,
                rows_updated = %(rows_updated)s,
                rows_skipped = %(rows_skipped)s,
                rows_failed = %(rows_failed)s,
                error_count = %(error_count)s,
                error_message = %(error_message)s,
                duration_seconds = %(duration_seconds)s
            WHERE id = %(id)s
            """,
            {
                "id": import_id,
                "now": _now(),
                "status": status,
                "rows_read": rows_read,
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "rows_skipped": rows_skipped,
                "rows_failed": rows_failed,
                "error_count": error_count,
                "error_message": error_message,
                "duration_seconds": duration_seconds,
            },
        )


def record_error(
    import_id: str,
    *,
    dataset: str | None,
    row_number: int | None,
    raw_data: str | None,
    error: str,
) -> None:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_import_error
                (id, import_id, dataset, row_number, raw_data, error, created_at)
            VALUES (%(id)s, %(import_id)s, %(dataset)s, %(row_number)s,
                    %(raw_data)s, %(error)s, %(now)s)
            """,
            {
                "id": str(uuid.uuid4()),
                "import_id": import_id,
                "dataset": dataset,
                "row_number": row_number,
                "raw_data": raw_data,
                "error": error,
                "now": _now(),
            },
        )


# --- Checkpoints ------------------------------------------------------------
def get_checkpoint(dataset_id: str, target_table: str) -> dict[str, Any] | None:
    with cursor() as cur:
        cur.execute(
            """
            SELECT last_row_number, total_rows, completed
            FROM inpi_import_checkpoint
            WHERE dataset_id = %s AND target_table = %s
            """,
            (dataset_id, target_table),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "last_row_number": row[0],
            "total_rows": row[1],
            "completed": row[2],
        }


def save_checkpoint(
    dataset_id: str,
    target_table: str,
    *,
    last_row_number: int,
    total_rows: int | None = None,
    completed: bool = False,
    meta: dict[str, Any] | None = None,
) -> None:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_import_checkpoint
                (id, dataset_id, target_table, last_row_number, total_rows,
                 completed, metadata, created_at, updated_at)
            VALUES
                (%(id)s, %(dataset_id)s, %(target_table)s, %(last)s, %(total)s,
                 %(completed)s, %(meta)s, %(now)s, %(now)s)
            ON CONFLICT (dataset_id, target_table) DO UPDATE SET
                last_row_number = EXCLUDED.last_row_number,
                total_rows = EXCLUDED.total_rows,
                completed = EXCLUDED.completed,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "id": str(uuid.uuid4()),
                "dataset_id": dataset_id,
                "target_table": target_table,
                "last": last_row_number,
                "total": total_rows,
                "completed": completed,
                "meta": _json(meta),
                "now": _now(),
            },
        )


def clear_checkpoint(dataset_id: str, target_table: str) -> None:
    with cursor() as cur:
        cur.execute(
            "DELETE FROM inpi_import_checkpoint WHERE dataset_id = %s AND target_table = %s",
            (dataset_id, target_table),
        )


# --- RPI --------------------------------------------------------------------
def upsert_rpi(
    *,
    number: str,
    edition_date: datetime | None = None,
    file_name: str | None = None,
    file_size: int | None = None,
    sha256: str | None = None,
    source_url: str | None = None,
    status: str = "DISCOVERED",
    raw_path: str | None = None,
) -> None:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO inpi_rpi
                (id, number, edition_date, file_name, file_size, sha256,
                 source_url, status, raw_path, created_at, updated_at)
            VALUES
                (%(id)s, %(number)s, %(edition_date)s, %(file_name)s,
                 %(file_size)s, %(sha256)s, %(source_url)s, %(status)s,
                 %(raw_path)s, %(now)s, %(now)s)
            ON CONFLICT (number) DO UPDATE SET
                edition_date = EXCLUDED.edition_date,
                file_name = EXCLUDED.file_name,
                file_size = EXCLUDED.file_size,
                sha256 = EXCLUDED.sha256,
                source_url = EXCLUDED.source_url,
                status = EXCLUDED.status,
                raw_path = EXCLUDED.raw_path,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "id": str(uuid.uuid4()),
                "number": number,
                "edition_date": edition_date,
                "file_name": file_name,
                "file_size": file_size,
                "sha256": sha256,
                "source_url": source_url,
                "status": status,
                "raw_path": raw_path,
                "now": _now(),
            },
        )


# --- Marcas logotipos (pePI images) ------------------------------------------
def logo_codes(
    *,
    apresentacoes: list[str] | None = None,
    only_pending: bool = True,
    limit: int | None = None,
) -> list[str]:
    """Return ``codigo_interno`` values that still need a logotipo.

    ``apresentacoes`` filters by ``marcas.descricao_apresentacao`` (e.g. only
    ``Mista``/``Figurativa``, which are the ones that usually carry an image).
    When ``only_pending`` is True, codes already recorded in ``marcas_logos``
    with a terminal status (``OK``/``SEM_IMAGEM``) are skipped so the downloader
    can resume cheaply.
    """
    where: list[str] = ["m.codigo_interno IS NOT NULL"]
    params: dict[str, Any] = {}
    if apresentacoes:
        where.append("m.descricao_apresentacao = ANY(%(apres)s)")
        params["apres"] = apresentacoes
    if only_pending:
        where.append(
            """
            NOT EXISTS (
                SELECT 1 FROM marcas_logos l
                WHERE l.codigo_interno = m.codigo_interno
                  AND l.status IN ('OK', 'SEM_IMAGEM')
            )
            """
        )
    sql = f"SELECT m.codigo_interno FROM marcas m WHERE {' AND '.join(where)}"
    if limit:
        sql += " LIMIT %(limit)s"
        params["limit"] = limit
    with cursor() as cur:
        cur.execute(sql, params)
        return [r[0] for r in cur.fetchall()]


def upsert_logo(
    *,
    codigo_interno: str,
    status: str,
    arquivo: str | None = None,
    mime: str | None = None,
    bytes_: int | None = None,
    sha256: str | None = None,
    tentativas: int = 0,
    erro: str | None = None,
    baixado_em: datetime | None = None,
) -> None:
    """Insert or update a ``marcas_logos`` row keyed by ``codigo_interno``."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO marcas_logos
                (id, codigo_interno, arquivo, mime, bytes, sha256, status,
                 tentativas, erro, baixado_em, created_at, updated_at)
            VALUES
                (%(id)s, %(codigo_interno)s, %(arquivo)s, %(mime)s, %(bytes)s,
                 %(sha256)s, %(status)s, %(tentativas)s, %(erro)s,
                 %(baixado_em)s, %(now)s, %(now)s)
            ON CONFLICT (codigo_interno) DO UPDATE SET
                arquivo = EXCLUDED.arquivo,
                mime = EXCLUDED.mime,
                bytes = EXCLUDED.bytes,
                sha256 = EXCLUDED.sha256,
                status = EXCLUDED.status,
                tentativas = EXCLUDED.tentativas,
                erro = EXCLUDED.erro,
                baixado_em = EXCLUDED.baixado_em,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "id": str(uuid.uuid4()),
                "codigo_interno": codigo_interno,
                "arquivo": arquivo,
                "mime": mime,
                "bytes": bytes_,
                "sha256": sha256,
                "status": status,
                "tentativas": tentativas,
                "erro": erro,
                "baixado_em": baixado_em,
                "now": _now(),
            },
        )
