"""What the API calls to send an email: count it against the site's daily cap, then enqueue the job.
The API never talks to Resend; the worker does."""

import logging
import uuid
from dataclasses import dataclass, field

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Retry

from app.core import clock
from app.core.config import Limits
from app.core.enums import EmailTokenPurpose
from app.core.errors import AppError, ErrorCode
from app.jobs.send_email import (
    FAILURE_TTL,
    JOB_TIMEOUT,
    RESULT_TTL,
    RETRY_INTERVALS,
    send_email_job,
)
from app.jobs.worker import QUEUE_NAME

logger = logging.getLogger("indesk.email")

DAILY_KEY = "email:daily:{day}"
DAILY_KEY_TTL = 2 * 24 * 3600


@dataclass(frozen=True)
class EmailRequest:
    purpose: EmailTokenPurpose
    user_id: uuid.UUID
    to: str = field(repr=False)
    lang: str
    token: str = field(repr=False)  # the plain token; only its hash is stored in the database
    token_id: uuid.UUID  # the email_tokens row; also the idempotency key


def _reserve_daily(redis: Redis, limit: int) -> bool:
    key = DAILY_KEY.format(day=clock.utcnow().date().isoformat())
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, DAILY_KEY_TTL, nx=True)
        count, _ = pipe.execute()
    except (RedisError, OSError):
        raise AppError(503, ErrorCode.NOT_READY) from None
    return bool(count <= limit)


def enqueue_email(redis: Redis, limits: Limits, request: EmailRequest) -> bool:
    """True when the job was queued; False when the site's daily email cap is used up (nothing is
    queued and the caller answers exactly as it would have). Redis down: 503, as the limits do."""
    if not _reserve_daily(redis, limits.email_daily_global):
        logger.warning("email not queued: daily cap reached purpose=%s", request.purpose.value)
        return False
    try:
        Queue(QUEUE_NAME, connection=redis).enqueue(
            send_email_job,
            request.purpose.value,
            str(request.user_id),
            request.to,
            request.lang,
            request.token,
            str(request.token_id),
            job_id=f"email-{request.token_id}",
            job_timeout=JOB_TIMEOUT,
            result_ttl=RESULT_TTL,
            failure_ttl=FAILURE_TTL,
            retry=Retry(max=len(RETRY_INTERVALS), interval=RETRY_INTERVALS),
        )
    except (RedisError, OSError):
        raise AppError(503, ErrorCode.NOT_READY) from None
    return True
