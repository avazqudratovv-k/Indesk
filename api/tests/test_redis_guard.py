"""The guard in conftest.py keeps tests off the dev Redis (database 0: the dev worker is there)."""

import os

import pytest
from redis import Redis

from tests.conftest import assert_redis_url_is_safe, redis_db_of


@pytest.mark.parametrize(
    "url",
    ["redis://redis:6379/0", "redis://redis:6379", "redis://redis:6379/", "redis://redis:6379/3"],
)
def test_the_start_check_refuses_anything_but_database_15(url: str) -> None:
    with pytest.raises(RuntimeError):
        assert_redis_url_is_safe(url)
    assert_redis_url_is_safe("redis://redis:6379/15")


def test_creating_a_client_for_database_0_trips_the_guard() -> None:
    dev_url = os.environ["REDIS_URL"]
    assert redis_db_of(dev_url) == 0  # the configured dev URL really is database 0
    with pytest.raises(RuntimeError):
        Redis.from_url(dev_url)
    with pytest.raises(RuntimeError):
        Redis(host="redis")  # no db given means database 0


def test_database_15_is_allowed() -> None:
    Redis.from_url(os.environ["REDIS_URL"].rsplit("/", 1)[0] + "/15").close()
