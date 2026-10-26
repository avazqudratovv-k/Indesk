"""RQ entry points for runs. `execute_run` is what the worker runs; `reap_stuck_runs` is what the
scheduler enqueues every limits.reaper_interval_seconds."""

import logging
import uuid

from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.ai.gateway import build_gateway
from app.core import clock
from app.core.config import Settings, get_settings
from app.core.enums import RunMode
from app.db.session import get_engine
from app.jobs.worker import QUEUE_NAME
from app.runs.executor import RunDeps, run_job
from app.runs.reaper import reap
from app.runs.registry import select_flow
from app.sandbox_client import run_pandas
from app.storage import LocalDiskStorage

logger = logging.getLogger("indesk.runs")


def build_deps(settings: Settings | None = None) -> RunDeps:
    settings = settings or get_settings()
    engine = get_engine(settings.database_url.get_secret_value())

    def factory() -> Session:
        return Session(engine)

    return RunDeps(
        session_factory=factory,
        gateway=build_gateway(settings, factory),
        sandbox=run_pandas,
        limits=settings.limits,
        flow_factory=lambda mode: select_flow(settings, RunMode(mode)),
        storage=LocalDiskStorage(settings.storage_dir),
    )


def execute_run(run_id: str) -> None:
    """The RQ job. Never raises for a run problem: the run ends finished, whatever happened."""
    run_job(uuid.UUID(run_id), build_deps())


def enqueue_run(redis: Redis, run_id: uuid.UUID, job_timeout: int) -> None:
    # The job id is the run id: the reaper finds the job from the run. No retries (RQ's retry would
    # run the job twice); the reaper owns recovery.
    Queue(QUEUE_NAME, connection=redis).enqueue(
        execute_run, str(run_id), job_id=str(run_id), job_timeout=job_timeout,
        result_ttl=60, failure_ttl=3600,
    )  # fmt: skip


def reap_stuck_runs() -> int:
    settings = get_settings()
    engine = get_engine(settings.database_url.get_secret_value())
    redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=3)
    try:
        result = reap(lambda: Session(engine), redis, settings.limits, clock.utcnow())
    finally:
        redis.close()
    if result.failed:
        logger.info("run reaper: failed=%d", result.failed)
    return result.failed
