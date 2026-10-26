"""Daily caps: per user, global, atomic, one slot per attempt, fail closed. No network."""

import threading
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.ai.caps import SessionFactory, reserve_call
from app.ai.gateway import Gateway, GatewayError, GatewayOk
from app.core.enums import AiPurpose, CapDecision, GatewayOutcome
from tests.ai_helpers import DAY, ai_rows, factory_for, limits_with, make_gateway, new_user, usage
from tests.factories import make_user
from tests.fake_model_client import FakeClient, ok, rate_limited


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


def ask(gateway: Gateway, user: uuid.UUID) -> GatewayOk | GatewayError:
    return gateway.ask("hello", purpose=AiPurpose.ROUTE, user_id=user)


def test_per_user_cap(factory: SessionFactory) -> None:
    user = new_user(factory)
    client = FakeClient([ok(), ok(), ok()])
    gateway = make_gateway(factory, client, limits=limits_with(daily_calls_per_user=2))
    assert isinstance(ask(gateway, user), GatewayOk)
    assert isinstance(ask(gateway, user), GatewayOk)
    third = ask(gateway, user)
    assert isinstance(third, GatewayError)
    assert (third.outcome, third.cap_scope) == (GatewayOutcome.CAP_REACHED, "user")
    assert len(client.calls) == 2  # refused BEFORE any model call
    assert len(ai_rows(factory)) == 2


def test_global_cap_across_users(factory: SessionFactory) -> None:
    a, b, c = (new_user(factory) for _ in range(3))
    client = FakeClient([ok(), ok(), ok()])
    gateway = make_gateway(factory, client, limits=limits_with(daily_calls_global=2))
    assert isinstance(ask(gateway, a), GatewayOk)
    assert isinstance(ask(gateway, b), GatewayOk)
    refused = ask(gateway, c)
    assert isinstance(refused, GatewayError)
    assert (refused.outcome, refused.cap_scope) == (GatewayOutcome.CAP_REACHED, "global")
    assert len(client.calls) == 2


def test_one_users_cap_does_not_block_another(factory: SessionFactory) -> None:
    a, b = new_user(factory), new_user(factory)
    gateway = make_gateway(
        factory, FakeClient([ok(), ok()]), limits=limits_with(daily_calls_per_user=1)
    )
    assert isinstance(ask(gateway, a), GatewayOk)
    assert isinstance(ask(gateway, b), GatewayOk)


def test_a_new_day_starts_at_zero(factory: SessionFactory) -> None:
    user = new_user(factory)
    limits = limits_with(daily_calls_per_user=1)
    client = FakeClient([ok(), ok()])
    assert isinstance(ask(make_gateway(factory, client, limits=limits), user), GatewayOk)
    tomorrow = make_gateway(factory, client, limits=limits, day=DAY + timedelta(days=1))
    assert isinstance(ask(tomorrow, user), GatewayOk)


def test_a_refused_reserve_counts_nothing(factory: SessionFactory) -> None:
    a, b = new_user(factory), new_user(factory)
    limits = limits_with(daily_calls_global=1, daily_calls_per_user=5)
    gateway = make_gateway(factory, FakeClient([ok(), ok()]), limits=limits)
    assert isinstance(ask(gateway, a), GatewayOk)
    refused = ask(gateway, b)  # B's user row is bumped first, then global refuses: all rolled back
    assert isinstance(refused, GatewayError) and refused.cap_scope == "global"
    assert usage(factory, f"user:{b}") == 0
    assert usage(factory, "global") == 1
    # and a user-cap refusal leaves the global counter alone
    c = new_user(factory)
    capped = make_gateway(factory, FakeClient([ok()]), limits=limits_with(daily_calls_per_user=1))
    assert isinstance(ask(capped, c), GatewayOk)
    before = usage(factory, "global")
    assert isinstance(ask(capped, c), GatewayError)
    assert usage(factory, "global") == before


def test_a_fallback_attempt_counts_one_slot(factory: SessionFactory) -> None:
    user = new_user(factory)
    gateway = make_gateway(factory, FakeClient([rate_limited(), ok()]))
    assert isinstance(ask(gateway, user), GatewayOk)
    assert usage(factory, f"user:{user}") == 2
    assert usage(factory, "global") == 2


def test_a_cap_hit_between_attempts_stops_the_chain(factory: SessionFactory) -> None:
    user = new_user(factory)
    client = FakeClient([rate_limited(), ok()])
    gateway = make_gateway(factory, client, limits=limits_with(daily_calls_per_user=1))
    result = ask(gateway, user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.CAP_REACHED
    assert len(client.calls) == 1 and result.attempts == 1
    assert usage(factory, f"user:{user}") == 1  # the refused second reserve counted nothing


def test_fail_closed_when_the_store_raises(factory: SessionFactory) -> None:
    user = new_user(factory)

    def broken() -> Session:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    client = FakeClient([ok()])
    result = ask(make_gateway(broken, client), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.MODEL_UNAVAILABLE
    assert not client.calls


def test_fail_closed_when_the_database_is_unreachable(factory: SessionFactory) -> None:
    user = new_user(factory)
    dead: Engine = create_engine(
        "postgresql+psycopg://nobody:nopass@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
    )
    client = FakeClient([ok()])
    result = ask(make_gateway(lambda: Session(dead), client), user)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.MODEL_UNAVAILABLE
    assert not client.calls
    dead.dispose()


def test_an_unknown_user_fails_closed(factory: SessionFactory) -> None:
    decision = reserve_call(factory, user_id=uuid.uuid4(), day=DAY, per_user=5, per_day=5)
    assert decision is CapDecision.UNAVAILABLE  # the foreign key refuses it


def test_the_reserve_is_atomic_under_concurrency(migrated_engine: Engine) -> None:
    """Real commits from many threads against one cap. Cleans up after itself."""
    day = date(2031, 1, 1)
    with Session(migrated_engine) as db, db.begin():
        user_id = make_user(db).id

    def build() -> Session:
        return Session(migrated_engine)

    results: list[CapDecision] = []
    lock = threading.Lock()

    def worker() -> None:
        decision = reserve_call(build, user_id=user_id, day=day, per_user=5, per_day=1000)
        with lock:
            results.append(decision)

    try:
        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results.count(CapDecision.RESERVED) == 5
        assert results.count(CapDecision.USER_CAP) == 15
        with Session(migrated_engine) as db:
            count = db.execute(
                text("SELECT model_calls FROM usage_daily WHERE day = :d AND scope = :s"),
                {"d": day, "s": f"user:{user_id}"},
            ).scalar_one()
        assert count == 5
    finally:
        with Session(migrated_engine) as db, db.begin():
            db.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})  # cascades
            db.execute(text("DELETE FROM usage_daily WHERE day = :d"), {"d": day})
