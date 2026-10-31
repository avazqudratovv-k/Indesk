"""Fixed-window rate limits in Redis. If Redis is down, the caller is refused (fail closed),
unless the limiter asks to fail open (reads: a rate limit must not break reading)."""

import logging
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.core.errors import AppError, ErrorCode

logger = logging.getLogger("indesk.ratelimit")

SIGNUP_LIMIT, SIGNUP_WINDOW = 5, 60 * 60  # per client IP
LOGIN_LIMIT, LOGIN_WINDOW = 10, 15 * 60  # per client IP + email
UPLOAD_WINDOW = 60 * 60  # per user; the number of uploads is `uploads_per_hour` in limits.toml
RUN_WINDOW = 60 * 60  # per user; the number of run requests is `runs_per_hour` in limits.toml
READ_WINDOW = 60  # per user; the number of reads is `reads_per_minute` in limits.toml
DELETE_WINDOW = 60 * 60  # per user; the number of deletes is `deletes_per_hour` in limits.toml


@lru_cache
def redis_client(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def hit(redis: Redis, key: str, limit: int, window: int, *, fail_open: bool = False) -> None:
    """Count one attempt. Over the limit: 429 with Retry-After. Redis down: 503, or (fail_open)
    the attempt passes and one warning line is logged (no key, no user data)."""
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window, nx=True)  # the window starts at the first attempt
        pipe.ttl(key)
        count, _, ttl = pipe.execute()
    except (RedisError, OSError):
        if fail_open:
            logger.warning("rate limit skipped: Redis unavailable")
            return
        raise AppError(503, ErrorCode.NOT_READY) from None
    if count > limit:
        retry_after = str(ttl if isinstance(ttl, int) and ttl > 0 else window)
        raise AppError(429, ErrorCode.RATE_LIMITED, headers={"Retry-After": retry_after})
