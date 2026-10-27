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


class EmbedOk(BaseModel):
    """One vector per text, in the order of the texts. The client has checked the count and size."""

    model_config = ConfigDict(frozen=True)

    vectors: list[list[float]] = Field(repr=False)
    tokens_in: NonNegativeInt = 0


EmbedResult = EmbedOk | ClientFailure


def estimate_tokens(texts: list[str]) -> int:
    """A rough input-token count for a cost estimate, used when the API reports none. NOT
    MEASURED: ASCII counts a quarter token a character, any other character one token (an upper
    bound for Korean and Japanese)."""
    ascii_chars = sum(1 for text in texts for ch in text if ch.isascii())
    other = sum(len(text) for text in texts) - ascii_chars
    return -(-ascii_chars // 4) + other


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

    def embed(
        self,
        *,
        model: str,
        texts: list[str],
        task_type: str,
        dimensions: int,
        timeout: float,
    ) -> EmbedResult:
        """One batch request to one embedding model. `task_type` is RETRIEVAL_DOCUMENT or
        RETRIEVAL_QUERY. A wrong vector count or size is a BAD_RESPONSE failure."""
        ...
