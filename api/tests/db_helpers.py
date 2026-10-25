"""Test-database helpers. Tests never touch the dev database: they build their own from scratch."""

import os
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

API_ROOT = Path(__file__).resolve().parent.parent
# The only databases a test may drop and recreate. Anything else is refused.
TEST_DATABASES = frozenset({"indesk_test", "indesk_test_migrations"})


def recreate_database(name: str) -> str:
    """Drop and create an empty test database; return its URL."""
    if name not in TEST_DATABASES:
        raise RuntimeError("refusing to recreate a database that is not a test database")
    base = make_url(os.environ["DATABASE_URL"])
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))  # noqa: S608
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()
    return base.set(database=name).render_as_string(hide_password=False)


def alembic_config(url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config
