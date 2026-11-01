"""Password reset: the forgot and reset routes, the single-use token, the limits and the end of
every older login (refresh tokens and access tokens)."""

import hashlib
import logging
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis import Redis
from rq import Queue
from sqlalchemy import Connection, select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Settings
from app.core.security import create_access_token, keyed_hash
from app.db.models import AuditLog, EmailToken, RefreshToken, User
from tests.conftest import TEST_AUTH_SECRET, _test_redis_url
from tests.test_auth import (
    ERR_UNAUTH,
    PASSWORD,
    MakeClient,
    login,
    signup,
    with_cookie,
)

NEW_PASSWORD = "a brand new passphrase"  # noqa: S105
ERR_RESET = {"error": {"code": "RESET_TOKEN_INVALID"}}
FORGOT = "/api/auth/password/forgot"
RESET = "/api/auth/password/reset"


def forgot(client: TestClient, email: str = "ada@example.com", **kw: Any) -> Any:
    return client.post(FORGOT, json={"email": email, **kw})


def reset(client: TestClient, token: str, password: str = NEW_PASSWORD) -> Any:
    return client.post(RESET, json={"token": token, "new_password": password})


def jobs() -> list[Any]:
    # Sign-up also queues a verification email; these tests are about reset emails only.
    queue = Queue("default", connection=Redis.from_url(_test_redis_url()))
    return [job for job in queue.jobs if job.args[0] == "reset"]


def sent_token() -> str:
    """The plain token of the one queued email (args: purpose, user, to, lang, token, token_id)."""
    (job,) = jobs()
    return str(job.args[4])


def request_token(client: TestClient, **kw: Any) -> str:
    assert forgot(client, **kw).status_code == 202
    return sent_token()


def rows(conn: Connection) -> list[EmailToken]:
    with Session(bind=conn) as db:
        return list(
            db.scalars(
                select(EmailToken)
                .where(EmailToken.purpose == "reset")
                .order_by(EmailToken.created_at)
            )
        )


def the_user(conn: Connection) -> User:
    with Session(bind=conn) as db:
        return db.scalars(select(User)).one()


@pytest.fixture
def ada(auth_client: TestClient) -> TestClient:
    assert signup(auth_client).status_code == 201
    return auth_client


# ---- forgot ----


def test_unknown_known_and_deleted_accounts_get_the_same_answer(
    make_client: MakeClient, auth_settings: Settings, db_connection: Connection
) -> None:
    client = make_client(auth_settings)
    signup(client, "known@example.com")
    signup(client, "gone@example.com")
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE users SET deleted_at = now() WHERE email = 'gone@example.com'"))
        db.commit()
    answers = [
        forgot(client, e) for e in ("nobody@example.com", "known@example.com", "gone@example.com")
    ]
    assert {r.status_code for r in answers} == {202}
    assert {r.content for r in answers} == {b""}
    shapes = {tuple(sorted((k, v) for k, v in r.headers.items() if k != "date")) for r in answers}
    assert len(shapes) == 1
    assert not any(r.headers.get_list("set-cookie") for r in answers)
    assert len(jobs()) == 1 and len(rows(db_connection)) == 1  # only the known account


def test_the_token_is_stored_as_sha256_for_30_minutes_and_older_ones_are_retired(
    ada: TestClient, db_connection: Connection
) -> None:
    first = request_token(ada)
    ada.post(FORGOT, json={"email": "ada@example.com"})
    first_row, second_row = rows(db_connection)
    assert first_row.token_hash == hashlib.sha256(first.encode()).hexdigest()
    assert first_row.purpose == "reset" and first_row.used_at is not None
    assert second_row.used_at is None
    assert second_row.expires_at - second_row.created_at == pytest.approx(
        timedelta(minutes=30), abs=timedelta(seconds=5)
    )
    assert reset(ada, first).json() == ERR_RESET  # the older link is dead


def test_lang_falls_back_to_english(ada: TestClient) -> None:
    for lang, expected in (("ko", "ko"), ("en", "en"), ("ja", "en"), (None, "en"), ("zz", "en")):
        Redis.from_url(_test_redis_url()).flushdb()
        forgot(ada, lang=lang)
        (job,) = jobs()
        assert job.args[3] == expected


def test_forgot_limits_are_per_ip_and_per_email_and_count_unknown_accounts(
    make_client: MakeClient, auth_settings: Settings
) -> None:
    client = make_client(auth_settings)
    for _ in range(3):
        assert forgot(client, "nobody@example.com").status_code == 202
    blocked = forgot(client, "nobody@example.com")
    assert blocked.status_code == 429 and blocked.headers["retry-after"]
    assert forgot(client, "other@example.com").status_code == 202  # another email still passes
    other_ip = make_client(auth_settings, peer=("203.0.113.99", 1))
    assert forgot(other_ip, "nobody@example.com").status_code == 429  # the email limit is global


def test_the_eleventh_forgot_from_one_ip_is_429(
    make_client: MakeClient, auth_settings: Settings
) -> None:
    client = make_client(auth_settings)
    codes = [forgot(client, f"u{n}@example.com").status_code for n in range(11)]
    assert codes == [202] * 10 + [429]


def test_the_email_key_is_hashed(ada: TestClient) -> None:
    forgot(ada)
    keys = [k.decode() for k in Redis.from_url(_test_redis_url()).scan_iter(match="rl:*")]
    assert keys and not any("ada@example.com" in k for k in keys)
    assert f"rl:forgot-email:{keyed_hash(TEST_AUTH_SECRET, 'ada@example.com')}" in keys


def test_redis_down_fails_closed(make_client: MakeClient, auth_settings: Settings) -> None:
    down = auth_settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/15")})
    client = make_client(down)
    assert forgot(client).status_code == 503
    assert reset(client, "whatever").status_code == 503
    assert forgot(client).json() == {"error": {"code": "NOT_READY"}}


def test_the_daily_cap_still_answers_202_and_sends_nothing(
    make_client: MakeClient, auth_settings: Settings, db_connection: Connection
) -> None:
    limits = auth_settings.limits.model_copy(update={"email_daily_global": 2})
    client = make_client(auth_settings.model_copy(update={"limits": limits}))
    signup(client)
    assert forgot(client).status_code == 202 and len(jobs()) == 1
    capped = forgot(client)
    assert capped.status_code == 202 and capped.content == b""
    assert len(jobs()) == 1  # nothing new was queued
    assert len(rows(db_connection)) == 1  # and no dangling token was kept


def test_forgot_validates_the_body(ada: TestClient) -> None:
    assert ada.post(FORGOT, json={"email": "not-an-email"}).status_code == 422
    assert ada.post(FORGOT, json={"email": "ada@example.com", "x": 1}).status_code == 422


# ---- reset ----


def test_a_reset_changes_the_password_and_ends_every_login(
    ada: TestClient, db_connection: Connection
) -> None:
    old_access = ada.cookies.get("indesk_access")
    old_refresh = ada.cookies.get("indesk_refresh")
    assert old_access and old_refresh
    # An access token issued earlier than the reset second (this one is 5 minutes old).
    user = the_user(db_connection)
    stale = create_access_token(
        user.id, TEST_AUTH_SECRET, now=clock.utcnow() - timedelta(minutes=5)
    )
    assert ada.get("/api/me", headers=with_cookie("indesk_access", stale)).status_code == 200
    assert user.email_verified_at is None

    token = request_token(ada)
    response = reset(ada, token)
    assert response.status_code == 204 and response.content == b""
    cleared = " ".join(response.headers.get_list("set-cookie"))
    assert "indesk_access=" in cleared and "indesk_refresh=" in cleared
    assert not ada.cookies.get("indesk_access")  # not logged in by the reset

    after = the_user(db_connection)
    assert after.tokens_valid_after is not None and after.email_verified_at is not None
    assert after.password_hash != user.password_hash
    assert ada.get("/api/me", headers=with_cookie("indesk_access", stale)).json() == ERR_UNAUTH
    assert (
        ada.post(
            "/api/auth/refresh", headers=with_cookie("indesk_refresh", old_refresh)
        ).status_code
        == 401
    )
    with Session(bind=db_connection) as db:
        assert all(r.revoked_at for r in db.scalars(select(RefreshToken)))
        (audit,) = db.scalars(select(AuditLog).where(AuditLog.action == "password_reset"))
        assert audit.user_id == user.id

    assert login(ada, password=PASSWORD).status_code == 401
    fresh = login(ada, password=NEW_PASSWORD)  # a new login works, in the same second too
    assert fresh.status_code == 200
    assert ada.get("/api/me").status_code == 200


def test_a_verified_email_stays_as_it_was(ada: TestClient, db_connection: Connection) -> None:
    marker = clock.utcnow() - timedelta(days=3)
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE users SET email_verified_at = :t"), {"t": marker})
        db.commit()
    reset(ada, request_token(ada))
    assert the_user(db_connection).email_verified_at == marker


def test_a_token_works_once(ada: TestClient) -> None:
    token = request_token(ada)
    assert reset(ada, token).status_code == 204
    assert reset(ada, token, "another good passphrase").json() == ERR_RESET


def test_unknown_expired_and_wrong_purpose_tokens_share_one_answer(
    ada: TestClient, db_connection: Connection
) -> None:
    expired = request_token(ada)
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE email_tokens SET expires_at = now() - interval '1 second'"))
        db.commit()
    verify = "verify-token-value"
    with Session(bind=db_connection) as db:
        user = db.scalars(select(User)).one()
        db.add(
            EmailToken(
                user_id=user.id,
                purpose="verify",
                token_hash=hashlib.sha256(verify.encode()).hexdigest(),
                expires_at=clock.utcnow() + timedelta(hours=1),
            )
        )
        db.commit()
    for token in ("never-issued", expired, verify):
        response = reset(ada, token)
        assert response.status_code == 400 and response.json() == ERR_RESET
    with Session(bind=db_connection) as db:  # the wrong-purpose token was not used up
        mine = EmailToken.token_hash == hashlib.sha256(verify.encode()).hexdigest()
        assert db.scalars(select(EmailToken).where(mine)).one().used_at is None


def test_the_new_password_follows_the_signup_rules(ada: TestClient) -> None:
    token = request_token(ada)
    assert reset(ada, token, "short").status_code == 422
    assert reset(ada, token, "x" * 129).status_code == 422
    assert reset(ada, token, "x" * 128).status_code == 204


def test_a_deleted_account_cannot_reset(ada: TestClient, db_connection: Connection) -> None:
    token = request_token(ada)
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE users SET deleted_at = now()"))
        db.commit()
    assert reset(ada, token).json() == ERR_RESET


def test_the_eleventh_reset_from_one_ip_is_429(ada: TestClient) -> None:
    codes = [reset(ada, f"bad-{n}").status_code for n in range(11)]
    assert codes == [400] * 10 + [429]


# ---- access tokens and tokens_valid_after ----


def test_without_a_reset_marker_nothing_changes(ada: TestClient) -> None:
    assert ada.get("/api/me").status_code == 200


def test_a_token_from_the_same_second_as_the_reset_marker_is_accepted(
    ada: TestClient, db_connection: Connection
) -> None:
    user = the_user(db_connection)
    now = clock.utcnow().replace(microsecond=900_000)
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE users SET tokens_valid_after = :t"), {"t": now})
        db.commit()
    same_second = create_access_token(user.id, TEST_AUTH_SECRET, now=now.replace(microsecond=0))
    earlier = create_access_token(user.id, TEST_AUTH_SECRET, now=now - timedelta(seconds=1))
    assert ada.get("/api/me", headers=with_cookie("indesk_access", same_second)).status_code == 200
    assert ada.get("/api/me", headers=with_cookie("indesk_access", earlier)).status_code == 401


# ---- logs ----


def test_no_token_address_or_password_reaches_a_log_or_an_audit_row(
    ada: TestClient, db_connection: Connection, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    token = request_token(ada)
    reset(ada, token)
    reset(ada, token)
    forgot(ada, "nobody@example.com")
    for secret in (token, "ada@example.com", NEW_PASSWORD, "nobody@example.com"):
        assert secret not in caplog.text
    with Session(bind=db_connection) as db:
        dump = " ".join(f"{r.action} {r.target} {r.ip_hash}" for r in db.scalars(select(AuditLog)))
    for secret in (token, "ada@example.com", NEW_PASSWORD):
        assert secret not in dump
