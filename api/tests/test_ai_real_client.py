"""The real Gemini client against httpx.MockTransport: request shape, failure mapping, the hard
deadline and the body cap. Nothing here touches the network, and nothing proves the request or
response shapes match the real API."""

import importlib.util
import json
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.ai.client import ClientFailure, ClientOk, ClientResult
from app.ai.real_client import (
    MAX_BODY_BYTES,
    GeminiRestClient,
    ListError,
    ListOk,
    list_text_models,
)  # fmt: skip
from app.core.enums import ModelFailure
from tests.fake_model_client import API_KEY, FakeClock

GEN = ["generateContent"]
GOOD = {
    "candidates": [{"content": {"parts": [{"text": "hel"}, {"text": "lo"}]}}],
    "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2, "thoughtsTokenCount": 4},
}


class Chunks(httpx.SyncByteStream):
    def __init__(self, chunks: list[bytes], on_chunk: Callable[[], None] | None = None) -> None:
        self.chunks, self.on_chunk, self.consumed = chunks, on_chunk, 0

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self.chunks:
            if self.on_chunk:
                self.on_chunk()
            self.consumed += 1
            yield chunk


def make(
    handler: Callable[[httpx.Request], httpx.Response], clock: Callable[[], float] | None = None
) -> GeminiRestClient:
    transport = httpx.MockTransport(handler)
    if clock is None:
        return GeminiRestClient(SecretStr(API_KEY), transport=transport)
    return GeminiRestClient(SecretStr(API_KEY), transport=transport, monotonic=clock)


def generate(client: GeminiRestClient, **kw: Any) -> ClientResult:
    args: dict[str, Any] = {
        "model": "gemini-2.5-flash", "prompt": "hi", "system": None, "response_schema": None,
        "max_output_tokens": 4096, "thinking_budget": 1024, "timeout": 5.0,
    }  # fmt: skip
    return client.generate(**{**args, **kw})


def json_response(data: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


# ---- request shape ----


def test_request_shape_and_key_in_header_only() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response(GOOD)

    schema = {"type": "object"}
    result = generate(make(handler), system="be brief", response_schema=schema)
    (request,) = seen
    assert request.method == "POST"
    assert request.url.path.endswith("/models/gemini-2.5-flash:generateContent")
    assert request.headers["x-goog-api-key"] == API_KEY
    assert API_KEY not in str(request.url) and API_KEY not in request.content.decode()
    body = json.loads(request.content)
    config = body["generationConfig"]
    assert config["maxOutputTokens"] == 4096
    assert config["thinkingConfig"] == {"thinkingBudget": 1024}
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"] == schema
    assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert body["contents"][0]["parts"][0]["text"] == "hi"
    assert result == ClientOk(text="hello", tokens_in=3, tokens_out=6)  # thinking tokens count out


def test_a_none_thinking_budget_sends_no_thinking_field() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return json_response(GOOD)

    generate(make(handler), thinking_budget=None)
    assert "thinkingConfig" not in seen[0]["generationConfig"]
    assert seen[0]["generationConfig"]["maxOutputTokens"] == 4096


def test_a_zero_thinking_budget_is_still_sent() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return json_response(GOOD)

    generate(make(handler), thinking_budget=0)
    assert seen[0]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert (
        "systemInstruction" not in seen[0]
        and "responseJsonSchema" not in seen[0]["generationConfig"]
    )


def test_a_thinking_level_is_sent_as_thinking_level() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return json_response(GOOD)

    generate(make(handler), thinking_budget=None, thinking_level="minimal")
    assert seen[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}


# ---- failure mapping ----


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, ModelFailure.RATE_LIMITED), (500, ModelFailure.SERVER_ERROR),
        (503, ModelFailure.SERVER_ERROR), (400, ModelFailure.OTHER), (401, ModelFailure.OTHER),
        (403, ModelFailure.OTHER), (404, ModelFailure.OTHER),
    ],
)  # fmt: skip
def test_http_status_maps_to_a_failure_kind(status: int, kind: ModelFailure) -> None:
    result = generate(make(lambda r: httpx.Response(status, text="SECRET-BODY " + API_KEY)))
    assert result == ClientFailure(kind=kind)
    assert "SECRET-BODY" not in repr(result) and API_KEY not in repr(result)


def test_timeout_and_transport_errors() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("took too long: " + API_KEY)

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused " + str(request.url))

    def odd(request: httpx.Request) -> httpx.Response:
        raise ValueError("anything")

    assert generate(make(slow)) == ClientFailure(kind=ModelFailure.TIMEOUT)
    assert generate(make(refused)) == ClientFailure(kind=ModelFailure.OTHER)
    assert generate(make(odd)) == ClientFailure(kind=ModelFailure.OTHER)


@pytest.mark.parametrize(
    "body",
    [
        b"not json", b"[]", b"{}", b'{"candidates": []}', b'{"candidates": [{}]}',
        b'{"candidates": [{"content": {"parts": []}}]}',
        b'{"candidates": [{"content": {"parts": [{"text": "  "}]}}]}',
        b'{"candidates": [{"content": {"parts": "x"}}]}',
    ],
)  # fmt: skip
def test_unreadable_answers_are_bad_response(body: bytes) -> None:
    result = generate(make(lambda r: httpx.Response(200, content=body)))
    assert result == ClientFailure(kind=ModelFailure.BAD_RESPONSE)


def test_thought_parts_are_not_part_of_the_answer() -> None:
    data = {"candidates": [{"content": {"parts": [
        {"text": "private reasoning", "thought": True}, {"text": "answer"}]}}]}  # fmt: skip
    assert generate(make(lambda r: json_response(data))) == ClientOk(text="answer")


# ---- the body cap and the total deadline ----


def test_a_body_over_the_cap_stops_the_read() -> None:
    stream = Chunks([b"x" * 100_000] * 40)  # 4 MB on offer
    result = generate(make(lambda r: httpx.Response(200, stream=stream)))
    assert result == ClientFailure(kind=ModelFailure.BAD_RESPONSE)
    assert stream.consumed * 100_000 <= MAX_BODY_BYTES + 100_000  # it stopped reading


def test_a_declared_length_over_the_cap_is_refused_without_reading() -> None:
    stream = Chunks([b"x"])
    headers = {"content-length": str(MAX_BODY_BYTES + 1)}
    result = generate(make(lambda r: httpx.Response(200, headers=headers, stream=stream)))
    assert result == ClientFailure(kind=ModelFailure.BAD_RESPONSE)
    assert stream.consumed == 0


def test_a_slow_trickle_is_cut_at_the_total_deadline() -> None:
    clock = FakeClock()
    stream = Chunks([b" "] * 50, on_chunk=lambda: clock.advance(2))  # 2 s per chunk, deadline 5 s
    result = generate(make(lambda r: httpx.Response(200, stream=stream), clock), timeout=5.0)
    assert result == ClientFailure(kind=ModelFailure.TIMEOUT)
    assert stream.consumed <= 3


def test_a_hung_server_cannot_outlast_the_deadline() -> None:
    release = threading.Event()

    class Hang(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            release.wait(10)  # a read that never returns, until the test ends
            yield b""

    client = make(lambda r: httpx.Response(200, stream=Hang()))
    started = time.monotonic()
    try:
        result = generate(client, timeout=0.3)
        assert result == ClientFailure(kind=ModelFailure.TIMEOUT)
        assert time.monotonic() - started < 3
    finally:
        release.set()


def test_the_client_repr_hides_the_key() -> None:
    assert API_KEY not in repr(make(lambda r: json_response(GOOD)))


# ---- listing models ----


def test_list_models_filters_pages_and_strips_the_prefix() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "pageToken" not in request.url.params:
            return json_response({
                "models": [
                    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": GEN},
                    {"name": "models/embed-x", "supportedGenerationMethods": ["embedContent"]},
                ],
                "nextPageToken": "p2",
            })  # fmt: skip
        return json_response({"models": [
            {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": GEN}
        ]})  # fmt: skip

    result = list_text_models(SecretStr(API_KEY), transport=httpx.MockTransport(handler))
    assert result == ListOk(names=["gemini-2.5-flash", "gemini-2.5-flash-lite"])
    assert len(seen) == 2
    for request in seen:
        assert request.headers["x-goog-api-key"] == API_KEY
        assert API_KEY not in str(request.url)


def test_list_models_errors_carry_only_a_status_or_class_name() -> None:
    forbidden = httpx.MockTransport(lambda r: httpx.Response(403, text="SECRET-BODY " + API_KEY))
    assert list_text_models(SecretStr(API_KEY), transport=forbidden) == ListError(label="HTTP 403")

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("could not reach " + str(request.url) + API_KEY)

    result = list_text_models(SecretStr(API_KEY), transport=httpx.MockTransport(boom))
    assert result == ListError(label="ConnectError")
    garbage = httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>"))
    assert list_text_models(SecretStr(API_KEY), transport=garbage) == ListError(
        label="bad response"
    )


# ---- scripts/list_models.py ----


def load_script() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / "list_models.py"
    spec = importlib.util.spec_from_file_location("list_models_script", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_script(
    env: dict[str, str], transport: httpx.MockTransport | None = None
) -> tuple[int, str]:
    lines: list[str] = []
    code = load_script().main(env, lines.append, transport=transport)
    return code, "\n".join(lines)


def test_script_says_clearly_when_the_key_is_missing() -> None:
    for env in ({}, {"GEMINI_API_KEY": ""}, {"GEMINI_API_KEY": "  "}):
        code, out = run_script(env)
        assert code == 2 and "GEMINI_API_KEY is not set" in out


def test_script_prints_names_and_checks_both_chains() -> None:
    models = [
        {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]}
    ]
    code, out = run_script(
        {"GEMINI_API_KEY": API_KEY},
        httpx.MockTransport(lambda r: json_response({"models": models})),
    )
    assert code == 0 and API_KEY not in out
    assert "light chain:" in out and "main chain:" in out
    assert out.count("gemini-3.8-flash: listed") == 2  # it sits in both chains
    assert "gemini-3.5-flash-lite: NOT LISTED" in out


def test_script_error_output_is_status_only() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(403, text="SECRET-BODY " + API_KEY))
    code, out = run_script({"GEMINI_API_KEY": API_KEY}, transport)
    assert code == 1 and out == "Could not list models: HTTP 403"
