"""The run-level gates at POST /api/runs (free runs, daily run caps, a look at the call caps), the
counting of used runs, and the refund of the daily run slot. Real API, real Postgres, no model."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, select, update

from app.core import clock
from app.core.enums import Plan, RunOutcome, RunReason
from app.db.models import AgentStep, Run, UsageDaily, UsageEvent, User
from app.runs import quota
from tests.quota_helpers import Rig, make_rig_for
from tests.test_auth import MakeClient
from tests.test_runs_api import code, db_of

LOTS = 1000  # a limit high enough to never be the one under test


@pytest.fixture
def build(make_client: MakeClient, db_connection: Connection, tmp_path: Path) -> Callable[..., Rig]:
    def go(**limits: Any) -> Rig:
        return make_rig_for(make_client, db_connection, tmp_path, **limits)

    return go


# ---- free runs: used, not used ----


def test_two_free_runs_then_the_third_is_refused(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=2, daily_runs_per_user=LOTS, daily_runs_global=LOTS)
    rig.start_and_finish(RunOutcome.ANSWERED)
    rig.start_and_finish(RunOutcome.PARTIAL)
    before, queued = rig.snapshot(), len(rig.enqueued)
    code(rig.start(), 403, "QUOTA_EXHAUSTED")
    assert rig.snapshot() == before and len(rig.enqueued) == queued


@pytest.mark.parametrize(
    ("outcome", "reason", "uses_a_free_run"),
    [
        (RunOutcome.ANSWERED, None, True),
        (RunOutcome.PARTIAL, None, True),
        (RunOutcome.NOT_ANSWERABLE, None, False),
        (RunOutcome.NEEDS_BETTER_INPUT, None, False),
        (RunOutcome.REJECTED, RunReason.DAILY_CAP_USER, False),
        (RunOutcome.REJECTED, RunReason.DAILY_CAP_GLOBAL, False),
        (RunOutcome.FAILED, RunReason.MODEL_BUSY, False),
        (RunOutcome.FAILED, RunReason.INTERNAL_ERROR, False),
    ],
)
def test_only_answered_and_partial_runs_use_a_free_run(
    build: Callable[..., Rig],
    outcome: RunOutcome,
    reason: RunReason | None,
    uses_a_free_run: bool,
) -> None:
    rig = build(free_runs=1, daily_runs_per_user=LOTS, daily_runs_global=LOTS)
    run_id = rig.start_and_finish(outcome, reason)
    with db_of(rig.connection) as db:
        events = db.scalars(select(UsageEvent)).all()
        run = db.get(Run, uuid.UUID(run_id))
        assert run is not None and run.counted is uses_a_free_run
        assert len(events) == (1 if uses_a_free_run else 0)
        if events:
            assert (events[0].kind, events[0].amount, events[0].run_id) == (
                "run",
                1,
                run.id,
            )
    # With one free run in total, the next start works exactly when this one did not use it.
    again = rig.start()
    assert again.status_code == (403 if uses_a_free_run else 202)


def test_the_count_is_per_user(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=1, daily_runs_per_user=LOTS, daily_runs_global=LOTS)
    rig.start_and_finish(RunOutcome.ANSWERED)
    code(rig.start(), 403, "QUOTA_EXHAUSTED")
    assert rig.start(rig.bob).status_code == 202


def test_a_plan_other_than_free_skips_the_free_run_check(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=1, daily_runs_per_user=LOTS, daily_runs_global=LOTS)
    rig.start_and_finish(RunOutcome.ANSWERED)
    code(rig.start(), 403, "QUOTA_EXHAUSTED")
    with db_of(rig.connection) as db:
        db.execute(update(User).where(User.email == "alice@example.com").values(plan=Plan.PRO))
        db.commit()
    assert rig.start().status_code == 202  # a test user on a paid plan: no free-run limit


def test_the_free_run_count_comes_from_config(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=0, daily_runs_per_user=LOTS, daily_runs_global=LOTS)
    code(rig.start(), 403, "QUOTA_EXHAUSTED")


def test_a_second_event_for_one_run_is_ignored(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=5, daily_runs_per_user=LOTS, daily_runs_global=LOTS)
    run_id = uuid.UUID(rig.start_and_finish(RunOutcome.ANSWERED))
    with db_of(rig.connection) as db:
        owner = db.scalar(select(User.id))
        assert owner is not None
        quota.record_used_run(db, owner, run_id)
        quota.record_used_run(db, owner, run_id)
        db.commit()
        assert len(db.scalars(select(UsageEvent)).all()) == 1


# ---- the daily run caps ----


def test_the_daily_user_cap_refuses_the_next_run(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=2, daily_runs_global=LOTS)
    rig.start_and_finish(RunOutcome.ANSWERED)
    rig.start_and_finish(RunOutcome.ANSWERED)
    before, queued = rig.snapshot(), len(rig.enqueued)
    code(rig.start(), 429, "DAILY_CAP_USER")
    assert rig.snapshot() == before and len(rig.enqueued) == queued
    assert rig.counter(rig.user_scope()) == 2
    assert rig.start(rig.bob).status_code == 202  # another user is not affected


def test_the_daily_site_cap_refuses_and_takes_nothing_from_the_user(
    build: Callable[..., Rig],
) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=LOTS, daily_runs_global=1)
    rig.start_and_finish(RunOutcome.ANSWERED)
    before, queued = rig.snapshot(), len(rig.enqueued)
    code(rig.start(rig.bob), 429, "DAILY_CAP_GLOBAL")
    # Bob's own slot was taken a moment before the site refused: it must have been rolled back.
    assert rig.snapshot() == before and len(rig.enqueued) == queued
    assert rig.counter(rig.user_scope(rig.bob)) == 0
    assert rig.counter("global") == 1


@pytest.mark.parametrize(
    ("scope", "expected"), [("user", "DAILY_CAP_USER"), ("global", "DAILY_CAP_GLOBAL")]
)
def test_a_call_cap_already_reached_refuses_before_the_run_exists(
    build: Callable[..., Rig], scope: str, expected: str
) -> None:
    rig = build(
        free_runs=LOTS,
        daily_runs_per_user=LOTS,
        daily_runs_global=LOTS,
        daily_calls_per_user=5,
        daily_calls_global=7,
    )
    uid = rig.user_id()
    with db_of(rig.connection) as db:
        if scope == "user":
            db.add(
                UsageDaily(day=clock.quota_day(), scope=f"user:{uid}", user_id=uid, model_calls=5)
            )
        else:
            db.add(UsageDaily(day=clock.quota_day(), scope="global", user_id=None, model_calls=7))
        db.commit()
    before, queued = rig.snapshot(), len(rig.enqueued)
    code(rig.start(), 429, expected)
    assert rig.snapshot() == before and len(rig.enqueued) == queued


def test_a_call_cap_not_yet_reached_lets_the_run_in(build: Callable[..., Rig]) -> None:
    rig = build(
        free_runs=LOTS, daily_runs_per_user=LOTS, daily_runs_global=LOTS, daily_calls_per_user=5
    )
    uid = rig.user_id()
    with db_of(rig.connection) as db:
        db.add(UsageDaily(day=clock.quota_day(), scope=f"user:{uid}", user_id=uid, model_calls=4))
        db.commit()
    assert rig.start().status_code == 202


# ---- order of the gates ----


def test_an_active_run_is_reported_before_any_quota_gate(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=0, daily_runs_per_user=LOTS, daily_runs_global=LOTS)
    with db_of(rig.connection) as db:
        db.execute(update(User).values(plan=Plan.PRO))  # lets the first start through
        db.commit()
    rig.start_ok()
    with db_of(rig.connection) as db:
        db.execute(update(User).values(plan=Plan.FREE))
        db.commit()
    code(rig.start(), 409, "RUN_ACTIVE")


def test_free_runs_are_checked_before_the_daily_caps(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=0, daily_runs_per_user=1, daily_runs_global=1)
    code(rig.start(), 403, "QUOTA_EXHAUSTED")


def test_the_user_cap_is_checked_before_the_site_cap(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=1, daily_runs_global=1)
    rig.start_and_finish(RunOutcome.ANSWERED)
    code(rig.start(), 429, "DAILY_CAP_USER")


def test_a_replayed_idempotent_request_takes_no_second_slot(build: Callable[..., Rig]) -> None:
    from tests.test_runs_api import body, new_upload  # noqa: PLC0415

    rig = build(free_runs=LOTS, daily_runs_per_user=1, daily_runs_global=LOTS)
    upload = new_upload(rig.alice)
    headers = {"Idempotency-Key": "quota-replay-12345"}
    first = rig.alice.post("/api/runs", json=body(upload), headers=headers)
    second = rig.alice.post("/api/runs", json=body(upload), headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert rig.counter(rig.user_scope()) == 1


# ---- the refund ----


def test_the_slot_is_taken_at_admission(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=5, daily_runs_global=LOTS)
    rig.start_ok()
    assert (rig.counter(rig.user_scope()), rig.counter("global")) == (1, 1)


@pytest.mark.parametrize(
    ("outcome", "reason", "given_back"),
    [
        (RunOutcome.REJECTED, RunReason.DAILY_CAP_USER, True),
        (RunOutcome.REJECTED, RunReason.DAILY_CAP_GLOBAL, True),
        (RunOutcome.FAILED, RunReason.MODEL_BUSY, True),
        (RunOutcome.FAILED, RunReason.MODEL_UNAVAILABLE, False),
        (RunOutcome.FAILED, RunReason.ANALYSIS_FAILED, False),
        (RunOutcome.ANSWERED, None, False),
        (RunOutcome.PARTIAL, None, False),
    ],
)
def test_busy_and_capped_runs_give_their_daily_slot_back(
    build: Callable[..., Rig], outcome: RunOutcome, reason: RunReason | None, given_back: bool
) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=5, daily_runs_global=LOTS)
    rig.start_and_finish(outcome, reason)
    expected = 0 if given_back else 1
    assert (rig.counter(rig.user_scope()), rig.counter("global")) == (expected, expected)


def test_a_user_at_the_cap_can_start_again_after_a_busy_run(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=1, daily_runs_global=LOTS)
    rig.start_and_finish(RunOutcome.FAILED, RunReason.MODEL_BUSY)
    assert rig.start().status_code == 202


def test_the_refund_is_in_the_same_transaction_as_the_closing_line(
    build: Callable[..., Rig], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=5, daily_runs_global=LOTS)
    run_id = rig.start_ok()

    def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("the refund failed")

    monkeypatch.setattr(quota, "release_run", broken)
    with pytest.raises(RuntimeError):
        rig.finish(run_id, RunOutcome.REJECTED, RunReason.DAILY_CAP_USER)
    # Nothing of the finish stayed: the run is still running, no closing line, the slot is held.
    with db_of(rig.connection) as db:
        run = db.get(Run, uuid.UUID(run_id))
        assert run is not None and (run.status, run.outcome) == ("running", None)
        assert db.scalars(select(AgentStep).where(AgentStep.run_id == run.id)).all() == []
    assert rig.counter(rig.user_scope()) == 1


def test_a_finish_that_loses_the_race_refunds_nothing(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=5, daily_runs_global=LOTS)
    run_id = rig.start_and_finish(RunOutcome.FAILED, RunReason.MODEL_BUSY)
    assert rig.counter("global") == 0
    with db_of(rig.connection) as db:
        from app.core.enums import RunStatus  # noqa: PLC0415
        from app.runs import store  # noqa: PLC0415

        again = store.finish_run(
            db,
            uuid.UUID(run_id),
            expected=RunStatus.RUNNING,
            outcome=RunOutcome.REJECTED,
            reason=RunReason.DAILY_CAP_USER,
            final=None,
            now=clock.utcnow(),
        )
        assert again is False
    assert rig.counter("global") == 0  # not driven below zero by a second finish


def test_the_counter_never_goes_below_zero(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=5, daily_runs_global=LOTS)
    uid, day = rig.user_id(), clock.quota_day()
    with db_of(rig.connection) as db:
        db.add(UsageDaily(day=day, scope=f"user:{uid}", user_id=uid, runs=0))
        db.add(UsageDaily(day=day, scope="global", user_id=None, runs=0))
        db.commit()
        for _ in range(3):
            quota.release_run(db, user_id=uid, day=day)
        db.commit()
    assert (rig.counter(rig.user_scope()), rig.counter("global")) == (0, 0)
    # A run that was never counted (no row at all) is fine too, and creates no row.
    with db_of(rig.connection) as db:
        quota.release_run(db, user_id=uuid.uuid4(), day=day - timedelta(days=30))
        db.commit()
        assert len(db.scalars(select(UsageDaily)).all()) == 2


def test_a_second_refund_for_one_slot_stops_at_zero(build: Callable[..., Rig]) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=5, daily_runs_global=LOTS)
    rig.start_ok()
    uid = rig.user_id()
    with db_of(rig.connection) as db:
        for _ in range(2):
            quota.release_run(db, user_id=uid, day=clock.quota_day())
        db.commit()
    assert (rig.counter(rig.user_scope()), rig.counter("global")) == (0, 0)


# ---- the UTC day ----


def test_a_new_utc_day_starts_new_counters(
    build: Callable[..., Rig], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=1, daily_runs_global=LOTS)
    now = datetime(2026, 10, 27, 23, 59, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "utcnow", lambda: now)
    rig.start_and_finish(RunOutcome.ANSWERED)
    code(rig.start(), 429, "DAILY_CAP_USER")
    monkeypatch.setattr(clock, "utcnow", lambda: now + timedelta(minutes=2))  # past midnight UTC
    assert rig.start().status_code == 202
    assert rig.counter(rig.user_scope(), now.date()) == 1
    assert rig.counter(rig.user_scope(), now.date() + timedelta(days=1)) == 1


def test_the_refund_goes_to_the_day_the_slot_was_taken(
    build: Callable[..., Rig], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = build(free_runs=LOTS, daily_runs_per_user=5, daily_runs_global=LOTS)
    start = datetime(2026, 10, 27, 23, 59, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "utcnow", lambda: start)
    run_id = rig.start_ok()
    monkeypatch.setattr(clock, "utcnow", lambda: start + timedelta(minutes=3))  # next UTC day
    rig.finish(run_id, RunOutcome.FAILED, RunReason.MODEL_BUSY)
    scope = rig.user_scope()
    assert rig.counter(scope, start.date()) == 0
    assert rig.counter(scope, start.date() + timedelta(days=1)) == 0  # no row, no minus one
    with db_of(rig.connection) as db:
        assert len(db.scalars(select(UsageDaily).where(UsageDaily.runs < 0)).all()) == 0


def test_quota_day_is_the_utc_date() -> None:
    kst = datetime(2026, 10, 28, 8, 30, tzinfo=UTC).astimezone(UTC)
    assert clock.quota_day(kst) == datetime(2026, 10, 28).date()
    late = datetime(2026, 10, 27, 23, 59, 59, tzinfo=UTC)
    assert clock.quota_day(late).isoformat() == "2026-10-27"
