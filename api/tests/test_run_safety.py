"""Safety nets around runs: the dev stub stays out of production, nothing private reaches logs or
responses, trace lines cannot carry free text, response shapes are closed, compose never sets
the stub."""

import logging
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Connection, select

from app.core.config import Settings
from app.core.enums import (
    AgentKey,
    AiPurpose,
    RunMode,
    RunOutcome,
    StepKind,
    StepState,
    TraceKey,
)
from app.db.models import AgentStep, AiCall
from app.main import app
from app.routers.runs import get_enqueue, get_session_factory
from app.runs import registry, stub
from app.runs.agents import AgentContext, AgentDone, AgentResult, Finish
from app.runs.ask_flow import AskFlow
from app.runs.executor import run_job
from app.runs.lang import detect_lang
from app.runs.registry import UnconfiguredFlow, select_flow
from app.runs.stub import StubFlow
from app.runs.trace import ALLOWED_ARGS, BadTraceLine, TraceLine
from app.schemas.events import DoneEvent, StepEvent
from app.schemas.runs import RunCreated, RunView
from tests.ai_helpers import factory_for
from tests.conftest import _test_redis_url
from tests.fake_model_client import API_KEY, ok
from tests.runs_helpers import FnAgent, ScriptFlow, line, make_rig, make_world, step_rows
from tests.test_compose_sandbox import CANDIDATES
from tests.test_runs_api import body, code, new_upload
from tests.test_runs_sse import parse
from tests.test_uploads import settings_for, signed_in

M = AgentKey.MANAGER
SECRET_QUESTION = "SECRET-QUESTION-TEXT-4711"
PROMPT = "PROMPT-MARKER-4711"
MODEL_OUTPUT = "MODEL-OUTPUT-MARKER-4711"


# ---- trace lines carry codes, not text ----


def test_every_trace_key_lists_its_arguments() -> None:
    assert set(ALLOWED_ARGS) == set(TraceKey)


@pytest.mark.parametrize(
    ("key", "args"),
    [
        (TraceKey.PLAN, {"note": "x"}),  # an argument the key does not take
        (TraceKey.STEP_FAILED, {"reason": "The model said something long and free"}),
        (TraceKey.STEP_FAILED, {"reason": "Upper"}),
        (TraceKey.STEP_FAILED, {"reason": "with space"}),
        (TraceKey.STEP_FAILED, {"reason": "x" * 41}),
        (TraceKey.STEP_FAILED, {"reason": ""}),
    ],
)
def test_a_trace_line_cannot_carry_free_text(key: TraceKey, args: dict[str, Any]) -> None:
    with pytest.raises(BadTraceLine):
        TraceLine(M, StepKind.SAY, StepState.RUNNING, key, args)


def test_trace_values_may_be_codes_and_numbers() -> None:
    TraceLine(
        M,
        StepKind.SAY,
        StepState.RUNNING,
        TraceKey.STEP_FAILED,
        {"reason": "model_busy", "attempt": 2},
    )
    TraceLine(
        M,
        StepKind.SAY,
        StepState.RUNNING,
        TraceKey.READ_CSV,
        {"rows": 4800, "cols": 3, "stub": True},
    )
    with pytest.raises(BadTraceLine):
        TraceLine(M, StepKind.SAY, StepState.RUNNING, TraceKey.PLAN, tok=-1)


# ---- language ----


@pytest.mark.parametrize(
    ("question", "lang"),
    [
        ("Which stations grew fastest since 2019?", "en"),
        ("가장 빠르게 성장한 역은 어디인가요?", "ko"),
        ("2019년 이후 which station grew fastest?", "en"),  # Hangul is a small share
        ("합정역 growth 2019 비교", "ko"),
        ("12345 ???", "en"),  # no letters
        ("", "en"),
        ("Какая станция выросла быстрее всего?", "en"),  # only en and ko exist for now
    ],
)
def test_language_from_the_hangul_share(question: str, lang: str) -> None:
    assert detect_lang(question).value == lang


# ---- the dev stub stays out of production ----


def settings_with(env: str, flag: bool) -> Settings:
    return Settings(
        app_env=env, runs_dev_stub=flag, auth_secret="x" * 40, redis_url=_test_redis_url(),
        allowed_origins=["https://indesk.example"], trusted_proxies=["10.0.0.0/8"],
    )  # fmt: skip


@pytest.mark.parametrize(
    ("env", "flag", "stubbed"),
    [
        ("development", True, True),
        ("development", False, False),
        ("production", True, False),
        ("production", False, False),
        ("test", True, False),
        ("test", False, False),
    ],
)
def test_the_stub_runs_only_in_development_with_the_flag(
    env: str, flag: bool, stubbed: bool
) -> None:
    flow = select_flow(settings_with(env, flag), RunMode.ASK)
    assert isinstance(flow, StubFlow if stubbed else AskFlow)  # Ask has real agents since P8a


def test_a_stub_flag_in_production_is_logged_once_and_ignored(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registry, "_warned", False)
    with caplog.at_level(logging.ERROR, logger="indesk.runs"):
        select_flow(settings_with("production", True), RunMode.ASK)
        select_flow(settings_with("production", True), RunMode.ASK)
    assert caplog.text.count("STUB_IGNORED") == 1


def test_the_flag_is_off_by_default_and_read_from_its_env_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert settings_with("development", False).runs_dev_stub is False
    monkeypatch.setenv("RUNS_DEV_STUB", "1")
    assert Settings().runs_dev_stub is True


def test_the_stub_says_it_goes_away_with_p8() -> None:
    assert stub.__doc__ and "P8" in stub.__doc__ and "REMOVED OR RE-DECIDED" in stub.__doc__


def test_compose_never_sets_the_stub_flag() -> None:
    seen = 0
    for name in ("compose.yaml", "compose.sandbox-test.yaml"):
        for folder in CANDIDATES:
            if (folder / name).is_file():
                seen += 1
                assert "RUNS_DEV_STUB" not in (folder / name).read_text(), name
                break
    assert seen == 2, "compose files not found; run the tests through docker compose"
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    if dockerfile.is_file():
        assert "RUNS_DEV_STUB" not in dockerfile.read_text()


def test_the_stub_plays_a_whole_run_without_a_model_or_the_sandbox(
    db_connection: Connection,
) -> None:
    factory = factory_for(db_connection)
    world = make_world(factory)
    rig = make_rig(factory, StubFlow(sleep=lambda seconds: None))
    run_job(world.run_id, rig.deps)

    steps = step_rows(factory, world.run_id)
    assert [s.key for s in steps] == [
        "plan", "dispatch", "readCsv", "runPython", "top3", "merge", "ready",
    ]  # fmt: skip
    assert all(s.args.get("stub") is True for s in steps)  # every line says it is a stub
    assert rig.client.calls == [] and rig.sandbox.calls == 0
    with factory() as db:
        assert db.scalars(select(AiCall)).all() == []
    from tests.runs_helpers import run_row  # noqa: PLC0415

    assert run_row(factory, world.run_id).outcome == "answered"


def test_without_agents_a_run_fails_honestly(db_connection: Connection) -> None:
    factory = factory_for(db_connection)
    world = make_world(factory)
    run_job(world.run_id, make_rig(factory, UnconfiguredFlow()).deps)
    from tests.runs_helpers import run_row  # noqa: PLC0415

    run = run_row(factory, world.run_id)
    assert (run.outcome, run.outcome_reason, run.counted) == ("failed", "model_unavailable", False)
    assert [s.key for s in step_rows(factory, world.run_id)] == ["stopped"]


# ---- nothing private in logs or responses ----


def test_no_question_prompt_model_text_or_key_in_logs_or_responses(
    make_client: Any,
    tmp_path: Path,
    db_connection: Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    factory = factory_for(db_connection)
    app.dependency_overrides[get_enqueue] = lambda: lambda run_id: None
    app.dependency_overrides[get_session_factory] = lambda: factory
    client: TestClient = signed_in(make_client, settings_for(tmp_path), "z@example.com", 20)
    posted = client.post("/api/runs", json=body(new_upload(client), question=SECRET_QUESTION))
    assert posted.status_code == 202
    run_id = uuid.UUID(posted.json()["id"])

    def fn(ctx: AgentContext) -> AgentResult:
        ctx.emit(line(M, StepState.RUNNING, TraceKey.PLAN))
        res = ctx.gateway.ask(
            PROMPT, purpose=AiPurpose.PLAN, user_id=ctx.user_id, run_id=ctx.run_id
        )
        assert res.ok and res.text == MODEL_OUTPUT
        return AgentDone(tokens_in=res.tokens_in, tokens_out=res.tokens_out)

    final = Finish(RunOutcome.ANSWERED, line(M, StepState.DONE, TraceKey.READY))
    rig = make_rig(factory, ScriptFlow(FnAgent(M, fn), final), steps=[ok(text=MODEL_OUTPUT)])
    run_job(run_id, rig.deps)

    get = client.get(f"/api/runs/{run_id}")
    events = client.get(f"/api/runs/{run_id}/events")
    assert events.status_code == 200 and parse(events.text)[0][-1]["event"] == "done"
    private = (PROMPT, MODEL_OUTPUT, API_KEY, "AIzaSy")
    for text in (posted.text, get.text, events.text, caplog.text):
        for secret in private:
            assert secret not in text, secret
    for text in (posted.text, events.text, caplog.text):
        assert SECRET_QUESTION not in text
    assert get.text.count(SECRET_QUESTION) == 1  # only the owner's own question field
    with factory() as db:  # and not in what the database keeps about the trace
        for step in db.scalars(select(AgentStep)):
            assert not any(
                s in f"{step.key}{step.args}{step.payload}" for s in (*private, SECRET_QUESTION)
            )
        assert [c.run_id for c in db.scalars(select(AiCall))] == [run_id]  # metadata only


# ---- response shapes are closed ----

RUN_VIEW_OK: dict[str, Any] = {
    "id": "r", "mode": "ask", "question": "q", "status": "queued", "outcome": None, "reason": None,
    "lang": "en", "tokens_in": 0, "tokens_out": 0, "tool_calls": 0, "created_at": None,
    "started_at": None, "finished_at": None, "steps": [], "report_id": None,
}  # fmt: skip


def test_run_view_forbids_unknown_fields_and_hides_internals() -> None:
    RunView.model_validate(RUN_VIEW_OK)
    with pytest.raises(ValidationError):
        RunView.model_validate({**RUN_VIEW_OK, "user_id": "u"})
    hidden = {
        "user_id",
        "owner_id",
        "cost_usd",
        "error",
        "payload",
        "model",
        "storage_key",
        "counted",
    }
    assert not hidden & set(RunView.model_fields)


def test_other_response_shapes_forbid_unknown_fields() -> None:
    RunCreated.model_validate({"id": "r", "status": "queued"})
    with pytest.raises(ValidationError):
        RunCreated.model_validate({"id": "r", "status": "queued", "user_id": "u"})
    step = {
        "run_id": "r",
        "seq": 1,
        "agent": "manager",
        "kind": "say",
        "state": "running",
        "key": "plan",
        "args": {},
        "tok": 0,
    }
    StepEvent.model_validate(step)
    with pytest.raises(ValidationError):
        StepEvent.model_validate({**step, "payload": {}})
    with pytest.raises(ValidationError):
        DoneEvent.model_validate({"run_id": "r", "outcome": "failed", "reason": "made_up"})
    DoneEvent.model_validate({"run_id": "r", "outcome": "failed", "reason": "model_busy"})


def test_errors_are_codes_only(make_client: Any, tmp_path: Path) -> None:
    client: TestClient = make_client(settings_for(tmp_path))
    code(client.post("/api/runs", json={"nonsense": True}), 401, "UNAUTHENTICATED")
    signed = signed_in(make_client, settings_for(tmp_path), "y@example.com", 21)
    bad = signed.post("/api/runs", json={"nonsense": True})
    code(bad, 422, "VALIDATION_ERROR")
    assert "nonsense" not in bad.text  # the input is never echoed back
