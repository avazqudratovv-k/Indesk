"""execute_run: happy path, retries, limits, and every way it can go wrong. Each test ends by
checking the run is TERMINAL. Fake gateway, fake sandbox, no network, nothing real."""

import logging
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from redis import Redis
from rq import Queue
from sqlalchemy import Connection, update

from app.ai.caps import SessionFactory, reserve_call
from app.ai.gateway import GatewayError
from app.core import clock
from app.core.enums import (
    AgentKey,
    AiPurpose,
    CapDecision,
    GatewayOutcome,
    RunMode,
    RunOutcome,
    RunReason,
    RunStatus,
    SandboxErrorCode,
    StepState,
    TraceKey,
    UploadStatus,
)
from app.db.models import AiCall, Upload
from app.jobs import runs as jobs_runs
from app.runs import store
from app.runs.agents import AgentContext, AgentDone, AgentFailed, AgentResult, Finish
from app.runs.executor import run_job
from app.runs.mapping import failure_from_gateway
from tests.ai_helpers import DAY, factory_for, limits_with, make_gateway
from tests.conftest import _test_redis_url
from tests.fake_model_client import FakeClient, ok, rate_limited, timed_out
from tests.runs_helpers import (
    FakeSandbox,
    FnAgent,
    LoopFlow,
    ScriptFlow,
    World,
    audit_rows,
    line,
    make_rig,
    make_world,
    run_row,
    sandbox_error,
    step_rows,
)

M, D = AgentKey.MANAGER, AgentKey.DATA
RUNNING, DONE = StepState.RUNNING, StepState.DONE
READY = Finish(RunOutcome.ANSWERED, line(M, DONE, TraceKey.READY))


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


def terminal(factory: SessionFactory, world: World) -> Any:
    run = run_row(factory, world.run_id)
    assert run.status == RunStatus.FINISHED, "a run must always end terminal"
    assert run.outcome is not None and run.finished_at is not None
    return run


def keys(factory: SessionFactory, world: World) -> list[str]:
    return [s.key for s in step_rows(factory, world.run_id)]


def talker(agent: AgentKey = M, tokens: int = 0) -> FnAgent:
    """Says one thing and is done."""

    def fn(ctx: AgentContext) -> AgentResult:
        ctx.emit(line(agent, RUNNING, TraceKey.PLAN))
        ctx.emit(line(agent, DONE, TraceKey.DISPATCH))
        return AgentDone(tokens_in=tokens, tokens_out=tokens)

    return FnAgent(agent, fn)


# ---- happy path ----


def test_happy_path_ends_done_with_ordered_events(factory: SessionFactory) -> None:
    world = make_world(factory)
    rig = make_rig(factory, ScriptFlow(talker(M, 10), READY))
    run_job(world.run_id, rig.deps)

    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason, run.counted) == ("answered", None, True)
    assert (run.tokens_in, run.tokens_out, run.tool_calls) == (10, 10, 1)
    assert run.started_at is not None
    steps = step_rows(factory, world.run_id)
    assert [s.seq for s in steps] == [1, 2, 3]
    assert [s.key for s in steps] == ["plan", "dispatch", "ready"]
    assert {s.owner_id for s in steps} == {world.user_id}
    [audit] = audit_rows(factory, "run_finished")
    assert audit.target == f"{world.run_id}:answered" and audit.user_id == world.user_id


def test_a_gateway_call_is_recorded_against_the_run(factory: SessionFactory) -> None:
    world = make_world(factory)

    def fn(ctx: AgentContext) -> AgentResult:
        ctx.emit(line(M, RUNNING))
        res = ctx.gateway.ask(
            "PROMPT", purpose=AiPurpose.PLAN, user_id=ctx.user_id, run_id=ctx.run_id
        )
        assert res.ok
        return AgentDone(tokens_in=res.tokens_in, tokens_out=res.tokens_out)

    rig = make_rig(
        factory, ScriptFlow(FnAgent(M, fn), READY), steps=[ok(tokens_in=7, tokens_out=3)]
    )
    run_job(world.run_id, rig.deps)
    run = terminal(factory, world)
    assert (run.tokens_in, run.tokens_out) == (7, 3)
    with factory() as db:
        [call] = db.query(AiCall).all()
        assert call.run_id == world.run_id


# ---- retry ----


def test_one_retry_then_success(factory: SessionFactory) -> None:
    world = make_world(factory)

    def fn(ctx: AgentContext) -> AgentResult:
        ctx.emit(line(D, RUNNING, TraceKey.READ_CSV))
        if ctx.attempt == 1:
            return AgentFailed(RunReason.MODEL_TIMEOUT, retryable=True, state=StepState.TIMED_OUT)
        ctx.emit(line(D, DONE, TraceKey.TOP3))
        return AgentDone()

    agent = FnAgent(D, fn)
    run_job(world.run_id, make_rig(factory, ScriptFlow(agent, READY)).deps)

    run = terminal(factory, world)
    assert run.outcome == "answered" and run.tool_calls == 2 and agent.calls == 2
    steps = step_rows(factory, world.run_id)
    assert [(s.state, s.attempt) for s in steps] == [
        ("running", 1), ("timed_out", 1), ("running", 2), ("done", 2), ("done", 1),
    ]  # fmt: skip
    assert steps[1].key == "stepFailed" and steps[1].args == {
        "reason": "model_timeout",
        "attempt": 1,
    }


def test_retry_exhausted_fails_after_exactly_two_attempts(factory: SessionFactory) -> None:
    world = make_world(factory)
    agent = FnAgent(D, lambda ctx: AgentFailed(RunReason.BAD_MODEL_OUTPUT, retryable=True))
    run_job(world.run_id, make_rig(factory, ScriptFlow(agent, READY)).deps)

    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason, run.counted) == ("failed", "bad_model_output", False)
    assert agent.calls == 2  # one retry, never a third
    # The agent said nothing itself, so the executor opened its card each time.
    assert keys(factory, world) == [
        "stepStarted", "stepFailed", "stepStarted", "stepFailed", "stopped",
    ]  # fmt: skip
    assert [s.attempt for s in step_rows(factory, world.run_id)][:4] == [1, 1, 2, 2]


def test_a_failure_that_is_not_retryable_is_not_retried(factory: SessionFactory) -> None:
    world = make_world(factory)
    agent = FnAgent(D, lambda ctx: AgentFailed(RunReason.MODEL_BUSY))
    run_job(world.run_id, make_rig(factory, ScriptFlow(agent, READY)).deps)
    assert agent.calls == 1
    assert terminal(factory, world).outcome_reason == "model_busy"


# ---- limits ----


def test_step_cap_stops_a_flow_that_never_finishes(factory: SessionFactory) -> None:
    world = make_world(factory)

    def fn(ctx: AgentContext) -> AgentResult:
        ctx.emit(line(M, RUNNING))
        return AgentDone()

    agent = FnAgent(M, fn)
    run_job(world.run_id, make_rig(factory, LoopFlow(agent), max_agent_steps=3).deps)
    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason, run.tool_calls) == ("failed", "step_cap", 3)
    assert agent.calls == 3
    assert keys(factory, world)[-1] == "stopped"


def test_the_step_cap_counts_retries(factory: SessionFactory) -> None:
    world = make_world(factory)
    agent = FnAgent(D, lambda ctx: AgentFailed(RunReason.MODEL_TIMEOUT, retryable=True))
    run_job(world.run_id, make_rig(factory, ScriptFlow(agent, READY), max_agent_steps=1).deps)
    assert agent.calls == 1  # no room left for the retry
    assert terminal(factory, world).outcome_reason == "model_timeout"


def test_run_timeout(factory: SessionFactory) -> None:
    world = make_world(factory)
    holder: list[Any] = []

    def fn(ctx: AgentContext) -> AgentResult:
        ctx.emit(line(M, RUNNING))
        holder[0].clock.advance(100)
        return AgentDone()

    agent = FnAgent(M, fn)
    rig = make_rig(factory, LoopFlow(agent), run_timeout_seconds=150)
    holder.append(rig)
    run_job(world.run_id, rig.deps)
    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason) == ("failed", "run_timeout")
    assert agent.calls == 2  # 100 s < 150 s, then 200 s > 150 s


def test_no_retry_when_the_run_is_out_of_time(factory: SessionFactory) -> None:
    world = make_world(factory)
    holder: list[Any] = []

    def fn(ctx: AgentContext) -> AgentResult:
        holder[0].clock.advance(500)
        return AgentFailed(RunReason.MODEL_TIMEOUT, retryable=True, state=StepState.TIMED_OUT)

    agent = FnAgent(D, fn)
    rig = make_rig(factory, ScriptFlow(agent, READY), run_timeout_seconds=100)
    holder.append(rig)
    run_job(world.run_id, rig.deps)
    assert agent.calls == 1
    assert terminal(factory, world).outcome_reason == "model_timeout"


def spend(tokens: int, then: AgentResult) -> FnAgent:
    def fn(ctx: AgentContext) -> AgentResult:
        ctx.emit(line(M, RUNNING))
        ctx.gateway.ask("p", purpose=AiPurpose.PLAN, user_id=ctx.user_id, run_id=ctx.run_id)
        return then

    return FnAgent(M, fn)


def test_token_budget_ends_the_run_after_the_step_that_crossed_it(factory: SessionFactory) -> None:
    world = make_world(factory)
    second = talker(D)
    flow = ScriptFlow(spend(0, AgentDone()), second, READY)
    rig = make_rig(
        factory, flow, steps=[ok(tokens_in=40000, tokens_out=30000)], max_tokens_per_run=60000
    )
    run_job(world.run_id, rig.deps)
    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason) == ("failed", "budget_exceeded")
    assert second.calls == 0


def test_token_budget_is_checked_before_a_retry(factory: SessionFactory) -> None:
    world = make_world(factory)
    agent = spend(0, AgentFailed(RunReason.BAD_MODEL_OUTPUT, retryable=True))
    rig = make_rig(
        factory, ScriptFlow(agent, READY), steps=[ok(tokens_in=70000)], max_tokens_per_run=60000
    )
    run_job(world.run_id, rig.deps)
    assert agent.calls == 1
    assert terminal(factory, world).outcome_reason == "budget_exceeded"


# ---- things that go wrong ----


def test_an_agent_that_raises_still_ends_terminal_and_leaks_nothing(
    factory: SessionFactory, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    world = make_world(factory)

    def boom(ctx: AgentContext) -> AgentResult:
        raise RuntimeError("SECRET-QUESTION-TEXT and AIzaSy-key")

    run_job(world.run_id, make_rig(factory, ScriptFlow(FnAgent(D, boom), READY)).deps)
    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason) == ("failed", "internal_error")
    assert "SECRET-QUESTION-TEXT" not in caplog.text and "AIzaSy" not in caplog.text


def test_a_flow_that_raises_ends_terminal(factory: SessionFactory) -> None:
    world = make_world(factory)

    class Broken:
        def next(self, info: Any) -> Any:
            raise ValueError("nope")

    run_job(world.run_id, make_rig(factory, Broken()).deps)
    assert terminal(factory, world).outcome_reason == "internal_error"
    assert keys(factory, world) == ["stopped"]


def test_a_flow_factory_that_raises_ends_terminal(factory: SessionFactory) -> None:
    world = make_world(factory)
    rig = make_rig(factory, ScriptFlow(READY))

    def factory_boom(mode: RunMode) -> Any:
        raise RuntimeError("no flow")

    rig.deps.flow_factory = factory_boom
    run_job(world.run_id, rig.deps)
    assert terminal(factory, world).outcome_reason == "internal_error"


def test_a_database_error_while_writing_a_line_ends_terminal(
    factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = make_world(factory)
    real = store.append_event
    calls: list[int] = []

    def flaky(*a: Any, **kw: Any) -> int:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("db hiccup")
        return real(*a, **kw)

    monkeypatch.setattr(store, "append_event", flaky)
    run_job(world.run_id, make_rig(factory, ScriptFlow(talker(), READY)).deps)
    assert terminal(factory, world).outcome_reason == "internal_error"


@pytest.mark.parametrize(
    "bad",
    [
        lambda ctx: None,
        lambda ctx: "done",
        lambda ctx: (ctx.emit(line(M, DONE)), ctx.emit(line(M, RUNNING)), AgentDone())[2],
        lambda ctx: (ctx.emit(line(M, DONE)), AgentFailed(RunReason.MODEL_BUSY))[1],
        lambda ctx: (ctx.emit(line(M, RUNNING, TraceKey.PLAN, free_text="x")), AgentDone())[1],
    ],
    ids=["none", "string", "done-then-running", "done-then-failed", "bad-trace-arg"],
)
def test_misbehaving_agents_end_internal_error(
    factory: SessionFactory, bad: Callable[[AgentContext], Any]
) -> None:
    world = make_world(factory)
    run_job(world.run_id, make_rig(factory, ScriptFlow(FnAgent(M, bad), READY)).deps)
    assert terminal(factory, world).outcome_reason == "internal_error"


def test_an_upload_that_is_gone_fails_without_running_an_agent(factory: SessionFactory) -> None:
    world = make_world(factory)
    with factory() as db, db.begin():
        db.execute(
            update(Upload)
            .where(Upload.id == world.upload_ids[0])
            .values(status=UploadStatus.DELETED, storage_key=None)
        )
    agent = talker()
    run_job(world.run_id, make_rig(factory, ScriptFlow(agent, READY)).deps)
    assert agent.calls == 0
    assert terminal(factory, world).outcome_reason == "input_unusable"


def test_a_duplicate_delivery_does_nothing(factory: SessionFactory) -> None:
    world = make_world(factory)
    agent = talker()
    rig = make_rig(factory, ScriptFlow(agent, READY))
    run_job(world.run_id, rig.deps)
    before = keys(factory, world)
    run_job(world.run_id, rig.deps)
    assert keys(factory, world) == before and agent.calls == 1


def test_an_unknown_run_is_ignored(factory: SessionFactory) -> None:
    run_job(uuid.uuid4(), make_rig(factory, ScriptFlow(READY)).deps)  # must not raise


def test_a_run_the_reaper_took_over_is_left_alone(factory: SessionFactory) -> None:
    world = make_world(factory)

    def fn(ctx: AgentContext) -> AgentResult:
        ctx.emit(line(M, RUNNING))
        with factory() as db:  # the reaper finishes the run while the agent works
            assert store.finish_run(
                db, ctx.run_id, expected=RunStatus.RUNNING, outcome=RunOutcome.FAILED,
                reason=RunReason.WORKER_LOST,
                final=line(M, DONE, TraceKey.STOPPED, reason="worker_lost"),
                now=clock.utcnow(),
            )  # fmt: skip
        ctx.emit(line(M, RUNNING))  # refused: the run is finished
        raise AssertionError("not reached")

    run_job(world.run_id, make_rig(factory, ScriptFlow(FnAgent(M, fn), READY)).deps)
    run = terminal(factory, world)
    assert run.outcome_reason == "worker_lost"
    assert keys(factory, world) == ["plan", "stopped"]
    assert len(audit_rows(factory, "run_finished")) == 1


# ---- every gateway outcome and sandbox code ends in the agreed reason ----

GATEWAY_CASES = [
    # outcome, cap scope, reason, run outcome, invocations, agent state
    (GatewayOutcome.BUSY, None, "model_busy", "failed", 1, "failed"),
    (GatewayOutcome.TIMEOUT, None, "model_timeout", "failed", 2, "timed_out"),
    (GatewayOutcome.MODEL_UNAVAILABLE, None, "model_unavailable", "failed", 2, "failed"),
    (GatewayOutcome.CAP_REACHED, "user", "daily_cap_user", "rejected", 1, "failed"),
    (GatewayOutcome.CAP_REACHED, "global", "daily_cap_global", "rejected", 1, "failed"),
    (GatewayOutcome.BAD_OUTPUT, None, "bad_model_output", "failed", 2, "failed"),
    (GatewayOutcome.BAD_INPUT, None, "input_unusable", "failed", 1, "failed"),
]


def test_every_gateway_error_outcome_is_covered() -> None:
    covered = {case[0] for case in GATEWAY_CASES}
    assert covered == set(GatewayOutcome) - {GatewayOutcome.OK}


@pytest.mark.parametrize(
    ("outcome", "scope", "reason", "run_outcome", "calls", "state"), GATEWAY_CASES
)
def test_gateway_outcome_mapping(
    factory: SessionFactory,
    outcome: Any,
    scope: Any,
    reason: str,
    run_outcome: str,
    calls: int,
    state: str,
) -> None:
    world = make_world(factory)
    error = GatewayError(outcome=outcome, cap_scope=scope)
    agent = FnAgent(D, lambda ctx: failure_from_gateway(error))
    run_job(world.run_id, make_rig(factory, ScriptFlow(agent, READY)).deps)
    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason, run.counted) == (run_outcome, reason, False)
    assert agent.calls == calls
    failed = [s for s in step_rows(factory, world.run_id) if s.key == "stepFailed"]
    assert failed[-1].state == state and failed[-1].args["reason"] == reason
    final = step_rows(factory, world.run_id)[-1]
    assert (final.key, final.args) == ("stopped", {"reason": reason})


SANDBOX_CASES = [
    (SandboxErrorCode.TIMEOUT, "analysis_failed", 2, "timed_out"),
    (SandboxErrorCode.FORBIDDEN, "analysis_failed", 2, "failed"),
    (SandboxErrorCode.RUNTIME, "analysis_failed", 2, "failed"),
    (SandboxErrorCode.MEMORY, "analysis_failed", 1, "failed"),
    (SandboxErrorCode.OUTPUT_TOO_LARGE, "analysis_failed", 1, "failed"),
    (SandboxErrorCode.BAD_INPUT, "input_unusable", 1, "failed"),
    (SandboxErrorCode.UNAVAILABLE, "sandbox_unavailable", 2, "failed"),
]


def test_every_sandbox_code_is_covered() -> None:
    assert {case[0] for case in SANDBOX_CASES} == set(SandboxErrorCode)


@pytest.mark.parametrize(("code", "reason", "calls", "state"), SANDBOX_CASES)
def test_sandbox_code_mapping(
    factory: SessionFactory, code: SandboxErrorCode, reason: str, calls: int, state: str
) -> None:
    from app.runs.mapping import failure_from_sandbox  # noqa: PLC0415

    world = make_world(factory)
    sandbox = FakeSandbox(*[sandbox_error(code)] * 2)

    def fn(ctx: AgentContext) -> AgentResult:
        res = ctx.sandbox("code", b"csv")
        assert not res.ok
        return failure_from_sandbox(res)

    agent = FnAgent(D, fn)
    run_job(world.run_id, make_rig(factory, ScriptFlow(agent, READY), sandbox=sandbox).deps)
    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason) == ("failed", reason)
    assert agent.calls == calls == sandbox.calls
    failed = [s for s in step_rows(factory, world.run_id) if s.key == "stepFailed"]
    assert failed[-1].state == state


def gateway_agent(prompt: str = "PROMPT-MARKER") -> FnAgent:
    def fn(ctx: AgentContext) -> AgentResult:
        res = ctx.gateway.ask(
            prompt, purpose=AiPurpose.PLAN, user_id=ctx.user_id, run_id=ctx.run_id
        )
        if not res.ok:
            return failure_from_gateway(res)
        return AgentDone(tokens_in=res.tokens_in, tokens_out=res.tokens_out)

    return FnAgent(D, fn)


def test_through_the_real_gateway_all_models_busy(factory: SessionFactory) -> None:
    world = make_world(factory)
    rig = make_rig(
        factory, ScriptFlow(gateway_agent(), READY), steps=[rate_limited(), rate_limited()]
    )
    run_job(world.run_id, rig.deps)
    assert terminal(factory, world).outcome_reason == "model_busy"
    assert len(rig.client.calls) == 2  # one attempt per model, no retry of the step


def test_through_the_real_gateway_a_timeout_is_retried_once(factory: SessionFactory) -> None:
    world = make_world(factory)
    rig = make_rig(
        factory, ScriptFlow(gateway_agent(), READY), steps=[timed_out(40), timed_out(40)]
    )
    run_job(world.run_id, rig.deps)
    assert terminal(factory, world).outcome_reason == "model_timeout"
    assert len(rig.client.calls) == 2


def test_through_the_real_gateway_bad_output_and_bad_input(factory: SessionFactory) -> None:
    world = make_world(factory)
    rig = make_rig(factory, ScriptFlow(gateway_agent(), READY), steps=[ok(text=""), ok(text="")])
    run_job(world.run_id, rig.deps)
    assert terminal(factory, world).outcome_reason == "bad_model_output"
    other = make_world(factory)
    rig = make_rig(factory, ScriptFlow(gateway_agent("x" * 50), READY), max_prompt_chars=10)
    run_job(other.run_id, rig.deps)
    assert terminal(factory, other).outcome_reason == "input_unusable"
    assert rig.client.calls == []


@pytest.mark.parametrize(
    ("scope", "reason"), [("user", "daily_cap_user"), ("global", "daily_cap_global")]
)
def test_through_the_real_gateway_a_daily_cap_rejects_the_run(
    factory: SessionFactory, scope: str, reason: str
) -> None:
    world = make_world(factory)
    limits = limits_with(daily_calls_per_user=1, daily_calls_global=1)
    if scope == "user":
        assert (
            reserve_call(factory, user_id=world.user_id, day=DAY, per_user=1, per_day=99)
            is CapDecision.RESERVED
        )
    else:
        stranger = make_world(factory).user_id
        reserve_call(factory, user_id=stranger, day=DAY, per_user=99, per_day=1)
    gateway = make_gateway(factory, FakeClient([]), limits=limits)
    rig = make_rig(factory, ScriptFlow(gateway_agent(), READY), gateway=gateway, limits=limits)
    run_job(world.run_id, rig.deps)
    run = terminal(factory, world)
    assert (run.outcome, run.outcome_reason, run.counted) == ("rejected", reason, False)


# ---- RQ ----


def test_execute_run_through_rq(
    factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = make_world(factory)
    rig = make_rig(factory, ScriptFlow(talker(), READY))
    monkeypatch.setattr(jobs_runs, "build_deps", lambda: rig.deps)
    connection = Redis.from_url(_test_redis_url())  # database 15, never the dev queue
    job = Queue("default", connection=connection, is_async=False).enqueue(
        jobs_runs.execute_run, str(world.run_id)
    )
    assert job.is_finished
    assert terminal(factory, world).outcome == "answered"


def test_enqueue_run_uses_the_run_id_as_job_id_and_the_job_timeout() -> None:
    connection = Redis.from_url(_test_redis_url())  # database 15, never the dev queue
    run_id = uuid.uuid4()
    jobs_runs.enqueue_run(connection, run_id, 240)
    job = Queue("default", connection=connection).fetch_job(str(run_id))
    assert job is not None
    assert (job.timeout, job.func_name, job.args) == (
        240,
        "app.jobs.runs.execute_run",
        (str(run_id),),
    )
    assert job.retries_left is None  # RQ must never run a job twice behind the reaper's back
