"""Lightweight CSV analysis.

Uses DuckDB's CSV sniffer to determine the delimiter, quoting, encoding and
header columns, and to count rows. This is the same engine used for the import
step, so what we analyze is exactly what we (would) load.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import duckdb

from ingestion import db
from ingestion.config import CONFIG
from ingestion.datasets import DatasetSpec, resolve
from ingestion.extract import extract, extracted_dir, raw_path
from ingestion.util import get_logger

logger = get_logger(__name__)


@dataclass
class CsvProfile:
    dataset: str
    path: str
    delimiter: str
    encoding: str
    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    error: str | None = None


def _csv_candidates(spec: DatasetSpec) -> list[Path]:
    """Return the CSV file(s) belonging to a dataset."""
    if spec.is_csv:
        return [raw_path(spec)]
    out_dir = extracted_dir(spec)
    if not out_dir.exists():
        extract(spec)
    return sorted(out_dir.rglob("*.csv"))


def profile_csv(path: Path, *, dataset: str) -> CsvProfile:
    """Sniff a single CSV file and return its profile."""
    con = duckdb.connect(database=":memory:")
    try:
        # The sniffer tolerates the INPI dumps' oddities; we pin a large sample.
        sample = con.execute(
            """
            SELECT Delimiter, Quote, Escape, HasHeader
            FROM sniff_csv(?)
            """,
            [str(path)],
        ).fetchone()
        delimiter = sample[0] if sample else ","
        encoding = "utf-8"  # DuckDB reads CSV as UTF-8

        # Column names via DESCRIBE (uses the same sniffer options).
        cols = con.execute(
            f"DESCRIBE SELECT * FROM read_csv(?, delim=?, header=true, sample_size=-1)",
            [str(path), delimiter],
        ).fetchall()
        columns = [c[0] for c in cols]

        row_count = con.execute(
            "SELECT count(*) FROM read_csv(?, delim=?, header=true, sample_size=-1, ignore_errors=true)",
            [str(path), delimiter],
        ).fetchone()[0]

        return CsvProfile(
            dataset=dataset,
            path=str(path),
            delimiter=delimiter,
            encoding=encoding,
            columns=columns,
            row_count=int(row_count),
        )
    except Exception as exc:  # noqa: BLE001 - report, don't crash the batch
        logger.warning("Analysis failed for %s: %s", path, exc)
        return CsvProfile(
            dataset=dataset, path=str(path), delimiter=",", encoding="utf-8", error=str(exc)
        )
    finally:
        con.close()


def analyze(spec: DatasetSpec) -> list[CsvProfile]:
    profiles: list[CsvProfile] = []
    for csv_path in _csv_candidates(spec):
        profile = profile_csv(csv_path, dataset=spec.name)
        profiles.append(profile)
        logger.info(
            "Analyzed %-32s rows=%-12s cols=%d delim=%r",
            csv_path.name,
            profile.row_count,
            len(profile.columns),
            profile.delimiter,
        )
    if profiles:
        db.set_dataset_status(
            spec.name,
            "ANALYZED",
            meta={
                "profiles": [
                    {
                        "path": p.path,
                        "delimiter": p.delimiter,
                        "encoding": p.encoding,
                        "columns": p.columns,
                        "row_count": p.row_count,
                        "error": p.error,
                    }
                    for p in profiles
                ]
            },
        )
    return profiles


def analyze_all(targets: list[str] | None = None) -> dict[str, list[CsvProfile]]:
    results: dict[str, list[CsvProfile]] = {}
    for spec in resolve(targets):
        results[spec.name] = analyze(spec)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze INPI CSV datasets.")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--dataset", action="append", dest="datasets")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)
    targets = (args.categories or []) + (args.datasets or [])
    results = analyze_all(targets or None)
    if args.json:
        payload = {
            name: [asdict(p) for p in profiles] for name, profiles in results.items()
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for name, profiles in results.items():
            for p in profiles:
                print(f"{name}: rows={p.row_count} cols={len(p.columns)} delim={p.delimiter!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
