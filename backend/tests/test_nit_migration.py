"""F1 — Alembic migration round-trip on an ISOLATED database.

Runs ``upgrade head`` → verifies the NIT tables exist → ``downgrade -1`` →
verifies they are gone → ``upgrade head`` again. The database is a throwaway
(``intelliinpi_migtest``) so no development data is ever touched.

If PostgreSQL is not reachable, the test is SKIPPED (never silently passed).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text

MIG_TEST_DB = os.environ.get(
    "MIGRATION_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/intelliinpi_migtest",
)

NIT_TABLES = {
    "invention_disclosures",
    "disclosure_inventors",
    "invention_documents",
    "document_acls",
    "workflow_states",
    "workflow_transitions",
    "workflow_instances",
    "workflow_history",
    "evaluations",
    "ip_assets",
    "ip_asset_public_links",
    # F2
    "trl_history",
    "committees",
    "committee_members",
    "committee_meetings",
    "committee_agenda_items",
    "committee_votes",
    "committee_decisions",
    # F3
    "technology_offers",
    "expressions_of_interest",
    "interest_interactions",
    "negotiations",
    "negotiation_history",
    "licenses",
    "contracts",
    "contract_parties",
    "contract_obligations",
    "royalties",
    # F4
    "projects",
    "project_members",
    "project_funders",
    "project_milestones",
    "project_asset_links",
    "startups",
    "startup_members",
    "incubation_programs",
    "incubation_participations",
    "incubation_stages",
    # F5
    "nit_notifications",
    "nit_notification_preferences",
    "nit_email_messages",
    "nit_portal_access",
    "nit_portal_requests",
    "nit_portal_request_notes",
    "nit_saved_reports",
    "nit_report_runs",
    "nit_integration_endpoints",
    "nit_integration_deliveries",
}


def _ensure_db() -> bool:
    base, _, dbname = MIG_TEST_DB.rpartition("/")
    admin = create_engine(f"{base}/postgres", isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{dbname}"'))
        return True
    except Exception:
        return False
    finally:
        admin.dispose()


@pytest.fixture(scope="module")
def mig_engine():
    if not _ensure_db():
        pytest.skip("PostgreSQL indisponível para o teste de migração")
    engine = create_engine(MIG_TEST_DB, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


def _alembic_config(url: str):
    from alembic.config import Config
    from pathlib import Path

    # Always resolve alembic.ini relative to this test file's backend/ directory.
    backend_dir = Path(__file__).parent.parent
    alembic_ini = backend_dir / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", url)
    # Ensure script_location is also resolved correctly.
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


def test_nit_migration_upgrade_and_downgrade(mig_engine, monkeypatch):
    from alembic import command

    from app.config import settings

    # ``alembic/env.py`` reads the URL from the settings singleton, so we point it
    # at the isolated migration database for the duration of this test only.
    monkeypatch.setattr(settings, "database_url", MIG_TEST_DB, raising=False)
    cfg = _alembic_config(MIG_TEST_DB)

    # Start clean.
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    insp = inspect(mig_engine)
    tables_after_upgrade = set(insp.get_table_names())
    missing = NIT_TABLES - tables_after_upgrade
    assert not missing, f"tabelas NIT ausentes: {missing}"

    # Downgrade all NIT revisions (back to the pre-NIT head).
    command.downgrade(cfg, "e5f6a7b8c9d0")
    insp = inspect(mig_engine)
    tables_after_downgrade = set(insp.get_table_names())
    assert not (NIT_TABLES & tables_after_downgrade), "downgrade não removeu as tabelas NIT"

    # Re-upgrade is idempotent and restores the schema.
    command.upgrade(cfg, "head")
    insp = inspect(mig_engine)
    assert NIT_TABLES <= set(insp.get_table_names())

    # The public INPI tables must be intact throughout.
    assert {"marcas", "patentes"} <= set(insp.get_table_names())

    command.downgrade(cfg, "base")
