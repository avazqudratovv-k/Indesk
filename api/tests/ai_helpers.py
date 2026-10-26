"""Builders shared by the gateway tests: a gateway on the test connection, a user, row readers."""

import uuid
from datetime import date
from typing import Any

from pydantic import SecretStr
from sqlalchemy import Connection, select
from sqlalchemy.orm import Session

from app.ai.caps import SessionFactory
from app.ai.config import ModelChain, ModelChains, ModelSpec
from app.ai.gateway import Gateway
from app.core.config import Limits, load_limits
from app.db.models import AiCall, UsageDaily
from tests.factories import make_user
from tests.fake_model_client import API_KEY, FakeClient, FakeClock

DAY = date(2026, 10, 26)

# The chain most tests use for BOTH job classes. It is not the file's chain: the file's chains are
# tested on their own (test_ai_chains.py), so a change of model names there breaks nothing else.
PRIMARY, FALLBACK = "gemini-2.5-flash", "gemini-2.5-flash-lite"
TEST_CHAIN = ModelChain(
    total_budget_seconds=35,
    chain=[
        ModelSpec(name=PRIMARY, timeout_seconds=20, max_output_tokens=4096, thinking_budget=1024),
        ModelSpec(name=FALLBACK, timeout_seconds=12, max_output_tokens=4096, thinking_budget=0),
    ],
)


def factory_for(connection: Connection) -> SessionFactory:
    def build() -> Session:
        return Session(bind=connection, join_transaction_mode="create_savepoint")

    return build


def new_user(factory: SessionFactory) -> uuid.UUID:
    with factory() as db, db.begin():
        return make_user(db).id


def limits_with(**overrides: int) -> Limits:
    return Limits(**{**load_limits().model_dump(), **overrides})


def chain_with(**overrides: Any) -> ModelChain:
    return ModelChain(**{**TEST_CHAIN.model_dump(), **overrides})


def make_gateway(
    factory: SessionFactory,
    client: FakeClient | None,
    *,
    clock: FakeClock | None = None,
    limits: Limits | None = None,
    chain: ModelChain | None = None,
    chains: ModelChains | None = None,
    api_key: str | None = API_KEY,
    day: date = DAY,
) -> Gateway:
    clock = clock or FakeClock()
    if client is not None and client.clock is None:
        client.clock = clock
    return Gateway(
        api_key=SecretStr(api_key) if api_key is not None else None,
        chains=chains or ModelChains(light=chain or TEST_CHAIN, main=chain or TEST_CHAIN),
        limits=limits or limits_with(),
        session_factory=factory,
        client=client,
        clock=clock,
        today=lambda: day,
    )


def ai_rows(factory: SessionFactory) -> list[AiCall]:
    with factory() as db:
        return list(db.scalars(select(AiCall).order_by(AiCall.created_at, AiCall.attempt)))


def usage(factory: SessionFactory, scope: str, day: date = DAY) -> int:
    with factory() as db:
        row = db.scalars(
            select(UsageDaily).where(UsageDaily.scope == scope, UsageDaily.day == day)
        ).first()
        return row.model_calls if row else 0
