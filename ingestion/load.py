"""Bulk loader: CSV -> existing PostgreSQL tables via DuckDB.

Strategy
--------
1. Read the CSV header and the target table's columns.
2. Match CSV columns to table columns case/accent-insensitively. Only matched
   columns are projected, so extra table columns (``id``, timestamps) fall back
   to their server defaults.
3. ``ATTACH`` the PostgreSQL database from DuckDB (``postgres`` extension) and
   run a single ``INSERT INTO pg.<table> SELECT ... FROM read_csv(...)``.
"""

from __future__ import annotations

import argparse
import time
import unicodedata
from pathlib import Path

import duckdb

from ingestion import db
from ingestion.config import CONFIG
from ingestion.datasets import DatasetSpec, resolve
from ingestion.analyze import _csv_candidates
from ingestion.util import get_logger

logger = get_logger(__name__)


def _normalize(name: str) -> str:
    """Lower-case and strip accents so 'Número_INPI' matches 'numero_inpi'."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return ascii_only.strip().lower().replace(" ", "_")


def _table_columns(con: duckdb.DuckDBPyConnection, table: str) -> dict[str, str]:
    """Return {normalized_name: actual_column} for a PostgreSQL table."""
    rows = con.execute(
        """
        SELECT column_name
        FROM pg.information_schema.columns
        WHERE table_schema = 'public' AND table_name = ?
        """,
        [table],
    ).fetchall()
    return {_normalize(r[0]): r[0] for r in rows}


def _unique_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Return the columns of the table's single-column UNIQUE constraint, if any.

    The INPI snapshot CSVs occasionally repeat entire rows for the same natural
    key; the ``marcas``/``patentes`` tables enforce a UNIQUE constraint on
    ``codigo_interno``. Knowing that column lets the loader deduplicate the
    source before inserting.
    """
    rows = con.execute(
        """
        SELECT a.attname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_attribute a
          ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE n.nspname = 'public'
          AND t.relname = ?
          AND c.contype = 'u'
          AND array_length(c.conkey, 1) = 1
        """,
        [table],
    ).fetchall()
    return [r[0] for r in rows]



def _csv_columns(con: duckdb.DuckDBPyConnection, path: Path) -> list[str]:
    cols = con.execute(
        "DESCRIBE SELECT * FROM read_csv(?, header=true, sample_size=-1, ignore_errors=true)",
        [str(path)],
    ).fetchall()
    return [c[0] for c in cols]


def _attach(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSTALL postgres; LOAD postgres;")
    # DuckDB >=0.10 attaches Postgres read-write by default; the older
    # READ_WRITE option keyword was removed from newer extension builds.
    con.execute(f"ATTACH '{CONFIG.psycopg_dsn}' AS pg (TYPE postgres)")


def _dataset_id(name: str) -> str:
    with db.cursor() as cur:
        cur.execute("SELECT id FROM inpi_dataset WHERE name = %s", (name,))
        row = cur.fetchone()
        return str(row[0]) if row else ""


def load_dataset(
    spec: DatasetSpec,
    *,
    force: bool = False,
    import_run_id: str | None = None,
) -> dict:
    """Load every CSV of a dataset into its target table. Returns counters."""
    if spec.target_table is None:
        logger.info("Dataset %s is a bundle; skipping load.", spec.name)
        return {"rows_read": 0, "rows_inserted": 0}

    csv_files = _csv_candidates(spec)
    if not csv_files:
        raise FileNotFoundError(f"No CSV found for {spec.name}")

    started = time.monotonic()
    total_read = 0
    total_inserted = 0

    con = duckdb.connect(database=":memory:")
    try:
        _attach(con)
        table = spec.target_table
        table_cols = _table_columns(con, table)
        if not table_cols:
            raise RuntimeError(f"Target table not found: {table}")
        unique_cols = _unique_columns(con, table)

        if force:
            con.execute(f'DELETE FROM pg."{table}"')

        for csv_path in csv_files:
            csv_cols = _csv_columns(con, csv_path)
            matched = [c for c in csv_cols if _normalize(c) in table_cols]
            if not matched:
                raise RuntimeError(
                    f"No matching columns between {csv_path.name} and {table}"
                )
            # Project matched CSV columns -> table columns, prefixing a fresh
            # UUID for the primary key (the model uses a Python-side uuid4
            # default with no server default, so raw inserts must supply it).
            select_parts = ['gen_random_uuid() AS "id"']
            target_parts = ['"id"']
            for c in matched:
                select_parts.append(f'"{c}" AS "{table_cols[_normalize(c)]}"')
                target_parts.append(f'"{table_cols[_normalize(c)]}"')
            select_list = ", ".join(select_parts)
            target_cols = ", ".join(target_parts)
            path_sql = csv_path.as_posix()

            # Deduplicate the source so a snapshot reload never violates the
            # table's UNIQUE constraint (INPI CSVs repeat identical rows for the
            # same natural key). When a single-column UNIQUE constraint exists,
            # keep one row per key; otherwise fall back to DISTINCT over all
            # projected data columns.
            if unique_cols:
                key = unique_cols[0]
                key_col = matched[
                    next(
                        i
                        for i, c in enumerate(matched)
                        if _normalize(c) == _normalize(key)
                    )
                ]
                source = (
                    f"(SELECT {select_list} FROM read_csv('{path_sql}', header=true, "
                    f"sample_size=-1, ignore_errors=true) "
                    f'QUALIFY row_number() OVER (PARTITION BY "{key_col}") = 1)'
                )
            else:
                data_cols = ", ".join(f'"{c}"' for c in matched)
                source = (
                    f"(SELECT {select_list} FROM (SELECT DISTINCT {data_cols} "
                    f"FROM read_csv('{path_sql}', header=true, "
                    f"sample_size=-1, ignore_errors=true)))"
                )

            logger.info("Loading %s -> %s (%d cols)", csv_path.name, table, len(matched))
            rows_read = con.execute(f"SELECT count(*) FROM read_csv('{path_sql}', header=true, sample_size=-1, ignore_errors=true)").fetchone()[0]
            con.execute(
                f'INSERT INTO pg."{table}" ({target_cols}) SELECT * FROM {source}'
            )
            rows_inserted = int(con.execute(f"SELECT count(*) FROM {source}").fetchone()[0])
            total_read += int(rows_read)
            total_inserted += rows_inserted


            if import_run_id:
                db.save_checkpoint(
                    _dataset_id(spec.name),
                    table,
                    last_row_number=int(rows_read),
                    total_rows=int(rows_read),
                    completed=True,
                    meta={"csv": csv_path.name},
                )

        con.execute("DETACH pg;")
    finally:
        con.close()

    duration = time.monotonic() - started
    logger.info(
        "Loaded %s: read=%d inserted=%d in %.1fs",
        spec.name,
        total_read,
        total_inserted,
        duration,
    )
    return {
        "rows_read": total_read,
        "rows_inserted": total_inserted,
        "duration_seconds": duration,
    }


def load_all(targets: list[str] | None = None, *, force: bool = False) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for spec in resolve(targets):
        if spec.target_table is None:
            continue
        dataset_id = _dataset_id(spec.name)
        run_id = (
            db.start_import(dataset_id, meta={"table": spec.target_table})
            if dataset_id
            else None
        )
        db.set_dataset_status(spec.name, "IMPORTING")
        try:
            stats = load_dataset(spec, force=force, import_run_id=run_id)
            if run_id:
                db.finish_import(
                    run_id,
                    status="COMPLETED",
                    rows_read=stats["rows_read"],
                    rows_inserted=stats["rows_inserted"],
                    duration_seconds=stats["duration_seconds"],
                )
            db.set_dataset_status(spec.name, "IMPORTED")
            results[spec.name] = stats
        except Exception as exc:  # noqa: BLE001 - record and continue per dataset
            logger.error("Import failed for %s: %s", spec.name, exc)
            if run_id:
                db.finish_import(
                    run_id, status="FAILED", error_count=1, error_message=str(exc)
                )
                db.record_error(
                    run_id, dataset=spec.name, row_number=None, raw_data=None, error=str(exc)
                )
            db.set_dataset_status(spec.name, "FAILED", meta={"error": str(exc)})
            results[spec.name] = {"error": str(exc)}
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load INPI datasets into PostgreSQL.")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--dataset", action="append", dest="datasets")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    targets = (args.categories or []) + (args.datasets or [])
    results = load_all(targets or None, force=args.force)
    for name, stats in results.items():
        print(f"{name}: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
