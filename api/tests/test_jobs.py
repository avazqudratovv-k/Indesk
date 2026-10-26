from redis import Redis
from rq import Queue

from app.jobs.tasks import ping
from tests.conftest import _test_redis_url


def test_ping_job_runs_through_rq() -> None:
    connection = Redis.from_url(_test_redis_url())
    job = Queue("default", connection=connection, is_async=False).enqueue(ping)
    assert job.return_value() == "pong"
