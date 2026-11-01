"""Development only: with no Resend key, print the link instead of sending. It exists so a
developer can try the reset and verify flows locally. It refuses to be built in any other
environment, so a production worker without a key stops instead of printing a token."""

import sys
from typing import TextIO

from app.email.client import EmailMessage, EmailOk, EmailResult


class ConsoleEmailClient:
    def __init__(self, app_env: str, *, out: TextIO | None = None) -> None:
        if app_env != "development":
            raise RuntimeError("the console email client is for APP_ENV=development only")
        self._out = out

    def send(self, message: EmailMessage) -> EmailResult:
        out = self._out or sys.stdout
        print(f"[dev email] to={message.to}\n{message.text}", file=out, flush=True)
        return EmailOk()
