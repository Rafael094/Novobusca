"""Generate TypeScript type declarations from the OpenAPI schema (R-18).

This addresses the "type drift" risk: the frontend can regenerate its types from
the backend's own OpenAPI document instead of hand-maintaining them. Only the
targeted subset needed for the contract is emitted (schemas), producing stable,
deterministic output for review.

No network access and no code execution: the OpenAPI dict is walked directly.
"""

from __future__ import annotations

import re
from typing import Any

_TS_PRIMITIVES = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
}


def _sanitize(name: str) -> str:
    """Turn an OpenAPI schema name into a safe TypeScript identifier."""
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def _schema_to_ts(schema: dict[str, Any]) -> str:
    if not isinstance(schema, dict):
        return "unknown"

    if "$ref" in schema:
        return _sanitize(schema["$ref"].split("/")[-1])

    if "anyOf" in schema or "oneOf" in schema:
        options = schema.get("anyOf") or schema.get("oneOf")
        parts = [_schema_to_ts(o) for o in options]
        # de-duplicate while preserving order
        seen: list[str] = []
        for p in parts:
            if p not in seen:
                seen.append(p)
        return " | ".join(seen)

    if "allOf" in schema:
        return " & ".join(_schema_to_ts(o) for o in schema["allOf"])

    stype = schema.get("type")
    if stype == "array":
        return f"{_schema_to_ts(schema.get('items', {}))}[]"
    if stype == "object" or "properties" in schema:
        props = schema.get("properties")
        if not props:
            return "Record<string, unknown>"
        lines = ["{"]
        for prop, spec in props.items():
            optional = "" if prop in set(schema.get("required", [])) else "?"
            lines.append(f"  {prop}{optional}: {_schema_to_ts(spec)};")
        lines.append("}")
        return "\n".join(lines)
    if stype in _TS_PRIMITIVES:
        return _TS_PRIMITIVES[stype]
    return "unknown"


def generate_types(openapi: dict[str, Any]) -> str:
    """Return a TypeScript module declaring every named schema as an exported type."""
    schemas = (openapi.get("components") or {}).get("schemas") or {}
    out = [
        "/**",
        " * AUTO-GENERATED from the API OpenAPI schema (R-18). Do not edit by hand.",
        f" * Source title: {openapi.get('info', {}).get('title', 'API')}",
        " */",
        "",
    ]
    for name in sorted(schemas):
        alias = _sanitize(name)
        out.append(f"export type {alias} = {_schema_to_ts(schemas[name])};")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
