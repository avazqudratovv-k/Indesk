import math
from datetime import datetime

from fastapi import Response

from app.core.config import Settings
from app.core import clock
from app.core.security import ACCESS_TTL

ACCESS_COOKIE = "indesk_access"
REFRESH_COOKIE = "indesk_refresh"
ACCESS_PATH = "/"
REFRESH_PATH = "/api/auth"  # the refresh token is only ever sent to the auth endpoints


def set_session_cookies(
    response: Response,
    settings: Settings,
    access_token: str,
    refresh_token: str,
    session_ends_at: datetime,
) -> None:
    """Cookies never outlive the session: the refresh cookie lasts the remaining session time."""
    secure = settings.cookie_secure
    remaining = max(1, math.ceil((session_ends_at - clock.utcnow()).total_seconds()))
    access_age = min(int(ACCESS_TTL.total_seconds()), remaining)
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=access_age, path=ACCESS_PATH,
        httponly=True, secure=secure, samesite="lax",
    )  # fmt: skip
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, max_age=remaining, path=REFRESH_PATH,
        httponly=True, secure=secure, samesite="lax",
    )  # fmt: skip


def clear_session_cookies(response: Response, settings: Settings) -> None:
    secure = settings.cookie_secure
    response.delete_cookie(
        ACCESS_COOKIE, path=ACCESS_PATH, httponly=True, secure=secure, samesite="lax"
    )
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_PATH, httponly=True, secure=secure, samesite="lax"
    )
