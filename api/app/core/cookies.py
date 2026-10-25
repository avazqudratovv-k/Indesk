from fastapi import Response

from app.core.config import Settings
from app.core.security import ACCESS_TTL, REFRESH_TTL

ACCESS_COOKIE = "indesk_access"
REFRESH_COOKIE = "indesk_refresh"
ACCESS_PATH = "/"
REFRESH_PATH = "/api/auth"  # the refresh token is only ever sent to the auth endpoints


def set_session_cookies(
    response: Response, settings: Settings, access_token: str, refresh_token: str
) -> None:
    secure = settings.cookie_secure
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=int(ACCESS_TTL.total_seconds()), path=ACCESS_PATH,
        httponly=True, secure=secure, samesite="lax",
    )  # fmt: skip
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, max_age=int(REFRESH_TTL.total_seconds()), path=REFRESH_PATH,
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
