"""Real transactions and real threads (committed rows, one connection per thread): the places where
a shared test connection would hide a race. Each test deletes what it committed."""

import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from redis import Redis
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.enums import AgentKey, RunOutcome, RunReason, RunStatus, StepState, TraceKey
from app.core.errors import AppError
from app.db.models import AuditLog, Run, User
from app.runs import sse, store
from app.runs.store import RunGone
from app.runs.trace import stopped_line
from app.schemas.runs import RunCreate
from app.services.runs import create_run
from tests.ai_helpers import limits_with
from tests.conftest import _test_redis_url
from tests.factories import make_run, make_upload, make_user
from tests.runs_helpers import line

LIMITS = limits_with()


@pytest.fixture
def engine_(migrated_engine: Engine) -> Iterator[Engine]:
    yield migrated_engine
    with Session(migrated_engine) as db, db.begin():
        users = db.scalars(select(User.id)).all()
        db.execute(delete(AuditLog).where(AuditLog.user_id.in_(users)))
        db.execute(delete(User))


def committed_user(engine: Engine, uploads: int = 1) -> tuple[uuid.UUID, list[uuid.UUID]]:
    with Session(engine) as db, db.begin():
        user = make_user(db)
        ups = [
            make_upload(db, user, status="ready", storage_key=f"k/{uuid.uuid4()}",
                        expires_at=clock.utcnow() + timedelta(hours=1))
            for _ in range(uploads)
        ]  # fmt: skip
        return user.id, [u.id for u in ups]


def request_for(upload_id: uuid.UUID) -> RunCreate:
    return RunCreate.model_validate(
        {
            "mode": "ask",
            "question": "Q",
            "files": [{"upload_id": str(upload_id), "role": "subject"}],
        }
    )


def attempt(engine: Engine, user_id: uuid.UUID, upload_id: uuid.UUID, key: str | None) -> str:
    redis = Redis.from_url(_test_redis_url())
    with Session(engine) as db:
        user = db.get(User, user_id)
        assert user is not None
        try:
            run, created = create_run(
                db, redis, LIMITS, user, request_for(upload_id), idempotency_key=key, ip_hash="h"
            )
        except AppError as error:
            return error.code.value
        return f"{'new' if created else 'replay'}:{run.id}"


def race(count: int, work: Callable[[], str]) -> list[str]:
    barrier = threading.Barrier(count)
    results: list[str] = []
    errors: list[BaseException] = []

    def go() -> None:
        try:
            barrier.wait(timeout=10)
            results.append(work())
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=go) for _ in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors, errors
    assert len(results) == count
    return results


def run_count(engine: Engine) -> int:
    with Session(engine) as db:
        return int(db.scalar(select(func.count()).select_from(Run)) or 0)


# ---- one active run: two concurrent POSTs, exactly one wins ----


def test_two_concurrent_posts_exactly_one_wins(engine_: Engine) -> None:
    user_id, [upload_id] = committed_user(engine_)
    results = race(2, lambda: attempt(engine_, user_id, upload_id, None))
    assert sorted(r.split(":")[0] for r in results) == ["RUN_ACTIVE", "new"]
    assert run_count(engine_) == 1


def test_many_concurrent_posts_exactly_one_wins(engine_: Engine) -> None:
    user_id, [upload_id] = committed_user(engine_)
    results = race(8, lambda: attempt(engine_, user_id, upload_id, None))
    assert [r.split(":")[0] for r in results].count("new") == 1
    assert [r for r in results if not r.startswith("new")] == ["RUN_ACTIVE"] * 7
    assert run_count(engine_) == 1


def test_the_unique_index_alone_also_stops_a_second_run(
    engine_: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the advisory lock and the active-run query switched off, the database still refuses
    the second run (migration 0002) and the service maps that to RUN_ACTIVE."""
    monkeypatch.setattr(store, "lock_user_runs", lambda db, user_id: None)
    monkeypatch.setattr(store, "active_run", lambda db, user_id: None)
    user_id, [upload_id] = committed_user(engine_)
    results = race(4, lambda: attempt(engine_, user_id, upload_id, None))
    assert [r.split(":")[0] for r in results].count("new") == 1
    assert [r for r in results if not r.startswith("new")] == ["RUN_ACTIVE"] * 3
    assert run_count(engine_) == 1


def test_concurrent_posts_with_one_idempotency_key_make_one_run(engine_: Engine) -> None:
    user_id, [upload_id] = committed_user(engine_)
    results = race(6, lambda: attempt(engine_, user_id, upload_id, "same-click-key-1"))
    kinds = [r.split(":")[0] for r in results]
    assert kinds.count("new") == 1 and kinds.count("replay") == 5
    assert len({r.split(":")[1] for r in results}) == 1  # everyone got the same run id
    assert run_count(engine_) == 1


def test_users_do_not_block_each_other(engine_: Engine) -> None:
    pairs = [committed_user(engine_) for _ in range(4)]
    barrier = threading.Barrier(len(pairs))
    results: list[str] = []

    def go(pair: tuple[uuid.UUID, list[uuid.UUID]]) -> None:
        barrier.wait(timeout=10)
        results.append(attempt(engine_, pair[0], pair[1][0], None))

    threads = [threading.Thread(target=go, args=(p,)) for p in pairs]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert [r.split(":")[0] for r in results] == ["new"] * 4


# ---- the reaper race: `done` can never overtake the last line ----


def running_run(engine: Engine, events: int = 2) -> uuid.UUID:
    with Session(engine) as db, db.begin():
        user = make_user(db)
        run = make_run(db, user, status=RunStatus.RUNNING, started_at=clock.utcnow())
        run_id = run.id
    for _ in range(events):
        with Session(engine) as db:
            store.append_event(
                db, run_id, line(AgentKey.MANAGER, StepState.RUNNING, TraceKey.PLAN),
                attempt=1, payload=None, now=clock.utcnow(),
            )  # fmt: skip
    return run_id


CLOSING = {"ready", "stopped"}


def one_round(engine_: Engine) -> None:
    run_id = running_run(engine_)
    barrier = threading.Barrier(4)
    won: dict[str, bool] = {}
    problems: list[str] = []
    stop = threading.Event()

    def worker_finishes() -> None:
        barrier.wait(timeout=10)
        with Session(engine_) as db:
            won["worker"] = store.finish_run(
                db, run_id, expected=RunStatus.RUNNING, outcome=RunOutcome.ANSWERED, reason=None,
                final=line(AgentKey.MANAGER, StepState.DONE, TraceKey.READY), now=clock.utcnow(),
            )  # fmt: skip

    def reaper_finishes() -> None:
        barrier.wait(timeout=10)
        with Session(engine_) as db:
            won["reaper"] = store.finish_run(
                db, run_id, expected=RunStatus.RUNNING, outcome=RunOutcome.FAILED,
                reason=RunReason.WORKER_LOST, final=stopped_line(RunReason.WORKER_LOST),
                now=clock.utcnow(),
            )  # fmt: skip

    def worker_keeps_writing() -> None:
        barrier.wait(timeout=10)
        for _ in range(40):
            with Session(engine_) as db:
                try:
                    store.append_event(
                        db, run_id, line(AgentKey.DATA, StepState.RUNNING, TraceKey.READ_CSV),
                        attempt=1, payload=None, now=clock.utcnow(),
                    )  # fmt: skip
                except RunGone:
                    return  # the run was closed under us: refused, as it must be

    def observer() -> None:
        """What an SSE stream does: status first, then the lines. Whenever it sees
        `finished`, the last line it reads must be the closing line."""
        barrier.wait(timeout=10)
        while not stop.is_set():
            snap = sse.read_snapshot(lambda: Session(engine_), run_id, 0)
            if snap.finished:
                if not snap.events or snap.events[-1].key not in CLOSING:
                    problems.append("finished seen before the closing line")
                return

    threads = [
        threading.Thread(target=f)
        for f in (worker_finishes, reaper_finishes, worker_keeps_writing, observer)
    ]
    for t in threads:
        t.start()
    for t in threads[:3]:
        t.join(timeout=30)
    stop.set()
    threads[3].join(timeout=30)

    assert not problems, problems
    assert sorted(won.values()) == [False, True]  # exactly one finisher
    with Session(engine_) as db:
        run = db.get(Run, run_id)
        assert run is not None and run.status == RunStatus.FINISHED
        steps = sse.read_snapshot(lambda: Session(engine_), run_id, 0).events
    closing = [s for s in steps if s.key in CLOSING]
    assert len(closing) == 1 and steps[-1].key in CLOSING  # nothing after the closing line
    assert [s.seq for s in steps] == list(range(1, len(steps) + 1))  # no gap, no duplicate
    winner = "worker" if won["worker"] else "reaper"
    assert (run.outcome, steps[-1].key) == (
        ("answered", "ready") if winner == "worker" else ("failed", "stopped")
    )


def test_worker_and_reaper_race_exactly_one_closes_the_run_and_done_never_overtakes(
    engine_: Engine,
) -> None:
    for _ in range(25):
        one_round(engine_)


def test_no_line_can_be_written_after_the_run_is_finished(engine_: Engine) -> None:
    run_id = running_run(engine_, events=1)
    with Session(engine_) as db:
        assert store.finish_run(
            db, run_id, expected=RunStatus.RUNNING, outcome=RunOutcome.FAILED,
            reason=RunReason.RUN_TIMEOUT,
            final=stopped_line(RunReason.RUN_TIMEOUT), now=clock.utcnow(),
        )  # fmt: skip
    with Session(engine_) as db, pytest.raises(RunGone):
        store.append_event(
            db, run_id, line(AgentKey.DATA, StepState.RUNNING, TraceKey.READ_CSV),
            attempt=1, payload=None, now=clock.utcnow(),
        )  # fmt: skip
    with Session(engine_) as db:
        assert store.finish_run(
            db, run_id, expected=RunStatus.RUNNING, outcome=RunOutcome.ANSWERED, reason=None,
            final=None, now=clock.utcnow(),
        ) is False  # fmt: skip
