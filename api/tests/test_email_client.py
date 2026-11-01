"""The Resend client against a mock transport: the request it builds, how each answer maps to a
failure kind, the total deadline, and that nothing private reaches a result or a repr. No network:
the suite's network guard fails any real httpx call."""

import json
import threading
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.email.client import EmailFailure, EmailFailureKind, EmailMessage, EmailOk
from app.email.resend_client import MAX_BODY_BYTES, ResendClient

KEY = SecretStr("re_test_key_0123456789")
ADDRESS = "someone.private@example.com"
FROM = "Indesk <no-reply@indesk.uz>"
MESSAGE = EmailMessage(
    to=ADDRESS,
    subject="Subject line",
    text="plain body https://indesk.uz/reset-password#token=SECRETTOKEN",
    html="<p>html body</p>",
    idempotency_key="reset-1234",
)


def client_for(handler: Any, **kw: Any) -> ResendClient:
    return ResendClient(KEY, FROM, transport=httpx.MockTransport(handler), **kw)


def answer(status: int, body: bytes = b"{}") -> Any:
    return lambda request: httpx.Response(status, content=body)


def test_it_posts_the_documented_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "49a3999c-0ce1"})

    result = client_for(handler).send(MESSAGE)

    assert result == EmailOk(message_id="49a3999c-0ce1")
    (request,) = seen
    assert (request.method, str(request.url)) == ("POST", "https://api.resend.com/emails")
    assert request.headers["authorization"] == "Bearer re_test_key_0123456789"
    assert request.headers["idempotency-key"] == "reset-1234"
    assert request.headers["content-type"] == "application/json"
    body = json.loads(request.content)
    assert body == {
        "from": FROM,
        "to": [ADDRESS],
        "subject": "Subject line",
        "text": MESSAGE.text,
        "html": MESSAGE.html,
    }
    assert "re_test_key" not in request.content.decode() and "re_test_key" not in str(request.url)


@pytest.mark.parametrize("body", [b"", b"not json", b"[1]", b'{"id": 5}', b"x" * (MAX_BODY_BYTES + 1)])
def test_an_accepted_mail_is_a_success_even_when_the_answer_is_unreadable(body: bytes) -> None:
    assert client_for(answer(200, body)).send(MESSAGE) == EmailOk(message_id=None)


@pytest.mark.parametrize(
    ("status", "kind", "retryable"),
    [
        (429, EmailFailureKind.RATE_LIMITED, True),
        (500, EmailFailureKind.SERVER_ERROR, True),
        (503, EmailFailureKind.SERVER_ERROR, True),
        (409, EmailFailureKind.CONFLICT, True),
        (400, EmailFailureKind.REJECTED, False),
        (401, EmailFailureKind.REJECTED, False),
        (403, EmailFailureKind.REJECTED, False),
        (422, EmailFailureKind.REJECTED, False),
        (302, EmailFailureKind.REJECTED, False),  # a redirect is not followed
    ],
)
def test_each_status_maps_to_a_kind_and_only_some_are_retried(
    status: int, kind: EmailFailureKind, retryable: bool
) -> None:
    result = client_for(answer(status, b'{"message": "private detail"}')).send(MESSAGE)

    assert result == EmailFailure(kind=kind, status=status)
    assert isinstance(result, EmailFailure) and result.retryable is retryable
    assert "private detail" not in repr(result)


def test_a_transport_error_is_a_failure_that_keeps_no_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("could not reach api.resend.com for someone.private@example.com")

    result = client_for(handler).send(MESSAGE)

    assert result == EmailFailure(kind=EmailFailureKind.TRANSPORT)
    assert "resend" not in repr(result) and "private" not in repr(result)


def test_a_timeout_from_the_transport_is_a_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    assert client_for(handler).send(MESSAGE) == EmailFailure(kind=EmailFailureKind.TIMEOUT)


def test_the_total_deadline_ends_the_wait_even_when_the_server_never_answers() -> None:
    release = threading.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        release.wait(5)
        return httpx.Response(200, json={"id": "late"})

    try:
        result = client_for(handler, deadline_seconds=0.2).send(MESSAGE)
    finally:
        release.set()
    assert result == EmailFailure(kind=EmailFailureKind.TIMEOUT)


def test_nothing_private_shows_in_a_repr() -> None:
    client = client_for(answer(200))
    shown = repr(client) + repr(MESSAGE) + repr(EmailOk(message_id="x"))
    assert "re_test_key" not in shown
    for private in (ADDRESS, "SECRETTOKEN", "Subject line", "html body"):
        assert private not in shown
