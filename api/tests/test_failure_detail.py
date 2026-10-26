"""ClientFailure equality ignores `detail`, but the gateway still stores it in ai_calls."""

import uuid

import pytest
from sqlalchemy import Connection

from app.ai.caps import SessionFactory
from app.ai.client import ClientFailure
from app.core.enums import AiPurpose, FailureKind, ModelFailure
from tests.ai_helpers import ai_rows, factory_for, make_gateway, new_user
from tests.fake_model_client import FakeClient, fail


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


def test_equal_failures_still_store_their_own_cause(factory: SessionFactory) -> None:
    a = ClientFailure(kind=ModelFailure.OTHER, detail=FailureKind.HTTP_400)
    b = ClientFailure(kind=ModelFailure.OTHER, detail=FailureKind.BAD_JSON)
    assert a == b and hash(a) == hash(b)  # equality reads `kind` alone
    assert a.detail is not b.detail  # ...but the cause is still carried
    user: uuid.UUID = new_user(factory)
    client = FakeClient(
        [
            fail(ModelFailure.OTHER, detail=FailureKind.HTTP_400),
            fail(ModelFailure.OTHER, detail=FailureKind.BAD_JSON),
        ]
    )
    make_gateway(factory, client).ask("hello", purpose=AiPurpose.ROUTE, user_id=user)
    assert [r.failure_kind for r in ai_rows(factory)] == ["http_400", "bad_json"]
