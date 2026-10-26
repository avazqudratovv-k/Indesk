"""Real threads and committed rows: several starts at once must never admit more runs than a cap
allows, and must never leave a counter out of step with the runs that exist. Each test deletes
what it committed."""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Run, UsageDaily, UsageEvent, User
from tests import test_run_concurrency as base
from tests.ai_helpers import limits_with
from tests.test_run_concurrency import committed_user, race


@pytest.fixture
def engine_(migrated_engine: Engine) -> Iterator[Engine]:
    yield migrated_engine
    with Session(migrated_engine) as db, db.begin():
        users = db.scalars(select(User.id)).all()
        db.execute(delete(AuditLog).where(AuditLog.user_id.in_(users)))
        db.execute(delete(UsageDaily))
        db.execute(delete(UsageEvent))
        db.execute(delete(User))


def counters(engine: Engine) -> dict[str, int]:
    with Session(engine) as db:
        return {r.scope: r.runs for r in db.scalars(select(UsageDaily))}


def test_the_site_cap_admits_exactly_its_number_of_runs(
    engine_: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(base, "LIMITS", limits_with(daily_runs_global=2, free_runs=100))
    people = [committed_user(engine_) for _ in range(5)]
    waiting = list(people)  # list.pop is atomic, so each thread takes a different user

    def work() -> str:
        user_id, uploads = waiting.pop()
        return base.attempt(engine_, user_id, uploads[0], None)

    results = race(5, work)
    assert sorted(r.split(":")[0] for r in results) == ["DAILY_CAP_GLOBAL"] * 3 + ["new"] * 2
    with Session(engine_) as db:
        assert db.scalar(select(func.count()).select_from(Run)) == 2
    seen = counters(engine_)
    assert seen["global"] == 2
    assert sorted(v for k, v in seen.items() if k != "global") == [1, 1]  # refused users: no row


def test_two_starts_of_one_user_take_one_slot(
    engine_: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(base, "LIMITS", limits_with(free_runs=100))
    user_id, uploads = committed_user(engine_)
    results = race(2, lambda: base.attempt(engine_, user_id, uploads[0], None))
    assert sorted(r.split(":")[0] for r in results) == ["RUN_ACTIVE", "new"]
    seen = counters(engine_)
    assert seen == {"global": 1, f"user:{user_id}": 1}


def test_the_user_cap_holds_under_a_burst_of_one_users_starts(
    engine_: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(base, "LIMITS", limits_with(daily_runs_per_user=1, free_runs=100))
    user_id, uploads = committed_user(engine_)
    results = race(4, lambda: base.attempt(engine_, user_id, uploads[0], None))
    kinds = sorted(r.split(":")[0] for r in results)
    assert kinds.count("new") == 1 and set(kinds) <= {"new", "RUN_ACTIVE", "DAILY_CAP_USER"}
    assert counters(engine_)[f"user:{user_id}"] == 1
    assert uuid.UUID(next(r for r in results if r.startswith("new:")).split(":")[1])
