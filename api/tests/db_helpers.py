"""Test-database helpers. Tests never touch the dev database: they build their own from scratch."""

import os
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

API_ROOT = Path(__file__).resolve().parent.parent
# The only databases a test may drop and recreate. Anything else is refused.
TEST_DATABASES = frozenset({"indesk_test", "indesk_test_migrations", "indesk_test_roles"})


def admin_url() -> URL:
    """The superuser URL that may create databases. In compose the app runs as a limited role, so
    the dev override passes TEST_ADMIN_DATABASE_URL; CI and plain setups use DATABASE_URL itself."""
    return make_url(os.environ.get("TEST_ADMIN_DATABASE_URL") or os.environ["DATABASE_URL"])


def recreate_database(name: str, *, vector: bool = True) -> str:
    """Drop and create an empty test database; return its URL. With `vector` (the default) the
    pgvector extension is created as the superuser, as db-init does on a fresh volume; migration
    0005 needs it and a limited role cannot create it."""
    if name not in TEST_DATABASES:
        raise RuntimeError("refusing to recreate a database that is not a test database")
    base = admin_url()
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))  # noqa: S608
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()
    if vector:
        own = create_engine(base.set(database=name), isolation_level="AUTOCOMMIT")
        try:
            with own.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        finally:
            own.dispose()
    return base.set(database=name).render_as_string(hide_password=False)


def alembic_config(url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config
