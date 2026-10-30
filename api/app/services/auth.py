"""Sign up, log in, refresh and log out. Every function commits its own work, so an audit row for
a refused request is kept even though the request ends in an error."""

import re
import secrets
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, ErrorCode
from app.core.security import (
    create_access_token,
    dummy_hash,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    verify_password,
)
from app.db.models import AuditLog, RefreshToken, User

HANDLE_ATTEMPTS = 5
SLUG_MAX = 20  # slug + "-" + 6 hex stays within the 30-character handle limit

AUDIT_SIGNUP = "signup"
AUDIT_LOGIN = "login"
AUDIT_LOGIN_FAILED = "login_failed"
AUDIT_REFRESH_REUSE = "refresh_reuse"
AUDIT_LOGOUT = "logout"


@dataclass
class IssuedSession:
    user: User
    access_token: str
    refresh_token: str
    session_ends_at: datetime  # login time + the absolute session limit; cookies never outlive it


def _audit(db: Session, action: str, user_id: uuid.UUID | None, ip_hash: str) -> None:
    db.add(AuditLog(action=action, user_id=user_id, ip_hash=ip_hash))


def _suffix() -> str:
    return secrets.token_hex(3)


def make_handle(display_name: str, suffix: str) -> str:
    """Slug of the name (ASCII letters and digits) plus a short random suffix. A name with no ASCII
    letters, such as a Korean name, becomes "user"."""
    ascii_name = unicodedata.normalize("NFKD", display_name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:SLUG_MAX].strip("-")
    return f"{slug or 'user'}-{suffix}"


def _violated_constraint(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


def _insert_user(db: Session, email: str, password_hash: str, display_name: str) -> User:
    for _ in range(HANDLE_ATTEMPTS):
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            handle=make_handle(display_name, _suffix()),
        )
        try:
            with db.begin_nested():
                db.add(user)
                db.flush()
        except IntegrityError as exc:
            constraint = _violated_constraint(exc)
            if constraint == "uq_users_handle":
                continue  # try another suffix
            if constraint == "uq_users_email":
                raise AppError(409, ErrorCode.EMAIL_TAKEN) from None
            raise
        return user
    raise AppError(500, ErrorCode.INTERNAL)


def _new_refresh_row(
    db: Session,
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    session_started_at: datetime,
    session_max: timedelta,
) -> tuple[str, RefreshToken]:
    """A rotated token inherits `session_started_at`, so a refresh chain ends at login + limit."""
    token = new_refresh_token()
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id,
        token_hash=hash_refresh_token(token),
        session_started_at=session_started_at,
        expires_at=session_started_at + session_max,
    )
    db.add(row)
    db.flush()
    return token, row


def _issue(db: Session, user: User, secret: str, session_max: timedelta) -> IssuedSession:
    refresh_token, row = _new_refresh_row(db, user.id, uuid.uuid4(), clock.utcnow(), session_max)
    return IssuedSession(
        user, create_access_token(user.id, secret), refresh_token, row.expires_at
    )


def _revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=clock.utcnow())
    )


def signup(
    db: Session,
    secret: str,
    session_max: timedelta,
    *,
    email: str, password: str,
    display_name: str,
    ip_hash: str,
) -> IssuedSession:
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AppError(409, ErrorCode.EMAIL_TAKEN)
    user = _insert_user(db, email, hash_password(password), display_name)
    issued = _issue(db, user, secret, session_max)
    _audit(db, AUDIT_SIGNUP, user.id, ip_hash)
    try:
        db.commit()
    except IntegrityError:  # pragma: no cover - race already handled at the insert
        db.rollback()
        raise AppError(409, ErrorCode.EMAIL_TAKEN) from None
    return issued


def login(
    db: Session, secret: str, session_max: timedelta, *, email: str, password: str, ip_hash: str
) -> IssuedSession:
    user = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    # An unknown email costs the same as a wrong password: verify against a dummy hash.
    good = verify_password(user.password_hash if user else dummy_hash(), password)
    if user is None or not good:
        _audit(db, AUDIT_LOGIN_FAILED, user.id if user else None, ip_hash)
        db.commit()
        raise AppError(401, ErrorCode.INVALID_CREDENTIALS)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    issued = _issue(db, user, secret, session_max)
    _audit(db, AUDIT_LOGIN, user.id, ip_hash)
    db.commit()
    return issued


def refresh(
    db: Session, secret: str, session_max: timedelta, *, token: str | None, ip_hash: str
) -> IssuedSession:
    unauthenticated = AppError(401, ErrorCode.UNAUTHENTICATED)
    if not token:
        raise unauthenticated
    row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(token))
        .with_for_update()  # two requests with one token run one after the other
    )
    if row is None:
        raise unauthenticated
    if row.replaced_by is not None:
        # An already-rotated token came back: assume it was stolen and end the whole login.
        _revoke_family(db, row.family_id)
        _audit(db, AUDIT_REFRESH_REUSE, row.user_id, ip_hash)
        db.commit()
        raise unauthenticated
    # NULL (a row from before migration 0006) counts as the row's own creation time.
    started = row.session_started_at or row.created_at
    ends_at = started + session_max
    if row.revoked_at is not None or min(row.expires_at, ends_at) <= clock.utcnow():
        raise unauthenticated
    user = db.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        _revoke_family(db, row.family_id)
        db.commit()
        raise unauthenticated
    new_token, new_row = _new_refresh_row(db, user.id, row.family_id, started, session_max)
    row.replaced_by = new_row.id
    db.commit()
    return IssuedSession(user, create_access_token(user.id, secret), new_token, ends_at)


def logout(db: Session, *, token: str | None, ip_hash: str) -> None:
    if not token:
        return
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if row is None:
        return
    _revoke_family(db, row.family_id)
    _audit(db, AUDIT_LOGOUT, row.user_id, ip_hash)
    db.commit()
