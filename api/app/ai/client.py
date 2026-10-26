"""The one interface the gateway talks to. The real client is real_client.py; tests use a fake.

A client never raises for a model problem: it returns ClientOk or ClientFailure. The prompt and the
answer are kept out of repr, so a log line or a failed assert cannot print them."""

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from app.core.enums import FailureKind, ModelFailure


class ClientOk(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(repr=False)
    tokens_in: NonNegativeInt = 0
    tokens_out: NonNegativeInt = 0


class ClientFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ModelFailure
    detail: FailureKind | None = None  # the cause behind `kind`, when the client knows it

    # `kind` is what a failure IS (the chain logic reads it); `detail` is only its recorded cause.
    # Equality and hash use `kind` alone, so a client that learns to say more never changes whether
    # two failures are the same failure. Tests that care about the cause read `.detail`.
    def __eq__(self, other: object) -> bool:
        return isinstance(other, ClientFailure) and self.kind == other.kind

    def __hash__(self) -> int:
        return hash(self.kind)


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
        thinking_level: str | None = None,
    ) -> ClientResult:
        """One request to one model. `timeout` is a hard limit on the whole attempt in seconds."""
        ...
