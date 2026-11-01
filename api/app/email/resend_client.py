"""The only code that talks to Resend, over plain httpx (no SDK).

Checked against Resend's docs on 2026-11-02: POST https://api.resend.com/emails, header
`Authorization: Bearer <key>`, JSON body `from`, `to`, `subject`, `html`, `text`, header
`Idempotency-Key` (1 to 256 characters, kept 24 hours), answer `{"id": ...}`.

Safety rules kept here:
- The key travels in the Authorization header only, never in a URL, a log line or a result.
- The attempt has a TOTAL wall deadline (a worker thread joined with the deadline, plus a check
  between body chunks), so a slow trickle cannot outlast it.
- The body read is capped at MAX_BODY_BYTES, and a failure answer's body is never read.
- No exception text, URL, address or response body is kept or logged: only a fixed failure kind
  and the HTTP status."""

import json
import threading
import time
from collections.abc import Callable

import httpx
from pydantic import SecretStr

from app.email.client import EmailFailure, EmailFailureKind, EmailMessage, EmailOk, EmailResult

BASE_URL = "https://api.resend.com"
DEADLINE_SECONDS = 10.0
MAX_BODY_BYTES = 16 * 1024  # an answer is one small JSON object
USER_AGENT = "indesk-worker/1"


def _failure_for(status: int) -> EmailFailure:
    if status == 429:
        kind = EmailFailureKind.RATE_LIMITED
    elif status >= 500:
        kind = EmailFailureKind.SERVER_ERROR
    elif status == 409:
        kind = EmailFailureKind.CONFLICT
    else:
        kind = EmailFailureKind.REJECTED
    return EmailFailure(kind=kind, status=status)


def _read_id(
    response: httpx.Response, *, deadline: float, mono: Callable[[], float], stop: threading.Event
) -> str | None:
    """The `id` of a 2xx answer, or None. The mail was accepted either way, so a body that is
    slow, too big or unreadable is not a failure (a retry could only send it twice)."""
    body = bytearray()
    for chunk in response.iter_bytes():
        if stop.is_set() or mono() > deadline:
            return None
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            return None
    try:
        value = json.loads(body).get("id")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and len(value) <= 100 else None


class ResendClient:
    def __init__(
        self,
        api_key: SecretStr,
        from_address: str,
        *,
        transport: httpx.BaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        base_url: str = BASE_URL,
        deadline_seconds: float = DEADLINE_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._from = from_address
        self._transport = transport
        self._mono = monotonic
        self._base_url = base_url
        self._deadline_seconds = deadline_seconds

    def __repr__(self) -> str:
        return "ResendClient(api_key=**********)"

    def send(self, message: EmailMessage) -> EmailResult:
        payload = json.dumps(
            {
                "from": self._from,
                "to": [message.to],
                "subject": message.subject,
                "text": message.text,
                "html": message.html,
            }
        ).encode()
        outcome: list[EmailResult] = []
        stop = threading.Event()

        def work() -> None:
            outcome.append(self._attempt(payload, message.idempotency_key, stop))

        try:
            worker = threading.Thread(target=work, daemon=True)
            worker.start()
        except RuntimeError:
            return EmailFailure(kind=EmailFailureKind.TRANSPORT)
        worker.join(self._deadline_seconds)
        if worker.is_alive():
            stop.set()  # the worker stops at its next chunk or when its own timeouts fire
            return EmailFailure(kind=EmailFailureKind.TIMEOUT)
        return outcome[0] if outcome else EmailFailure(kind=EmailFailureKind.TRANSPORT)

    def _attempt(self, payload: bytes, idempotency_key: str, stop: threading.Event) -> EmailResult:
        deadline = self._mono() + self._deadline_seconds
        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "User-Agent": USER_AGENT,
        }
        try:
            with (
                httpx.Client(
                    transport=self._transport, timeout=httpx.Timeout(self._deadline_seconds)
                ) as http,
                http.stream(
                    "POST", f"{self._base_url}/emails", headers=headers, content=payload
                ) as response,
            ):
                if not 200 <= response.status_code < 300:
                    return _failure_for(response.status_code)
                message_id = _read_id(response, deadline=deadline, mono=self._mono, stop=stop)
        except httpx.TimeoutException:
            return EmailFailure(kind=EmailFailureKind.TIMEOUT)
        except Exception:  # noqa: BLE001  # any transport error; its text could hold the URL
            return EmailFailure(kind=EmailFailureKind.TRANSPORT)
        return EmailOk(message_id=message_id)
