"""Every database write of a run lives here. Each function commits its own work.

Rules that hold the SSE stream together:
- A run is finished by ONE compare-and-set UPDATE (`WHERE status = expected`), so the worker and the
  reaper cannot both finish it. The closing trace line and the audit row go in the SAME transaction,
  so a reader that sees `finished` also sees the last line.
- append_event takes a shared lock on the run row and refuses unless the run is `running`. Finishing
  needs the exclusive lock, so no line can ever be committed after the run is finished.
Nothing here logs. It never touches a prompt, a question or a file."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import RunOutcome, RunReason, RunStatus
from app.db.models import AgentStep, AiCall, AuditLog, Run
from app.runs.machine import check_finish, counts_as_run, require_run_transition
from app.runs.trace import TraceLine

AUDIT_RUN_CREATED = "run_created"
AUDIT_RUN_FINISHED = "run_finished"


class RunGone(Exception):  # noqa: N818  # not an error: the run was finished by someone else
    """The run is no longer `running` (the reaper finished it, or it never started)."""


def lock_user_runs(db: Session, user_id: uuid.UUID) -> None:
    """Serialise run creation per user until the transaction ends (advisory lock, no table)."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"run:{user_id}"}
    )


def active_run(db: Session, user_id: uuid.UUID) -> Run | None:
    return db.scalar(
        select(Run).where(Run.user_id == user_id, Run.status != RunStatus.FINISHED).limit(1)
    )


def claim_run(db: Session, run_id: uuid.UUID, now: datetime) -> bool:
    """queued -> running. False when the run is not queued (a duplicate delivery, or reaped)."""
    require_run_transition(RunStatus.QUEUED, RunStatus.RUNNING)
    claimed = db.execute(
        update(Run)
        .where(Run.id == run_id, Run.status == RunStatus.QUEUED)
        .values(status=RunStatus.RUNNING, started_at=now)
        .returning(Run.id)
    ).first()
    db.commit()
    return claimed is not None


def _next_seq(db: Session, run_id: uuid.UUID) -> int:
    top = db.scalar(
        select(func.coalesce(func.max(AgentStep.seq), 0)).where(AgentStep.run_id == run_id)
    )
    return int(top or 0) + 1


def _step_row(
    run_id: uuid.UUID,
    owner_id: uuid.UUID,
    seq: int,
    line: TraceLine,
    attempt: int,
    payload: BaseModel | None,
    now: datetime,
) -> AgentStep:
    data: dict[str, Any] | None = payload.model_dump(mode="json") if payload is not None else None
    return AgentStep(
        run_id=run_id,
        owner_id=owner_id,
        seq=seq,
        agent=line.agent,
        kind=line.kind,
        state=line.state,
        key=line.key.value,
        args=dict(line.args),
        tok=line.tok,
        bubble=line.bubble,
        attempt=attempt,
        payload=data,
        started_at=now,
        finished_at=now,
    )


def append_event(
    db: Session,
    run_id: uuid.UUID,
    line: TraceLine,
    *,
    attempt: int,
    payload: BaseModel | None,
    now: datetime,
) -> int:
    """Write one trace line and return its seq. Raises RunGone unless the run is `running`."""
    row = db.execute(
        select(Run.status, Run.user_id).where(Run.id == run_id).with_for_update(read=True)
    ).first()
    if row is None or row.status != RunStatus.RUNNING:
        db.rollback()
        raise RunGone
    seq = _next_seq(db, run_id)
    try:
        db.add(_step_row(run_id, row.user_id, seq, line, attempt, payload, now))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RunGone from None
    return seq


def add_counters(
    db: Session, run_id: uuid.UUID, *, tokens_in: int, tokens_out: int, tool_calls: int
) -> None:
    db.execute(
        update(Run)
        .where(Run.id == run_id, Run.status == RunStatus.RUNNING)
        .values(
            tokens_in=Run.tokens_in + tokens_in,
            tokens_out=Run.tokens_out + tokens_out,
            tool_calls=Run.tool_calls + tool_calls,
        )
    )
    db.commit()


def run_tokens(db: Session, run_id: uuid.UUID) -> int:
    """Tokens (in + out) the gateway recorded for this run: the source for max_tokens_per_run."""
    total = db.scalar(
        select(func.coalesce(func.sum(AiCall.tokens_in + AiCall.tokens_out), 0)).where(
            AiCall.run_id == run_id
        )
    )
    db.rollback()  # end the read transaction; nothing to keep
    return int(total or 0)


def finish_run(
    db: Session,
    run_id: uuid.UUID,
    *,
    expected: RunStatus,
    outcome: RunOutcome,
    reason: RunReason | None,
    final: TraceLine | None,
    now: datetime,
    attempt: int = 1,
) -> bool:
    """Finish the run if it is still in `expected`. One transaction: status, closing line, audit
    row. False (and nothing written) when someone else finished it first."""
    require_run_transition(expected, RunStatus.FINISHED)
    check_finish(outcome, reason)
    owner = db.execute(
        update(Run)
        .where(Run.id == run_id, Run.status == expected)
        .values(
            status=RunStatus.FINISHED,
            outcome=outcome,
            outcome_reason=reason.value if reason else None,
            counted=counts_as_run(outcome),
            finished_at=now,
        )
        .returning(Run.user_id)
    ).scalar()
    if owner is None:
        db.rollback()
        return False
    if final is not None:
        db.add(_step_row(run_id, owner, _next_seq(db, run_id), final, attempt, None, now))
    # `target` holds "<run id>:<reason or outcome>": audit_log has no column for the reason.
    db.add(
        AuditLog(
            user_id=owner,
            action=AUDIT_RUN_FINISHED,
            target=f"{run_id}:{reason.value if reason else outcome.value}",
        )
    )
    db.commit()
    return True
