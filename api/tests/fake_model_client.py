"""A scripted stand-in for the Gemini client, and a clock tests can move. No network, no sleeping.

Each step of the script is one request: a result to return, an exception to raise, or garbage to
return. A step can also move the fake clock, to model a slow answer."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.ai.client import ClientFailure, ClientOk, ClientResult
from app.core.enums import ModelFailure

API_KEY = "AIzaSy-FAKE-TEST-KEY-0123456789"  # not a real key


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class Step:
    result: object = None
    raises: Exception | None = None
    elapsed: float = 0.0


def ok(text: str = "{}", tokens_in: int = 10, tokens_out: int = 5, elapsed: float = 0.0) -> Step:
    return Step(ClientOk(text=text, tokens_in=tokens_in, tokens_out=tokens_out), elapsed=elapsed)


def fail(kind: ModelFailure, elapsed: float = 0.0) -> Step:
    return Step(ClientFailure(kind=kind), elapsed=elapsed)


def rate_limited() -> Step:
    return fail(ModelFailure.RATE_LIMITED)


def server_error() -> Step:
    return fail(ModelFailure.SERVER_ERROR)


def timed_out(elapsed: float) -> Step:
    return fail(ModelFailure.TIMEOUT, elapsed)


@dataclass
class Call:
    model: str
    max_output_tokens: int
    thinking_budget: int | None
    timeout: float
    has_schema: bool
    prompt_chars: int


@dataclass
class FakeClient:
    """Pops one step per generate() call. Running out of steps is a test bug and raises."""

    steps: list[Step]
    clock: FakeClock | None = None
    calls: list[Call] = field(default_factory=list)

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
        self.calls.append(
            Call(
                model,
                max_output_tokens,
                thinking_budget,
                timeout,
                response_schema is not None,
                len(prompt) + len(system or ""),
            )  # fmt: skip
        )
        step = self.steps.pop(0)
        if self.clock is not None:
            self.clock.advance(step.elapsed)
        if step.raises is not None:
            raise step.raises
        return step.result  # type: ignore[return-value]  # a step may hold garbage on purpose


def new_user_id() -> uuid.UUID:
    return uuid.uuid4()
