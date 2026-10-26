"""DEV-ONLY scripted agents, so a developer can watch a whole run (queue, worker, trace, SSE)
without Gemini. Nothing here calls a model or the sandbox, reads a file or computes an answer: it
plays back a fixed script and every line is marked `stub=true`.

It runs only when app_env is "development" AND RUNS_DEV_STUB is on (app.runs.registry). compose.yaml
never sets it (a test checks), and production and test ignore it, like the web dev_session cookie
(DECISIONS #67).

THIS FILE IS REMOVED OR RE-DECIDED WHEN P8 LANDS (the real Owl and Beaver). Do not build on it."""

import time
from collections.abc import Callable

from app.core.enums import AgentKey, Bubble, RunOutcome, StepKind, StepState, TraceKey
from app.runs.agents import Agent, AgentContext, AgentDone, AgentResult, Finish, FlowInput
from app.runs.trace import TraceLine, TraceValue

PAUSE_SECONDS = 0.4  # long enough to watch the cards change


def _line(
    agent: AgentKey, kind: StepKind, state: StepState, key: TraceKey,
    bubble: Bubble | None = None, **args: TraceValue,
) -> TraceLine:  # fmt: skip
    return TraceLine(agent, kind, state, key, {"stub": True, **args}, tok=0, bubble=bubble)


class _Scripted:
    def __init__(
        self, key: AgentKey, lines: list[TraceLine], sleep: Callable[[float], None]
    ) -> None:
        self.key = key
        self._lines = lines
        self._sleep = sleep

    def run(self, ctx: AgentContext) -> AgentResult:
        for line in self._lines:
            self._sleep(PAUSE_SECONDS)
            ctx.emit(line)
        return AgentDone()


class StubFlow:
    """Owl plans, Beaver "reads and computes", Owl merges, then the run is answered (no report)."""

    def __init__(self, sleep: Callable[[float], None] = time.sleep) -> None:
        self._sleep = sleep

    def next(self, info: FlowInput) -> Agent | Finish:
        done = len(info.history)
        n_files = len(info.upload_ids)
        m, b, r = AgentKey.MANAGER, AgentKey.DATA, StepState.RUNNING
        steps: list[Agent] = [
            _Scripted(m, [
                _line(m, StepKind.SAY, r, TraceKey.PLAN, Bubble.OWL_SPLIT, files=n_files),
                _line(m, StepKind.SAY, r, TraceKey.DISPATCH, Bubble.OWL_SPLIT, agents=1),
            ], self._sleep),
            _Scripted(b, [
                _line(b, StepKind.TOOL, r, TraceKey.READ_CSV),
                _line(b, StepKind.TOOL, r, TraceKey.RUN_PYTHON),
                _line(b, StepKind.SAY, StepState.DONE, TraceKey.TOP3),
            ], self._sleep),
            _Scripted(
                m, [_line(m, StepKind.SAY, r, TraceKey.MERGE, Bubble.OWL_MERGE)], self._sleep
            ),
        ]  # fmt: skip
        if done < len(steps):
            return steps[done]
        return Finish(RunOutcome.ANSWERED, _line(m, StepKind.SAY, StepState.DONE, TraceKey.READY))
