import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis import Redis
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import Settings
from app.core.cookies import REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from app.core.enums import EmailTokenPurpose
from app.core.security import keyed_hash
from app.db.models import EmailToken
from app.db.models import User as UserRow
from app.email.queue import EmailRequest, enqueue_email
from app.routers.deps import AppSettings, CurrentUser, Db, IpHash, RedisDep, Secret
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyConfirmRequest,
)
from app.schemas.users import User
from app.services import auth as service

logger = logging.getLogger("indesk.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def signup_guard(redis: RedisDep, ip_hash: IpHash) -> str:
    """Runs before the body is checked, so refused sign-ups count too."""
    ratelimit.hit(redis, f"rl:signup:{ip_hash}", ratelimit.SIGNUP_LIMIT, ratelimit.SIGNUP_WINDOW)
    return ip_hash


def _limit_login(redis: Redis, secret: str, ip_hash: str, email: str) -> None:
    key = f"rl:login:{ip_hash}:{keyed_hash(secret, email)}"
    ratelimit.hit(redis, key, ratelimit.LOGIN_LIMIT, ratelimit.LOGIN_WINDOW)


def _queue_token_email(
    db: Session,
    redis: Redis,
    settings: Settings,
    user: UserRow,
    purpose: EmailTokenPurpose,
    token: str,
    row: EmailToken,
    lang: str,
) -> None:
    """Queue the email of a token that is flushed but not committed. Queued: commit. The daily cap
    is used up: roll back, so nothing is kept for an email that was not sent."""
    request = EmailRequest(
        purpose=purpose, user_id=user.id, to=user.email, lang=lang, token=token, token_id=row.id
    )
    if enqueue_email(redis, settings.limits, request):
        db.commit()
    else:
        db.rollback()


def _send_verification(db: Session, redis: Redis, settings: Settings, user: UserRow) -> None:
    """Best effort: sign-up has already succeeded, so nothing here may fail it. Only the error
    type is logged (never the address or the token)."""
    try:
        token, row = service.issue_token(db, user, EmailTokenPurpose.VERIFY)
        _queue_token_email(
            db, redis, settings, user, EmailTokenPurpose.VERIFY, token, row, user.lang
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("verification email not queued: %s", type(exc).__name__)


@router.post("/signup", status_code=201, response_model=User)
def signup(
    body: SignupRequest,
    response: Response,
    db: Db,
    settings: AppSettings,
    secret: Secret,
    redis: RedisDep,
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
        lang=body.lang,
    )
    _send_verification(db, redis, settings, issued.user)
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
        # Nothing was sent when the daily cap is used up, so the older link keeps working.
        _queue_token_email(
            db,
            redis,
            settings,
            user,
            EmailTokenPurpose.RESET,
            token,
            row,
            service.mail_lang(body.lang),
        )
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


def verify_guard(redis: RedisDep, ip_hash: IpHash) -> None:
    ratelimit.hit(redis, f"rl:verify:{ip_hash}", ratelimit.VERIFY_LIMIT, ratelimit.VERIFY_WINDOW)


@router.post("/verify/confirm", status_code=204, dependencies=[Depends(verify_guard)])
def verify_confirm(body: VerifyConfirmRequest, db: Db, ip_hash: IpHash) -> Response:
    service.confirm_email(db, token=body.token, ip_hash=ip_hash)
    return Response(status_code=204)


@router.post("/verify/resend", status_code=204)
def verify_resend(user: CurrentUser, db: Db, settings: AppSettings, redis: RedisDep) -> Response:
    """Signed in only. Every request counts toward 3 an hour; an already verified user gets 204
    and nothing is sent. The daily email cap answers the same 204."""
    ratelimit.hit(
        redis, f"rl:verify-resend:{user.id}", ratelimit.RESEND_LIMIT, ratelimit.RESEND_WINDOW
    )
    if user.email_verified_at is None:
        token, row = service.issue_token(db, user, EmailTokenPurpose.VERIFY)
        _queue_token_email(
            db, redis, settings, user, EmailTokenPurpose.VERIFY, token, row, user.lang
        )
    return Response(status_code=204)
