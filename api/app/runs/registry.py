"""Which Flow runs a given mode. Ask has the real flow (Owl, Beaver; P8a). Check and Compare have
no agents yet: their runs end at once with `model_unavailable`. The dev stub (development only)
wins."""

import logging

from app.core.config import Settings
from app.core.enums import AgentKey, RunMode, RunOutcome, RunReason, StepKind, StepState, TraceKey
from app.runs.agents import Agent, Finish, Flow, FlowInput
from app.runs.ask_flow import AskFlow
from app.runs.stub import StubFlow
from app.runs.trace import TraceLine

logger = logging.getLogger("indesk.runs")
_warned = False


class UnconfiguredFlow:
    """No agents exist yet for this mode. Honest failure instead of a pretend answer."""

    def next(self, info: FlowInput) -> Agent | Finish:
        reason = RunReason.MODEL_UNAVAILABLE
        final = TraceLine(
            AgentKey.MANAGER,
            StepKind.SAY,
            StepState.DONE,
            TraceKey.STOPPED,
            {"reason": reason.value},
        )
        return Finish(RunOutcome.FAILED, final, reason)


def stub_allowed(settings: Settings) -> bool:
    return settings.runs_dev_stub and settings.app_env == "development"


def select_flow(settings: Settings, mode: RunMode) -> Flow:
    global _warned
    if settings.runs_dev_stub and not stub_allowed(settings) and not _warned:
        _warned = True
        logger.error("RUNS_DEV_STUB is set but ignored outside development code=%s", "STUB_IGNORED")
    if stub_allowed(settings):
        return StubFlow()
    if mode is RunMode.ASK:
        return AskFlow(settings.limits)
    return UnconfiguredFlow()
