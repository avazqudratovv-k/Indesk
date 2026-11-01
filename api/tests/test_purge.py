"""The daily purge (services/purge.py) against real Postgres: what it removes, what it must never
touch, batches, idempotence, and the scheduler wiring."""

import logging
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Limits
from app.core.enums import RunOutcome, RunStatus
from app.db.models import (
    AgentStep,
    AiCall,
    AuditLog,
    Claim,
    EmailToken,
    Evidence,
    Report,
    Run,
    RunFile,
    Upload,
    UsageDaily,
    UsageEvent,
    User,
)
from app.jobs.purge import purge_expired_job
from app.jobs.scheduler import PURGE_INTERVAL_SECONDS, build_scheduler
from app.services.purge import purge_expired
from app.storage import LocalDiskStorage, StorageError
from tests.ai_helpers import limits_with
from tests.conftest import _test_redis_url
from tests.factories import (
    NOW,
    add,
    make_claim,
    make_email_token,
    make_evidence,
    make_report,
    make_run,
    make_run_file,
    make_step,
    make_upload,
    make_user,
)

LIMITS = limits_with(purge_batch=2)


@pytest.fixture
def redis() -> Redis:
    return Redis.from_url(_test_redis_url())


@pytest.fixture
def storage(tmp_path: Path) -> LocalDiskStorage:
    return LocalDiskStorage(tmp_path / "files")


def finished_run(session: Session, user: User, *, ago: timedelta, **kw: object) -> Run:
    return make_run(
        session,
        user,
        status=RunStatus.FINISHED,
        outcome=RunOutcome.ANSWERED,
        finished_at=NOW - ago,
        **kw,
    )


def run_ids(session: Session) -> set[object]:
    return set(session.scalars(select(Run.id)))


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_removes_only_expired_reports_and_their_children(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    gone = finished_run(session, user, ago=timedelta(days=40))
    step = make_step(session, gone)
    report = make_report(session, gone, expires_at=NOW - timedelta(seconds=1))
    make_claim(session, report)
    make_evidence(session, gone, step)
    edge = finished_run(session, user, ago=timedelta(days=1))
    make_report(session, edge, expires_at=NOW)  # expires_at <= now is expired
    kept = finished_run(session, user, ago=timedelta(days=1))
    make_report(session, kept, expires_at=NOW + timedelta(days=1))

    done = purge_expired(session, storage, LIMITS, NOW)

    assert done.expired_runs == 2
    assert run_ids(session) == {kept.id}
    assert count(session, Report) == 1
    assert count(session, Claim) == 0 and count(session, Evidence) == 0
    assert count(session, AgentStep) == 0


def test_runs_in_batches_until_nothing_is_left(
    session: Session, storage: LocalDiskStorage, caplog: pytest.LogCaptureFixture
) -> None:
    for _ in range(5):  # purge_batch is 2: three passes with rows, then one empty pass
        run = finished_run(session, make_user(session), ago=timedelta(days=2))
        make_report(session, run, expires_at=NOW - timedelta(days=1))
    caplog.set_level(logging.INFO, logger="indesk.purge")

    done = purge_expired(session, storage, LIMITS, NOW)

    assert done.expired_runs == 5 and count(session, Run) == 0
    lines = [r.getMessage() for r in caplog.records if r.name == "indesk.purge"]
    assert len(lines) == 4
    assert lines[0].startswith("purge pass: expired_runs=2 ")
    assert lines[-1] == (
        "purge pass: expired_runs=0 old_no_report_runs=0 ai_calls=0 email_tokens=0 pdf_failed=0"
    )


def test_old_finished_runs_without_a_report_go_after_the_limit(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    old = finished_run(session, user, ago=timedelta(days=31))
    edge = finished_run(session, user, ago=timedelta(days=30))  # not "more than" 30 days
    young = finished_run(session, user, ago=timedelta(days=5))
    old_with_report = finished_run(session, user, ago=timedelta(days=60))
    make_report(session, old_with_report, expires_at=NOW + timedelta(days=10))
    old_id, edge_id, young_id, report_id = old.id, edge.id, young.id, old_with_report.id

    done = purge_expired(session, storage, LIMITS, NOW)

    assert done.old_no_report_runs == 1
    assert old_id not in run_ids(session)
    assert run_ids(session) == {edge_id, young_id, report_id}


def test_active_runs_are_never_deleted(session: Session, storage: LocalDiskStorage) -> None:
    queued = make_run(session, make_user(session), created_at=NOW - timedelta(days=90))
    running = make_run(
        session,
        make_user(session),
        status=RunStatus.RUNNING,
        started_at=NOW - timedelta(days=90),
        created_at=NOW - timedelta(days=90),
    )
    # Even with an expired report row, a run that is not finished stays.
    make_report(session, running, expires_at=NOW - timedelta(days=1))

    done = purge_expired(session, storage, LIMITS, NOW)

    assert done.total == 0
    assert run_ids(session) == {queued.id, running.id}


def test_keeps_usage_events_usage_daily_uploads_users_and_audit_log(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    upload = make_upload(session, user)
    run = finished_run(session, user, ago=timedelta(days=40), counted=True)
    make_run_file(session, run, upload)
    make_report(session, run, expires_at=NOW - timedelta(days=1))
    add(session, UsageEvent(user_id=user.id, run_id=run.id, kind="run", amount=1))
    add(session, UsageDaily(day=NOW.date(), scope=f"user:{user.id}", user_id=user.id, runs=3))
    add(session, AuditLog(user_id=user.id, action="run_created", target=str(run.id)))
    free_before = count(session, UsageEvent)

    purge_expired(session, storage, LIMITS, NOW)

    assert count(session, Run) == 0 and count(session, RunFile) == 0
    event = session.scalars(select(UsageEvent)).one()
    assert event.run_id is None and event.user_id == user.id  # the free-run count is unchanged
    assert count(session, UsageEvent) == free_before
    assert session.scalars(select(UsageDaily)).one().runs == 3
    assert count(session, Upload) == 1 and count(session, User) == 1
    assert count(session, AuditLog) == 1


def test_ai_calls_older_than_the_retention_go(session: Session, storage: LocalDiskStorage) -> None:
    user = make_user(session)

    def call(age: timedelta) -> AiCall:
        return add(
            session,
            AiCall(
                user_id=user.id,
                purpose="plan",
                model="m",
                attempt=1,
                status="ok",
                est_cost_usd=Decimal(0),
                created_at=NOW - age,
            ),
        )

    call(timedelta(days=91))
    call(timedelta(days=100))
    call(timedelta(days=95))
    edge = call(timedelta(days=90))
    fresh = call(timedelta(days=1))

    done = purge_expired(session, storage, LIMITS, NOW)

    assert done.ai_calls == 3
    assert set(session.scalars(select(AiCall.id))) == {edge.id, fresh.id}


def test_used_or_expired_email_tokens_go_after_seven_days(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    week = timedelta(days=7)
    gone = [
        make_email_token(session, user, expires_at=NOW - week - timedelta(seconds=1)),  # expired
        make_email_token(
            session,
            user,
            purpose="verify",
            expires_at=NOW + timedelta(days=1),  # still valid, but used long ago
            used_at=NOW - week - timedelta(seconds=1),
        ),
    ]
    kept = [
        make_email_token(session, user, expires_at=NOW - week),  # exactly 7 days: kept
        make_email_token(session, user, expires_at=NOW + timedelta(minutes=5)),  # live
        make_email_token(
            session, user, expires_at=NOW + timedelta(days=1), used_at=NOW - timedelta(days=2)
        ),  # used recently
    ]

    done = purge_expired(session, storage, LIMITS, NOW)

    assert done.email_tokens == len(gone)
    assert set(session.scalars(select(EmailToken.id))) == {t.id for t in kept}
    assert count(session, User) == 1  # the user is never touched


def test_is_idempotent(session: Session, storage: LocalDiskStorage) -> None:
    run = finished_run(session, make_user(session), ago=timedelta(days=40))
    make_report(session, run, expires_at=NOW - timedelta(days=1))

    assert purge_expired(session, storage, LIMITS, NOW).total == 1
    assert purge_expired(session, storage, LIMITS, NOW).total == 0


def test_removes_the_pdf_best_effort(
    session: Session, storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(session)
    key = storage.put(b"%PDF-1.4")
    run = finished_run(session, user, ago=timedelta(days=2))
    make_report(session, run, expires_at=NOW - timedelta(days=1), pdf_key=key)
    bad = finished_run(session, user, ago=timedelta(days=2))
    make_report(session, bad, expires_at=NOW - timedelta(days=1), pdf_key="not-a-key")

    done = purge_expired(session, storage, LIMITS, NOW)

    assert done.expired_runs == 2 and done.pdf_failed == 1  # a bad key never fails the pass
    with pytest.raises(StorageError):
        storage.get(key)


def test_a_storage_error_does_not_fail_the_pass(session: Session) -> None:
    class Broken:
        def delete(self, key: str) -> None:
            raise OSError("disk")

    run = finished_run(session, make_user(session), ago=timedelta(days=2))
    make_report(session, run, expires_at=NOW - timedelta(days=1), pdf_key="a" * 32)

    done = purge_expired(session, Broken(), LIMITS, NOW)  # type: ignore[arg-type]

    assert (done.expired_runs, done.pdf_failed) == (1, 1)


def test_the_new_keys_are_required_and_drift_is_rejected() -> None:
    from app.core.config import load_limits  # noqa: PLC0415

    values = load_limits().model_dump()
    assert (values["purge_batch"], values["purge_no_report_days"]) == (200, 30)
    assert values["ai_calls_retention_days"] == 90
    assert values["email_token_retention_days"] == 7
    for key in (
        "purge_batch",
        "purge_no_report_days",
        "ai_calls_retention_days",
        "email_token_retention_days",
    ):
        with pytest.raises(ValueError):
            Limits(**{k: v for k, v in values.items() if k != key})
        with pytest.raises(ValueError):
            Limits(**{**values, key: 0})
    with pytest.raises(ValueError):
        Limits(**{**values, "purge_batchh": 5})


def test_the_scheduler_registers_the_daily_purge(redis: Redis) -> None:
    scheduler = build_scheduler(redis, 3600, 60)
    jobs = {job.name: job for job in scheduler.get_jobs()}
    assert "purge-expired" in jobs
    assert PURGE_INTERVAL_SECONDS == 86400
    assert purge_expired_job.__module__ == "app.jobs.purge"
