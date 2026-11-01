from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis import Redis

from app.core import ratelimit
from app.core.cookies import REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from app.core.enums import EmailTokenPurpose, Lang
from app.core.security import keyed_hash
from app.email.queue import EmailRequest, enqueue_email
from app.routers.deps import AppSettings, Db, IpHash, RedisDep, Secret
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from app.schemas.users import User
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["auth"])


def signup_guard(redis: RedisDep, ip_hash: IpHash) -> str:
    """Runs before the body is checked, so refused sign-ups count too."""
    ratelimit.hit(redis, f"rl:signup:{ip_hash}", ratelimit.SIGNUP_LIMIT, ratelimit.SIGNUP_WINDOW)
    return ip_hash


def _limit_login(redis: Redis, secret: str, ip_hash: str, email: str) -> None:
    key = f"rl:login:{ip_hash}:{keyed_hash(secret, email)}"
    ratelimit.hit(redis, key, ratelimit.LOGIN_LIMIT, ratelimit.LOGIN_WINDOW)


@router.post("/signup", status_code=201, response_model=User)
def signup(
    body: SignupRequest,
    response: Response,
    db: Db,
    settings: AppSettings,
    secret: Secret,
    ip_hash: Annotated[str, Depends(signup_guard)],
) -> User:
    issued = service.signup(
        db,
        secret,
        timedelta(seconds=settings.session_max_seconds),
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        ip_hash=ip_hash,
    )
    set_session_cookies(
        response, settings, issued.access_token, issued.refresh_token, issued.session_ends_at
    )
    return User.model_validate(issued.user)


@router.post("/login", response_model=User)
def login(
    body: LoginRequest,
    response: Response,
    db: Db,
    settings: AppSettings,
    secret: Secret,
    redis: RedisDep,
    ip_hash: IpHash,
) -> User:
    _limit_login(redis, secret, ip_hash, body.email)
    issued = service.login(
        db,
        secret,
        timedelta(seconds=settings.session_max_seconds),
        email=body.email,
        password=body.password,
        ip_hash=ip_hash,
    )
    set_session_cookies(
        response, settings, issued.access_token, issued.refresh_token, issued.session_ends_at
    )
    return User.model_validate(issued.user)


@router.post("/refresh", status_code=204)
def refresh(
    request: Request,
    response: Response,
    db: Db,
    settings: AppSettings,
    secret: Secret,
    ip_hash: IpHash,
) -> None:
    issued = service.refresh(
        db,
        secret,
        timedelta(seconds=settings.session_max_seconds),
        token=request.cookies.get(REFRESH_COOKIE),
        ip_hash=ip_hash,
    )
    set_session_cookies(
        response, settings, issued.access_token, issued.refresh_token, issued.session_ends_at
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request, response: Response, db: Db, settings: AppSettings, ip_hash: IpHash
) -> None:
    service.logout(db, token=request.cookies.get(REFRESH_COOKIE), ip_hash=ip_hash)
    clear_session_cookies(response, settings)


def forgot_guard(redis: RedisDep, ip_hash: IpHash) -> None:
    """Runs before the body is checked. Redis down: 503 (fail closed)."""
    ratelimit.hit(
        redis, f"rl:forgot:{ip_hash}", ratelimit.FORGOT_IP_LIMIT, ratelimit.FORGOT_IP_WINDOW
    )


def reset_guard(redis: RedisDep, ip_hash: IpHash) -> None:
    ratelimit.hit(redis, f"rl:reset:{ip_hash}", ratelimit.RESET_LIMIT, ratelimit.RESET_WINDOW)


def _mail_lang(lang: str | None) -> str:
    return lang if lang in (Lang.EN.value, Lang.KO.value) else Lang.EN.value


@router.post("/password/forgot", status_code=202, dependencies=[Depends(forgot_guard)])
def forgot_password(
    body: ForgotPasswordRequest,
    db: Db,
    settings: AppSettings,
    secret: Secret,
    redis: RedisDep,
) -> Response:
    """Always the same empty 202, whether or not the account exists, is deleted, or the daily
    email cap is used up. The email limit counts every request."""
    ratelimit.hit(
        redis,
        f"rl:forgot-email:{keyed_hash(secret, body.email)}",
        ratelimit.FORGOT_EMAIL_LIMIT,
        ratelimit.FORGOT_EMAIL_WINDOW,
    )
    created = service.create_reset_token(db, body.email)
    if created is not None:
        user, token, row = created
        request = EmailRequest(
            purpose=EmailTokenPurpose.RESET,
            user_id=user.id,
            to=user.email,
            lang=_mail_lang(body.lang),
            token=token,
            token_id=row.id,
        )
        if enqueue_email(redis, settings.limits, request):
            db.commit()
        else:
            db.rollback()  # nothing was sent, so the older link keeps working
    return Response(status_code=202)


@router.post("/password/reset", status_code=204, dependencies=[Depends(reset_guard)])
def reset_password(
    body: ResetPasswordRequest,
    db: Db,
    settings: AppSettings,
    ip_hash: IpHash,
) -> Response:
    service.reset_password(db, token=body.token, new_password=body.new_password, ip_hash=ip_hash)
    response = Response(status_code=204)
    clear_session_cookies(response, settings)
    return response
