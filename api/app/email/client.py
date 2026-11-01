"""The one interface the email job talks to. The real client is resend_client.py; tests use a fake.

A client never raises: it returns EmailOk or EmailFailure. A message keeps its address and body out
of repr, so a log line or a failed assert cannot print them."""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class EmailFailureKind(StrEnum):
    """Why a send failed. `retryable` ones may work later; the others will not."""

    RATE_LIMITED = "rate_limited"  # HTTP 429
    SERVER_ERROR = "server_error"  # HTTP 5xx
    CONFLICT = "conflict"  # HTTP 409: the same idempotency key is still in flight
    TIMEOUT = "timeout"
    TRANSPORT = "transport"  # connection error, TLS error, anything below HTTP
    REJECTED = "rejected"  # any other 4xx: a bad key, an unverified domain, a bad request


RETRYABLE = frozenset(
    {
        EmailFailureKind.RATE_LIMITED,
        EmailFailureKind.SERVER_ERROR,
        EmailFailureKind.CONFLICT,
        EmailFailureKind.TIMEOUT,
        EmailFailureKind.TRANSPORT,
    }
)


class EmailMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    to: str = Field(repr=False)
    subject: str = Field(repr=False)
    text: str = Field(repr=False)
    html: str = Field(repr=False)
    # Sent as the Idempotency-Key header, so a retry after a lost answer cannot send twice.
    idempotency_key: str = Field(min_length=1, max_length=256)


class EmailOk(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: str | None = None  # the provider's id, when it was readable


class EmailFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: EmailFailureKind
    status: int | None = None  # the HTTP status, when there was one (metadata only)

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE


EmailResult = EmailOk | EmailFailure


class EmailClient(Protocol):
    def send(self, message: EmailMessage) -> EmailResult: ...
