"""The real Ask flow (P8a): Owl plans, Beaver computes, the run ends `answered` with NO report
(Cat and the report come in P9). Replaces UnconfiguredFlow for Ask in app.runs.registry; the dev
stub still wins in development only.

An Ask with more than one file is refused here, before any agent runs: no file read, no model
call, no cap slot (only one CSV is analysed; comma-delimited files only, see app.runs.profile).

NOT VERIFIED against real Gemini."""

from collections.abc import Callable

from app.core.config import Limits
from app.core.enums import (
    AgentKey,
    RunOutcome,
    RunReason,
    StepKind,
    StepState,
    TraceKey,
)
from app.runs.agents import Agent, Finish, FlowInput
from app.runs.ask_schemas import OwlPlan
from app.runs.beaver import BeaverAgent
from app.runs.owl import OwlAgent
from app.runs.prompts import new_nonce
from app.runs.trace import TraceLine, stopped_line


def _stop(reason: RunReason) -> Finish:
    return Finish(RunOutcome.FAILED, stopped_line(reason), reason)


class AskFlow:
    def __init__(self, limits: Limits, nonce: Callable[[], str] = new_nonce) -> None:
        self._limits = limits
        self._nonce = nonce

    def next(self, info: FlowInput) -> Agent | Finish:
        if len(info.upload_ids) != 1:
            return _stop(RunReason.INPUT_UNUSABLE)
        done = len(info.history)
        if done == 0:
            return OwlAgent(self._limits, self._nonce)
        if done == 1:
            plan = info.history[0].result.data
            if not isinstance(plan, OwlPlan):  # cannot happen; fail closed, never guess a plan
                return _stop(RunReason.INTERNAL_ERROR)
            return BeaverAgent(self._limits, plan, self._nonce)
        ready = TraceLine(AgentKey.MANAGER, StepKind.SAY, StepState.DONE, TraceKey.READY)
        return Finish(RunOutcome.ANSWERED, ready)
