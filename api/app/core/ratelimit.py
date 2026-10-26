"""Fixed-window rate limits in Redis. If Redis is down, the caller is refused (fail closed)."""

from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.core.errors import AppError, ErrorCode

SIGNUP_LIMIT, SIGNUP_WINDOW = 5, 60 * 60  # per client IP
LOGIN_LIMIT, LOGIN_WINDOW = 10, 15 * 60  # per client IP + email
UPLOAD_WINDOW = 60 * 60  # per user; the number of uploads is `uploads_per_hour` in limits.toml


@lru_cache
def redis_client(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def hit(redis: Redis, key: str, limit: int, window: int) -> None:
    """Count one attempt. Over the limit: 429 with Retry-After. Redis down: 503."""
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window, nx=True)  # the window starts at the first attempt
        pipe.ttl(key)
        count, _, ttl = pipe.execute()
    except (RedisError, OSError):
        raise AppError(503, ErrorCode.NOT_READY) from None
    if count > limit:
        retry_after = str(ttl if isinstance(ttl, int) and ttl > 0 else window)
        raise AppError(429, ErrorCode.RATE_LIMITED, headers={"Retry-After": retry_after})
