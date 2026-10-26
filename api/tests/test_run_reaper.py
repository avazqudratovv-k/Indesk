"""The stuck-run reaper, and what the upload sweep does around it."""

import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from redis import Redis
from rq import Queue
from rq.job import JobStatus
from sqlalchemy import Connection, update
from sqlalchemy.orm import Session

from app.ai.caps import SessionFactory
from app.core import clock
from app.core.enums import RunOutcome, RunReason, RunStatus, UploadStatus
from app.db.models import Run, Upload
from app.jobs.scheduler import build_scheduler
from app.jobs.tasks import ping
from app.runs import reaper, store
from app.runs.trace import stopped_line
from app.services.uploads import sweep_expired_uploads
from app.storage import LocalDiskStorage
from tests.ai_helpers import factory_for, limits_with
from tests.conftest import _test_redis_url
from tests.runs_helpers import World, audit_rows, make_world, run_row, step_rows, upload_row

LIMITS = limits_with()  # grace 30 s, hard limit 300 s


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


@pytest.fixture
def redis() -> Redis:
    return Redis.from_url(_test_redis_url())


def start_job(redis: Redis, world: World, status: JobStatus | None = None) -> None:
    """A real RQ job with the run's id, in the state a worker would leave it in. No worker runs."""
    job = Queue("default", connection=redis).enqueue(ping, job_id=str(world.run_id))
    if status is not None:
        job.set_status(status)


def set_started(factory: SessionFactory, world: World, seconds_ago: float) -> None:
    with factory() as db:
        db.execute(
            update(Run)
            .where(Run.id == world.run_id)
            .values(started_at=clock.utcnow() - timedelta(seconds=seconds_ago))
        )
        db.commit()


def reap(factory: SessionFactory, redis: Redis) -> reaper.ReapResult:
    return reaper.reap(factory, redis, LIMITS, clock.utcnow())


def test_a_run_whose_job_vanished_is_failed_as_worker_lost(
    factory: SessionFactory, redis: Redis
) -> None:
    world = make_world(factory, status=RunStatus.RUNNING, created_ago=100)
    assert reap(factory, redis).failed == 1
    run = run_row(factory, world.run_id)
    assert (run.status, run.outcome, run.outcome_reason, run.counted) == (
        "finished", "failed", "worker_lost", False,
    )  # fmt: skip
    last = step_rows(factory, world.run_id)[-1]
    assert (last.key, last.args) == ("stopped", {"reason": "worker_lost"})
    [audit] = audit_rows(factory, "run_finished")
    assert audit.target == f"{world.run_id}:worker_lost"


def test_a_young_run_is_never_called_lost(factory: SessionFactory, redis: Redis) -> None:
    world = make_world(
        factory, status=RunStatus.QUEUED, created_ago=10
    )  # the job may not be enqueued yet
    assert reap(factory, redis) == reaper.ReapResult(failed=0, checked=1)
    assert run_row(factory, world.run_id).status == RunStatus.QUEUED


def test_a_queued_run_behind_a_busy_worker_is_not_killed_early(
    factory: SessionFactory, redis: Redis
) -> None:
    world = make_world(factory, status=RunStatus.QUEUED, created_ago=200)  # past the grace period
    start_job(redis, world)  # waiting in the queue: the worker is busy, not dead
    assert reap(factory, redis).failed == 0
    assert run_row(factory, world.run_id).status == RunStatus.QUEUED


def test_a_queued_run_is_killed_only_at_the_hard_limit(
    factory: SessionFactory, redis: Redis
) -> None:
    world = make_world(factory, status=RunStatus.QUEUED, created_ago=301)
    start_job(redis, world)
    assert reap(factory, redis).failed == 1
    run = run_row(factory, world.run_id)
    assert (run.outcome, run.outcome_reason) == ("failed", "run_timeout")


def test_a_running_run_is_measured_from_its_start_not_its_creation(
    factory: SessionFactory, redis: Redis
) -> None:
    world = make_world(factory, status=RunStatus.RUNNING, created_ago=400)
    set_started(factory, world, 100)  # waited 300 s in the queue, has run for 100 s
    start_job(redis, world, JobStatus.STARTED)
    assert reap(factory, redis).failed == 0
    set_started(factory, world, 301)
    assert reap(factory, redis).failed == 1
    assert run_row(factory, world.run_id).outcome_reason == "run_timeout"


@pytest.mark.parametrize(
    "status", [JobStatus.FAILED, JobStatus.FINISHED, JobStatus.STOPPED, JobStatus.CANCELED]
)
def test_a_job_that_ended_while_the_run_did_not_is_worker_lost(
    factory: SessionFactory, redis: Redis, status: JobStatus
) -> None:
    world = make_world(factory, status=RunStatus.RUNNING, created_ago=60)
    start_job(redis, world, status)
    assert reap(factory, redis).failed == 1
    assert run_row(factory, world.run_id).outcome_reason == "worker_lost"


@pytest.mark.parametrize(
    "status", [JobStatus.QUEUED, JobStatus.STARTED, JobStatus.DEFERRED, JobStatus.SCHEDULED]
)
def test_a_job_that_is_waiting_or_working_keeps_its_run(
    factory: SessionFactory, redis: Redis, status: JobStatus
) -> None:
    world = make_world(factory, status=RunStatus.RUNNING, created_ago=100)
    start_job(redis, world, status)
    assert reap(factory, redis).failed == 0
    assert run_row(factory, world.run_id).status == RunStatus.RUNNING


def test_when_redis_cannot_say_only_the_hard_limit_applies(
    factory: SessionFactory, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reaper, "job_alive", lambda r, run_id: None)
    young = make_world(factory, status=RunStatus.RUNNING, created_ago=100)
    old = make_world(factory, status=RunStatus.RUNNING, created_ago=301)
    assert reap(factory, redis).failed == 1
    assert run_row(factory, young.run_id).status == RunStatus.RUNNING
    assert run_row(factory, old.run_id).outcome_reason == "run_timeout"


def test_finished_runs_are_left_alone(factory: SessionFactory, redis: Redis) -> None:
    world = make_world(factory, status=RunStatus.FINISHED, created_ago=1000)
    assert reap(factory, redis) == reaper.ReapResult(failed=0, checked=0)
    assert run_row(factory, world.run_id).outcome == "answered"


def test_a_run_that_finishes_while_the_reaper_looks_is_not_overwritten(
    factory: SessionFactory, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker wins the race: the reaper's compare-and-set finds the run already finished."""
    world = make_world(factory, status=RunStatus.RUNNING, created_ago=100)

    def worker_finishes_first(_: Any, run_id: uuid.UUID) -> bool:
        with factory() as db:
            assert store.finish_run(
                db, run_id, expected=RunStatus.RUNNING, outcome=RunOutcome.ANSWERED, reason=None,
                final=stopped_line(RunReason.INTERNAL_ERROR), now=clock.utcnow(),
            )  # fmt: skip
        return False  # "the job is gone" - true, it just ended

    monkeypatch.setattr(reaper, "job_alive", worker_finishes_first)
    assert reap(factory, redis).failed == 0
    run = run_row(factory, world.run_id)
    assert (run.outcome, run.outcome_reason) == ("answered", None)
    assert len(step_rows(factory, world.run_id)) == 1  # one closing line, not two
    assert len(audit_rows(factory, "run_finished")) == 1


# ---- the upload sweep ----


def expire(db_connection: Connection, world: World, storage: LocalDiskStorage) -> str:
    key = storage.put(b"a,b\n1,2\n")
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db:
        db.execute(
            update(Upload)
            .where(Upload.id == world.upload_ids[0])
            .values(storage_key=key, expires_at=clock.utcnow() - timedelta(minutes=1))
        )
        db.commit()
    return key


def test_the_sweep_never_takes_the_upload_of_an_active_run_and_the_reaper_frees_it(
    factory: SessionFactory, redis: Redis, db_connection: Connection, tmp_path: Path
) -> None:
    storage = LocalDiskStorage(tmp_path / "uploads")
    world = make_world(factory, status=RunStatus.RUNNING, created_ago=100)
    key = expire(db_connection, world, storage)

    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db:
        during = sweep_expired_uploads(db, storage, clock.utcnow())
    assert (during.deleted, during.in_use) == (0, 1)  # waits while the run is active
    assert storage.get(key)

    assert reap(factory, redis).failed == 1  # no job: worker_lost, which frees the upload
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db:
        after = sweep_expired_uploads(db, storage, clock.utcnow())
    assert after.deleted == 1
    assert upload_row(factory, world.upload_ids[0]).status == UploadStatus.DELETED


def test_the_sweep_waits_for_a_queued_run_too(
    factory: SessionFactory, db_connection: Connection, tmp_path: Path
) -> None:
    storage = LocalDiskStorage(tmp_path / "uploads")
    world = make_world(factory, status=RunStatus.QUEUED)
    expire(db_connection, world, storage)
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db:
        result = sweep_expired_uploads(db, storage, clock.utcnow())
    assert (result.deleted, result.in_use) == (0, 1)


# ---- wiring and numbers ----


def test_the_scheduler_runs_the_reaper(redis: Redis) -> None:
    scheduler = build_scheduler(redis, 3600, 60)
    names = {job.name for job in scheduler.get_jobs()}
    assert {"upload-sweep", "run-reaper"} <= names


def test_the_time_limits_fit_together() -> None:
    lim = LIMITS
    # soft deadline + one 35 s model request must fit inside the job kill, which must fit inside
    # the reaper's hard limit, which must fit inside the longest stream.
    assert lim.run_timeout_seconds + 35 < lim.run_job_timeout_seconds
    assert lim.run_job_timeout_seconds < lim.run_hard_limit_seconds < lim.sse_max_seconds
    assert lim.reaper_gone_grace_seconds < lim.run_hard_limit_seconds
