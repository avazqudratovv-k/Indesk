"""The one interface the gateway talks to. The real client is real_client.py; tests use a fake.

A client never raises for a model problem: it returns ClientOk or ClientFailure. The prompt and the
answer are kept out of repr, so a log line or a failed assert cannot print them."""

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from app.core.enums import ModelFailure


class ClientOk(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(repr=False)
    tokens_in: NonNegativeInt = 0
    tokens_out: NonNegativeInt = 0


class ClientFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ModelFailure


ClientResult = ClientOk | ClientFailure


class ModelClient(Protocol):
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
    ) -> ClientResult:
        """One request to one model. `timeout` is a hard limit on the whole attempt in seconds."""
        ...
