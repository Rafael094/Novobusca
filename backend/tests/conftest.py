"""Pytest fixtures for the IntelliINPI backend test-suite.

Tests run against a DEDICATED PostgreSQL database (default ``intelliinpi_test``)
so they never touch the development data. The schema is created from the ORM
metadata and dropped afterwards. Every test gets a clean set of tables.

Set TEST_DATABASE_URL to override the target database.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest

# Configure the test database BEFORE importing the app so the engine binds to it.
# Derive the test URL from the app's DATABASE_URL by appending "_test".
_APP_URL = os.environ.get("DATABASE_URL")
if _APP_URL:
    _base, _, _dbname = _APP_URL.rpartition("/")
    _default_test_url = f"{_base}/{_dbname}_test"
else:
    _default_test_url = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/intelliinpi_test"
    )
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", _default_test_url)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
import app.models  # noqa: E402,F401  (register models on Base.metadata)
import app.seed as seed  # noqa: E402
from app.security import hash_password  # noqa: E402

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


def _ensure_database_exists() -> None:
    """Create the test database if it does not exist (best effort)."""
    base, _, dbname = TEST_DATABASE_URL.rpartition("/")
    admin_url = f"{base}/postgres"
    try:
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{dbname}"'))
        admin_engine.dispose()
    except Exception:
        # Assume the database already exists / no permission to create it.
        pass


_ensure_database_exists()

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
TestingSessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True
)


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Generator[None, None, None]:
    # Enable trigram extension if available (search indexes rely on it).
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        except Exception:
            pass
        # The accent-folding helper functions live in database/01_extensions.sql
        # (outside the ORM metadata). Recreate them in the test database so the
        # marcas search (which uses public.fold) behaves like production.
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            conn.execute(
                text(
                    """
                    CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
                    RETURNS text
                    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
                    AS $$ SELECT public.unaccent('public.unaccent', $1) $$;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE OR REPLACE FUNCTION public.fold(text)
                    RETURNS text
                    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
                    AS $$ SELECT lower(public.immutable_unaccent($1)) $$;
                    """
                )
            )
        except Exception:
            pass
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _override_get_db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


fastapi_app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_tables() -> Generator[None, None, None]:
    """Truncate all tables before each test (except Alembic's version table)."""
    with engine.begin() as conn:
        table_names = [
            f'"{t.name}"'
            for t in reversed(Base.metadata.sorted_tables)
            if t.name != "alembic_version"
        ]
        if table_names:
            conn.execute(
                text(f"TRUNCATE {', '.join(table_names)} RESTART IDENTITY CASCADE")
            )
    yield


@pytest.fixture()
def seeded(db: Session) -> dict:
    """Seed modules, permissions, roles + master admin, returning key handles."""
    modules = seed.seed_modules(db)
    perms = seed.seed_permissions(db, modules)
    resources = seed.seed_resources(db, modules)
    seed.seed_roles(db, modules, perms)
    master = seed.seed_master_admin(db)
    db.commit()
    return {
        "modules": modules,
        "permissions": perms,
        "resources": resources,
        "master": master,
    }


@pytest.fixture()
def seeded_full(db: Session) -> dict:
    """Seed everything incl. the default tenant + full admin access.

    Mirrors ``app.seed.run_seed`` so the default-tenant data migration is also
    exercised by the tests.
    """
    modules = seed.seed_modules(db)
    perms = seed.seed_permissions(db, modules)
    resources = seed.seed_resources(db, modules)
    seed.seed_roles(db, modules, perms)
    master = seed.seed_master_admin(db)
    tenant = seed.seed_default_tenant(db, modules)
    seed.seed_default_admin_access(db, tenant, master, perms)
    db.commit()
    return {
        "modules": modules,
        "permissions": perms,
        "resources": resources,
        "master": master,
        "tenant": tenant,
    }


# --- Factory helpers --------------------------------------------------------


def make_user(
    db: Session,
    *,
    email: str,
    password: str = "Password123!",
    tenant_id: uuid.UUID | None = None,
    is_master_admin: bool = False,
    active: bool = True,
):
    """Create a credential-only User with its 1:1 Person profile."""
    from app.models import Person, User

    user = User(
        tenant_id=tenant_id,
        access_code=email.lower(),
        email=email.lower(),
        password_hash=hash_password(password),
        active=active,
        is_master_admin=is_master_admin,
    )
    db.add(user)
    db.flush()
    person = Person(
        tenant_id=tenant_id,
        user_id=user.id,
        name=email.split("@")[0],
        email=email.lower(),
        active=True,
    )
    db.add(person)
    db.flush()
    user.person_id = person.id
    db.commit()
    db.refresh(user)
    return user


def make_tenant(db: Session, *, name: str, module_codes: list[str] | None = None):
    from app.models import Module, Tenant, TenantModule

    tenant = Tenant(social_reason=name, company_name=name, active=True)
    db.add(tenant)
    db.flush()
    for code in module_codes or []:
        module = db.execute(
            text("SELECT id FROM modules WHERE code = :c"), {"c": code}
        ).first()
        if module is None:
            continue
        db.add(TenantModule(tenant_id=tenant.id, module_id=module[0], active=True))
    db.commit()
    db.refresh(tenant)
    return tenant


def make_company(db: Session, *, tenant_id: uuid.UUID, name: str = "Empresa Teste"):
    from app.models import Company

    company = Company(tenant_id=tenant_id, company_name=name, active=True)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def make_unity(
    db: Session, *, tenant_id: uuid.UUID, company_id: uuid.UUID, name: str = "Filial 1"
):
    from app.models import Unity

    unity = Unity(
        tenant_id=tenant_id,
        company_id=company_id,
        name=name,
        matriz_type="FILIAL",
        active=True,
    )
    db.add(unity)
    db.commit()
    db.refresh(unity)
    return unity

def login(client: TestClient, email: str, password: str = "Password123!") -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assign_role(db: Session, user_id: uuid.UUID, role_code: str) -> None:
    from app.models import UserRole

    role = db.execute(
        text("SELECT id FROM roles WHERE code = :c"), {"c": role_code}
    ).first()
    assert role is not None, f"role {role_code} not found"
    db.add(UserRole(user_id=user_id, role_id=role[0]))
    db.commit()
