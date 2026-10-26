"""Run quotas: the Free plan's total free runs (from usage_events) and the daily run counters
(usage_daily.runs). Model-call caps are not here; they live in app.ai.caps and the gateway.

Every function works inside the caller's transaction and commits nothing, so a refusal rolls the
whole admission back (no run row, no counter change) and a refund lands in the same transaction as
the run's closing line.

Race safety: run creation holds the per-user advisory lock and the database allows one unfinished
run per user, so the used count is final before the next run can start. The daily counters are one
atomic upsert-with-a-WHERE each, the same pattern as the model-call caps."""

import uuid
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.enums import CapDecision, UsageKind
from app.db.models import UsageDaily, UsageEvent

GLOBAL_SCOPE = "global"


def user_scope(user_id: uuid.UUID) -> str:
    return f"user:{user_id}"


def free_runs_used(db: Session, user_id: uuid.UUID) -> int:
    """Runs this user has used, in total: the sum of their `run` usage events."""
    total = db.scalar(
        select(func.coalesce(func.sum(UsageEvent.amount), 0)).where(
            UsageEvent.user_id == user_id, UsageEvent.kind == UsageKind.RUN
        )
    )
    return int(total or 0)


def record_used_run(db: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> None:
    """One usage event for a run that counts. The unique index makes a second call a no-op."""
    db.execute(
        insert(UsageEvent)
        .values(user_id=user_id, run_id=run_id, kind=UsageKind.RUN.value, amount=1)
        .on_conflict_do_nothing(
            index_elements=[UsageEvent.run_id], index_where=UsageEvent.kind == UsageKind.RUN.value
        )
    )


def _bump_runs(db: Session, *, day: date, scope: str, user_id: uuid.UUID | None, cap: int) -> bool:
    """Add one run to (day, scope) unless it is already at `cap`. True if it was added."""
    statement = (
        insert(UsageDaily)
        .values(day=day, scope=scope, user_id=user_id, runs=1)
        .on_conflict_do_update(
            index_elements=[UsageDaily.day, UsageDaily.scope],
            set_={"runs": UsageDaily.runs + 1},
            where=UsageDaily.runs < cap,
        )
        .returning(UsageDaily.runs)
    )
    return db.execute(statement).first() is not None


def reserve_run(
    db: Session, *, user_id: uuid.UUID, day: date, per_user: int, per_day: int
) -> CapDecision:
    """Take one run slot for the user and one for the site. USER_CAP or GLOBAL_CAP means the caller
    must roll the transaction back (a user slot taken before a global refusal goes with it)."""
    if not _bump_runs(db, day=day, scope=user_scope(user_id), user_id=user_id, cap=per_user):
        return CapDecision.USER_CAP
    if not _bump_runs(db, day=day, scope=GLOBAL_SCOPE, user_id=None, cap=per_day):
        return CapDecision.GLOBAL_CAP
    return CapDecision.RESERVED


def release_run(db: Session, *, user_id: uuid.UUID, day: date) -> None:
    """Give a run slot back, never below zero."""
    db.execute(
        update(UsageDaily)
        .where(
            UsageDaily.day == day,
            UsageDaily.scope.in_([user_scope(user_id), GLOBAL_SCOPE]),
        )
        .values(runs=func.greatest(UsageDaily.runs - 1, 0))
    )


def calls_cap_reached(
    db: Session, *, user_id: uuid.UUID, day: date, per_user: int, per_day: int
) -> CapDecision:
    """A read-only look at the model-call counters, so a user who is already at a call cap is
    refused at POST /runs instead of after a worker picked the run up. The gateway stays the
    authority: it reserves each call atomically."""
    rows = {
        scope: calls
        for scope, calls in db.execute(
            select(UsageDaily.scope, UsageDaily.model_calls).where(
                UsageDaily.day == day,
                UsageDaily.scope.in_([user_scope(user_id), GLOBAL_SCOPE]),
            )
        )
    }
    if rows.get(user_scope(user_id), 0) >= per_user:
        return CapDecision.USER_CAP
    if rows.get(GLOBAL_SCOPE, 0) >= per_day:
        return CapDecision.GLOBAL_CAP
    return CapDecision.RESERVED
