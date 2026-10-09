"""CLI shim: ``python -m ingestion.retry_failed``.

Re-runs the pipeline for every dataset currently marked ``FAILED``.
"""

from __future__ import annotations

import json

from ingestion.import_all import retry_failed


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(retry_failed(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
