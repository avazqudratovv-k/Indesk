"""Walk one run through its flow. `run_job` never raises (except an RQ kill, which the reaper
cleans up) and always leaves the run finished: done, or failed/rejected with a reason code.

It owns the state machine, the step cap, the one retry, the run timeout and the token budget; the
agents only do their step. It never logs a question, a prompt, model output, file content or a key:
a run id, a reason code, counts and durations only.

NOT VERIFIED against real Gemini: every agent used so far is a test double or the dev stub."""

import logging
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial

from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.ai.caps import SessionFactory
from app.ai.gateway import Gateway
from app.core import clock
from app.core.config import Limits
from app.core.enums import (
    AgentKey,
    FileRole,
    RunMode,
    RunOutcome,
    RunReason,
    RunStatus,
    StepKind,
    StepState,
    TraceKey,
    UploadMime,
    UploadStatus,
)
from app.db.models import Run, RunFile, Upload
from app.runs import store
from app.runs.agents import (
    Agent,
    AgentContext,
    AgentDone,
    AgentFailed,
    Finish,
    Flow,
    FlowInput,
    SandboxRunner,
    StepRecord,
)
from app.runs.cat_schemas import ReportDraft
from app.runs.machine import MAX_ATTEMPTS, IllegalTransition, require_agent_transition
from app.runs.store import RunGone
from app.runs.trace import BadTraceLine, TraceLine, stopped_line
from app.storage import Storage, StorageError

logger = logging.getLogger("indesk.runs")

# Hound's failure line has its own key in the web mock (searchFailed); the other agents share one.
_FAILED_KEY = {AgentKey.RETRIEVAL: TraceKey.SEARCH_FAILED}


@dataclass
class RunDeps:
    """Everything a run needs from outside, so a test can hand in fakes."""

    session_factory: SessionFactory
    gateway: Gateway
    sandbox: SandboxRunner
    limits: Limits
    flow_factory: Callable[[RunMode], Flow]
    storage: Storage | None = None  # where uploads live; without it no agent can read a file
    monotonic: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = clock.utcnow


@dataclass
class _Tracker:
    """The last state and attempt each agent showed, so each line is checked against the machine."""

    seen: dict[AgentKey, tuple[StepState, int]] = field(default_factory=dict)

    def apply(self, line: TraceLine, attempt: int) -> None:
        previous, previous_attempt = self.seen.get(line.agent, (None, 0))
        require_agent_transition(previous, line.state, attempt, previous_attempt)
        self.seen[line.agent] = (line.state, attempt)


class _Runner:
    def __init__(self, run_id: uuid.UUID, deps: RunDeps) -> None:
        self.run_id = run_id
        self.deps = deps
        self.tracker = _Tracker()
        self.invocations = 0
        self.history: list[StepRecord] = []
        self.question = ""

    @contextmanager
    def _db(self) -> Iterator[Session]:
        with self.deps.session_factory() as db:
            yield db

    # ---- writes ----

    def _finish(
        self,
        outcome: RunOutcome,
        reason: RunReason | None,
        final: TraceLine | None,
        report: ReportDraft | None = None,
    ) -> None:
        with self._db() as db:
            store.finish_run(
                db,
                self.run_id,
                expected=RunStatus.RUNNING,
                outcome=outcome,
                reason=reason,
                final=final,
                now=self.deps.now(),
                report=report,
            )
        logger.info(
            "run %s finished outcome=%s reason=%s steps=%d",
            self.run_id, outcome.value, reason.value if reason else "-", self.invocations,
        )  # fmt: skip

    def _stop(self, reason: RunReason, outcome: RunOutcome = RunOutcome.FAILED) -> None:
        self._finish(outcome, reason, stopped_line(reason))

    def _emit(self, line: TraceLine, attempt: int, payload: BaseModel | None = None) -> None:
        self.tracker.apply(line, attempt)
        with self._db() as db:
            store.append_event(
                db, self.run_id, line, attempt=attempt, payload=payload, now=self.deps.now()
            )

    # ---- checks ----

    def _out_of_time(self, deadline: float) -> bool:
        return self.deps.monotonic() >= deadline

    def _over_budget(self) -> bool:
        with self._db() as db:
            used = store.run_tokens(db, self.run_id)
        return used > self.deps.limits.max_tokens_per_run

    # ---- the run ----

    def run(self) -> None:
        with self._db() as db:
            if not store.claim_run(db, self.run_id, self.deps.now()):
                return  # a duplicate delivery, or the reaper got there first
            run = db.get(Run, self.run_id)
            if run is None:  # cannot happen after a claim; do not crash a worker over it
                return
            mode, lang, user_id = RunMode(run.mode), run.lang, run.user_id
            self.question = run.question
            upload_ids = tuple(
                db.scalars(
                    select(RunFile.upload_id)
                    .where(RunFile.run_id == self.run_id)
                    # The subject file first, so an agent that uses one file uses that one.
                    .order_by(
                        case((RunFile.role == FileRole.SUBJECT, 0), else_=1), RunFile.upload_id
                    )
                )
            )
            usable = self._uploads_usable(db, upload_ids)
            mime_rows = db.execute(select(Upload.id, Upload.mime).where(Upload.id.in_(upload_ids)))
            mime_of: dict[uuid.UUID, str] = {row[0]: row[1] for row in mime_rows}
            mimes = tuple(UploadMime(mime_of[u]) for u in upload_ids if u in mime_of)
        if not usable:
            self._stop(RunReason.INPUT_UNUSABLE)
            return
        flow = self.deps.flow_factory(mode)
        deadline = self.deps.monotonic() + self.deps.limits.run_timeout_seconds
        while True:
            step = flow.next(
                FlowInput(self.run_id, mode, lang, upload_ids, tuple(self.history), mimes)
            )
            if isinstance(step, Finish):
                self._finish(step.outcome, step.reason, step.final, step.report)
                return
            if not self._drive(step, user_id, mode, lang, upload_ids, deadline):
                return

    @staticmethod
    def _uploads_usable(db: Session, upload_ids: tuple[uuid.UUID, ...]) -> bool:
        rows = list(db.scalars(select(Upload).where(Upload.id.in_(upload_ids))))
        return len(rows) == len(upload_ids) and all(
            u.status == UploadStatus.READY and u.deleted_at is None and u.storage_key is not None
            for u in rows
        )

    def _drive(
        self,
        agent: Agent,
        user_id: uuid.UUID,
        mode: RunMode,
        lang: str,
        upload_ids: tuple[uuid.UUID, ...],
        deadline: float,
    ) -> bool:
        """Run one agent step with its one retry. True: the step is done, go on. False: the run
        has been finished (or taken over by the reaper)."""
        limits = self.deps.limits
        attempt = 1
        while True:
            if self.invocations >= limits.max_agent_steps:
                self._stop(RunReason.STEP_CAP)
                return False
            if self._out_of_time(deadline):
                self._stop(RunReason.RUN_TIMEOUT)
                return False
            if self._over_budget():
                self._stop(RunReason.BUDGET_EXCEEDED)
                return False
            self.invocations += 1
            ctx = AgentContext(
                run_id=self.run_id, user_id=user_id, mode=mode, lang=lang,
                upload_ids=upload_ids, attempt=attempt, deadline=deadline,
                gateway=self.deps.gateway, sandbox=self.deps.sandbox,
                emit=lambda line, payload=None, _a=attempt: self._emit(line, _a, payload),
                read_upload=partial(self._read_upload, user_id),
                question=self.question, session_factory=self.deps.session_factory,
                monotonic=self.deps.monotonic,
            )  # fmt: skip
            result = self._call(agent, ctx)
            with self._db() as db:
                store.add_counters(
                    db, self.run_id,
                    tokens_in=result.tokens_in if isinstance(result, AgentDone) else 0,
                    tokens_out=result.tokens_out if isinstance(result, AgentDone) else 0,
                    tool_calls=1,
                )  # fmt: skip
            if isinstance(result, AgentDone):
                self.history.append(StepRecord(agent.key, result))
                if self._over_budget():  # the step that crossed the line is the last one
                    self._stop(RunReason.BUDGET_EXCEEDED)
                    return False
                return True
            self._report_failure(agent.key, result, attempt)
            retry = (
                result.retryable
                and attempt < MAX_ATTEMPTS
                and not self._out_of_time(deadline)
                and self.invocations < limits.max_agent_steps
            )
            if not retry:
                self._stop(result.reason, result.outcome)
                return False
            attempt += 1

    def _read_upload(self, user_id: uuid.UUID, upload_id: uuid.UUID) -> bytes | None:
        """The bytes of an upload, only if it is attached to THIS run, owned by the run's user,
        ready and not deleted. Anything else is None (no reason given, nothing logged)."""
        storage = self.deps.storage
        if storage is None:
            return None
        with self._db() as db:
            key = db.scalar(
                select(Upload.storage_key)
                .join(RunFile, RunFile.upload_id == Upload.id)
                .where(
                    RunFile.run_id == self.run_id,
                    RunFile.owner_id == user_id,
                    Upload.id == upload_id,
                    Upload.user_id == user_id,
                    Upload.status == UploadStatus.READY,
                    Upload.deleted_at.is_(None),
                    Upload.storage_key.is_not(None),
                )
            )
        if key is None:
            return None
        try:
            return storage.get(key)
        except StorageError:
            return None

    def _call(self, agent: Agent, ctx: AgentContext) -> AgentDone | AgentFailed:
        try:
            result = agent.run(ctx)
        except (RunGone, IllegalTransition, BadTraceLine):
            raise
        except Exception:  # noqa: BLE001  # an agent must not raise; one that does is a bug
            logger.error(
                "run %s agent %s raised code=%s", self.run_id, agent.key.value, "AGENT_RAISED"
            )
            return AgentFailed(RunReason.INTERNAL_ERROR)
        if not isinstance(result, (AgentDone, AgentFailed)):
            logger.error("run %s agent %s returned garbage", self.run_id, agent.key.value)
            return AgentFailed(RunReason.INTERNAL_ERROR)
        return result

    def _report_failure(self, agent: AgentKey, failed: AgentFailed, attempt: int) -> None:
        """Show the failure on the agent's own card: open it first if it has not started."""
        last = self.tracker.seen.get(agent)
        if last is None or last[0] in (StepState.QUEUED, StepState.FAILED, StepState.TIMED_OUT):
            self._emit(
                TraceLine(agent, StepKind.SAY, StepState.RUNNING, TraceKey.STEP_STARTED,
                          {"attempt": attempt}),
                attempt,
            )  # fmt: skip
        self._emit(
            TraceLine(agent, StepKind.FLAG, failed.state,
                      _FAILED_KEY.get(agent, TraceKey.STEP_FAILED),
                      {"reason": failed.reason.value, "attempt": attempt}),
            attempt,
        )  # fmt: skip


def run_job(run_id: uuid.UUID, deps: RunDeps) -> None:
    runner = _Runner(run_id, deps)
    try:
        runner.run()
    except RunGone:
        logger.info("run %s was finished by someone else", run_id)
    except Exception as error:  # noqa: BLE001  # the run must end terminal whatever happens
        logger.error(
            "run %s failed code=%s type=%s", run_id, "RUN_UNEXPECTED", type(error).__name__
        )
        try:
            with deps.session_factory() as db:
                store.finish_run(
                    db, run_id, expected=RunStatus.RUNNING, outcome=RunOutcome.FAILED,
                    reason=RunReason.INTERNAL_ERROR, final=stopped_line(RunReason.INTERNAL_ERROR),
                    now=deps.now(),
                )  # fmt: skip
        except Exception:  # noqa: BLE001
            logger.error("run %s could not be closed code=%s", run_id, "RUN_CLOSE_FAILED")
