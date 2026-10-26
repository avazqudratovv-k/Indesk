"""The gateway with the fake client: order, outcomes, budget, records, secrets. No network."""

import logging
import uuid
from typing import Any

import pytest
from pydantic import BaseModel, SecretStr
from sqlalchemy import Connection, inspect, select, text

from app.ai.caps import SessionFactory
from app.ai.gateway import Gateway, GatewayError, GatewayOk, GatewayResult
from app.core.enums import AiCallStatus, AiPurpose, GatewayOutcome, ModelFailure
from app.db.models import Run
from tests.ai_helpers import (
    ai_rows,
    chain_with,
    factory_for,
    limits_with,
    make_gateway,
    new_user,
    usage,
)  # fmt: skip
from tests.fake_model_client import (
    API_KEY,
    FakeClient,
    Step,
    fail,
    ok,
    rate_limited,
    server_error,
    timed_out,
)  # fmt: skip

PRIMARY, FALLBACK = "gemini-2.5-flash", "gemini-2.5-flash-lite"


class Answer(BaseModel):
    total: int


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


@pytest.fixture
def user(factory: SessionFactory) -> uuid.UUID:
    return new_user(factory)


def ask(gateway: Gateway, user: uuid.UUID, prompt: Any = "hello", **kw: Any) -> GatewayResult:
    return gateway.ask(prompt, purpose=AiPurpose.ROUTE, user_id=user, **kw)


# ---- success, order, fallback ----


def test_success_uses_the_first_model_and_records_it(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([ok("fine", 11, 7)])
    result = ask(make_gateway(factory, client), user)
    assert isinstance(result, GatewayOk)
    assert (result.text, result.model, result.attempts) == ("fine", PRIMARY, 1)
    assert (result.tokens_in, result.tokens_out) == (11, 7)
    (row,) = ai_rows(factory)
    assert (row.model, row.status, row.attempt) == (PRIMARY, "ok", 1)
    assert (row.tokens_in, row.tokens_out, row.purpose) == (11, 7, "route")


def test_cost_guards_are_always_sent(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([rate_limited(), ok()])
    ask(make_gateway(factory, client), user)
    first, second = client.calls
    assert (first.model, first.max_output_tokens, first.thinking_budget) == (PRIMARY, 4096, 1024)
    assert (second.model, second.max_output_tokens, second.thinking_budget) == (FALLBACK, 4096, 0)
    assert (first.timeout, second.timeout) == (20, 12)


@pytest.mark.parametrize(
    "first", [rate_limited(), server_error(), timed_out(1), fail(ModelFailure.OTHER)]
)
def test_falls_to_the_next_model(factory: SessionFactory, user: uuid.UUID, first: Step) -> None:
    client = FakeClient([first, ok("second")])
    result = ask(make_gateway(factory, client), user)
    assert isinstance(result, GatewayOk)
    assert (result.model, result.attempts) == (FALLBACK, 2)
    assert [c.model for c in client.calls] == [PRIMARY, FALLBACK]
    assert [r.attempt for r in ai_rows(factory)] == [1, 2]


def test_every_attempt_status_is_recorded(factory: SessionFactory, user: uuid.UUID) -> None:
    ask(make_gateway(factory, FakeClient([rate_limited(), ok()])), user)
    assert [r.status for r in ai_rows(factory)] == [
        AiCallStatus.RATE_LIMITED.value, AiCallStatus.OK.value,
    ]  # fmt: skip


def test_a_client_that_raises_counts_as_a_failure(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([Step(raises=RuntimeError("boom " + API_KEY)), ok()])
    result = ask(make_gateway(factory, client), user)
    assert isinstance(result, GatewayOk) and result.model == FALLBACK


# ---- exhausted chain: BUSY / TIMEOUT / MODEL_UNAVAILABLE ----


def test_busy_only_when_every_model_said_429(factory: SessionFactory, user: uuid.UUID) -> None:
    result = ask(make_gateway(factory, FakeClient([rate_limited(), rate_limited()])), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BUSY
    assert result.attempts == 2


def test_one_5xx_among_429s_is_not_busy(factory: SessionFactory, user: uuid.UUID) -> None:
    result = ask(make_gateway(factory, FakeClient([rate_limited(), server_error()])), user)
    assert isinstance(result, GatewayError)
    assert result.outcome is GatewayOutcome.MODEL_UNAVAILABLE


def test_a_timeout_among_429s_is_a_timeout(factory: SessionFactory, user: uuid.UUID) -> None:
    result = ask(make_gateway(factory, FakeClient([rate_limited(), timed_out(2)])), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.TIMEOUT


def test_all_5xx_is_model_unavailable(factory: SessionFactory, user: uuid.UUID) -> None:
    result = ask(make_gateway(factory, FakeClient([server_error(), server_error()])), user)
    assert isinstance(result, GatewayError)
    assert result.outcome is GatewayOutcome.MODEL_UNAVAILABLE


# ---- the 35 s budget (fake clock, no sleeping) ----


def test_each_attempt_gets_the_time_that_is_left(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([timed_out(30), ok()])
    result = ask(make_gateway(factory, client), user)
    assert isinstance(result, GatewayOk)
    assert [c.timeout for c in client.calls] == [20, 5]  # 35 - 30 left for the second model


def test_the_budget_stops_the_chain(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([timed_out(35), ok()])
    result = ask(make_gateway(factory, client), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.TIMEOUT
    assert len(client.calls) == 1  # the second model was never tried
    assert usage(factory, "global") == 1  # and no slot was spent on it


def test_a_shorter_budget_from_config_is_respected(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([timed_out(8), ok()])
    ask(make_gateway(factory, client, chain=chain_with(total_budget_seconds=10)), user)
    assert [c.timeout for c in client.calls] == [10, 2]


# ---- no key, no client, no chain ----


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_or_empty_key(factory: SessionFactory, user: uuid.UUID, key: str | None) -> None:
    client = FakeClient([ok()])
    result = ask(make_gateway(factory, client, api_key=key), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.MODEL_UNAVAILABLE
    assert not client.calls and not ai_rows(factory) and usage(factory, "global") == 0


def test_no_client_and_no_chain(factory: SessionFactory, user: uuid.UUID) -> None:
    no_client = make_gateway(factory, None)
    no_chain = Gateway(
        api_key=SecretStr(API_KEY), chain=None, limits=limits_with(),
        session_factory=factory, client=FakeClient([ok()]),
    )  # fmt: skip
    for gateway in (no_client, no_chain):
        result = ask(gateway, user)
        assert isinstance(result, GatewayError)
        assert result.outcome is GatewayOutcome.MODEL_UNAVAILABLE
    assert usage(factory, "global") == 0


# ---- prompt size ----


def test_prompt_over_the_cap_is_refused_before_anything(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([ok()])
    gateway = make_gateway(factory, client, limits=limits_with(max_prompt_chars=100))
    result = ask(gateway, user, "x" * 101)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_INPUT
    assert not client.calls and not ai_rows(factory) and usage(factory, "global") == 0


def test_system_text_counts_toward_the_cap(factory: SessionFactory, user: uuid.UUID) -> None:
    gateway = make_gateway(factory, FakeClient([ok()]), limits=limits_with(max_prompt_chars=100))
    result = ask(gateway, user, "x" * 60, system="y" * 41)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_INPUT


def test_prompt_exactly_at_the_cap_is_sent(factory: SessionFactory, user: uuid.UUID) -> None:
    gateway = make_gateway(factory, FakeClient([ok()]), limits=limits_with(max_prompt_chars=100))
    assert isinstance(ask(gateway, user, "x" * 100), GatewayOk)


def test_non_string_prompt_is_bad_input(factory: SessionFactory, user: uuid.UUID) -> None:
    result = ask(make_gateway(factory, FakeClient([ok()])), user, 12345)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_INPUT


# ---- bad output, garbage from the client ----


def test_unusable_output_is_bad_output_with_no_fallback(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([ok("this is not json", 9, 3), ok('{"total": 1}')])
    result = ask(make_gateway(factory, client), user, response_model=Answer)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_OUTPUT
    assert len(client.calls) == 1
    (row,) = ai_rows(factory)
    assert (row.status, row.tokens_in, row.tokens_out) == ("error", 9, 3)


def test_valid_structured_output_is_parsed(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([ok('{"total": 3}')])
    result = ask(make_gateway(factory, client), user, response_model=Answer)
    assert isinstance(result, GatewayOk) and result.parsed == Answer(total=3)
    assert client.calls[0].has_schema


def test_wrong_shape_is_bad_output(factory: SessionFactory, user: uuid.UUID) -> None:
    result = ask(
        make_gateway(factory, FakeClient([ok('{"total": "many"}')])), user, response_model=Answer
    )
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_OUTPUT


def test_empty_text_is_bad_output(factory: SessionFactory, user: uuid.UUID) -> None:
    result = ask(make_gateway(factory, FakeClient([ok("   ")])), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_OUTPUT


@pytest.mark.parametrize("garbage", [None, "text", 42, {"text": "x"}, object()])
def test_garbage_from_the_client_never_raises(
    factory: SessionFactory, user: uuid.UUID, garbage: object
) -> None:
    result = ask(make_gateway(factory, FakeClient([Step(garbage)])), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_OUTPUT


def test_a_client_that_always_raises_never_raises(factory: SessionFactory, user: uuid.UUID) -> None:
    steps = [Step(raises=ValueError("x")), Step(raises=KeyError("y"))]
    result = ask(make_gateway(factory, FakeClient(steps)), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.MODEL_UNAVAILABLE


# ---- records: metadata only ----


def test_rows_hold_no_prompt_answer_or_cost(
    factory: SessionFactory, user: uuid.UUID, db_connection: Connection
) -> None:
    run_marker, answer_marker = "PROMPT-MARKER-Hapjeong-4800", "ANSWER-MARKER-Seongsu-9000"
    client = FakeClient([ok(answer_marker)])
    ask(make_gateway(factory, client), user, run_marker, system="SYSTEM-MARKER-xyz")
    dump = ""
    for table in ("ai_calls", "usage_daily"):
        for row in db_connection.execute(text(f"SELECT * FROM {table}")):  # noqa: S608  # fixed names
            dump += repr(tuple(row))
    for marker in (run_marker, answer_marker, "SYSTEM-MARKER", API_KEY):
        assert marker not in dump
    columns = {c["name"] for c in inspect(db_connection).get_columns("ai_calls")}
    assert not columns & {"prompt", "response", "text", "content"}
    assert db_connection.execute(text("SELECT est_cost_usd FROM ai_calls")).scalar() == 0


def test_run_id_is_stored(factory: SessionFactory, user: uuid.UUID) -> None:
    with factory() as db, db.begin():
        db.add(Run(user_id=user, question="q", mode="ask", lang="en"))
    with factory() as db:
        run_id = db.scalars(select(Run.id).where(Run.user_id == user)).one()
    ask(make_gateway(factory, FakeClient([ok()])), user, run_id=run_id)
    assert ai_rows(factory)[0].run_id == run_id


def test_usage_daily_is_incremented_for_user_and_global(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    ask(make_gateway(factory, FakeClient([ok()])), user)
    assert usage(factory, f"user:{user}") == 1 and usage(factory, "global") == 1


# ---- bookkeeping failures never change the result ----


def test_a_failed_ai_calls_write_does_not_change_the_answer(
    factory: SessionFactory, user: uuid.UUID, caplog: pytest.LogCaptureFixture
) -> None:
    opened = {"n": 0}

    def flaky() -> object:
        opened["n"] += 1
        if opened["n"] > 1:  # the cap reserve (1st) works; the ai_calls write (2nd) fails
            raise RuntimeError("database gone: " + API_KEY + " SQL-WITH-PROMPT-MARKER")
        return factory()

    caplog.set_level(logging.DEBUG)
    result = ask(make_gateway(flaky, FakeClient([ok("good answer")])), user)  # type: ignore[arg-type]
    assert isinstance(result, GatewayOk) and result.text == "good answer"
    assert "AI_RECORD_FAILED" in caplog.text
    assert API_KEY not in caplog.text and "PROMPT-MARKER" not in caplog.text


# ---- secrets ----


def test_the_key_is_nowhere(
    factory: SessionFactory, user: uuid.UUID, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    gateway = make_gateway(factory, FakeClient([server_error(), ok("answer")]))
    good = ask(gateway, user, "PROMPT-MARKER")
    bad = ask(make_gateway(factory, FakeClient([rate_limited(), rate_limited()])), user)
    for thing in (gateway, good, bad, repr(gateway._api_key), str(gateway._api_key)):
        assert API_KEY not in repr(thing)
    assert API_KEY not in caplog.text and "PROMPT-MARKER" not in caplog.text
    assert "answer" not in caplog.text  # the answer text is never logged


def test_log_lines_carry_only_metadata(
    factory: SessionFactory, user: uuid.UUID, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="indesk.ai")
    ask(make_gateway(factory, FakeClient([ok("x", 4, 2)])), user)
    (line,) = [r.getMessage() for r in caplog.records]
    assert line.startswith("ai model=gemini-2.5-flash outcome=ok ms=")
    assert "tokens_in=4 tokens_out=2 run=-" in line
