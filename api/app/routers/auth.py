from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis import Redis

from app.core import ratelimit
from app.core.cookies import REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from app.core.security import keyed_hash
from app.routers.deps import AppSettings, Db, IpHash, RedisDep, Secret
from app.schemas.auth import LoginRequest, SignupRequest
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
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        ip_hash=ip_hash,
    )
    set_session_cookies(response, settings, issued.access_token, issued.refresh_token)
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
    issued = service.login(db, secret, email=body.email, password=body.password, ip_hash=ip_hash)
    set_session_cookies(response, settings, issued.access_token, issued.refresh_token)
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
    issued = service.refresh(db, secret, token=request.cookies.get(REFRESH_COOKIE), ip_hash=ip_hash)
    set_session_cookies(response, settings, issued.access_token, issued.refresh_token)


@router.post("/logout", status_code=204)
def logout(
    request: Request, response: Response, db: Db, settings: AppSettings, ip_hash: IpHash
) -> None:
    service.logout(db, token=request.cookies.get(REFRESH_COOKIE), ip_hash=ip_hash)
    clear_session_cookies(response, settings)
