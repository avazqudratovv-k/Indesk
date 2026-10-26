"""Which Flow runs a given mode. P7 has no real agents: by default every run ends at once with
`model_unavailable`. P8 puts the real Ask flow here."""

import logging

from app.core.config import Settings
from app.core.enums import AgentKey, RunMode, RunOutcome, RunReason, StepKind, StepState, TraceKey
from app.runs.agents import Agent, Finish, Flow, FlowInput
from app.runs.stub import StubFlow
from app.runs.trace import TraceLine

logger = logging.getLogger("indesk.runs")
_warned = False


class UnconfiguredFlow:
    """No agents exist yet. Honest failure instead of a pretend answer."""

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
    return UnconfiguredFlow()
