"""GET /api/reports/{id}, and the HTTP-level proof that Beaver's code, Owl's plan and the stored
payloads are in NO response: a full run, then GET /runs/{id}, the SSE stream and GET /reports/{id}."""

# ruff: noqa: E501  # one assertion per line reads better than wrapped ones

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, select, update

from app.core.config import Settings
from app.db.models import Report, Run, RunFile
from app.main import app
from app.routers.runs import get_enqueue, get_session_factory
from app.runs.executor import run_job
from tests.ai_helpers import factory_for
from tests.ask_helpers import CODE_OK, ask_rig, code_answer, plan_answer, sandbox_ok
from tests.runs_helpers import World
from tests.test_auth import MakeClient
from tests.test_uploads import post as upload_csv
from tests.test_uploads import settings_for, signed_in

SENTINEL = "SENTINEL_CODE_7f3a"
FORBIDDEN_EVERYWHERE = [
    SENTINEL, "groupby", "group_by", "time_column", "top_n", "prompt_version", "owl-1",
    "beaver-1", "cat-1", "owl-2", "beaver-2", "cat-2", "add_metrics", "aggregation", '"code"', "run_python(",
]  # fmt: skip


@pytest.fixture
def enqueued() -> list[uuid.UUID]:
    return []


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_for(tmp_path)


@pytest.fixture(autouse=True)
def _wire(db_connection: Connection, enqueued: list[uuid.UUID]) -> None:
    app.dependency_overrides[get_enqueue] = lambda: enqueued.append
    app.dependency_overrides[get_session_factory] = lambda: factory_for(db_connection)


@pytest.fixture
def alice(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "alice@example.com", 10)


@pytest.fixture
def bob(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "bob@example.com", 11)


@pytest.fixture
def anonymous(make_client: MakeClient, settings: Settings) -> TestClient:
    return make_client(settings, peer=("203.0.113.99", 50000))


def finished_run(
    client: TestClient, db_connection: Connection, enqueued: list[uuid.UUID]
) -> uuid.UUID:
    """Upload through the API, start a run, then run the job inline with the fake model."""
    factory = factory_for(db_connection)
    upload_id = str(upload_csv(client).json()["id"])
    body = {"mode": "ask", "question": "Which station has the most riders?",
            "files": [{"upload_id": upload_id, "role": "subject"}]}  # fmt: skip
    started = client.post("/api/runs", json=body)
    assert started.status_code == 202, started.text
    run_id = uuid.UUID(started.json()["id"])
    assert enqueued == [run_id]
    with factory() as db:
        user_id = db.scalar(select(Run.user_id).where(Run.id == run_id))
        uploads = tuple(db.scalars(select(RunFile.upload_id).where(RunFile.run_id == run_id)))
    assert user_id is not None
    world = World(user_id, run_id, uploads)
    code = CODE_OK + f"\n# {SENTINEL}"
    rig, _, _ = ask_rig(factory, world, plan_answer(), code_answer(code), sandbox=[sandbox_ok()])
    run_job(run_id, rig.deps)
    return run_id


def test_a_full_run_then_run_events_and_report_leak_nothing(
    alice: TestClient, db_connection: Connection, enqueued: list[uuid.UUID]
) -> None:
    run_id = finished_run(alice, db_connection, enqueued)

    run = alice.get(f"/api/runs/{run_id}")
    assert run.status_code == 200 and run.json()["outcome"] == "answered"
    report_id = run.json()["report_id"]
    assert report_id is not None

    events = alice.get(f"/api/runs/{run_id}/events")
    assert events.status_code == 200
    assert "event: done" in events.text and report_id in events.text
    assert '"key":"verify"' in events.text

    report = alice.get(f"/api/reports/{report_id}")
    assert report.status_code == 200, report.text
    detail = report.json()
    assert detail["report"]["total_claims"] == 2 and detail["report"]["confidence"] == "high"
    assert [c["status"] for c in detail["claims"]] == ["verified", "verified"]
    assert detail["evidence"][0]["payload"]["table"]["headers"] == ["station", "riders"]

    for name, body in (("run", run.text), ("events", events.text), ("report", report.text)):
        for text in FORBIDDEN_EVERYWHERE:
            assert text not in body, (name, text)
    for name, body in (("run", run.text), ("events", events.text)):
        assert '"payload"' not in body and "123456" not in body, name
        assert "Synthetic Station" not in body, name  # the table is only in the report


def test_the_evidence_payload_has_only_the_allowed_keys(
    alice: TestClient, db_connection: Connection, enqueued: list[uuid.UUID]
) -> None:
    run_id = finished_run(alice, db_connection, enqueued)
    report_id = alice.get(f"/api/runs/{run_id}").json()["report_id"]
    detail = alice.get(f"/api/reports/{report_id}").json()
    allowed = {"columns", "rows_used", "tool", "method", "table", "reason"}
    for item in detail["evidence"]:
        assert set(item["payload"]) <= allowed
    assert set(detail["report"]) == {
        "id", "run_id", "owner_id", "mode", "lang", "title", "summary_json", "confidence",
        "verified_count", "total_claims", "pdf_key", "template", "typeface", "text_size",
        "created_at", "expires_at", "deleted_at", "purge_at", "translations",
    }  # fmt: skip


def test_another_user_gets_the_same_404_as_a_missing_report(
    alice: TestClient, bob: TestClient, db_connection: Connection, enqueued: list[uuid.UUID]
) -> None:
    run_id = finished_run(alice, db_connection, enqueued)
    report_id = alice.get(f"/api/runs/{run_id}").json()["report_id"]
    expected = {"error": {"code": "NOT_FOUND"}}
    for who, rid in ((bob, report_id), (alice, str(uuid.uuid4())), (alice, "not-a-uuid")):
        response = who.get(f"/api/reports/{rid}")
        assert response.status_code == 404 and response.json() == expected


def test_a_report_needs_a_session(
    alice: TestClient, anonymous: TestClient, db_connection: Connection,
    enqueued: list[uuid.UUID],
) -> None:  # fmt: skip
    run_id = finished_run(alice, db_connection, enqueued)
    report_id = alice.get(f"/api/runs/{run_id}").json()["report_id"]
    response = anonymous.get(f"/api/reports/{report_id}")
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "UNAUTHENTICATED"}}


@pytest.mark.parametrize("change", ["deleted", "expired"])
def test_a_deleted_or_expired_report_is_a_404(
    alice: TestClient, db_connection: Connection, enqueued: list[uuid.UUID], change: str
) -> None:
    from app.core import clock  # noqa: PLC0415

    run_id = finished_run(alice, db_connection, enqueued)
    report_id = alice.get(f"/api/runs/{run_id}").json()["report_id"]
    values: dict[str, object] = (
        {"deleted_at": clock.utcnow()} if change == "deleted"
        else {"expires_at": clock.utcnow() - __import__("datetime").timedelta(seconds=1)}
    )  # fmt: skip
    with factory_for(db_connection)() as db:
        db.execute(update(Report).where(Report.id == uuid.UUID(report_id)).values(**values))
        db.commit()
    assert alice.get(f"/api/reports/{report_id}").status_code == 404


def test_the_report_response_is_json_the_web_contract_can_read(
    alice: TestClient, db_connection: Connection, enqueued: list[uuid.UUID]
) -> None:
    from app.schemas.reports import ReportDetail  # noqa: PLC0415

    run_id = finished_run(alice, db_connection, enqueued)
    report_id = alice.get(f"/api/runs/{run_id}").json()["report_id"]
    text = alice.get(f"/api/reports/{report_id}").text
    assert ReportDetail.model_validate_json(text).report.id == report_id
    assert json.loads(text)["report"]["summary_json"]["answer"]
