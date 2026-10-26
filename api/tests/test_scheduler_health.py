from pathlib import Path

import pytest

from app.jobs import scheduler_health
from tests.conftest import _test_redis_url


def test_pid_1_must_be_the_scheduler(tmp_path: Path) -> None:
    good = tmp_path / "good"
    good.write_bytes(b"python\0-m\0app.jobs.scheduler\0")
    other = tmp_path / "other"
    other.write_bytes(b"python\0-m\0app.jobs.worker\0")
    assert scheduler_health.scheduler_is_pid_1(good) is True
    assert scheduler_health.scheduler_is_pid_1(other) is False
    assert scheduler_health.scheduler_is_pid_1(tmp_path / "missing") is False


def test_redis_answers() -> None:
    assert scheduler_health.redis_answers(_test_redis_url()) is True
    assert scheduler_health.redis_answers("redis://127.0.0.1:1/15") is False


def test_main_is_unhealthy_when_either_check_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler_health, "scheduler_is_pid_1", lambda: True)
    monkeypatch.setattr(scheduler_health, "redis_answers", lambda url: True)
    assert scheduler_health.main() == 0
    monkeypatch.setattr(scheduler_health, "redis_answers", lambda url: False)
    assert scheduler_health.main() == 1
    monkeypatch.setattr(scheduler_health, "redis_answers", lambda url: True)
    monkeypatch.setattr(scheduler_health, "scheduler_is_pid_1", lambda: False)
    assert scheduler_health.main() == 1
