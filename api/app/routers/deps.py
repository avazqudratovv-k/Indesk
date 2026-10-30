"""Request dependencies shared by routers. `current_user` is the one later prompts depend on."""

import logging
import uuid
from typing import Annotated

from fastapi import Depends, Request
from redis import Redis
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import Settings, get_settings
from app.core.cookies import ACCESS_COOKIE
from app.core.errors import AppError, ErrorCode
from app.core.network import (
    SAFE_METHODS,
    body_type_allowed,
    client_ip,
    has_body,
    request_origin,
)
from app.core.ratelimit import redis_client
from app.core.security import decode_access_token, keyed_hash
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger("indesk.auth")
_warned_missing_secret = False


def check_write_request(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """CSRF defence for every write request: Origin (or Referer) must be allow-listed, and a body
    must be JSON or multipart. Cookies are SameSite=Lax on top of this."""
    if request.method in SAFE_METHODS:
        return
    origin = request_origin(request)
    if origin is None or origin not in settings.allowed_origins:
        raise AppError(403, ErrorCode.ORIGIN_NOT_ALLOWED)
    if has_body(request) and not body_type_allowed(request):
        raise AppError(415, ErrorCode.UNSUPPORTED_TYPE)


def auth_secret(settings: Annotated[Settings, Depends(get_settings)]) -> str:
    """The signing secret, or 503 when it is missing or too short (logged once, no value)."""
    global _warned_missing_secret
    if settings.auth_secret is None or not settings.auth_ready:
        if not _warned_missing_secret:
            _warned_missing_secret = True
            logger.error("AUTH_SECRET is missing or shorter than 32 characters: auth is disabled")
        raise AppError(503, ErrorCode.NOT_READY)
    return settings.auth_secret.get_secret_value()


Secret = Annotated[str, Depends(auth_secret)]
Db = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_redis(settings: AppSettings) -> Redis:
    return redis_client(settings.redis_url.get_secret_value())


def ip_hash(request: Request, settings: AppSettings, secret: Secret) -> str:
    return keyed_hash(secret, client_ip(request, settings.trusted_proxies))


IpHash = Annotated[str, Depends(ip_hash)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def current_user(request: Request, db: Db, secret: Secret) -> User:
    """The signed-in user from the access cookie. 401 on anything wrong; never trusts the client."""
    token = request.cookies.get(ACCESS_COOKIE)
    user_id: uuid.UUID | None = decode_access_token(token, secret) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None or user.deleted_at is not None:
        raise AppError(401, ErrorCode.UNAUTHENTICATED)
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def read_limit(user: CurrentUser, settings: AppSettings, redis: RedisDep) -> None:
    """120 reads a minute per user, shared by the report and upload read routes. Runs after
    authentication. Redis down: the read goes through (fail open)."""
    ratelimit.hit(
        redis,
        f"rl:read:{user.id}",
        settings.limits.reads_per_minute,
        ratelimit.READ_WINDOW,
        fail_open=True,
    )


def delete_limit(user: CurrentUser, settings: AppSettings, redis: RedisDep) -> None:
    """30 deletes an hour per user, shared by the report and upload delete routes. Runs after
    authentication. Redis down: refused (503, fail closed)."""
    ratelimit.hit(
        redis, f"rl:delete:{user.id}", settings.limits.deletes_per_hour, ratelimit.DELETE_WINDOW
    )


ReadLimit = Depends(read_limit)
DeleteLimit = Depends(delete_limit)
