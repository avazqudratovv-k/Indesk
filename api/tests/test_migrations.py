from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text

from app.db.base import Base
from tests.db_helpers import alembic_config, recreate_database

EXPECTED_TABLES = {
    "users",
    "refresh_tokens",
    "uploads",
    "runs",
    "run_files",
    "agent_steps",
    "evidence",
    "reports",
    "claims",
    "ai_calls",
    "usage_daily",
    "usage_events",
    "audit_log",
}
LATER_TABLES = {"subscriptions", "payments", "share_links", "chunks", "benchmark_runs"}


def tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_upgrade_downgrade_upgrade_on_an_empty_database() -> None:
    url = recreate_database("indesk_test_migrations")
    config = alembic_config(url)
    assert tables(url) == set()

    command.upgrade(config, "head")
    assert tables(url) == EXPECTED_TABLES

    command.downgrade(config, "base")
    assert tables(url) == set()

    command.upgrade(config, "head")
    assert tables(url) == EXPECTED_TABLES


def test_there_are_two_migrations_and_one_head() -> None:
    script = ScriptDirectory.from_config(alembic_config("postgresql+psycopg://unused/unused"))
    assert len(list(script.walk_revisions())) == 2
    assert script.get_heads() == ["0002"]


def test_later_tables_are_not_created_yet() -> None:
    assert not LATER_TABLES & set(Base.metadata.tables)
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_models_and_migration_agree(migrated_engine: Engine) -> None:
    """Autogenerate against the migrated database finds nothing left to do."""
    with migrated_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == []
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
