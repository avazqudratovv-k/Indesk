from redis import Redis
from rq import Queue

from app.core.config import Settings
from app.jobs.tasks import ping


def test_ping_job_runs_through_rq(settings: Settings) -> None:
    connection = Redis.from_url(settings.redis_url.get_secret_value())
    job = Queue("default", connection=connection, is_async=False).enqueue(ping)
    assert job.return_value() == "pong"
