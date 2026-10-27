"""The embedding path (P14a part 2): the REST client's request and parsing, the config, and the
gateway's rules (one model, retries only, call caps, ai_calls rows, cost). No network."""

import json
import uuid
from typing import Any

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import Connection

from app.ai.caps import SessionFactory
from app.ai.client import ClientFailure, EmbedOk, estimate_tokens
from app.ai.config import EmbedSpec, load_model_chains
from app.ai.gateway import EmbedGatewayOk, Gateway, GatewayError
from app.ai.real_client import GeminiRestClient
from app.core.enums import (
    AiCallStatus,
    AiPurpose,
    EmbedTask,
    FailureKind,
    GatewayOutcome,
    ModelFailure,
)
from tests.ai_helpers import ai_rows, factory_for, limits_with, make_gateway, new_user, usage
from tests.fake_model_client import API_KEY, FakeClient, Step, fail, rate_limited, server_error

DIM = 768


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


@pytest.fixture
def user(factory: SessionFactory) -> uuid.UUID:
    return new_user(factory)


def vectors(count: int, size: int = DIM) -> dict[str, Any]:
    return {"embeddings": [{"values": [0.5] * size} for _ in range(count)]}


def rest(handler: Any) -> GeminiRestClient:
    return GeminiRestClient(SecretStr(API_KEY), transport=httpx.MockTransport(handler))


def embed(client: GeminiRestClient, texts: list[str]) -> Any:
    return client.embed(
        model="gemini-embedding-2", texts=texts, task_type="RETRIEVAL_DOCUMENT",
        dimensions=DIM, timeout=5.0,
    )  # fmt: skip


# ---- config ----


def test_models_toml_has_one_embed_model_with_768_dimensions() -> None:
    embed_chain = load_model_chains().embed
    assert embed_chain is not None
    assert embed_chain.spec.name == "gemini-embedding-2"
    assert embed_chain.spec.dimensions == DIM
    assert embed_chain.total_budget_seconds == 35


def test_the_embed_model_is_one_model_not_a_chain(tmp_path: Any) -> None:
    from app.ai.config import _ModelsFile  # noqa: PLC0415

    spec = {"name": "a", "timeout_seconds": 1, "dimensions": 768, "attempts": 1, "batch_size": 1}
    base = {"total_budget_seconds": 35, "light": [], "main": []}
    with pytest.raises(ValidationError):
        _ModelsFile.model_validate({**base, "embed": [spec, {**spec, "name": "b"}]})


def test_attempts_and_batch_size_are_bounded() -> None:
    ok = {"name": "a", "timeout_seconds": 1, "dimensions": 768}
    EmbedSpec(**ok, attempts=3, batch_size=100)
    for bad in ({"attempts": 4, "batch_size": 1}, {"attempts": 1, "batch_size": 101}):
        with pytest.raises(ValidationError):
            EmbedSpec(**ok, **bad)


# ---- the REST client ----


def test_the_request_shape_and_the_key_in_the_header_only() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=vectors(2))

    result = embed(rest(handler), ["alpha", "beta"])
    assert isinstance(result, EmbedOk) and len(result.vectors) == 2
    request = seen[0]
    assert request.url.path.endswith("/models/gemini-embedding-2:batchEmbedContents")
    assert API_KEY not in str(request.url) and request.headers["x-goog-api-key"] == API_KEY
    first = json.loads(request.content)["requests"][0]
    assert first["model"] == "models/gemini-embedding-2"
    assert first["taskType"] == "RETRIEVAL_DOCUMENT" and first["outputDimensionality"] == DIM
    assert first["content"]["parts"] == [{"text": "alpha"}]


def test_tokens_are_the_apis_own_when_given_else_an_estimate() -> None:
    given = {**vectors(1), "usageMetadata": {"promptTokenCount": 9}}
    assert embed(rest(lambda r: httpx.Response(200, json=given)), ["x"]).tokens_in == 9
    got = embed(rest(lambda r: httpx.Response(200, json=vectors(1))), ["abcd" * 10])
    assert got.tokens_in == estimate_tokens(["abcd" * 10]) == 10


@pytest.mark.parametrize(
    "body",
    [vectors(1), vectors(2, size=10), vectors(2, size=DIM + 1), {"embeddings": [{}, {}]},
     {"nothing": 1}, {"embeddings": [{"values": ["a"] * DIM}] * 2}],
    ids=["too-few", "wrong-size", "too-long", "no-values", "no-key", "not-numbers"],
)  # fmt: skip
def test_a_wrong_count_or_size_is_a_bad_response(body: dict[str, Any]) -> None:
    got = embed(rest(lambda r: httpx.Response(200, json=body)), ["a", "b"])
    assert got == ClientFailure(kind=ModelFailure.BAD_RESPONSE)
    assert got.detail is FailureKind.BAD_JSON


def test_http_errors_map_like_generate() -> None:
    assert embed(rest(lambda r: httpx.Response(429)), ["a"]).kind is ModelFailure.RATE_LIMITED
    assert embed(rest(lambda r: httpx.Response(503)), ["a"]).kind is ModelFailure.SERVER_ERROR
    got = embed(rest(lambda r: httpx.Response(404)), ["a"])
    assert (got.kind, got.detail) == (ModelFailure.OTHER, FailureKind.HTTP_404)


# ---- the gateway ----


def gateway(factory: SessionFactory, client: FakeClient, **limits: float) -> Gateway:
    return make_gateway(factory, client, limits=limits_with(**limits))


def run_embed(gw: Gateway, user: uuid.UUID, texts: list[str] | None = None) -> Any:
    return gw.embed(texts or ["hello"], task=EmbedTask.DOCUMENT, user_id=user)


def test_a_good_batch_is_recorded_with_purpose_embed_and_a_cost(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([])
    result = run_embed(gateway(factory, client), user, ["abcd" * 1000])
    assert isinstance(result, EmbedGatewayOk) and len(result.vectors) == 1
    assert client.embed_calls[0].task_type == "RETRIEVAL_DOCUMENT"
    (row,) = ai_rows(factory)
    assert (row.purpose, row.status, row.model) == ("embed", "ok", "test-embed")
    assert (row.tokens_in, row.tokens_out, row.attempt) == (1000, 0, 1)
    assert float(row.est_cost_usd) == pytest.approx(1000 * 0.20 / 1_000_000)


def test_a_query_uses_the_query_task_type(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([])
    gateway(factory, client).embed(["q"], task=EmbedTask.QUERY, user_id=user)
    assert client.embed_calls[0].task_type == "RETRIEVAL_QUERY"


def test_texts_are_split_in_batches_of_batch_size(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([])
    result = run_embed(gateway(factory, client), user, [f"t{i}" for i in range(70)])
    assert isinstance(result, EmbedGatewayOk) and len(result.vectors) == 70
    assert [len(c.texts) for c in client.embed_calls] == [32, 32, 6]
    assert len(ai_rows(factory)) == 3


def test_a_failure_is_retried_on_the_same_model_only(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([], embed_steps=[server_error()])
    result = run_embed(gateway(factory, client), user)
    assert isinstance(result, EmbedGatewayOk) and result.attempts == 2
    assert {c.model for c in client.embed_calls} == {"test-embed"}
    first, second = ai_rows(factory)
    assert (first.status, first.attempt, first.failure_kind) == ("error", 1, "http_5xx")
    assert (second.status, second.attempt) == ("ok", 2)


def test_when_every_attempt_fails_there_is_no_other_model(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([], embed_steps=[rate_limited(), rate_limited()])
    result = run_embed(gateway(factory, client), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BUSY
    assert len(client.embed_calls) == 2 and {c.model for c in client.embed_calls} == {"test-embed"}
    assert [r.status for r in ai_rows(factory)] == ["rate_limited", "rate_limited"]


def test_a_refused_request_is_not_retried(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([], embed_steps=[fail(ModelFailure.OTHER, detail=FailureKind.HTTP_403)])
    result = run_embed(gateway(factory, client), user)
    assert isinstance(result, GatewayError)
    assert result.outcome is GatewayOutcome.MODEL_UNAVAILABLE and len(client.embed_calls) == 1


def test_a_bad_response_stops_without_a_retry(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([], embed_steps=[fail(ModelFailure.BAD_RESPONSE)])
    result = run_embed(gateway(factory, client), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_OUTPUT
    assert len(client.embed_calls) == 1


def test_wrong_vectors_from_a_client_that_did_not_check_are_refused(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    short = Step(EmbedOk(vectors=[[0.1] * 5], tokens_in=1))
    client = FakeClient([], embed_steps=[short])
    result = run_embed(gateway(factory, client), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_OUTPUT
    assert ai_rows(factory)[0].status == AiCallStatus.ERROR.value


def test_embedding_requests_count_toward_the_call_caps(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([])
    gw = gateway(factory, client, daily_calls_per_user=1)
    assert isinstance(run_embed(gw, user), EmbedGatewayOk)
    refused = run_embed(gw, user)
    assert isinstance(refused, GatewayError) and refused.outcome is GatewayOutcome.CAP_REACHED
    assert refused.cap_scope == "user" and len(client.embed_calls) == 1
    assert usage(factory, f"user:{user}") == 1


def test_bad_input_and_no_key_send_nothing(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([])
    gw = gateway(factory, client)
    for bad in ([], ["  "], ["x" * 50_000]):
        got = gw.embed(bad, task=EmbedTask.DOCUMENT, user_id=user)
        assert isinstance(got, GatewayError) and got.outcome is GatewayOutcome.BAD_INPUT
    keyless = make_gateway(factory, client, api_key=None)
    got = run_embed(keyless, user)
    assert isinstance(got, GatewayError) and got.outcome is GatewayOutcome.MODEL_UNAVAILABLE
    assert client.embed_calls == []


def test_a_client_that_raises_is_a_failure_not_a_crash(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([], embed_steps=[Step(raises=RuntimeError("boom"))] * 2)
    got = run_embed(gateway(factory, client), user)
    assert isinstance(got, GatewayError)
    assert {r.purpose for r in ai_rows(factory)} == {AiPurpose.EMBED.value}


def test_embedding_tokens_are_not_in_the_run_token_budget(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    from app.runs import store  # noqa: PLC0415
    from tests.runs_helpers import make_world  # noqa: PLC0415

    world = make_world(factory)
    client = FakeClient([])
    gw = gateway(factory, client)
    gw.embed(["abcd" * 500], task=EmbedTask.DOCUMENT, user_id=world.user_id, run_id=world.run_id)
    with factory() as db:
        assert store.run_tokens(db, world.run_id) == 0
        assert store.run_embed_tokens(db, world.run_id) == 500


# ---- scripts/list_models.py --embed ----


def test_list_models_embed_mode_checks_the_configured_embedding_model() -> None:
    import importlib.util  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    path = Path(__file__).resolve().parents[1] / "scripts" / "list_models.py"
    spec = importlib.util.spec_from_file_location("list_models_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def handler(request: httpx.Request) -> httpx.Response:
        models = [
            {"name": "models/gemini-embedding-2", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
        ]
        return httpx.Response(200, json={"models": models})

    lines: list[str] = []
    code = module.main(
        {"GEMINI_API_KEY": API_KEY}, lines.append, transport=httpx.MockTransport(handler),
        embed=True,
    )  # fmt: skip
    text = "\n".join(lines)
    assert code == 0 and "gemini-embedding-2: listed" in text
    assert "gemini-3.8-flash" not in text and API_KEY not in text
