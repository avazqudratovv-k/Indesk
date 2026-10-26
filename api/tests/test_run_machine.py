"""The run state machine: every legal and every illegal move, checked against an explicit list
written separately from the tables in app/runs/machine.py."""

import itertools

import pytest

from app.core.enums import RunOutcome, RunReason, RunStatus, StepState
from app.runs import machine
from app.runs.machine import IllegalTransition

LEGAL_RUN = {
    (RunStatus.QUEUED, RunStatus.RUNNING),
    (RunStatus.QUEUED, RunStatus.FINISHED),
    (RunStatus.RUNNING, RunStatus.FINISHED),
}


@pytest.mark.parametrize(
    ("old", "new"), list(itertools.product(RunStatus, RunStatus)), ids=lambda v: v.value
)
def test_every_run_transition(old: RunStatus, new: RunStatus) -> None:
    legal = (old, new) in LEGAL_RUN
    assert machine.can_run_transition(old, new) is legal
    if legal:
        machine.require_run_transition(old, new)
    else:
        with pytest.raises(IllegalTransition):
            machine.require_run_transition(old, new)


def test_finished_is_terminal_and_nothing_goes_back() -> None:
    assert machine.RUN_TRANSITIONS[RunStatus.FINISHED] == frozenset()
    for status in RunStatus:
        assert not machine.can_run_transition(status, RunStatus.QUEUED)


S = StepState
# (previous state, previous attempt) -> (new state, attempt) that are legal.
LEGAL_AGENT = {
    (None, 0): {(S.QUEUED, 1), (S.RUNNING, 1), (S.SKIPPED, 1)},
    (S.QUEUED, 1): {(S.RUNNING, 1), (S.SKIPPED, 1)},
    (S.RUNNING, 1): {(S.RUNNING, 1), (S.DONE, 1), (S.FAILED, 1), (S.TIMED_OUT, 1)},
    (S.RUNNING, 2): {(S.RUNNING, 2), (S.DONE, 2), (S.FAILED, 2), (S.TIMED_OUT, 2)},
    (S.FAILED, 1): {(S.RUNNING, 2)},
    (S.TIMED_OUT, 1): {(S.RUNNING, 2)},
    (S.FAILED, 2): set(),  # the one retry is spent
    (S.TIMED_OUT, 2): set(),
    (S.DONE, 1): set(),
    (S.DONE, 2): set(),
    (S.SKIPPED, 1): set(),
}


def test_every_agent_transition() -> None:
    checked = 0
    for (prev, prev_attempt), new, attempt in itertools.product(
        LEGAL_AGENT, StepState, (1, 2, 3)
    ):  # every reachable previous state x every new state x every attempt
        expected = (new, attempt) in LEGAL_AGENT.get((prev, prev_attempt), set())
        got = machine.can_agent_transition(prev, new, attempt, prev_attempt)
        assert got is expected, (prev, prev_attempt, new, attempt)
        checked += 1
    assert checked > 100


def test_a_third_attempt_is_never_legal() -> None:
    for prev in (S.FAILED, S.TIMED_OUT):
        assert not machine.can_agent_transition(prev, S.RUNNING, 3, 2)


def test_require_agent_transition_raises_on_a_bad_move() -> None:
    machine.require_agent_transition(None, S.RUNNING, 1)
    with pytest.raises(IllegalTransition):
        machine.require_agent_transition(S.DONE, S.RUNNING, 1, 1)


@pytest.mark.parametrize("outcome", list(RunOutcome))
def test_finish_rules(outcome: RunOutcome) -> None:
    needs = outcome in (RunOutcome.FAILED, RunOutcome.REJECTED)
    if needs:
        with pytest.raises(IllegalTransition):
            machine.check_finish(outcome, None)
    else:
        machine.check_finish(outcome, None)
    assert machine.counts_as_run(outcome) is (outcome in (RunOutcome.ANSWERED, RunOutcome.PARTIAL))


def test_rejected_means_a_daily_cap_and_answered_has_no_reason() -> None:
    machine.check_finish(RunOutcome.REJECTED, RunReason.DAILY_CAP_USER)
    machine.check_finish(RunOutcome.REJECTED, RunReason.DAILY_CAP_GLOBAL)
    with pytest.raises(IllegalTransition):
        machine.check_finish(RunOutcome.REJECTED, RunReason.MODEL_BUSY)
    with pytest.raises(IllegalTransition):
        machine.check_finish(RunOutcome.ANSWERED, RunReason.MODEL_BUSY)
    machine.check_finish(RunOutcome.FAILED, RunReason.MODEL_BUSY)
