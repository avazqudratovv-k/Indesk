"""Fail runs that cannot finish on their own: the worker died, the job vanished, or it is too old.

- worker_lost: the run is past the grace period and its RQ job is gone or ended (not queued, not
  started). A run still waiting in the queue is NOT lost: a busy worker is not a dead one.
- run_timeout: any run still unfinished at the hard limit (queued: counted from creation; running:
  from its start). Also the answer when Redis cannot say what the job is doing.
Finishing goes through the same compare-and-set as the worker, so a run that finishes at the same
moment is left alone. Its uploads are freed by the finish itself: the sweep only protects
uploads of unfinished runs."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from redis import Redis
from redis.exceptions import RedisError
from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus
from sqlalchemy import select

from app.ai.caps import SessionFactory
from app.core.config import Limits
from app.core.enums import RunOutcome, RunReason, RunStatus
from app.db.models import Run
from app.runs import store
from app.runs.trace import stopped_line

logger = logging.getLogger("indesk.runs")

_ALIVE = frozenset({JobStatus.QUEUED, JobStatus.STARTED, JobStatus.DEFERRED, JobStatus.SCHEDULED})


@dataclass(frozen=True)
class ReapResult:
    failed: int
    checked: int


def job_alive(redis: Redis, run_id: uuid.UUID) -> bool | None:
    """True: queued, started or waiting. False: gone or ended. None: Redis could not say."""
    try:
        job = Job.fetch(str(run_id), connection=redis)
        return job.get_status(refresh=True) in _ALIVE
    except NoSuchJobError:
        return False
    except (RedisError, OSError):
        return None


def reap(
    session_factory: SessionFactory, redis: Redis, limits: Limits, now: datetime
) -> ReapResult:
    with session_factory() as db:
        stuck = list(
            db.execute(
                select(Run.id, Run.status, Run.created_at, Run.started_at).where(
                    Run.status != RunStatus.FINISHED
                )
            )
        )
    failed = 0
    for run_id, status, created_at, started_at in stuck:
        since = started_at if status == RunStatus.RUNNING and started_at else created_at
        reason: RunReason | None = None
        if (now - created_at).total_seconds() >= limits.reaper_gone_grace_seconds:
            if job_alive(redis, run_id) is False:
                reason = RunReason.WORKER_LOST
        if reason is None and (now - since).total_seconds() >= limits.run_hard_limit_seconds:
            reason = RunReason.RUN_TIMEOUT
        if reason is None:
            continue
        with session_factory() as db:
            done = store.finish_run(
                db, run_id, expected=RunStatus(status), outcome=RunOutcome.FAILED,
                reason=reason, final=stopped_line(reason), now=now,
            )  # fmt: skip
        if done:
            failed += 1
            logger.info("run %s reaped reason=%s", run_id, reason.value)
    return ReapResult(failed=failed, checked=len(stuck))
