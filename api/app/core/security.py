"""Password hashing, access tokens and refresh tokens. No database and no request code here."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ACCESS_TTL = timedelta(minutes=15)
JWT_ALGORITHM = "HS256"

# Library defaults: Argon2id with the RFC 9106 low-memory profile (t=3, m=64 MiB, p=4).
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def dummy_hash() -> str:
    """Verified against when the email is unknown, so both paths cost the same time."""
    return _hasher.hash(secrets.token_urlsafe(16))


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)  # 32 random bytes


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def keyed_hash(secret: str, value: str) -> str:
    """HMAC-SHA256 of a value (IP, email). Not reversible without the secret."""
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_access_token(user_id: uuid.UUID, secret: str, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    claims = {"sub": str(user_id), "iat": issued, "exp": issued + ACCESS_TTL}
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> uuid.UUID | None:
    """The user id in a valid token, or None for anything wrong (expired, tampered, alg=none)."""
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],  # always pinned
            options={"require": ["sub", "iat", "exp"]},
        )
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
