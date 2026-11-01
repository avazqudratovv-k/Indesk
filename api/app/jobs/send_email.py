"""The RQ job that sends one email. The API enqueues it (app/email/queue.py); only the worker, which
has a route to the internet and the key, runs it.

Retries are RQ's: 1, 5 and 15 minutes after a retryable failure (a 429, a 5xx, a timeout, a
transport error, a 409). Any other failure from Resend, such as a 4xx for a bad key or an
unverified domain, will not get better, so it is final at once. A final failure writes one log
line and one `email_failed` audit row, both metadata only: never the address, the token or the
link. The token travels in the job arguments (Redis, internal network, no snapshots) with a short
result_ttl and failure_ttl."""

import logging
import uuid
from collections.abc import Callable

from rq import get_current_job
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import EmailTokenPurpose
from app.db.models import AuditLog
from app.db.session import get_engine
from app.email.client import EmailClient, EmailFailure, EmailMessage
from app.email.factory import EmailNotConfigured, build_email_client
from app.email.templates import render

logger = logging.getLogger("indesk.email")

AUDIT_EMAIL_FAILED = "email_failed"
RETRY_INTERVALS = [60, 300, 900]  # seconds before attempt 2, 3 and 4
RESULT_TTL = 60
FAILURE_TTL = 3600
JOB_TIMEOUT = 60


class EmailRetry(Exception):  # noqa: N818  # not an error: it asks RQ for the next try
    """Raised after a retryable failure so RQ schedules the next try. Carries no text."""


def _final_failure(
    session_factory: Callable[[], Session],
    purpose: str,
    user_id: uuid.UUID,
    what: str,
) -> None:
    logger.error("email failed: purpose=%s cause=%s", purpose, what)
    with session_factory() as db:
        db.add(AuditLog(action=AUDIT_EMAIL_FAILED, user_id=user_id, target=f"{purpose}:{what}"))
        db.commit()


def deliver(
    client: EmailClient,
    session_factory: Callable[[], Session],
    *,
    purpose: EmailTokenPurpose,
    user_id: uuid.UUID,
    to: str,
    lang: str,
    token: str,
    token_id: uuid.UUID,
    base_url: str,
    retries_left: int | None,
) -> None:
    """One attempt. `retries_left`: retries RQ has left (None or 0: this was the last)."""
    content = render(purpose, lang, base_url, token)
    message = EmailMessage(
        to=to,
        subject=content.subject,
        text=content.text,
        html=content.html,
        idempotency_key=f"{purpose.value}-{token_id}",
    )
    result = client.send(message)
    if not isinstance(result, EmailFailure):
        logger.info("email sent: purpose=%s", purpose.value)
        return
    what = result.kind.value if result.status is None else f"{result.kind.value}:{result.status}"
    if result.retryable and retries_left:
        logger.warning("email attempt failed, will retry: purpose=%s cause=%s", purpose.value, what)
        raise EmailRetry
    _final_failure(session_factory, purpose.value, user_id, what)


def send_email_job(
    purpose: str, user_id: str, to: str, lang: str, token: str, token_id: str
) -> None:
    settings = get_settings()
    engine = get_engine(settings.database_url.get_secret_value())

    def factory() -> Session:
        return Session(engine)

    try:
        client = build_email_client(settings)
    except EmailNotConfigured:
        _final_failure(factory, purpose, uuid.UUID(user_id), "not_configured")
        return
    job = get_current_job()
    deliver(
        client,
        factory,
        purpose=EmailTokenPurpose(purpose),
        user_id=uuid.UUID(user_id),
        to=to,
        lang=lang,
        token=token,
        token_id=uuid.UUID(token_id),
        base_url=settings.email_link_base,
        retries_left=job.retries_left if job is not None else None,
    )
