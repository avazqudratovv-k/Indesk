"""ai_calls.failure_kind: a closed code for why a model request failed. Never a response body, a
URL, a header or a key. The real client is driven through httpx.MockTransport; the gateway writes
the rows."""

import uuid
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.ai.caps import SessionFactory
from app.ai.client import ClientFailure
from app.ai.config import ModelChains
from app.ai.gateway import Gateway
from app.ai.real_client import GeminiRestClient
from app.core.enums import AiCallStatus, AiPurpose, FailureKind, ModelFailure
from app.db.models import AiCall
from tests.ai_helpers import TEST_CHAIN, ai_rows, factory_for, limits_with, make_gateway, new_user
from tests.fake_model_client import API_KEY, FakeClient, fail, ok, rate_limited
from tests.test_ai_real_client import generate, make

BODY = "SECRET-BODY " + API_KEY


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


@pytest.fixture
def user(factory: SessionFactory) -> uuid.UUID:
    return new_user(factory)


def ask(gateway: Gateway, user: uuid.UUID) -> None:
    gateway.ask("hello", purpose=AiPurpose.ROUTE, user_id=user)


# ---- the real client names the cause ----


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        (400, FailureKind.HTTP_400),
        (401, FailureKind.HTTP_401),
        (403, FailureKind.HTTP_403),
        (404, FailureKind.HTTP_404),
        (418, FailureKind.HTTP_4XX),
        (422, FailureKind.HTTP_4XX),
        (500, FailureKind.HTTP_5XX),
        (503, FailureKind.HTTP_5XX),
        (429, None),  # the call status already says rate_limited
    ],
)
def test_http_status_gives_a_cause(status: int, detail: FailureKind | None) -> None:
    result = generate(make(lambda r: httpx.Response(status, text=BODY)))
    assert isinstance(result, ClientFailure) and result.detail is detail


def test_transport_error_and_unreadable_answers_give_a_cause() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom " + str(request.url))

    result = generate(make(broken))
    assert isinstance(result, ClientFailure) and result.detail is FailureKind.TRANSPORT
    result = generate(make(lambda r: httpx.Response(200, text="not json")))
    assert isinstance(result, ClientFailure) and result.detail is FailureKind.BAD_JSON


def test_a_body_over_the_cap_is_too_large() -> None:
    from app.ai.real_client import MAX_BODY_BYTES  # noqa: PLC0415

    big = httpx.Response(200, content=b"x" * (MAX_BODY_BYTES + 1))
    result = generate(make(lambda r: big))
    assert isinstance(result, ClientFailure) and result.detail is FailureKind.TOO_LARGE


# ---- the gateway stores it ----


def test_the_gateway_stores_the_cause_of_each_failed_attempt(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient(
        [fail(ModelFailure.OTHER, detail=FailureKind.HTTP_400), ok()]
    )  # a 400, then the fallback answers
    ask(make_gateway(factory, client), user)
    first, second = ai_rows(factory)
    assert (first.status, first.failure_kind) == (AiCallStatus.ERROR, "http_400")
    assert (second.status, second.failure_kind) == (AiCallStatus.OK, None)


def test_a_failure_without_a_named_cause_gets_the_default_for_its_kind(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient(
        [
            fail(ModelFailure.SERVER_ERROR),
            fail(ModelFailure.OTHER),
        ]
    )
    ask(make_gateway(factory, client), user)
    assert [r.failure_kind for r in ai_rows(factory)] == ["http_5xx", "other"]


def test_rate_limit_and_timeout_have_no_cause_beyond_their_status(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    client = FakeClient([rate_limited(), fail(ModelFailure.TIMEOUT)])
    ask(make_gateway(factory, client), user)
    rows = ai_rows(factory)
    assert [r.status for r in rows] == [AiCallStatus.RATE_LIMITED, AiCallStatus.TIMEOUT]
    assert [r.failure_kind for r in rows] == [None, None]


def test_a_client_that_raises_is_stored_as_other(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([])  # running out of steps makes generate() raise IndexError
    ask(make_gateway(factory, client), user)
    assert [r.failure_kind for r in ai_rows(factory)] == ["other", "other"]  # both models


# ---- nothing but a code is stored ----


@pytest.mark.parametrize("status", [400, 401, 403, 404, 418, 500])
def test_a_failing_real_call_stores_no_body_no_key_no_url(
    factory: SessionFactory, user: uuid.UUID, status: int
) -> None:
    client = GeminiRestClient(
        SecretStr(API_KEY),
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text=BODY)),
    )
    gateway = Gateway(
        api_key=SecretStr(API_KEY),
        chains=ModelChains(light=TEST_CHAIN, main=TEST_CHAIN),
        limits=limits_with(),
        session_factory=factory,
        client=client,
    )
    ask(gateway, user)
    rows = ai_rows(factory)
    assert rows and all(r.failure_kind in {k.value for k in FailureKind} for r in rows)
    for row in rows:
        stored = " ".join(str(getattr(row, c.name)) for c in AiCall.__table__.columns)
        for secret in (API_KEY, "SECRET-BODY", "googleapis", "https://", "x-goog"):
            assert secret not in stored


def test_the_database_refuses_anything_that_is_not_a_closed_code(
    db_connection: Connection, factory: SessionFactory, user: uuid.UUID
) -> None:
    def row(kind: Any) -> AiCall:
        return AiCall(
            user_id=user, purpose="plan", model="m", attempt=1, status="error", failure_kind=kind
        )

    with factory() as db:
        db.add(row("HTTP 400: key AIzaSy-leaked"))
        with pytest.raises(IntegrityError):
            db.flush()
    with factory() as db:
        db.add(row("http_400"))
        db.add(row(None))
        db.flush()  # a code and NULL are fine
