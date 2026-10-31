"""Server-sent events of a run, read from the database only (no in-memory fan-out).

Per poll: read the run's status FIRST, then the trace lines after the last one sent. A run is only
`finished` after its closing line is committed (same transaction, app.runs.store), so if the status
read says finished, the lines read right after include the last one: `done` can never overtake it.

Event ids are the trace `seq`; the `done` event has the id after the last line. The browser resumes
with Last-Event-ID and gets only what is newer. A finished run whose `done` the client already got
answers 204, which tells EventSource to stop reconnecting."""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import anyio
from fastapi import Request
from sqlalchemy import func, select

from app.ai.caps import SessionFactory
from app.core.config import Limits
from app.core.enums import RunOutcome, RunReason, RunStatus
from app.db.models import AgentStep, Report, Run
from app.runs.not_answerable import read_for_run
from app.schemas.events import DoneEvent, StepEvent
from app.schemas.not_answerable import NotAnswerable

BATCH = 100
MAX_ID = 10**9


@dataclass(frozen=True)
class Snapshot:
    finished: bool
    outcome: RunOutcome | None
    reason: RunReason | None
    report_id: uuid.UUID | None
    events: list[StepEvent]
    not_answerable: NotAnswerable | None = None


def parse_last_event_id(raw: str | None) -> int:
    if raw is None:
        return 0
    value = raw.strip()
    if not value.isdigit() or len(value) > 9:
        return 0
    return min(int(value), MAX_ID)


def read_head(factory: SessionFactory, run_id: uuid.UUID) -> tuple[bool, int]:
    """(finished, highest seq) of a run."""
    with factory() as db:
        status = db.scalar(select(Run.status).where(Run.id == run_id))
        top = db.scalar(
            select(func.coalesce(func.max(AgentStep.seq), 0)).where(AgentStep.run_id == run_id)
        )
        return status == RunStatus.FINISHED, int(top or 0)


def read_snapshot(factory: SessionFactory, run_id: uuid.UUID, after: int) -> Snapshot:
    with factory() as db:
        head = db.execute(
            select(Run.status, Run.outcome, Run.outcome_reason).where(Run.id == run_id)
        ).first()  # first, before the lines (see the module note)
        rows = db.scalars(
            select(AgentStep)
            .where(AgentStep.run_id == run_id, AgentStep.seq > after)
            .order_by(AgentStep.seq)
            .limit(BATCH)
        ).all()
        events = [StepEvent.model_validate(row) for row in rows]
        finished = head is not None and head.status == RunStatus.FINISHED
        report_id = (
            db.scalar(select(Report.id).where(Report.run_id == run_id)) if finished else None
        )
        why = (
            read_for_run(db, run_id)
            if finished and head is not None and head.outcome == RunOutcome.NOT_ANSWERABLE
            else None
        )
        return Snapshot(
            finished=finished,
            outcome=RunOutcome(head.outcome)
            if finished and head is not None and head.outcome
            else None,
            reason=RunReason(head.outcome_reason)
            if finished and head is not None and head.outcome_reason
            else None,
            report_id=report_id,
            events=events,
            not_answerable=why,
        )


def format_step(event: StepEvent) -> str:
    return f"id: {event.seq}\nevent: step\ndata: {event.model_dump_json()}\n\n"


def format_done(seq: int, snap: Snapshot, run_id: uuid.UUID) -> str:
    # A finished run always has an outcome; fall back to failed rather than send nothing.
    done = DoneEvent(
        run_id=str(run_id),
        outcome=snap.outcome or RunOutcome.FAILED,
        report_id=str(snap.report_id) if snap.report_id else None,
        reason=snap.reason,
        not_answerable=snap.not_answerable,
    )
    return f"id: {seq}\nevent: done\ndata: {done.model_dump_json()}\n\n"


async def stream_events(
    *,
    request: Request,
    factory: SessionFactory,
    limits: Limits,
    run_id: uuid.UUID,
    after: int,
    on_ping: Callable[[], None],
    on_close: Callable[[], None],
) -> AsyncIterator[str]:
    """Yield SSE text until the run is done, the client leaves, or sse_max_seconds pass. A slow
    client only slows its own generator: nothing is buffered, each poll waits for the last send."""
    started = last_ping = time.monotonic()
    sent = after
    try:
        while not await request.is_disconnected():
            snap = await anyio.to_thread.run_sync(read_snapshot, factory, run_id, sent)
            for event in snap.events:
                yield format_step(event)
                sent = event.seq
            full = len(snap.events) == BATCH
            if snap.finished and not full:
                yield format_done(sent + 1, snap, run_id)
                return
            if full:
                continue
            now = time.monotonic()
            if now - started >= limits.sse_max_seconds:
                return
            if now - last_ping >= limits.sse_ping_seconds:
                last_ping = now
                yield ": ping\n\n"
                await anyio.to_thread.run_sync(on_ping)
            await asyncio.sleep(limits.sse_poll_seconds)
    finally:
        on_close()
