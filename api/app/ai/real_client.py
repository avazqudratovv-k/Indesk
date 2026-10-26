"""The only code that talks to Google, over plain httpx REST.

NOTHING HERE HAS RUN AGAINST REAL GEMINI: the request fields and the response shape are written
from memory of the public API and are checked only against test doubles. scripts/list_models.py
and the first manual call must confirm them.

Safety rules kept here:
- The key travels in the x-goog-api-key header only, never in a URL, a log line or a result.
- Every attempt has a TOTAL wall deadline (a worker thread joined with the deadline, plus a check
  between body chunks), so a slow trickle cannot outlast the budget.
- The body read is capped at MAX_BODY_BYTES.
- No exception text, URL or response body is ever kept or logged: only a fixed failure kind."""

import json
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.ai.client import ClientFailure, ClientOk, ClientResult
from app.core.enums import ModelFailure

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_BODY_BYTES = 1024 * 1024  # about 1 MB; a reply that big is not an answer we want
LIST_TIMEOUT_SECONDS = 20.0
LIST_MAX_PAGES = 10


def _declared_length(response: httpx.Response) -> int | None:
    try:
        return int(response.headers["content-length"])
    except (KeyError, ValueError):
        return None


def _read_bounded(
    response: httpx.Response, *, deadline: float, mono: Callable[[], float], stop: threading.Event
) -> bytes | ModelFailure:
    """Read the body, giving up at the deadline (TIMEOUT) or past MAX_BODY_BYTES (BAD_RESPONSE)."""
    declared = _declared_length(response)
    if declared is not None and declared > MAX_BODY_BYTES:
        return ModelFailure.BAD_RESPONSE
    body = bytearray()
    for chunk in response.iter_bytes():
        if stop.is_set() or mono() > deadline:
            return ModelFailure.TIMEOUT
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            return ModelFailure.BAD_RESPONSE
    if mono() > deadline:
        return ModelFailure.TIMEOUT
    return bytes(body)


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _parse_answer(body: bytes) -> ClientResult:
    """Text and token counts from a generateContent answer; anything else is BAD_RESPONSE."""
    try:
        data = json.loads(body)
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(
            part["text"]
            for part in parts
            if isinstance(part.get("text"), str) and not part.get("thought")
        )
        usage = data.get("usageMetadata") or {}
        tokens_in = _count(usage.get("promptTokenCount"))
        # Thinking tokens are billed as output, so they count here (unverified field name).
        tokens_out = _count(usage.get("candidatesTokenCount")) + _count(
            usage.get("thoughtsTokenCount")
        )
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return ClientFailure(kind=ModelFailure.BAD_RESPONSE)
    if not text.strip():
        return ClientFailure(kind=ModelFailure.BAD_RESPONSE)
    return ClientOk(text=text, tokens_in=tokens_in, tokens_out=tokens_out)


def _status_failure(status: int) -> ModelFailure | None:
    if status == 200:
        return None
    if status == 429:
        return ModelFailure.RATE_LIMITED
    if status >= 500:
        return ModelFailure.SERVER_ERROR
    return ModelFailure.OTHER


class GeminiRestClient:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        transport: httpx.BaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        base_url: str = BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._mono = monotonic
        self._base_url = base_url

    def __repr__(self) -> str:
        return "GeminiRestClient(api_key=**********)"

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None,
        response_schema: dict[str, Any] | None,
        max_output_tokens: int,
        thinking_budget: int | None,
        timeout: float,
        thinking_level: str | None = None,
    ) -> ClientResult:
        generation: dict[str, Any] = {"maxOutputTokens": max_output_tokens}
        if thinking_budget is not None:  # None: leave the field out; 0 is sent as 0
            generation["thinkingConfig"] = {"thinkingBudget": thinking_budget}
        if thinking_level is not None:  # gemini-3.x; never sent together with a budget
            generation["thinkingConfig"] = {"thinkingLevel": thinking_level}
        if response_schema is not None:
            generation["responseMimeType"] = "application/json"
            generation["responseJsonSchema"] = response_schema
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation,
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{self._base_url}/models/{model}:generateContent"
        return self._run_with_deadline(url, json.dumps(payload).encode(), timeout)

    def _run_with_deadline(self, url: str, payload: bytes, timeout: float) -> ClientResult:
        """Run the attempt in a worker thread and stop waiting at the deadline."""
        outcome: list[ClientResult] = []
        stop = threading.Event()

        def work() -> None:
            outcome.append(self._attempt(url, payload, timeout, stop))

        try:
            worker = threading.Thread(target=work, daemon=True)
            worker.start()
        except RuntimeError:
            return ClientFailure(kind=ModelFailure.OTHER)
        worker.join(timeout)
        if worker.is_alive():
            stop.set()  # the worker stops at its next chunk or when its own timeouts fire
            return ClientFailure(kind=ModelFailure.TIMEOUT)
        return outcome[0] if outcome else ClientFailure(kind=ModelFailure.OTHER)

    def _attempt(
        self, url: str, payload: bytes, timeout: float, stop: threading.Event
    ) -> ClientResult:
        deadline = self._mono() + timeout
        headers = {
            "x-goog-api-key": self._api_key.get_secret_value(),
            "content-type": "application/json",
        }
        try:
            with (
                httpx.Client(transport=self._transport, timeout=httpx.Timeout(timeout)) as http,
                http.stream("POST", url, headers=headers, content=payload) as response,
            ):
                failure = _status_failure(response.status_code)
                if failure is not None:
                    return ClientFailure(kind=failure)
                body = _read_bounded(response, deadline=deadline, mono=self._mono, stop=stop)
        except httpx.TimeoutException:
            return ClientFailure(kind=ModelFailure.TIMEOUT)
        except Exception:  # noqa: BLE001  # any transport error; its text could hold the URL
            return ClientFailure(kind=ModelFailure.OTHER)
        if isinstance(body, ModelFailure):
            return ClientFailure(kind=body)
        return _parse_answer(body)


# ---- listing models, for scripts/list_models.py only ----


class ListOk(BaseModel):
    model_config = ConfigDict(frozen=True)

    names: list[str]


class ListError(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str = Field(description="'HTTP <status>', an exception class name, or a fixed phrase")


def _page_names(body: bytes) -> tuple[list[str], str | None]:
    data = json.loads(body)
    names: list[str] = []
    for entry in data.get("models", []):
        methods = entry.get("supportedGenerationMethods", [])
        if "generateContent" in methods and isinstance(entry.get("name"), str):
            names.append(entry["name"].removeprefix("models/"))
    token = data.get("nextPageToken")
    return names, token if isinstance(token, str) and token else None


def list_text_models(
    api_key: SecretStr,
    *,
    transport: httpx.BaseTransport | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> ListOk | ListError:
    """Names of the models this key can use for text generation. Never raises; on failure the
    label is only an HTTP status, an exception class name or a fixed phrase."""
    deadline = monotonic() + LIST_TIMEOUT_SECONDS
    headers = {"x-goog-api-key": api_key.get_secret_value()}
    names: list[str] = []
    token: str | None = None
    try:
        with httpx.Client(transport=transport, timeout=httpx.Timeout(LIST_TIMEOUT_SECONDS)) as http:
            for _ in range(LIST_MAX_PAGES):
                params = {"pageSize": "100", **({"pageToken": token} if token else {})}
                with http.stream(
                    "GET", f"{BASE_URL}/models", headers=headers, params=params
                ) as response:
                    if response.status_code != 200:
                        return ListError(label=f"HTTP {response.status_code}")
                    body = _read_bounded(
                        response, deadline=deadline, mono=monotonic, stop=threading.Event()
                    )
                if isinstance(body, ModelFailure):
                    return ListError(
                        label="timeout" if body is ModelFailure.TIMEOUT else "bad response"
                    )
                page, token = _page_names(body)
                names += page
                if token is None:
                    break
    except (ValueError, KeyError, TypeError, AttributeError):
        return ListError(label="bad response")
    except Exception as error:  # noqa: BLE001  # only the class name leaves this function
        return ListError(label=type(error).__name__)
    return ListOk(names=sorted(set(names)))
