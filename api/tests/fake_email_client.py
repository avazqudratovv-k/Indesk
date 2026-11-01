"""A scripted stand-in for the Resend client. No network, no sleeping. Every message it is asked to
send is recorded, so a test can read what would have been sent; each step of the script is the
result of one send (the default is success)."""

from app.email.client import (
    EmailFailure,
    EmailFailureKind,
    EmailMessage,
    EmailOk,
    EmailResult,
)


def failure(kind: EmailFailureKind, status: int | None = None) -> EmailFailure:
    return EmailFailure(kind=kind, status=status)


class FakeEmailClient:
    def __init__(self, *script: EmailResult) -> None:
        self.script = list(script)
        self.sent: list[EmailMessage] = []  # every attempt, including the ones that failed

    def send(self, message: EmailMessage) -> EmailResult:
        self.sent.append(message)
        return self.script.pop(0) if self.script else EmailOk(message_id="fake-id")
