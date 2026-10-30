"""Read limit (120 a minute, fails open) and delete limit (30 an hour, fails closed), per user."""

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import SecretStr
from redis import Redis

from app.core import ratelimit
from app.core.config import Settings, get_settings, load_limits
from app.core.errors import AppError
from app.main import app
from tests.conftest import TEST_AUTH_SECRET, _test_redis_url
from tests.test_auth import MakeClient, signup

MISSING = "/api/reports/" + "0" * 32
MISSING_UPLOAD = "/api/uploads/" + "0" * 32


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        auth_secret=TEST_AUTH_SECRET,
        redis_url=_test_redis_url(),
        storage_dir=tmp_path / "storage",
        limits=load_limits(),
    )


def client_for(make_client: MakeClient, settings: Settings, email: str, peer_last: int) -> Any:
    client = make_client(settings, peer=(f"203.0.113.{peer_last}", 50000))
    assert signup(client, email).status_code == 201
    return client


def redis_down(settings: Settings) -> None:
    down = settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/15")})
    app.dependency_overrides[get_settings] = lambda: down


def test_the_numbers_are_in_the_config_file() -> None:
    limits = load_limits()
    assert (limits.reads_per_minute, limits.deletes_per_hour) == (120, 30)


def test_the_keys_are_required_and_drift_is_rejected() -> None:
    from app.core.config import Limits  # noqa: PLC0415

    values = load_limits().model_dump()
    for key in ("reads_per_minute", "deletes_per_hour"):
        with pytest.raises(ValueError):
            Limits(**{k: v for k, v in values.items() if k != key})
        with pytest.raises(ValueError):
            Limits(**{**values, key: 0})
    with pytest.raises(ValueError):
        Limits(**{**values, "reads_per_minutes": 5})


def test_the_121st_read_in_a_minute_is_429_shared_by_reports_and_uploads(
    make_client: MakeClient, settings: Settings
) -> None:
    client = client_for(make_client, settings, "reader@example.com", 60)
    for _ in range(40):
        assert client.get("/api/reports").status_code == 200
        assert client.get(MISSING).status_code == 404  # a miss still counts
        assert client.get("/api/uploads").status_code == 200
    blocked = client.get("/api/uploads/" + uuid4().hex)
    assert blocked.status_code == 429
    assert blocked.json() == {"error": {"code": "RATE_LIMITED"}}
    assert 0 < int(blocked.headers["retry-after"]) <= 60
    assert client.get(MISSING_UPLOAD).status_code == 429
    assert client.get("/api/reports").status_code == 429


def test_the_31st_delete_in_an_hour_is_429_shared_by_reports_and_uploads(
    make_client: MakeClient, settings: Settings
) -> None:
    client = client_for(make_client, settings, "deleter@example.com", 61)
    for _ in range(15):
        assert client.delete(MISSING).status_code == 404
        assert client.delete(MISSING_UPLOAD).status_code == 404
    blocked = client.delete(MISSING)
    assert blocked.status_code == 429
    assert blocked.json() == {"error": {"code": "RATE_LIMITED"}}
    assert 0 < int(blocked.headers["retry-after"]) <= 3600
    assert client.delete(MISSING_UPLOAD).status_code == 429


def test_reads_and_deletes_are_counted_apart(make_client: MakeClient, settings: Settings) -> None:
    client = client_for(make_client, settings, "apart@example.com", 62)
    for _ in range(31):
        client.delete(MISSING)
    assert client.delete(MISSING).status_code == 429
    assert client.get("/api/reports").status_code == 200


def test_limits_are_per_user(make_client: MakeClient, settings: Settings) -> None:
    busy = client_for(make_client, settings, "busy@example.com", 63)
    calm = client_for(make_client, settings, "calm@example.com", 64)
    for _ in range(31):
        busy.delete(MISSING)
    for _ in range(121):
        busy.get("/api/reports")
    assert busy.delete(MISSING).status_code == 429
    assert busy.get("/api/reports").status_code == 429
    assert calm.delete(MISSING).status_code == 404
    assert calm.get("/api/reports").status_code == 200


def test_signed_out_calls_are_401_and_do_not_count(
    make_client: MakeClient, settings: Settings
) -> None:
    anonymous = make_client(settings, peer=("203.0.113.65", 50000))
    for _ in range(130):
        assert anonymous.get("/api/reports").status_code == 401
    assert anonymous.delete(MISSING).status_code == 401


def test_redis_down_reads_still_work_and_one_warning_is_logged(
    make_client: MakeClient, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    client = client_for(make_client, settings, "open@example.com", 66)
    redis_down(settings)
    with caplog.at_level(logging.WARNING, logger="indesk.ratelimit"):
        assert client.get("/api/reports").status_code == 200
        assert client.get("/api/uploads").status_code == 200
        assert client.get(MISSING).status_code == 404
    lines = [r for r in caplog.records if r.name == "indesk.ratelimit"]
    assert len(lines) == 3  # one line per skipped check
    for record in lines:
        text = record.getMessage()
        assert "open@example.com" not in text
        assert "rl:" not in text


def test_redis_down_deletes_are_refused_503(make_client: MakeClient, settings: Settings) -> None:
    client = client_for(make_client, settings, "closed@example.com", 67)
    redis_down(settings)
    for url in (MISSING, MISSING_UPLOAD):
        response = client.delete(url)
        assert response.status_code == 503
        assert response.json() == {"error": {"code": "NOT_READY"}}


# ---- the limiter itself: the default is unchanged ----


def broken_redis() -> Redis:
    return Redis.from_url("redis://127.0.0.1:1/15", socket_connect_timeout=1, socket_timeout=1)


def test_hit_fails_closed_by_default() -> None:
    with pytest.raises(AppError) as caught:
        ratelimit.hit(broken_redis(), "rl:x", 5, 60)
    assert caught.value.status == 503


def test_hit_fail_open_passes_when_redis_is_down(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="indesk.ratelimit"):
        ratelimit.hit(broken_redis(), "rl:x", 5, 60, fail_open=True)
    assert len(caplog.records) == 1


def test_fail_open_still_counts_and_refuses_over_the_limit() -> None:
    redis = Redis.from_url(_test_redis_url())
    try:
        for _ in range(3):
            ratelimit.hit(redis, "rl:fo", 3, 60, fail_open=True)
        with pytest.raises(AppError) as caught:
            ratelimit.hit(redis, "rl:fo", 3, 60, fail_open=True)
        assert caught.value.status == 429
        assert caught.value.headers is not None
        assert "Retry-After" in caught.value.headers
    finally:
        redis.close()


def test_existing_limiter_constants_are_unchanged() -> None:
    assert (ratelimit.SIGNUP_LIMIT, ratelimit.SIGNUP_WINDOW) == (5, 3600)
    assert (ratelimit.LOGIN_LIMIT, ratelimit.LOGIN_WINDOW) == (10, 900)
    assert (ratelimit.UPLOAD_WINDOW, ratelimit.RUN_WINDOW) == (3600, 3600)
