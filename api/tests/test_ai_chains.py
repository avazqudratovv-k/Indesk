"""The two model chains of config/models.toml, by job class (light, main), through the gateway with
the fake client. Uses the REAL file's chains, so a change of model names there is seen here.
No network."""

import uuid

import pytest
from pydantic import BaseModel
from sqlalchemy import Connection

from app.ai.caps import SessionFactory
from app.ai.config import load_model_chains
from app.ai.gateway import Gateway, GatewayError, GatewayOk, GatewayResult
from app.core.enums import AiPurpose, GatewayOutcome, JobClass
from tests.ai_helpers import factory_for, make_gateway, new_user
from tests.fake_model_client import FakeClient, ok, rate_limited, server_error

CHAINS = load_model_chains()
LIGHT = [m.name for m in CHAINS.light.chain]
MAIN = [m.name for m in CHAINS.main.chain]


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


@pytest.fixture
def user(factory: SessionFactory) -> uuid.UUID:
    return new_user(factory)


def gateway_for(factory: SessionFactory, client: FakeClient | None, **kw: object) -> Gateway:
    return make_gateway(factory, client, chains=CHAINS, **kw)  # type: ignore[arg-type]


def ask(
    gateway: Gateway, user: uuid.UUID, job_class: JobClass | None, purpose: AiPurpose
) -> GatewayResult:
    return gateway.ask("hello", purpose=purpose, user_id=user, job_class=job_class)


CLASSES = [(JobClass.LIGHT, AiPurpose.PLAN, LIGHT), (JobClass.MAIN, AiPurpose.COMPUTE, MAIN)]


@pytest.mark.parametrize(("job_class", "purpose", "names"), CLASSES)
def test_each_class_falls_back_in_its_own_order(
    factory: SessionFactory,
    user: uuid.UUID,
    job_class: JobClass,
    purpose: AiPurpose,
    names: list[str],
) -> None:
    client = FakeClient([rate_limited(), server_error(), ok("third")])
    result = ask(gateway_for(factory, client), user, job_class, purpose)
    assert isinstance(result, GatewayOk)
    assert [c.model for c in client.calls] == names
    assert (result.model, result.attempts) == (names[2], 3)


@pytest.mark.parametrize(("job_class", "purpose", "names"), CLASSES)
def test_busy_only_when_every_entry_answered_429(
    factory: SessionFactory,
    user: uuid.UUID,
    job_class: JobClass,
    purpose: AiPurpose,
    names: list[str],
) -> None:
    all_429 = FakeClient([rate_limited(), rate_limited(), rate_limited()])
    result = ask(gateway_for(factory, all_429), user, job_class, purpose)
    assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BUSY
    mixed = FakeClient([rate_limited(), rate_limited(), server_error()])
    result = ask(gateway_for(factory, mixed), user, job_class, purpose)
    assert isinstance(result, GatewayError)
    assert result.outcome is GatewayOutcome.MODEL_UNAVAILABLE


@pytest.mark.parametrize(
    ("purpose", "names"),
    [
        (AiPurpose.ROUTE, LIGHT),
        (AiPurpose.PLAN, LIGHT),
        (AiPurpose.PICK, LIGHT),
        (AiPurpose.EXTRACT_CLAIMS, LIGHT),
        (AiPurpose.COMPUTE, MAIN),
        (AiPurpose.CRITIC, MAIN),
        (AiPurpose.VISION, MAIN),
    ],
)
def test_the_purpose_picks_the_class_when_none_is_given(
    factory: SessionFactory, user: uuid.UUID, purpose: AiPurpose, names: list[str]
) -> None:
    client = FakeClient([ok()])
    ask(gateway_for(factory, client), user, None, purpose)
    assert client.calls[0].model == names[0]


def test_an_explicit_class_beats_the_purpose(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([ok()])
    ask(gateway_for(factory, client), user, JobClass.MAIN, AiPurpose.PLAN)
    assert client.calls[0].model == MAIN[0]


def test_output_limits_come_from_the_file(factory: SessionFactory, user: uuid.UUID) -> None:
    client = FakeClient([ok(), ok()])
    gateway = gateway_for(factory, client)
    ask(gateway, user, JobClass.LIGHT, AiPurpose.PLAN)
    ask(gateway, user, JobClass.MAIN, AiPurpose.COMPUTE)
    light, main = client.calls
    assert main.max_output_tokens == 8192
    assert light.max_output_tokens == CHAINS.light.chain[0].max_output_tokens
    assert (light.timeout, main.timeout) == (12, 20)


def test_a_bad_answer_does_not_fall_back_in_either_class(
    factory: SessionFactory, user: uuid.UUID
) -> None:
    class Plan(BaseModel):
        x: int

    for job_class in JobClass:
        client = FakeClient([ok("not json"), ok('{"x": 1}')])
        result = gateway_for(factory, client).ask(
            "p", purpose=AiPurpose.PLAN, user_id=user, response_model=Plan, job_class=job_class
        )
        assert isinstance(result, GatewayError) and result.outcome is GatewayOutcome.BAD_OUTPUT
        assert len(client.calls) == 1


def test_is_configured(factory: SessionFactory) -> None:
    assert gateway_for(factory, FakeClient([])).is_configured()
    assert not gateway_for(factory, FakeClient([]), api_key=None).is_configured()
    assert not gateway_for(factory, FakeClient([]), api_key="  ").is_configured()
    assert not gateway_for(factory, None).is_configured()
