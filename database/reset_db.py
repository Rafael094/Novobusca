"""Drops and recreates a scratch database (used to verify Alembic migrations).

Usage (from the project root, with the backend venv):
    .\\backend\\.venv\\Scripts\\python.exe database\\reset_db.py intelliinpi_migcheck
"""

from __future__ import annotations

import sys

import psycopg

URL = "postgresql://postgres:postgres@localhost:5432/postgres"
name = sys.argv[1] if len(sys.argv) > 1 else "intelliinpi_test"

conn = psycopg.connect(URL, autocommit=True)
with conn.cursor() as cur:
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
        (name,),
    )
    cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
    cur.execute(f'CREATE DATABASE "{name}"')
conn.close()
print(f"reset {name}")
