"""scripts/smoke_live.py --reset-quota: a dev helper that clears the smoke account's own run usage
and rate-limit keys, and refuses everywhere but APP_ENV=development. No network, no real Gemini."""

import importlib.util
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Connection, func, select

from app.core.config import Settings
from app.core.security import keyed_hash
from app.db.models import UsageDaily, UsageEvent
from tests.ai_helpers import factory_for
from tests.conftest import TEST_AUTH_SECRET
from tests.factories import make_user
from tests.test_uploads import settings_for

# A day long past, so the rows cannot collide with a real day's counters in the test database.
DAY = date(2001, 1, 2)
MINE = (UsageDaily.day <= DAY, UsageDaily.day >= DAY - timedelta(days=1))


def load_script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_live.py"
    spec = importlib.util.spec_from_file_location("smoke_live_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemoryRedis:
    def __init__(self, keys: list[str]) -> None:
        self.keys = set(keys)

    def scan_iter(self, match: str) -> Iterator[str]:
        prefix, _, suffix = match.partition("*")
        return iter([k for k in sorted(self.keys) if k.startswith(prefix) and k.endswith(suffix)])

    def delete(self, *keys: str) -> int:
        gone = self.keys & set(keys)
        self.keys -= gone
        return len(gone)


def settings_in(env: str, tmp_path: Path) -> Settings:
    return settings_for(tmp_path).model_copy(update={"app_env": env})


def test_it_refuses_outside_development_and_touches_nothing(
    db_connection: Connection, tmp_path: Path
) -> None:
    script = load_script()
    factory = factory_for(db_connection)
    with factory() as db, db.begin():
        user = make_user(db, email=script.EMAIL)
        db.add(UsageEvent(user_id=user.id, kind="run", amount=1))
        db.add(UsageDaily(day=DAY, scope=f"user:{user.id}", user_id=user.id, runs=3))
        user_id = user.id
    redis = MemoryRedis([f"rl:run:{user_id}"])
    for env in ("test", "production"):
        with factory() as db, pytest.raises(SystemExit, match="only works in development"):
            script.reset_quota(settings_in(env, tmp_path), db, redis, "10.0.0.5")
    assert redis.keys == {f"rl:run:{user_id}"}
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(UsageEvent)) == 1
        assert db.scalar(select(func.count()).select_from(UsageDaily).where(*MINE)) == 1


def test_in_development_it_clears_only_the_smoke_accounts_own_rows_and_keys(
    db_connection: Connection, tmp_path: Path
) -> None:
    script = load_script()
    factory = factory_for(db_connection)
    with factory() as db, db.begin():
        smoke = make_user(db, email=script.EMAIL)
        other = make_user(db)
        db.add_all(
            [
                UsageEvent(user_id=smoke.id, kind="run", amount=1),
                UsageEvent(user_id=other.id, kind="run", amount=1),
            ]
        )
        today, yesterday = DAY, DAY - timedelta(days=1)
        db.add_all(
            [
                UsageDaily(day=today, scope=f"user:{smoke.id}", user_id=smoke.id, runs=5),
                UsageDaily(day=yesterday, scope=f"user:{smoke.id}", user_id=smoke.id, runs=2),
                UsageDaily(day=today, scope=f"user:{other.id}", user_id=other.id, runs=7),
                UsageDaily(day=today, scope="global", user_id=None, runs=40, model_calls=90),
            ]
        )
        smoke_id, other_id = smoke.id, other.id
    secret = TEST_AUTH_SECRET
    mine = keyed_hash(secret, script.EMAIL)
    keep = {f"rl:run:{other_id}", f"rl:login:iphash:{keyed_hash(secret, 'someone@x.test')}",
            f"rl:signup:{keyed_hash(secret, '10.9.9.9')}", "rl:upload:abc"}  # fmt: skip
    gone = {f"rl:run:{smoke_id}", f"rl:login:ip-a:{mine}", f"rl:login:ip-b:{mine}",
            f"rl:signup:{keyed_hash(secret, '10.0.0.5')}"}  # fmt: skip
    redis = MemoryRedis([*keep, *gone])
    with factory() as db:
        done = script.reset_quota(settings_in("development", tmp_path), db, redis, "10.0.0.5")
    assert redis.keys == keep
    assert done[0] == "usage_events (run) deleted: 1"
    assert done[1] == "usage_daily (this user's counters) deleted: 2"
    with factory() as db:  # the other user's and the global counters stay as they were
        left_daily = sorted(
            (row.scope == "global", row.runs) for row in db.scalars(select(UsageDaily).where(*MINE))
        )
    assert left_daily == [(False, 7), (True, 40)]
    with factory() as db:
        left = list(db.scalars(select(UsageEvent.user_id)))
    assert left == [other_id]


def test_a_first_run_without_the_account_still_clears_the_login_and_signup_keys(
    db_connection: Connection, tmp_path: Path
) -> None:
    script = load_script()
    factory = factory_for(db_connection)
    mine = keyed_hash(TEST_AUTH_SECRET, script.EMAIL)
    redis = MemoryRedis([f"rl:login:ip:{mine}"])
    with factory() as db:
        done = script.reset_quota(settings_in("development", tmp_path), db, redis, None)
    assert redis.keys == set() and done == ["redis rate-limit keys deleted: 1"]
