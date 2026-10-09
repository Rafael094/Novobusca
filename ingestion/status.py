"""CLI shim: ``python -m ingestion.status``.

Prints the current ingestion pipeline state (dataset statuses + imports).
"""

from __future__ import annotations

import json

from ingestion.import_all import status


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
