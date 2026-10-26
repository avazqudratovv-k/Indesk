"""GET /api/usage: counts and the plan name, nothing else (#74)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, update

from app.core.config import Settings
from app.core.enums import Plan, RunOutcome, RunReason
from app.db.models import UsageEvent, User
from app.schemas.usage import Usage
from tests.quota_helpers import Rig, make_rig_for
from tests.test_auth import MakeClient
from tests.test_runs_api import db_of

URL = "/api/usage"
FORBIDDEN_WORDS = ("model", "token", "cost", "price", "usd", "gemini", "call", "latency")


@pytest.fixture
def rig(make_client: MakeClient, db_connection: Connection, tmp_path: Path) -> Rig:
    return make_rig_for(make_client, db_connection, tmp_path, free_runs=2)


def test_a_new_user_has_all_free_runs_left(rig: Rig) -> None:
    response = rig.alice.get(URL)
    assert response.status_code == 200
    assert response.json() == {
        "plan": "free",
        "free_runs_total": 2,
        "free_runs_used": 0,
        "free_runs_left": 2,
    }


def test_used_runs_come_from_answered_and_partial_runs(rig: Rig) -> None:
    rig.start_and_finish(RunOutcome.ANSWERED)
    rig.start_and_finish(RunOutcome.FAILED, RunReason.INTERNAL_ERROR)  # does not count
    data = rig.alice.get(URL).json()
    assert (data["free_runs_used"], data["free_runs_left"]) == (1, 1)


def test_left_is_never_negative(rig: Rig) -> None:
    with db_of(rig.connection) as db:
        user_id = rig.user_id()
        for _ in range(3):  # run_id NULL: the run was deleted, the usage stays
            db.add(UsageEvent(user_id=user_id, run_id=None, kind="run", amount=1))
        db.commit()
    data = rig.alice.get(URL).json()
    assert (data["free_runs_used"], data["free_runs_left"]) == (3, 0)


def test_a_plan_without_free_runs_gets_nulls(rig: Rig) -> None:
    with db_of(rig.connection) as db:
        db.execute(update(User).values(plan=Plan.PRO.value))
        db.commit()
    assert rig.alice.get(URL).json() == {
        "plan": "pro",
        "free_runs_total": None,
        "free_runs_used": None,
        "free_runs_left": None,
    }


def test_it_needs_a_session(make_client: MakeClient, auth_settings: Settings) -> None:
    client: TestClient = make_client(auth_settings)
    assert client.get(URL).status_code == 401


def test_the_shape_holds_no_model_token_or_cost_field(rig: Rig) -> None:
    assert set(Usage.model_fields) == {
        "plan",
        "free_runs_total",
        "free_runs_used",
        "free_runs_left",
    }
    for name in Usage.model_fields:
        assert not any(word in name for word in FORBIDDEN_WORDS)
    text = json.dumps(rig.alice.get(URL).json()).lower()
    assert not any(word in text for word in ("gemini", "usd", "token", "cost"))
