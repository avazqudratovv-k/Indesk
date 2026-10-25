import os
from collections.abc import Iterator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from tests.db_helpers import alembic_config, recreate_database


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _require_services() -> None:
    assert os.environ.get("DATABASE_URL"), "run tests through docker compose (see api/README.md)"


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """A fresh `indesk_test` database with the schema made by `alembic upgrade head`."""
    url = recreate_database("indesk_test")
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(migrated_engine: Engine) -> Iterator[Session]:
    """A session rolled back after each test, so tests do not see each other's rows."""
    connection = migrated_engine.connect()
    outer = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db
    finally:
        db.close()
        outer.rollback()
        connection.close()
