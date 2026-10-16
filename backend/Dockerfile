# IntelliINPI backend image (FastAPI + SQLAlchemy + Alembic + ingestion deps).
FROM python:3.13-slim AS ingestion_reqs
# Reads ingestion/requirements.txt from the additional build context declared in
# docker-compose.prod.yml (Docker cannot COPY files outside the build context,
# and the primary context is ./backend).
ARG INGESTION_REQS=requirements.txt
COPY ${INGESTION_REQS} /requirements.txt

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: build tools for psycopg/argon2 are not needed with wheels,
# but libpq is required at runtime for psycopg.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching).
# The ingestion requirements come from the secondary build context (stage
# `ingestion_reqs` above), because the primary context is ./backend.
COPY requirements.txt ./requirements.txt
COPY --from=ingestion_reqs requirements.txt ./ingestion-requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install -r ingestion-requirements.txt

# Copy application code.
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
