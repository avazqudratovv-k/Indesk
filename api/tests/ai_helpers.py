"""Builders shared by the gateway tests: a gateway on the test connection, a user, row readers."""

import uuid
from datetime import date
from typing import Any

from pydantic import SecretStr
from sqlalchemy import Connection, select
from sqlalchemy.orm import Session

from app.ai.caps import SessionFactory
from app.ai.config import ModelChain, load_model_chain
from app.ai.gateway import Gateway
from app.core.config import Limits, load_limits
from app.db.models import AiCall, UsageDaily
from tests.factories import make_user
from tests.fake_model_client import API_KEY, FakeClient, FakeClock

DAY = date(2026, 10, 26)


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
    return ModelChain(**{**load_model_chain().model_dump(), **overrides})


def make_gateway(
    factory: SessionFactory,
    client: FakeClient | None,
    *,
    clock: FakeClock | None = None,
    limits: Limits | None = None,
    chain: ModelChain | None = None,
    api_key: str | None = API_KEY,
    day: date = DAY,
) -> Gateway:
    clock = clock or FakeClock()
    if client is not None and client.clock is None:
        client.clock = clock
    return Gateway(
        api_key=SecretStr(api_key) if api_key is not None else None,
        chain=chain if chain is not None else load_model_chain(),
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
