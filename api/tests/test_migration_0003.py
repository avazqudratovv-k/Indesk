"""Migration 0003 on a database that already has runs, usage events and model calls: it upgrades
without losing a run, drops only duplicate `run` events, enforces one quota row per run, and
downgrades and upgrades again."""

from datetime import timedelta

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AiCall, Run, UsageEvent
from tests.db_helpers import alembic_config, recreate_database
from tests.factories import NOW, make_run, make_user

INDEX = "uq_usage_events_run_id_run"


def index_names(engine: Engine) -> set[str]:
    return {i["name"] for i in inspect(engine).get_indexes("usage_events") if i["name"]}


def ai_columns(engine: Engine) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns("ai_calls")}


def scalar(engine: Engine, sql: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql)).scalar() or 0)


@pytest.fixture
def old_database() -> Engine:
    """A database at revision 0002 holding rows, as a deployed one would."""
    url = recreate_database("indesk_test_migrations")
    command.upgrade(alembic_config(url), "0002")
    engine = create_engine(url)
    with Session(engine) as db, db.begin():
        user = make_user(db)
        answered = make_run(db, user, status="finished", outcome="answered", counted=True)
        failed = make_run(
            db, user, status="finished", outcome="failed", outcome_reason="model_busy"
        )
        db.flush()
        stamp = NOW + timedelta(minutes=1)
        for run_id, at in [(answered.id, NOW), (answered.id, stamp), (failed.id, NOW)]:
            db.execute(
                text(
                    "INSERT INTO usage_events (user_id, run_id, kind, amount, created_at)"
                    " VALUES (:u, :r, 'run', 1, :t)"
                ),
                {"u": user.id, "r": run_id, "t": at},
            )  # the first two are a duplicate for one run
        for kind in ("credit_purchase", "credit_purchase", "run", "run"):
            db.add(UsageEvent(user_id=user.id, run_id=None, kind=kind, amount=1))
        db.execute(
            text(
                "INSERT INTO ai_calls (user_id, purpose, model, attempt, status)"
                " VALUES (:u, 'plan', 'm', 1, 'ok')"
            ),
            {"u": user.id},
        )
    return engine


def test_upgrade_keeps_every_run_and_drops_only_the_duplicate_event(old_database: Engine) -> None:
    config = alembic_config(old_database.url.render_as_string(hide_password=False))
    assert "failure_kind" not in ai_columns(old_database) and INDEX not in index_names(old_database)
    command.upgrade(config, "0003")
    assert scalar(old_database, "SELECT count(*) FROM runs") == 2
    assert scalar(old_database, "SELECT count(*) FROM usage_events") == 7 - 1
    assert scalar(old_database, "SELECT count(*) FROM usage_events WHERE run_id IS NOT NULL") == 2
    # The kept event of the duplicated run is the first one.
    late_events = (  # NOW is 2026-10-25 09:00 UTC; the duplicate was stamped a minute later
        "SELECT count(*) FROM usage_events"
        " WHERE run_id IS NOT NULL AND created_at > '2026-10-25 09:00:30+00'"
    )
    assert scalar(old_database, late_events) == 0
    assert "failure_kind" in ai_columns(old_database) and INDEX in index_names(old_database)
    assert scalar(old_database, "SELECT count(*) FROM ai_calls WHERE failure_kind IS NULL") == 1


def test_after_upgrade_a_run_has_one_quota_row_and_other_kinds_are_free(
    old_database: Engine,
) -> None:
    command.upgrade(alembic_config(old_database.url.render_as_string(hide_password=False)), "0003")
    with Session(old_database) as db:
        run = db.query(Run).filter(Run.outcome == "answered").one()
        db.add(UsageEvent(user_id=run.user_id, run_id=run.id, kind="run", amount=1))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        db.add(UsageEvent(user_id=run.user_id, run_id=run.id, kind="credit_purchase", amount=1))
        db.add(UsageEvent(user_id=run.user_id, run_id=None, kind="run", amount=1))  # NULLs differ
        db.flush()
        db.rollback()


def test_the_failure_kind_column_only_takes_a_closed_code(old_database: Engine) -> None:
    command.upgrade(alembic_config(old_database.url.render_as_string(hide_password=False)), "0003")
    with Session(old_database) as db:
        call = db.query(AiCall).one()
        call.failure_kind = "http_400"
        db.flush()
        call.failure_kind = "HTTP 400 AIzaSy-leaked"
        with pytest.raises(IntegrityError):
            db.flush()


def test_downgrade_removes_only_what_the_migration_added_then_upgrade_again(
    old_database: Engine,
) -> None:
    config = alembic_config(old_database.url.render_as_string(hide_password=False))
    command.upgrade(config, "0003")
    events = scalar(old_database, "SELECT count(*) FROM usage_events")
    command.downgrade(config, "0002")
    assert "failure_kind" not in ai_columns(old_database) and INDEX not in index_names(old_database)
    assert scalar(old_database, "SELECT count(*) FROM runs") == 2
    assert scalar(old_database, "SELECT count(*) FROM usage_events") == events
    assert scalar(old_database, "SELECT count(*) FROM ai_calls") == 1
    command.upgrade(config, "head")
    assert "failure_kind" in ai_columns(old_database) and INDEX in index_names(old_database)
