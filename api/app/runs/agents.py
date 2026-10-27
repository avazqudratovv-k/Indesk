"""The seam P8 and P9 plug into. A Flow chooses the next Agent; an Agent does one step and reports
a result. The executor (app.runs.executor) owns the state machine, the limits and the writes, so
a new agent or flow never touches them.

Rules for an Agent: say things only through ctx.emit (TraceLine); never raise (return AgentFailed);
ask a model only through ctx.gateway and run code only through ctx.sandbox."""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from app.ai.caps import SessionFactory
from app.ai.gateway import Gateway
from app.core.enums import AgentKey, RunMode, RunOutcome, RunReason, StepState, UploadMime
from app.runs.cat_schemas import ReportDraft
from app.runs.trace import TraceLine
from app.sandbox_client import SandboxResult

Emit = Callable[..., None]  # emit(line: TraceLine, payload: BaseModel | None = None)


class SandboxRunner(Protocol):
    def __call__(self, code: str, csv_bytes: bytes, /) -> SandboxResult: ...


def _no_upload(upload_id: uuid.UUID, /) -> bytes | None:
    return None


@dataclass(frozen=True)
class AgentContext:
    run_id: uuid.UUID
    user_id: uuid.UUID
    mode: RunMode
    lang: str
    upload_ids: tuple[uuid.UUID, ...]
    attempt: int
    deadline: float  # time.monotonic() value after which the run is out of time
    gateway: Gateway
    sandbox: SandboxRunner
    emit: Emit
    # The stored bytes of an upload that is attached to THIS run and owned by the run's user;
    # None for any other upload, a deleted one, or a storage failure. The only way to read a file.
    read_upload: Callable[[uuid.UUID], bytes | None] = _no_upload
    question: str = field(default="", repr=False)  # the user's text: never log it
    # For agents that read the database themselves (Hound, Cat on a PDF). Their queries select the
    # uploads from this run's run_files, so they cannot reach another run's or user's data.
    session_factory: SessionFactory | None = None
    monotonic: Callable[[], float] = field(default=lambda: 0.0)


@dataclass(frozen=True)
class AgentDone:
    tokens_in: int = 0
    tokens_out: int = 0
    model: str | None = None
    data: BaseModel | None = None  # handed to the flow (not stored, not sent): e.g. Owl's plan


@dataclass(frozen=True)
class AgentFailed:
    reason: RunReason
    retryable: bool = False
    state: StepState = StepState.FAILED  # TIMED_OUT when the step ran out of time
    outcome: RunOutcome = RunOutcome.FAILED  # REJECTED for a daily cap


AgentResult = AgentDone | AgentFailed


class Agent(Protocol):
    key: AgentKey

    def run(self, ctx: AgentContext) -> AgentResult: ...


@dataclass(frozen=True)
class Finish:
    """The flow is done. `final` is the closing line, written in the same transaction that marks
    the run finished, so a stream can never show the end before the last line exists."""

    outcome: RunOutcome
    final: TraceLine
    reason: RunReason | None = None
    report: ReportDraft | None = None  # saved in the same transaction that finishes the run


@dataclass(frozen=True)
class StepRecord:
    agent: AgentKey
    result: AgentDone


@dataclass(frozen=True)
class FlowInput:
    run_id: uuid.UUID
    mode: RunMode
    lang: str
    upload_ids: tuple[uuid.UUID, ...]
    history: Sequence[StepRecord] = field(default_factory=tuple)
    # The type of each upload, in the order of upload_ids; the flow routes on it in code.
    upload_mimes: tuple[UploadMime, ...] = ()


class Flow(Protocol):
    def next(self, info: FlowInput) -> Agent | Finish: ...
