"""Full ingestion orchestrator.

Runs the pipeline end-to-end for the requested targets::

    discover -> download -> extract -> analyze -> load

Exposes the entry points used by the backend router and the CLI:

* ``run_sync(categories=None, force=False)`` - full pipeline for targets.
* ``status()`` - current pipeline state summary.
* ``retry_failed()`` - re-run every dataset currently in ``FAILED`` state.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from ingestion import analyze, db, discover, download, extract, load
from ingestion.config import CONFIG
from ingestion.datasets import resolve
from ingestion.util import get_logger

logger = get_logger(__name__)


def run_pipeline(
    targets: list[str] | None = None,
    *,
    force: bool = False,
    skip_load: bool = False,
) -> dict:
    """Run the full pipeline for the given targets and return a summary."""
    specs = resolve(targets)
    names = [s.name for s in specs]
    logger.info("=== Pipeline start for %d dataset(s): %s ===", len(specs), ", ".join(names))
    started = time.monotonic()

    discover.discover_all(targets)
    download.download_all(targets, force=force)
    extract.extract_all(targets, force=force)
    analyze.analyze_all(targets)
    if skip_load:
        logger.info("skip_load=True; stopping before the load phase.")
        load_results: dict = {}
    else:
        load_results = load.load_all(targets, force=force)

    duration = time.monotonic() - started
    summary = {
        "datasets": names,
        "duration_seconds": round(duration, 2),
        "loaded": load_results,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("=== Pipeline finished in %.1fs ===", duration)
    return summary


def run_sync(
    categories: list[str] | None = None,
    *,
    force: bool = False,
    datasets: list[str] | None = None,
) -> dict:
    """Backend/router entry point. ``categories`` and ``datasets`` are targets."""
    targets: list[str] = []
    targets.extend(categories or [])
    targets.extend(datasets or [])
    return run_pipeline(targets or None, force=force)


def status() -> dict:
    """Return a concise pipeline-state summary from the tracking tables."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT status, count(*) FROM inpi_dataset GROUP BY status ORDER BY status"
        )
        by_status = {row[0]: int(row[1]) for row in cur.fetchall()}

        cur.execute("SELECT count(*) FROM inpi_dataset")
        total_datasets = int(cur.fetchone()[0])

        cur.execute(
            "SELECT status, count(*) FROM inpi_import GROUP BY status ORDER BY status"
        )
        imports_by_status = {row[0]: int(row[1]) for row in cur.fetchall()}

        cur.execute(
            """
            SELECT name, category, status, file_size, reference_date
            FROM inpi_dataset
            ORDER BY category, name
            """
        )
        datasets = [
            {
                "name": r[0],
                "category": r[1],
                "status": r[2],
                "file_size": r[3],
                "reference_date": r[4].isoformat() if r[4] else None,
            }
            for r in cur.fetchall()
        ]

    return {
        "total_datasets": total_datasets,
        "by_status": by_status,
        "imports_by_status": imports_by_status,
        "datasets": datasets,
        "data_dir": str(CONFIG.data_dir),
    }


def retry_failed() -> dict:
    """Re-run the pipeline for every dataset currently in FAILED state."""
    with db.cursor() as cur:
        cur.execute("SELECT name FROM inpi_dataset WHERE status = 'FAILED'")
        failed = [row[0] for row in cur.fetchall()]
    if not failed:
        logger.info("No failed datasets to retry.")
        return {"retried": []}
    logger.info("Retrying %d failed dataset(s): %s", len(failed), ", ".join(failed))
    # Force so the previously-failed dataset is fully re-downloaded/reloaded.
    summary = run_pipeline(failed, force=True)
    summary["retried"] = failed
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the full INPI ingestion pipeline.")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--dataset", action="append", dest="datasets")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-load", action="store_true", help="Stop before loading.")
    parser.add_argument("--status", action="store_true", help="Print status and exit.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed datasets.")
    args = parser.parse_args(argv)

    if args.status:
        import json

        print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.retry_failed:
        import json

        print(json.dumps(retry_failed(), ensure_ascii=False, indent=2, default=str))
        return 0

    targets = (args.categories or []) + (args.datasets or [])
    summary = run_pipeline(targets or None, force=args.force, skip_load=args.skip_load)
    import json

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
