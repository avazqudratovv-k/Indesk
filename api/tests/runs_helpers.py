"""Builders for the run tests: a world (user, uploads, run), scripted agents and flows, readers.
Everything uses the fake model client and a fake sandbox. No network, no real Gemini."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.caps import SessionFactory
from app.ai.gateway import Gateway
from app.core import clock
from app.core.config import Limits
from app.core.enums import (
    AgentKey,
    RunMode,
    RunStatus,
    SandboxErrorCode,
    StepKind,
    StepState,
    TraceKey,
)
from app.db.models import AgentStep, AuditLog, Run, Upload
from app.runs.agents import Agent, AgentContext, AgentResult, Finish, FlowInput
from app.runs.executor import RunDeps
from app.runs.trace import TraceLine
from app.sandbox_client import SandboxError, SandboxOk, SandboxResult
from tests.ai_helpers import limits_with, make_gateway
from tests.factories import make_run, make_run_file, make_upload, make_user
from tests.fake_model_client import FakeClient, FakeClock


@dataclass(frozen=True)
class World:
    user_id: uuid.UUID
    run_id: uuid.UUID
    upload_ids: tuple[uuid.UUID, ...]


def make_world(
    factory: SessionFactory,
    *,
    uploads: int = 1,
    status: RunStatus = RunStatus.QUEUED,
    created_ago: float = 0.0,
    user_id: uuid.UUID | None = None,
    question: str = "Which stations grew fastest since 2019?",
) -> World:
    with factory() as db, db.begin():
        owner = make_user(db) if user_id is None else _user(db, user_id)
        ups = [
            make_upload(
                db,
                owner,
                storage_key=f"k/{uuid.uuid4()}",
                status="ready",
                expires_at=clock.utcnow() + timedelta(hours=1),
            )  # fmt: skip
            for _ in range(uploads)
        ]
        values: dict[str, Any] = {"status": status, "question": question}
        if status is RunStatus.FINISHED:
            values["outcome"] = "answered"
        run = make_run(db, owner, **values)
        for up in ups:
            make_run_file(db, run, up)
        if created_ago:
            run.created_at = clock.utcnow() - timedelta(seconds=created_ago)
            if status is RunStatus.RUNNING:
                run.started_at = run.created_at
        return World(owner.id, run.id, tuple(u.id for u in ups))


def _user(db: Session, user_id: uuid.UUID) -> Any:
    from app.db.models import User  # noqa: PLC0415

    found = db.get(User, user_id)
    assert found is not None
    return found


def run_row(factory: SessionFactory, run_id: uuid.UUID) -> Run:
    with factory() as db:
        run = db.get(Run, run_id)
        assert run is not None
        db.refresh(run)
        db.expunge(run)
        return run


def step_rows(factory: SessionFactory, run_id: uuid.UUID) -> list[AgentStep]:
    with factory() as db:
        rows = list(
            db.scalars(select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.seq))
        )
        db.expunge_all()
        return rows


def audit_rows(factory: SessionFactory, action: str) -> list[AuditLog]:
    with factory() as db:
        rows = list(db.scalars(select(AuditLog).where(AuditLog.action == action)))
        db.expunge_all()
        return rows


def upload_row(factory: SessionFactory, upload_id: uuid.UUID) -> Upload:
    with factory() as db:
        up = db.get(Upload, upload_id)
        assert up is not None
        db.refresh(up)
        db.expunge(up)
        return up


# ---- scripted agents and flows ----


def line(
    agent: AgentKey = AgentKey.MANAGER,
    state: StepState = StepState.RUNNING,
    key: TraceKey = TraceKey.PLAN,
    kind: StepKind = StepKind.SAY,
    tok: int = 0,
    **args: Any,
) -> TraceLine:
    return TraceLine(agent, kind, state, key, args, tok=tok)


class FnAgent:
    """An agent whose behaviour is one function of the context."""

    def __init__(self, key: AgentKey, fn: Callable[[AgentContext], AgentResult]) -> None:
        self.key = key
        self._fn = fn
        self.calls = 0

    def run(self, ctx: AgentContext) -> AgentResult:
        self.calls += 1
        return self._fn(ctx)


class ScriptFlow:
    """Plays its steps in order (one per finished step); the last item repeats."""

    def __init__(self, *steps: Agent | Finish) -> None:
        self.steps = list(steps)

    def next(self, info: FlowInput) -> Agent | Finish:
        index = min(len(info.history), len(self.steps) - 1)
        return self.steps[index]


class LoopFlow:
    """Never finishes: the same agent, forever."""

    def __init__(self, agent: Agent) -> None:
        self.agent = agent

    def next(self, info: FlowInput) -> Agent | Finish:
        return self.agent


class FakeSandbox:
    def __init__(self, *results: SandboxResult) -> None:
        self.results = list(results)
        self.calls = 0

    def __call__(self, code: str, csv_bytes: bytes, /) -> SandboxResult:
        self.calls += 1
        return self.results.pop(0) if self.results else SandboxOk(result={}, duration_ms=1)


def sandbox_error(code: SandboxErrorCode) -> SandboxError:
    return SandboxError(code=code, duration_ms=1)


@dataclass
class Rig:
    deps: RunDeps
    clock: FakeClock
    client: FakeClient
    sandbox: FakeSandbox = field(default_factory=FakeSandbox)


def make_rig(
    factory: SessionFactory,
    flow: Any,
    *,
    steps: list[Any] | None = None,
    sandbox: FakeSandbox | None = None,
    limits: Limits | None = None,
    gateway: Gateway | None = None,
    **limit_overrides: Any,
) -> Rig:
    clock_ = FakeClock()
    client = FakeClient(steps or [])
    limits = limits or limits_with(**limit_overrides)
    sandbox = sandbox or FakeSandbox()
    gateway = gateway or make_gateway(factory, client, limits=limits)
    deps = RunDeps(
        session_factory=factory,
        gateway=gateway,
        sandbox=sandbox,
        limits=limits,
        flow_factory=lambda mode: flow,
        monotonic=clock_,
    )
    return Rig(deps, clock_, client, sandbox)


def modes() -> list[RunMode]:
    return list(RunMode)


def talker(agent: AgentKey = AgentKey.MANAGER, tokens: int = 0) -> FnAgent:
    """An agent that says two things and is done."""

    def fn(ctx: AgentContext) -> AgentResult:
        from app.runs.agents import AgentDone  # noqa: PLC0415

        ctx.emit(line(agent, StepState.RUNNING, TraceKey.PLAN))
        ctx.emit(line(agent, StepState.DONE, TraceKey.DISPATCH))
        return AgentDone(tokens_in=tokens, tokens_out=tokens)

    return FnAgent(agent, fn)
