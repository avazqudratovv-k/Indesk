"""The email job's decision after each attempt: success, retry, and the final failure with its
log line and audit row. Uses the fake client; the retry schedule is checked on the queued job."""

import logging
import uuid

import pytest
from redis import Redis
from rq import Queue
from sqlalchemy import Connection, select

from app.core.enums import EmailTokenPurpose
from app.core.errors import AppError
from app.db.models import AuditLog
from app.email.client import EmailFailureKind
from app.email.queue import DAILY_KEY, EmailRequest, enqueue_email
from app.jobs.send_email import (
    FAILURE_TTL,
    JOB_TIMEOUT,
    RESULT_TTL,
    RETRY_INTERVALS,
    EmailRetry,
    deliver,
    send_email_job,
)
from tests.ai_helpers import factory_for, limits_with
from tests.conftest import _test_redis_url
from tests.factories import make_user
from tests.fake_email_client import FakeEmailClient, failure

ADDRESS = "someone.private@example.com"
TOKEN = "SECRET-TOKEN-VALUE"
BASE = "https://indesk.uz"


def attempt(
    db_connection: Connection, client: FakeEmailClient, retries_left: int | None
) -> uuid.UUID:
    factory = factory_for(db_connection)
    with factory() as db, db.begin():
        user_id = make_user(db).id
    deliver(
        client,
        factory,
        purpose=EmailTokenPurpose.RESET,
        user_id=user_id,
        to=ADDRESS,
        lang="en",
        token=TOKEN,
        token_id=uuid.uuid4(),
        base_url=BASE,
        retries_left=retries_left,
    )
    return user_id


def audit_rows(db_connection: Connection) -> list[AuditLog]:
    with factory_for(db_connection)() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.action == "email_failed")))


def test_a_success_sends_the_rendered_message_and_writes_no_audit_row(
    db_connection: Connection,
) -> None:
    client = FakeEmailClient()
    attempt(db_connection, client, 3)
    (sent,) = client.sent
    assert sent.to == ADDRESS and f"{BASE}/reset-password#token={TOKEN}" in sent.text
    assert sent.idempotency_key.startswith("reset-")
    assert audit_rows(db_connection) == []


@pytest.mark.parametrize(
    "kind",
    [
        EmailFailureKind.RATE_LIMITED,
        EmailFailureKind.SERVER_ERROR,
        EmailFailureKind.TIMEOUT,
        EmailFailureKind.TRANSPORT,
        EmailFailureKind.CONFLICT,
    ],
)
def test_a_retryable_failure_asks_for_another_try_while_retries_remain(
    db_connection: Connection, kind: EmailFailureKind
) -> None:
    for left in (3, 2, 1):
        with pytest.raises(EmailRetry):
            attempt(db_connection, FakeEmailClient(failure(kind, 503)), left)
    assert audit_rows(db_connection) == []


@pytest.mark.parametrize("last", [0, None])
def test_after_the_last_retry_one_log_line_and_one_audit_row_with_metadata_only(
    db_connection: Connection, caplog: pytest.LogCaptureFixture, last: int | None
) -> None:
    caplog.set_level(logging.INFO, logger="indesk.email")
    user_id = attempt(db_connection, FakeEmailClient(failure(EmailFailureKind.SERVER_ERROR, 503)), last)

    (row,) = audit_rows(db_connection)
    assert (row.user_id, row.target) == (user_id, "reset:server_error:503")
    lines = [r.getMessage() for r in caplog.records if r.name == "indesk.email"]
    assert lines == ["email failed: purpose=reset cause=server_error:503"]
    for private in (ADDRESS, TOKEN, "indesk.uz"):
        assert private not in caplog.text and private not in (row.target or "")


def test_a_rejection_is_final_at_once_even_with_retries_left(db_connection: Connection) -> None:
    client = FakeEmailClient(failure(EmailFailureKind.REJECTED, 403))
    attempt(db_connection, client, 3)  # does not raise
    assert len(client.sent) == 1
    (row,) = audit_rows(db_connection)
    assert row.target == "reset:rejected:403"


def test_retry_failure_text_carries_nothing(db_connection: Connection) -> None:
    with pytest.raises(EmailRetry) as caught:
        attempt(db_connection, FakeEmailClient(failure(EmailFailureKind.TIMEOUT)), 3)
    assert str(caught.value) == ""


# ---- the queued job: schedule, lifetimes, daily cap ----


@pytest.fixture
def redis() -> Redis:
    return Redis.from_url(_test_redis_url())


def request_for(n: int = 0) -> EmailRequest:
    return EmailRequest(
        purpose=EmailTokenPurpose.VERIFY,
        user_id=uuid.uuid4(),
        to=ADDRESS,
        lang="ko",
        token=TOKEN,
        token_id=uuid.uuid4(),
    )


def test_the_queued_job_retries_after_1_5_and_15_minutes_and_expires_quickly(
    redis: Redis,
) -> None:
    request = request_for()
    assert enqueue_email(redis, limits_with(), request) is True

    (job,) = Queue("default", connection=redis).jobs
    assert RETRY_INTERVALS == [60, 300, 900]
    assert (job.retries_left, job.retry_intervals) == (3, [60, 300, 900])
    assert (job.result_ttl, job.failure_ttl, job.timeout) == (RESULT_TTL, FAILURE_TTL, JOB_TIMEOUT)
    assert RESULT_TTL <= 60 and FAILURE_TTL <= 3600
    assert job.func is send_email_job
    assert job.args[0] == "verify" and job.id == f"email-{request.token_id}"
    assert TOKEN not in repr(request) and ADDRESS not in repr(request)


def test_the_daily_cap_stops_the_queue_without_an_error(
    redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    limits = limits_with(email_daily_global=2)
    caplog.set_level(logging.WARNING, logger="indesk.email")
    results = [enqueue_email(redis, limits, request_for()) for _ in range(4)]

    assert results == [True, True, False, False]
    assert len(Queue("default", connection=redis).jobs) == 2
    keys = [k for k in redis.scan_iter(match=DAILY_KEY.format(day="*"))]
    assert len(keys) == 1 and redis.ttl(keys[0]) > 0
    assert ADDRESS not in caplog.text and TOKEN not in caplog.text


def test_with_redis_down_the_request_is_refused_not_dropped() -> None:
    dead = Redis(host="127.0.0.1", port=1, db=15, socket_connect_timeout=0.2)
    with pytest.raises(AppError) as caught:
        enqueue_email(dead, limits_with(), request_for())
    assert caught.value.status == 503
