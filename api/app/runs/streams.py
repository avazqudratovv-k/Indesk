"""Open event streams per user, kept in Redis so every API process counts the same ones.

A sorted set per user: member = stream id, score = the time it expires. A stream refreshes its score
on every ping; one that crashes or whose client vanished drops out after STREAM_TTL seconds. Acquire
is one Lua script, so two connects at once cannot both take the last slot. Redis down: refused."""

import time
import uuid

from redis import Redis
from redis.exceptions import RedisError

from app.core.errors import AppError, ErrorCode

STREAM_TTL = 45.0

_ACQUIRE = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then return 0 end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[4])
redis.call('EXPIRE', KEYS[1], 120)
return 1
"""


def _key(user_id: uuid.UUID) -> str:
    return f"sse:{user_id}"


def acquire(redis: Redis, user_id: uuid.UUID, stream_id: str, limit: int) -> None:
    now = time.time()
    try:
        taken = redis.eval(_ACQUIRE, 1, _key(user_id), now, now + STREAM_TTL, limit, stream_id)
    except (RedisError, OSError):
        raise AppError(503, ErrorCode.NOT_READY) from None
    if taken != 1:
        raise AppError(429, ErrorCode.TOO_MANY_STREAMS)


def refresh(redis: Redis, user_id: uuid.UUID, stream_id: str) -> None:
    try:
        redis.zadd(_key(user_id), {stream_id: time.time() + STREAM_TTL}, xx=True)
    except (RedisError, OSError):
        pass  # the slot expires by itself


def release(redis: Redis, user_id: uuid.UUID, stream_id: str) -> None:
    try:
        redis.zrem(_key(user_id), stream_id)
    except (RedisError, OSError):
        pass
