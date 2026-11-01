"""Sign-up verification: the email queued at sign-up, confirm and resend, /me, the run gate, and
the rule that a reset token and a verify token never work for each other."""

import hashlib
import logging
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis import Redis
from rq import Queue
from sqlalchemy import Connection, func, select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.db.models import AuditLog, EmailToken, Run, UsageDaily, UsageEvent, User
from app.main import app
from app.routers.runs import get_enqueue, get_session_factory
from tests.ai_helpers import factory_for
from tests.conftest import _test_redis_url
from tests.test_auth import MakeClient, signup
from tests.test_password_reset import NEW_PASSWORD, RESET, forgot
from tests.test_runs_api import URL as RUNS
from tests.test_runs_api import body, new_upload
from tests.test_uploads import settings_for, signed_in

CONFIRM = "/api/auth/verify/confirm"
RESEND = "/api/auth/verify/resend"
ERR_VERIFY = {"error": {"code": "VERIFY_TOKEN_INVALID"}}
ERR_RESET = {"error": {"code": "RESET_TOKEN_INVALID"}}
ERR_NOT_VERIFIED = {"error": {"code": "EMAIL_NOT_VERIFIED"}}


def confirm(client: TestClient, token: str) -> Any:
    return client.post(CONFIRM, json={"token": token})


def queued(purpose: str = "verify") -> list[Any]:
    queue = Queue("default", connection=Redis.from_url(_test_redis_url()))
    return [job for job in queue.jobs if job.args[0] == purpose]


def verify_token() -> str:
    """The plain token of the one queued verification email (args[4])."""
    (job,) = queued()
    return str(job.args[4])


def tokens(conn: Connection, purpose: str = "verify") -> list[EmailToken]:
    with Session(bind=conn) as db:
        return list(
            db.scalars(
                select(EmailToken)
                .where(EmailToken.purpose == purpose)
                .order_by(EmailToken.created_at)
            )
        )


def the_user(conn: Connection) -> User:
    with Session(bind=conn) as db:
        return db.scalars(select(User)).one()


def mark_verified(conn: Connection) -> None:
    with Session(bind=conn) as db:
        db.execute(text("UPDATE users SET email_verified_at = now()"))
        db.commit()


@pytest.fixture
def ada(auth_client: TestClient) -> TestClient:
    assert signup(auth_client).status_code == 201
    return auth_client


# ---- sign-up ----


def test_signup_queues_the_verification_email_in_the_chosen_language(
    auth_client: TestClient, db_connection: Connection
) -> None:
    assert signup(auth_client, lang="ko").status_code == 201
    (job,) = queued()
    assert job.args[0] == "verify" and job.args[2] == "ada@example.com" and job.args[3] == "ko"
    (row,) = tokens(db_connection)
    assert row.token_hash == hashlib.sha256(job.args[4].encode()).hexdigest()
    assert row.expires_at - row.created_at == pytest.approx(
        timedelta(hours=24), abs=timedelta(seconds=5)
    )
    assert the_user(db_connection).lang == "ko"


@pytest.mark.parametrize("lang", [None, "en", "ja", "zz", ""])
def test_any_other_language_is_english(
    auth_client: TestClient, db_connection: Connection, lang: str | None
) -> None:
    extra = {} if lang is None else {"lang": lang}
    assert signup(auth_client, **extra).status_code == 201
    assert queued()[0].args[3] == "en" and the_user(db_connection).lang == "en"


def test_signup_still_works_when_the_queue_fails(
    auth_client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(*_: object, **__: object) -> bool:
        raise AppError(503, ErrorCode.NOT_READY)

    monkeypatch.setattr("app.routers.auth.enqueue_email", broken)
    caplog.set_level(logging.DEBUG)
    response = signup(auth_client)
    assert response.status_code == 201 and response.json()["email_verified"] is False
    assert tokens(db_connection) == [] and queued() == []  # nothing dangling
    assert auth_client.get("/api/me").status_code == 200  # and the user is signed in
    assert "ada@example.com" not in caplog.text


def test_signup_still_works_when_the_token_cannot_be_made(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object, **__: object) -> None:
        raise RuntimeError("boom ada@example.com")

    monkeypatch.setattr("app.services.auth.issue_token", broken)
    assert signup(auth_client).status_code == 201


def test_the_daily_cap_does_not_fail_signup_and_keeps_no_token(
    make_client: MakeClient, auth_settings: Settings, db_connection: Connection
) -> None:
    limits = auth_settings.limits.model_copy(update={"email_daily_global": 1})
    client = make_client(auth_settings.model_copy(update={"limits": limits}))
    assert signup(client, "one@example.com").status_code == 201
    assert signup(client, "two@example.com").status_code == 201
    assert len(queued()) == 1 and len(tokens(db_connection)) == 1


def test_an_email_that_is_taken_is_still_409(auth_client: TestClient) -> None:
    signup(auth_client)
    again = signup(auth_client)
    assert again.status_code == 409 and again.json() == {"error": {"code": "EMAIL_TAKEN"}}
    assert len(queued()) == 1


# ---- confirm ----


def test_confirm_verifies_once_without_a_login(
    ada: TestClient, make_client: MakeClient, auth_settings: Settings, db_connection: Connection
) -> None:
    token = verify_token()
    assert ada.get("/api/me").json()["email_verified"] is False
    stranger = make_client(auth_settings, peer=("203.0.113.50", 1))  # no cookies at all
    response = confirm(stranger, token)
    assert response.status_code == 204 and response.content == b""
    assert the_user(db_connection).email_verified_at is not None
    assert ada.get("/api/me").json()["email_verified"] is True
    assert confirm(stranger, token).json() == ERR_VERIFY  # single use
    with Session(bind=db_connection) as db:
        assert db.scalars(select(AuditLog).where(AuditLog.action == "email_verified")).one()


def test_confirm_keeps_an_earlier_verification_time(
    ada: TestClient, db_connection: Connection
) -> None:
    marker = clock.utcnow() - timedelta(days=2)
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE users SET email_verified_at = :t"), {"t": marker})
        db.commit()
    assert confirm(ada, verify_token()).status_code == 204
    assert the_user(db_connection).email_verified_at == marker


def test_unknown_used_expired_and_wrong_purpose_tokens_share_one_answer(
    ada: TestClient, db_connection: Connection
) -> None:
    expired = verify_token()
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE email_tokens SET expires_at = now() - interval '1 second'"))
        db.commit()
    assert forgot(ada).status_code == 202
    (job,) = queued("reset")
    reset_token = str(job.args[4])
    for token in ("never-issued", expired, reset_token):
        response = confirm(ada, token)
        assert response.status_code == 400 and response.json() == ERR_VERIFY
    assert the_user(db_connection).email_verified_at is None
    assert tokens(db_connection, "reset")[0].used_at is None  # a reset token is not used up


def test_a_verify_token_cannot_reset_a_password(ada: TestClient, db_connection: Connection) -> None:
    token = verify_token()
    response = ada.post(RESET, json={"token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 400 and response.json() == ERR_RESET
    assert tokens(db_connection)[0].used_at is None
    assert the_user(db_connection).tokens_valid_after is None


def test_a_deleted_account_cannot_confirm(ada: TestClient, db_connection: Connection) -> None:
    token = verify_token()
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE users SET deleted_at = now()"))
        db.commit()
    assert confirm(ada, token).json() == ERR_VERIFY


def test_confirm_is_limited_per_ip_and_fails_closed(
    ada: TestClient, make_client: MakeClient, auth_settings: Settings
) -> None:
    codes = [confirm(ada, f"bad-{n}").status_code for n in range(11)]
    assert codes == [400] * 10 + [429]
    down = auth_settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/15")})
    response = confirm(make_client(down), "x")
    assert response.status_code == 503 and response.json() == {"error": {"code": "NOT_READY"}}


def test_confirm_validates_the_body(ada: TestClient) -> None:
    assert ada.post(CONFIRM, json={}).status_code == 422
    assert ada.post(CONFIRM, json={"token": ""}).status_code == 422
    assert ada.post(CONFIRM, json={"token": "a", "x": 1}).status_code == 422


# ---- resend ----


def test_resend_needs_a_login(
    ada: TestClient, make_client: MakeClient, auth_settings: Settings
) -> None:
    anonymous = make_client(auth_settings, peer=("203.0.113.51", 1))
    assert anonymous.post(RESEND).status_code == 401


def test_resend_retires_the_older_link_and_queues_a_new_one(
    ada: TestClient, db_connection: Connection
) -> None:
    first = verify_token()
    assert ada.post(RESEND).status_code == 204
    jobs = queued()
    assert len(jobs) == 2
    first_row, second_row = tokens(db_connection)
    assert first_row.used_at is not None and second_row.used_at is None
    assert jobs[1].args[4] != first and jobs[1].args[3] == "en"
    assert confirm(ada, first).json() == ERR_VERIFY
    assert confirm(ada, str(jobs[1].args[4])).status_code == 204


def test_resend_is_limited_to_three_an_hour_per_user_and_fails_closed(
    ada: TestClient, make_client: MakeClient, auth_settings: Settings
) -> None:
    assert [ada.post(RESEND).status_code for _ in range(4)] == [204, 204, 204, 429]
    assert ada.post(RESEND).headers["retry-after"]
    # Another user is not blocked.
    other = make_client(auth_settings, peer=("203.0.113.52", 1))
    signup(other, "bob@example.com")
    assert other.post(RESEND).status_code == 204


def test_resend_with_redis_down_is_503(
    ada: TestClient, make_client: MakeClient, auth_settings: Settings, db_connection: Connection
) -> None:
    down = auth_settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/15")})
    client = make_client(down)
    client.cookies.update(ada.cookies)
    assert client.post(RESEND).status_code == 503


def test_resend_for_a_verified_user_sends_nothing(
    ada: TestClient, db_connection: Connection
) -> None:
    mark_verified(db_connection)
    before = len(queued())
    response = ada.post(RESEND)
    assert response.status_code == 204 and response.content == b""
    assert len(queued()) == before and len(tokens(db_connection)) == 1


def test_resend_at_the_daily_cap_answers_the_same_and_keeps_the_old_link(
    make_client: MakeClient, auth_settings: Settings, db_connection: Connection
) -> None:
    limits = auth_settings.limits.model_copy(update={"email_daily_global": 1})
    client = make_client(auth_settings.model_copy(update={"limits": limits}))
    signup(client)
    first = verify_token()
    response = client.post(RESEND)
    assert response.status_code == 204 and response.content == b""
    assert len(queued()) == 1
    (row,) = tokens(db_connection)
    assert row.used_at is None
    assert confirm(client, first).status_code == 204


# ---- /me ----


def test_me_has_email_verified_and_not_the_time(ada: TestClient) -> None:
    body_ = ada.get("/api/me").json()
    assert body_["email_verified"] is False and "email_verified_at" not in body_
    assert signup(ada, "x@example.com").json()["email_verified"] is False


# ---- the run gate ----


@pytest.fixture
def enqueued() -> list[uuid.UUID]:
    return []


@pytest.fixture(autouse=True)
def _wire(db_connection: Connection, enqueued: list[uuid.UUID]) -> None:
    app.dependency_overrides[get_enqueue] = lambda: enqueued.append
    app.dependency_overrides[get_session_factory] = lambda: factory_for(db_connection)


def gated(tmp_path: Path, on: bool) -> Settings:
    return settings_for(tmp_path).model_copy(update={"email_verification_required": on})


def counts(conn: Connection) -> tuple[int, int, int]:
    with Session(bind=conn) as db:
        return tuple(  # type: ignore[return-value]
            db.scalar(select(func.count()).select_from(model)) or 0
            for model in (Run, UsageDaily, UsageEvent)
        )


def test_the_gate_refuses_an_unverified_user_before_anything_is_touched(
    make_client: MakeClient, tmp_path: Path, db_connection: Connection, enqueued: list[uuid.UUID]
) -> None:
    client = signed_in(make_client, gated(tmp_path, True), "gate@example.com", 20)
    upload = new_upload(client)  # uploads are not gated
    before = counts(db_connection)
    response = client.post(RUNS, json=body(upload))
    assert response.status_code == 403 and response.json() == ERR_NOT_VERIFIED
    assert counts(db_connection) == before and enqueued == []
    assert client.get("/api/me").status_code == 200  # nothing else is gated
    assert client.post(RESEND).status_code == 204


def test_the_gate_lets_a_verified_user_through(
    make_client: MakeClient, tmp_path: Path, db_connection: Connection, enqueued: list[uuid.UUID]
) -> None:
    client = signed_in(make_client, gated(tmp_path, True), "gate@example.com", 21)
    upload = new_upload(client)
    assert client.post(RUNS, json=body(upload)).status_code == 403
    assert confirm(client, verify_token()).status_code == 204
    assert client.post(RUNS, json=body(upload)).status_code == 202 and len(enqueued) == 1


def test_a_user_verified_before_the_gate_existed_passes_it(
    make_client: MakeClient, tmp_path: Path, db_connection: Connection
) -> None:
    client = signed_in(make_client, gated(tmp_path, True), "old@example.com", 22)
    mark_verified(db_connection)  # what the 0007 backfill did for every existing account
    upload = new_upload(client)
    assert client.post(RUNS, json=body(upload)).status_code == 202


def test_with_the_gate_off_nothing_changes(
    make_client: MakeClient, tmp_path: Path, enqueued: list[uuid.UUID]
) -> None:
    client = signed_in(make_client, gated(tmp_path, False), "free@example.com", 23)
    upload = new_upload(client)
    assert client.post(RUNS, json=body(upload)).status_code == 202 and len(enqueued) == 1


# ---- logs ----


def test_no_token_or_address_reaches_a_log_or_an_audit_row(
    auth_client: TestClient, db_connection: Connection, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    signup(auth_client)
    token = verify_token()
    auth_client.post(RESEND)
    confirm(auth_client, token)
    confirm(auth_client, token)
    for secret in (token, "ada@example.com"):
        assert secret not in caplog.text
    with Session(bind=db_connection) as db:
        dump = " ".join(f"{r.action} {r.target} {r.ip_hash}" for r in db.scalars(select(AuditLog)))
    assert token not in dump and "ada@example.com" not in dump
