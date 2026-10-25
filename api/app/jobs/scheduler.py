"""Runs periodic jobs: enqueues them on the default queue and the worker does the work. Run exactly
one scheduler (compose service `scheduler`); two would enqueue every job twice."""

from redis import Redis
from rq.cron import CronScheduler

from app.core.config import get_settings
from app.jobs.sweep import run_sweep
from app.jobs.worker import QUEUE_NAME


def build_scheduler(connection: Redis, interval_seconds: int) -> CronScheduler:
    scheduler = CronScheduler(connection=connection, name="indesk-cron")
    scheduler.register(run_sweep, QUEUE_NAME, interval=interval_seconds, name="upload-sweep")
    return scheduler


def main() -> None:
    settings = get_settings()
    connection = Redis.from_url(settings.redis_url.get_secret_value())
    scheduler = build_scheduler(connection, settings.limits.sweep_interval_seconds)
    scheduler.start()  # type: ignore[no-untyped-call]  # rq 2.12 ships this method untyped


if __name__ == "__main__":
    main()
