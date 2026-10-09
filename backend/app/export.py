"""CSV export helpers (streaming responses)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from fastapi.responses import StreamingResponse


def rows_to_csv(
    rows: Iterable[dict], fieldnames: list[str], *, filename: str
) -> StreamingResponse:
    """Return a streaming CSV response for the given rows.

    Writes a UTF-8 BOM so Excel opens accented Portuguese text correctly.
    """
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if v is None else v) for k, v in row.items()})
    buffer.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )
