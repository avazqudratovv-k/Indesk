"""The seam P8 and P9 plug into. A Flow chooses the next Agent; an Agent does one step and reports
a result. The executor (app.runs.executor) owns the state machine, the limits and the writes, so
a new agent or flow never touches them.

Rules for an Agent: say things only through ctx.emit (TraceLine); never raise (return AgentFailed);
ask a model only through ctx.gateway and run code only through ctx.sandbox."""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.ai.gateway import Gateway
from app.core.enums import AgentKey, RunMode, RunOutcome, RunReason, StepState
from app.runs.trace import TraceLine
from app.sandbox_client import SandboxResult

Emit = Callable[..., None]  # emit(line: TraceLine, payload: BaseModel | None = None)


class SandboxRunner(Protocol):
    def __call__(self, code: str, csv_bytes: bytes, /) -> SandboxResult: ...


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


@dataclass(frozen=True)
class AgentDone:
    tokens_in: int = 0
    tokens_out: int = 0
    model: str | None = None


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


class Flow(Protocol):
    def next(self, info: FlowInput) -> Agent | Finish: ...
