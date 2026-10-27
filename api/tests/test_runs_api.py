"""POST /api/runs and GET /api/runs/{id}: auth, ownership, validation, idempotency, limits."""

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Settings
from app.core.enums import RunOutcome, RunStatus
from app.db.models import AuditLog, Run, RunFile, Upload, UsageDaily, UsageEvent
from app.main import app
from app.routers.runs import get_enqueue, get_session_factory
from app.runs.agents import Finish
from app.runs.executor import run_job
from app.schemas.runs import RunCreated, RunView
from tests.ai_helpers import factory_for
from tests.runs_helpers import ScriptFlow, line, make_rig, talker
from tests.test_auth import MakeClient
from tests.test_uploads import post as upload_csv
from tests.test_uploads import settings_for, signed_in

URL = "/api/runs"


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


def new_upload(client: TestClient) -> str:
    response = upload_csv(client)
    assert response.status_code == 201
    return str(response.json()["id"])


def body(
    *upload_ids: str, question: str = "Which stations grew fastest?", **extra: Any
) -> dict[str, Any]:
    return {
        "mode": "ask",
        "question": question,
        "files": [{"upload_id": u, "role": "subject"} for u in upload_ids],
        **extra,
    }


def code(response: Any, status: int, expected: str) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == expected
    # RUN_ACTIVE alone carries a run id; every other error body is the code and nothing else.
    assert set(error) == {"code"} | ({"run_id"} if expected == "RUN_ACTIVE" else set())


def db_of(connection: Connection) -> Session:
    return Session(bind=connection, join_transaction_mode="create_savepoint")


def edit_upload(connection: Connection, upload_id: str, **values: Any) -> None:
    with db_of(connection) as db:
        db.execute(update(Upload).where(Upload.id == uuid.UUID(upload_id)).values(**values))
        db.commit()


def finish_runs(connection: Connection) -> None:
    with db_of(connection) as db:
        db.execute(update(Run).values(status="finished", outcome="answered"))
        db.commit()


def counters(connection: Connection) -> list[tuple[Any, ...]]:
    with db_of(connection) as db:
        rows = db.execute(
            select(UsageDaily.scope, UsageDaily.runs, UsageDaily.model_calls).order_by(
                UsageDaily.scope
            )
        )
        return [tuple(r) for r in rows]


def count(connection: Connection, model: Any) -> int:
    with db_of(connection) as db:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)


# ---- POST /runs ----


def test_start_a_run(
    alice: TestClient, enqueued: list[uuid.UUID], db_connection: Connection
) -> None:
    upload = new_upload(alice)
    response = alice.post(URL, json=body(upload))
    assert response.status_code == 202
    data = response.json()
    assert set(data) == {"id", "status"} and data["status"] == "queued"
    RunCreated.model_validate(data)
    assert enqueued == [uuid.UUID(data["id"])]
    with db_of(db_connection) as db:
        run = db.get(Run, uuid.UUID(data["id"]))
        assert run is not None
        assert (run.status, run.mode, run.lang, run.counted) == ("queued", "ask", "en", False)
        files = db.scalars(select(RunFile).where(RunFile.run_id == run.id)).all()
        assert [(str(f.upload_id), f.role, f.owner_id) for f in files] == [
            (upload, "subject", run.user_id)
        ]
        [audit] = db.scalars(select(AuditLog).where(AuditLog.action == "run_created")).all()
        assert audit.target == data["id"] and audit.user_id == run.user_id
        assert audit.ip_hash and "203.0.113" not in audit.ip_hash  # a keyed hash, never the address


def test_the_language_comes_from_the_question_not_from_the_client(
    alice: TestClient, db_connection: Connection
) -> None:
    upload = new_upload(alice)
    response = alice.post(URL, json=body(upload, question="가장 빠르게 성장한 역은 어디인가요?"))
    assert response.status_code == 202
    with db_of(db_connection) as db:
        assert db.get(Run, uuid.UUID(response.json()["id"])).lang == "ko"  # type: ignore[union-attr]


@pytest.mark.parametrize("field", ["user_id", "lang", "status", "price", "plan", "cost_usd"])
def test_the_client_cannot_set_server_decided_fields(alice: TestClient, field: str) -> None:
    upload = new_upload(alice)
    code(alice.post(URL, json=body(upload, **{field: "x"})), 422, "VALIDATION_ERROR")


def test_unsigned_is_401(make_client: MakeClient, settings: Settings) -> None:
    client = make_client(settings)
    code(client.post(URL, json=body(str(uuid.uuid4()))), 401, "UNAUTHENTICATED")
    code(client.get(f"{URL}/{uuid.uuid4()}"), 401, "UNAUTHENTICATED")
    code(client.get(f"{URL}/{uuid.uuid4()}/events"), 401, "UNAUTHENTICATED")


def test_wrong_or_missing_origin_is_refused(
    alice: TestClient, make_client: MakeClient, settings: Settings
) -> None:
    upload = new_upload(alice)
    response = alice.post(URL, json=body(upload), headers={"Origin": "http://evil.example"})
    code(response, 403, "ORIGIN_NOT_ALLOWED")
    bare = make_client(settings, origin=None)
    bare.cookies.update(alice.cookies)
    code(bare.post(URL, json=body(upload)), 403, "ORIGIN_NOT_ALLOWED")


def test_another_users_upload_and_a_missing_one_look_the_same(
    alice: TestClient, bob: TestClient
) -> None:
    bobs = new_upload(bob)
    foreign = alice.post(URL, json=body(bobs))
    missing = alice.post(URL, json=body(str(uuid.uuid4())))
    code(foreign, 404, "NOT_FOUND")
    assert foreign.json() == missing.json() and foreign.status_code == missing.status_code
    # And nothing was started: Alice can still run her own file.
    assert alice.post(URL, json=body(new_upload(alice))).status_code == 202


def test_a_foreign_upload_is_refused_as_not_found(
    alice: TestClient, bob: TestClient, enqueued: list[uuid.UUID], db_connection: Connection
) -> None:
    foreign = new_upload(bob)
    before = (count(db_connection, UsageEvent), counters(db_connection))
    code(alice.post(URL, json=body(foreign)), 404, "NOT_FOUND")
    assert enqueued == [] and count(db_connection, Run) == 0
    assert (count(db_connection, UsageEvent), counters(db_connection)) == before


def test_the_file_count_gate_comes_before_the_ownership_check(
    alice: TestClient, bob: TestClient, enqueued: list[uuid.UUID], db_connection: Connection
) -> None:
    mine, foreign = new_upload(alice), new_upload(bob)
    before = (count(db_connection, UsageEvent), counters(db_connection))
    code(alice.post(URL, json=body(mine, foreign)), 422, "TOO_MANY_FILES")
    assert enqueued == [] and count(db_connection, Run) == 0
    assert (count(db_connection, UsageEvent), counters(db_connection)) == before


@pytest.mark.parametrize(
    ("change", "status", "expected"),
    [
        ({"status": "uploaded"}, 409, "UPLOAD_NOT_READY"),
        ({"moderation": "blocked"}, 409, "UPLOAD_NOT_READY"),
        ({"storage_key": None}, 409, "UPLOAD_NOT_READY"),
        ({"mime": "image/png"}, 422, "UNSUPPORTED_TYPE"),
        ({"status": "deleted", "deleted_at": clock.utcnow()}, 404, "NOT_FOUND"),
    ],
    ids=["uploaded", "blocked", "no-file", "png", "deleted"],
)
def test_upload_must_be_a_ready_csv(
    alice: TestClient, db_connection: Connection, change: dict[str, Any], status: int, expected: str
) -> None:
    upload = new_upload(alice)
    edit_upload(db_connection, upload, **change)
    code(alice.post(URL, json=body(upload)), status, expected)


def test_a_ready_pdf_is_accepted_for_a_run(alice: TestClient, db_connection: Connection) -> None:
    """P14a part 2 lifted the PDF refusal; any other type is still UNSUPPORTED_TYPE."""
    upload = new_upload(alice)
    edit_upload(db_connection, upload, mime="application/pdf")
    response = alice.post(URL, json=body(upload))
    assert response.status_code == 202, response.text


def test_an_expired_upload_is_not_found(alice: TestClient, db_connection: Connection) -> None:
    upload = new_upload(alice)
    edit_upload(db_connection, upload, expires_at=clock.utcnow().replace(year=2020))
    code(alice.post(URL, json=body(upload)), 404, "NOT_FOUND")


@pytest.mark.parametrize("question", ["", "   ", "x" * 1001])
def test_question_length_limits(alice: TestClient, question: str) -> None:
    code(alice.post(URL, json=body(new_upload(alice), question=question)), 422, "VALIDATION_ERROR")


def test_question_length_comes_from_config(make_client: MakeClient, tmp_path: Path) -> None:
    client = signed_in(
        make_client, settings_for(tmp_path, max_question_chars=20), "c@example.com", 12
    )
    upload = new_upload(client)
    code(client.post(URL, json=body(upload, question="x" * 21)), 422, "VALIDATION_ERROR")
    assert client.post(URL, json=body(upload, question="x" * 20)).status_code == 202


def test_file_count_comes_from_config(make_client: MakeClient, tmp_path: Path) -> None:
    client = signed_in(
        make_client,
        settings_for(
            tmp_path,
            files_per_slot={"files": 1, "document": 1, "sources": 4, "fileA": 1, "fileB": 1},
        ),
        "d@example.com",
        13,
    )
    first, second = new_upload(client), new_upload(client)
    code(client.post(URL, json=body(first, second)), 422, "TOO_MANY_FILES")
    assert client.post(URL, json=body(first)).status_code == 202


def test_six_files_or_a_repeated_file_is_refused(
    alice: TestClient, enqueued: list[uuid.UUID], db_connection: Connection
) -> None:
    ids = [new_upload(alice) for _ in range(6)]
    before = (count(db_connection, Run), count(db_connection, UsageEvent), counters(db_connection))
    code(alice.post(URL, json=body(*ids)), 422, "TOO_MANY_FILES")
    code(alice.post(URL, json=body(ids[0], ids[0])), 422, "TOO_MANY_FILES")
    after = (count(db_connection, Run), count(db_connection, UsageEvent), counters(db_connection))
    assert after == before and before[:2] == (0, 0) and enqueued == []


def test_one_file_is_accepted(alice: TestClient, db_connection: Connection) -> None:
    response = alice.post(URL, json=body(new_upload(alice)))
    assert response.status_code == 202
    with db_of(db_connection) as db:
        roles = db.scalars(
            select(RunFile.role).where(RunFile.run_id == uuid.UUID(response.json()["id"]))
        )
        assert list(roles) == ["subject"]


def test_two_files_are_refused_without_side_effects(
    alice: TestClient, enqueued: list[uuid.UUID], db_connection: Connection
) -> None:
    first, second = new_upload(alice), new_upload(alice)
    before = (count(db_connection, UsageEvent), counters(db_connection))
    code(alice.post(URL, json=body(first, second)), 422, "TOO_MANY_FILES")
    assert count(db_connection, Run) == 0 and enqueued == []
    assert (count(db_connection, UsageEvent), counters(db_connection)) == before
    assert alice.post(URL, json=body(first)).status_code == 202  # nothing was spent or locked


def test_zero_files_are_refused(alice: TestClient, db_connection: Connection) -> None:
    code(alice.post(URL, json=body()), 422, "VALIDATION_ERROR")
    assert count(db_connection, Run) == 0


def test_only_ask_mode_exists_for_now(alice: TestClient) -> None:
    doc, source, a, b = (new_upload(alice) for _ in range(4))
    check = {
        "mode": "check",
        "question": "Check it",
        "files": [{"upload_id": doc, "role": "subject"}, {"upload_id": source, "role": "source"}],
    }
    compare = {"mode": "compare", "question": "What changed?", "files": [
        {"upload_id": a, "role": "a"}, {"upload_id": b, "role": "b"}]}  # fmt: skip
    code(alice.post(URL, json=check), 422, "MODE_NOT_AVAILABLE")
    code(alice.post(URL, json=compare), 422, "MODE_NOT_AVAILABLE")
    code(alice.post(URL, json={**compare, "mode": "nonsense"}), 422, "VALIDATION_ERROR")


# ---- one active run, idempotency ----


def test_a_second_post_while_a_run_is_active_is_refused(
    alice: TestClient, enqueued: list[uuid.UUID], db_connection: Connection
) -> None:
    upload = new_upload(alice)
    assert alice.post(URL, json=body(upload)).status_code == 202
    code(alice.post(URL, json=body(upload)), 409, "RUN_ACTIVE")
    assert len(enqueued) == 1 and count(db_connection, Run) == 1


def test_another_user_is_not_blocked_by_my_active_run(alice: TestClient, bob: TestClient) -> None:
    assert alice.post(URL, json=body(new_upload(alice))).status_code == 202
    assert bob.post(URL, json=body(new_upload(bob))).status_code == 202


def test_a_new_run_is_allowed_once_the_last_one_finished(
    alice: TestClient, db_connection: Connection
) -> None:
    upload = new_upload(alice)
    first = alice.post(URL, json=body(upload))
    finish_runs(db_connection)
    second = alice.post(URL, json=body(upload))
    assert second.status_code == 202 and second.json()["id"] != first.json()["id"]


def test_the_same_idempotency_key_replays_the_same_run(
    alice: TestClient, enqueued: list[uuid.UUID], db_connection: Connection
) -> None:
    upload = new_upload(alice)
    headers = {"Idempotency-Key": "click-0001-abcdef"}
    first = alice.post(URL, json=body(upload), headers=headers)
    again = alice.post(URL, json=body(upload), headers=headers)
    assert first.status_code == again.status_code == 202
    assert first.json() == again.json()
    assert len(enqueued) == 1 and count(db_connection, Run) == 1
    finish_runs(db_connection)  # even after the run ended, the key still names that run
    third = alice.post(URL, json=body(upload), headers=headers)
    assert third.status_code == 202 and third.json()["id"] == first.json()["id"]
    assert third.json()["status"] == "finished"  # the same run, as it is now
    assert count(db_connection, Run) == 1


def test_a_reused_key_with_a_different_request_is_refused(alice: TestClient) -> None:
    upload = new_upload(alice)
    headers = {"Idempotency-Key": "click-0002-abcdef"}
    assert alice.post(URL, json=body(upload), headers=headers).status_code == 202
    other = alice.post(URL, json=body(upload, question="A different question"), headers=headers)
    code(other, 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("key", ["short", "has space in it", "x" * 65, "bad/char/here!"])
def test_a_malformed_idempotency_key_is_refused(alice: TestClient, key: str) -> None:
    code(
        alice.post(URL, json=body(new_upload(alice)), headers={"Idempotency-Key": key}),
        422,
        "VALIDATION_ERROR",
    )


def test_a_key_belongs_to_one_user(alice: TestClient, bob: TestClient) -> None:
    headers = {"Idempotency-Key": "shared-key-12345"}
    a = alice.post(URL, json=body(new_upload(alice)), headers=headers)
    b = bob.post(URL, json=body(new_upload(bob)), headers=headers)
    assert a.status_code == b.status_code == 202 and a.json()["id"] != b.json()["id"]


def test_the_redis_value_never_holds_the_question(alice: TestClient, settings: Settings) -> None:
    from redis import Redis  # noqa: PLC0415

    upload = new_upload(alice)
    alice.post(
        URL,
        json=body(upload, question="PRIVATE-QUESTION-TEXT"),
        headers={"Idempotency-Key": "key-for-redis-1"},
    )
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    values = [redis.get(k) for k in redis.scan_iter("idem:run:*")]
    stored = b" ".join(v if isinstance(v, bytes) else b"" for v in values)
    assert stored and b"PRIVATE-QUESTION-TEXT" not in stored


# ---- rate limit, queue failure ----


def test_run_requests_are_rate_limited(make_client: MakeClient, tmp_path: Path) -> None:
    client = signed_in(make_client, settings_for(tmp_path, runs_per_hour=2), "e@example.com", 14)
    ghost = body(str(uuid.uuid4()))
    assert client.post(URL, json=ghost).status_code == 404
    assert client.post(URL, json=ghost).status_code == 404
    limited = client.post(URL, json=ghost)
    code(limited, 429, "RATE_LIMITED")
    assert int(limited.headers["Retry-After"]) > 0


def test_a_queue_failure_ends_the_run_and_frees_the_user(
    alice: TestClient, db_connection: Connection
) -> None:
    def broken() -> Callable[[uuid.UUID], None]:
        def enqueue(run_id: uuid.UUID) -> None:
            raise ConnectionError("redis is down")

        return enqueue

    upload = new_upload(alice)
    headers = {"Idempotency-Key": "queue-down-12345"}
    app.dependency_overrides[get_enqueue] = broken
    code(alice.post(URL, json=body(upload), headers=headers), 503, "NOT_READY")
    with db_of(db_connection) as db:
        [run] = db.scalars(select(Run)).all()
        assert (run.status, run.outcome, run.outcome_reason) == (
            "finished",
            "failed",
            "internal_error",
        )
    sent: list[uuid.UUID] = []
    app.dependency_overrides[get_enqueue] = lambda: sent.append
    retry = alice.post(URL, json=body(upload), headers=headers)  # the key was forgotten
    assert retry.status_code == 202 and len(sent) == 1


# ---- GET /runs/{id} ----


def test_get_run_for_the_owner(alice: TestClient, db_connection: Connection) -> None:
    upload = new_upload(alice)
    run_id = alice.post(URL, json=body(upload)).json()["id"]
    response = alice.get(f"{URL}/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == set(RunView.model_fields)
    for hidden in ("user_id", "cost_usd", "error", "payload", "model", "owner_id"):
        assert hidden not in data
    assert (data["id"], data["status"], data["outcome"], data["reason"], data["steps"]) == (
        run_id, "queued", None, None, []
    )  # fmt: skip


def test_another_users_run_missing_and_malformed_ids_are_one_404(
    alice: TestClient, bob: TestClient
) -> None:
    run_id = alice.post(URL, json=body(new_upload(alice))).json()["id"]
    mine = alice.get(f"{URL}/{run_id}")
    foreign = bob.get(f"{URL}/{run_id}")
    missing = bob.get(f"{URL}/{uuid.uuid4()}")
    malformed = bob.get(f"{URL}/not-a-uuid")
    assert mine.status_code == 200
    for response in (foreign, missing, malformed):
        code(response, 404, "NOT_FOUND")
    assert run_id not in foreign.text


def test_end_to_end_with_test_agents(alice: TestClient, db_connection: Connection) -> None:
    upload = new_upload(alice)
    run_id = alice.post(URL, json=body(upload, question="PRIVATE-QUESTION-TEXT")).json()["id"]
    rig = make_rig(
        factory_for(db_connection),
        ScriptFlow(
            talker(tokens=5), Finish(RunOutcome.ANSWERED, line(key=_ready(), state=_done()))
        ),
    )
    run_job(uuid.UUID(run_id), rig.deps)
    data = alice.get(f"{URL}/{run_id}").json()
    assert (data["status"], data["outcome"], data["reason"]) == (
        RunStatus.FINISHED,
        "answered",
        None,
    )
    assert [s["key"] for s in data["steps"]] == ["plan", "dispatch", "ready"]
    assert [s["seq"] for s in data["steps"]] == [1, 2, 3]
    assert (data["tokens_in"], data["tool_calls"]) == (5, 1)
    for step in data["steps"]:
        assert "payload" not in step and "model" not in step and "cost_usd" not in step


def _ready() -> Any:
    from app.core.enums import TraceKey  # noqa: PLC0415

    return TraceKey.READY


def _done() -> Any:
    from app.core.enums import StepState  # noqa: PLC0415

    return StepState.DONE
