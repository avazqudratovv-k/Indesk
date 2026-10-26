"""The run state machine. The ONLY place that says which moves are legal.

Two levels:
- the run: RunStatus queued -> running -> finished (finished is terminal; the result is the outcome
  and, for failed and rejected runs, a reason code);
- each agent, as the trace shows it: the StepState carried by its events.

This module is pure (no database). The writes live in app.runs.store, and every run-status write
there is a compare-and-set, so two writers (the worker and the reaper) can never both finish a run.
"""

from collections.abc import Mapping
from typing import Final

from app.core.enums import RunOutcome, RunReason, RunStatus, StepState

RUN_TRANSITIONS: Final[Mapping[RunStatus, frozenset[RunStatus]]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.FINISHED}),
    RunStatus.RUNNING: frozenset({RunStatus.FINISHED}),
    RunStatus.FINISHED: frozenset(),
}

# Previous state of an agent (None = it has not appeared yet) -> states it may move to.
AGENT_TRANSITIONS: Final[Mapping[StepState | None, frozenset[StepState]]] = {
    None: frozenset({StepState.QUEUED, StepState.RUNNING, StepState.SKIPPED}),
    StepState.QUEUED: frozenset({StepState.RUNNING, StepState.SKIPPED}),
    StepState.RUNNING: frozenset(
        {StepState.RUNNING, StepState.DONE, StepState.FAILED, StepState.TIMED_OUT}
    ),
    # The one retry: a failed or timed-out agent may start again, as attempt 2 only.
    StepState.FAILED: frozenset({StepState.RUNNING}),
    StepState.TIMED_OUT: frozenset({StepState.RUNNING}),
    StepState.DONE: frozenset(),
    StepState.SKIPPED: frozenset(),
}

MAX_ATTEMPTS: Final = 2  # one retry per agent step

# Outcomes that need a reason code, and the ones that count as a used run (DATA.md runs.counted).
_NEEDS_REASON: Final = frozenset({RunOutcome.FAILED, RunOutcome.REJECTED})
_COUNTED: Final = frozenset({RunOutcome.ANSWERED, RunOutcome.PARTIAL})
_REJECTED_REASONS: Final = frozenset({RunReason.DAILY_CAP_USER, RunReason.DAILY_CAP_GLOBAL})


class IllegalTransition(Exception):  # noqa: N818  # a name the callers read as a state, not an error
    """A move the tables above do not allow. A bug in an agent or a flow, never user input."""


def can_run_transition(current: RunStatus, new: RunStatus) -> bool:
    return new in RUN_TRANSITIONS[current]


def require_run_transition(current: RunStatus, new: RunStatus) -> None:
    if not can_run_transition(current, new):
        raise IllegalTransition(f"run {current.value} -> {new.value}")


def can_agent_transition(
    previous: StepState | None, new: StepState, attempt: int, previous_attempt: int = 0
) -> bool:
    """Is it legal for an agent last seen in `previous` (as attempt `previous_attempt`, 0 if never
    seen) to emit `new` as attempt number `attempt`? The first line is attempt 1; a restart after a
    failure is exactly the next attempt (at most MAX_ATTEMPTS); other lines keep the attempt."""
    if new not in AGENT_TRANSITIONS[previous]:
        return False
    if previous in (StepState.FAILED, StepState.TIMED_OUT):
        return attempt == previous_attempt + 1 and attempt <= MAX_ATTEMPTS
    return attempt == max(previous_attempt, 1)


def require_agent_transition(
    previous: StepState | None, new: StepState, attempt: int, previous_attempt: int = 0
) -> None:
    if not can_agent_transition(previous, new, attempt, previous_attempt):
        was = previous.value if previous else "none"
        raise IllegalTransition(f"agent {was} -> {new.value} (attempt {attempt})")


def check_finish(outcome: RunOutcome, reason: RunReason | None) -> None:
    """A failed or rejected run carries a reason; a rejected run's reason is a daily cap."""
    if outcome in _NEEDS_REASON and reason is None:
        raise IllegalTransition(f"outcome {outcome.value} needs a reason")
    if outcome is RunOutcome.REJECTED and reason not in _REJECTED_REASONS:
        raise IllegalTransition("a rejected run is a daily cap")
    if outcome is RunOutcome.ANSWERED and reason is not None:
        raise IllegalTransition("an answered run has no failure reason")


def counts_as_run(outcome: RunOutcome) -> bool:
    return outcome in _COUNTED
