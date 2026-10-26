import os
from collections.abc import Callable, Iterator
from urllib.parse import urlparse

import httpx
import pytest
from alembic import command
from fastapi.testclient import TestClient
from redis import Redis
from redis.connection import ConnectionPool
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
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


# ---- auth fixtures: real Postgres (rolled back per test) and a separate Redis database ----

TEST_AUTH_SECRET = "test-secret-" + "x" * 40
TEST_ORIGIN = "http://localhost:3000"


def _test_redis_url() -> str:
    """Tests use Redis database 15 so they never reset the rate limits of the dev database 0."""
    return os.environ["REDIS_URL"].rsplit("/", 1)[0] + f"/{TEST_REDIS_DB}"


TEST_REDIS_DB = 15


def redis_db_of(url: str) -> int:
    """The database number a Redis URL points at (no number means database 0)."""
    path = urlparse(url).path.strip("/")
    return int(path) if path.isdigit() else 0


def assert_redis_url_is_safe(url: str) -> None:
    if redis_db_of(url) != TEST_REDIS_DB:
        raise RuntimeError(
            f"tests may only use Redis database {TEST_REDIS_DB}, never the dev database 0"
        )


@pytest.fixture(scope="session", autouse=True)
def _redis_guard() -> Iterator[None]:
    """Fail the run at start if the test Redis URL is database 0, and refuse (loudly) any Redis
    connection pool a test creates for another database. A dev worker listens on database 0."""
    assert_redis_url_is_safe(_test_redis_url())
    original = ConnectionPool.__init__

    def guarded(self: ConnectionPool, *args: object, **kwargs: object) -> None:
        if kwargs.get("db", 0) != TEST_REDIS_DB:
            raise RuntimeError("a test tried to use a Redis database other than 15")
        original(self, *args, **kwargs)  # type: ignore[arg-type]

    patcher = pytest.MonkeyPatch()
    patcher.setattr(ConnectionPool, "__init__", guarded)
    yield
    patcher.undo()


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(app_env="test", auth_secret=TEST_AUTH_SECRET, redis_url=_test_redis_url())


@pytest.fixture(autouse=True)
def _clean_test_redis() -> Iterator[None]:
    redis = Redis.from_url(_test_redis_url())
    redis.flushdb()
    yield
    redis.flushdb()
    redis.close()


@pytest.fixture
def db_connection(migrated_engine: Engine) -> Iterator[Connection]:
    connection = migrated_engine.connect()
    outer = connection.begin()
    try:
        yield connection
    finally:
        outer.rollback()
        connection.close()


@pytest.fixture
def make_client(db_connection: Connection) -> Iterator[Callable[..., TestClient]]:
    """Build clients that talk to the app with the test database. A client keeps its own cookies."""
    opened: list[TestClient] = []

    def get_test_db() -> Iterator[Session]:
        with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db:
            yield db

    def build(
        settings: Settings,
        *,
        peer: tuple[str, int] = ("203.0.113.7", 50000),
        origin: str | None = TEST_ORIGIN,
    ) -> TestClient:
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_db] = get_test_db
        headers = {"Origin": origin} if origin else {}
        test_client = TestClient(app, raise_server_exceptions=False, client=peer, headers=headers)
        test_client.__enter__()
        opened.append(test_client)
        return test_client

    yield build
    for test_client in opened:
        test_client.__exit__(None, None, None)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(make_client: Callable[..., TestClient], auth_settings: Settings) -> TestClient:
    return make_client(auth_settings)


# ---- no real network from httpx, ever ----


@pytest.fixture(autouse=True)
def network_guard(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Block only httpx's REAL network transports. TestClient, MockTransport and urllib (the
    sandbox tests) are different classes and are not touched. A blocked call is recorded and the
    test fails at teardown even if the code under test swallowed the error."""
    blocked: list[str] = []

    def refuse(self: object, request: httpx.Request) -> httpx.Response:
        blocked.append(request.url.host)
        raise RuntimeError("real network call blocked by the test suite")

    async def refuse_async(self: object, request: httpx.Request) -> httpx.Response:
        blocked.append(request.url.host)
        raise RuntimeError("real network call blocked by the test suite")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse_async)
    yield blocked
    assert not blocked, f"a test tried a real network call to {blocked}"
