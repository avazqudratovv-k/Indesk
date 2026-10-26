import json
import uuid
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.schemas.common import ErrorResponse
from app.schemas.events import DoneEvent, EvidenceEvent, RunEvent, StepEvent
from app.schemas.runs import Run, RunCreate
from app.schemas.users import Upload, User
from tests.factories import make_run, make_step, make_upload, make_user


def create(
    mode: str, files: list[tuple[str, str]], question: str = "How many riders?"
) -> dict[str, Any]:
    return {
        "mode": mode,
        "question": question,
        "files": [
            {"upload_id": str(uuid.uuid4()) if u == "new" else u, "role": r} for u, r in files
        ],
    }


# ---- error codes ----


def test_error_codes_are_the_agreed_list() -> None:
    assert {c.value for c in ErrorCode} == {
        "VALIDATION_ERROR",
        "NOT_FOUND",
        "METHOD_NOT_ALLOWED",
        "NOT_READY",
        "INTERNAL",
        "EMAIL_TAKEN",
        "INVALID_CREDENTIALS",
        "RATE_LIMITED",
        "UNAUTHENTICATED",
        "ORIGIN_NOT_ALLOWED",
        "CONSENT_REQUIRED",
        "FILE_TOO_LARGE",
        "UNSUPPORTED_TYPE",
        "TYPE_MISMATCH",
        "TOO_MANY_ROWS",
        "TOO_MANY_COLUMNS",
        "EMPTY_FILE",
        "BAD_CSV",
        "MODE_NOT_AVAILABLE",
        "DAILY_CAP_USER",
        "DAILY_CAP_GLOBAL",
        "QUOTA_EXHAUSTED",
        "NOT_RETRYABLE",
        "MODEL_UNAVAILABLE",
        "RUN_ACTIVE",
        "UPLOAD_NOT_READY",
        "TOO_MANY_STREAMS",
        "UPLOAD_IN_USE",
    }


def test_error_format_accepts_only_known_codes() -> None:
    assert (
        ErrorResponse.model_validate({"error": {"code": "DAILY_CAP_USER"}}).error.code
        is ErrorCode.DAILY_CAP_USER
    )
    with pytest.raises(ValidationError):
        ErrorResponse.model_validate({"error": {"code": "SOMETHING_ELSE"}})


# ---- RunCreate ----


def test_ask_with_files_is_valid() -> None:
    run = RunCreate.model_validate(create("ask", [("new", "subject"), ("new", "subject")]))
    assert run.question == "How many riders?"


@pytest.mark.parametrize(
    ("mode", "files"),
    [
        ("ask", [("new", "subject")]),
        ("check", [("new", "subject"), ("new", "source"), ("new", "source")]),
        ("compare", [("new", "a"), ("new", "b")]),
    ],
)
def test_each_mode_accepts_its_roles(mode: str, files: list[tuple[str, str]]) -> None:
    assert RunCreate.model_validate(create(mode, files)).mode.value == mode


@pytest.mark.parametrize(
    ("mode", "files"),
    [
        ("ask", []),
        ("ask", [("new", "subject")] * 6),  # more than 5, and the same upload twice is caught too
        ("ask", [("new", "source")]),
        ("check", [("new", "source")]),
        ("check", [("new", "subject"), ("new", "subject")]),
        ("check", [("new", "subject")] + [("new", "source")] * 5),
        ("compare", [("new", "a")]),
        ("compare", [("new", "a"), ("new", "a")]),
        ("compare", [("new", "subject"), ("new", "subject")]),
    ],
)
def test_wrong_roles_or_counts_are_rejected(mode: str, files: list[tuple[str, str]]) -> None:
    with pytest.raises(ValidationError):
        RunCreate.model_validate(create(mode, files))


def test_the_same_upload_cannot_be_used_twice() -> None:
    same = str(uuid.uuid4())
    with pytest.raises(ValidationError):
        RunCreate.model_validate(create("ask", [(same, "subject"), (same, "subject")]))


@pytest.mark.parametrize("question", ["", "   ", "x" * 1001])
def test_question_length_is_enforced(question: str) -> None:
    with pytest.raises(ValidationError):
        RunCreate.model_validate(create("ask", [("new", "subject")], question))


def test_client_cannot_set_server_fields() -> None:
    for field in ("user_id", "lang", "cost_usd", "plan", "counted"):
        with pytest.raises(ValidationError):
            RunCreate.model_validate({**create("ask", [("new", "subject")]), field: "x"})


def test_check_and_compare_modes_parse_even_though_only_ask_runs() -> None:
    # MODE_NOT_AVAILABLE is the service's answer, not a schema error.
    assert RunCreate.model_validate(create("compare", [("new", "a"), ("new", "b")]))


# ---- SSE events ----

EVENTS = TypeAdapter(RunEvent)


def test_step_event_is_a_key_plus_args() -> None:
    event = EVENTS.validate_python(
        {
            "event": "step",
            "run_id": "r_1",
            "seq": 3,
            "agent": "data",
            "kind": "tool",
            "state": "running",
            "key": "runPython",
            "args": {"rows": 4800, "file": "a.csv"},
            "tok": 1850,
        }
    )
    assert isinstance(event, StepEvent)
    assert event.bubble is None


@pytest.mark.parametrize(
    "patch",
    [
        {"key": "Owl is now thinking about your private file"},  # a sentence is not a key
        {"key": ""},
        {"args": {"note": "x" * 121}},  # long text does not fit an arg
        {"args": {"nested": {"a": 1}}},
        {"agent": "owl"},  # the UI name, not the database key
        {"state": "working"},
        {"extra": 1},
    ],
)
def test_step_event_rejects_free_text_and_unknown_values(patch: dict[str, Any]) -> None:
    base: dict[str, Any] = {
        "event": "step",
        "run_id": "r_1",
        "seq": 1,
        "agent": "manager",
        "kind": "say",
        "state": "running",
        "key": "plan",
        "args": {},
        "tok": 0,
    }
    with pytest.raises(ValidationError):
        EVENTS.validate_python({**base, **patch})


def test_evidence_and_done_events_parse_by_their_tag() -> None:
    evidence = EVENTS.validate_python(
        {
            "event": "evidence",
            "run_id": "r_1",
            "step_seq": 4,
            "ref": "D1",
            "type": "table",
            "file_name": "a.csv",
            "location": "rows 1-10",
        }
    )
    done = EVENTS.validate_python(
        {"event": "done", "run_id": "r_1", "outcome": "answered", "report_id": "rep_1"}
    )
    assert isinstance(evidence, EvidenceEvent)
    assert isinstance(done, DoneEvent)
    assert (
        "payload" not in evidence.model_dump()
    )  # evidence content is read from the report, not streamed


def test_unknown_event_tag_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EVENTS.validate_python({"event": "token", "text": "free model text"})


# ---- secrets never serialize ----


def test_user_never_serializes_the_password_hash(session: Session) -> None:
    user = make_user(session)
    session.refresh(user)
    dumped = json.dumps(User.model_validate(user).model_dump(mode="json"))
    assert "password" not in dumped
    assert "argon2" not in dumped
    assert "password_hash" not in User.model_fields
    assert User.model_validate(user).email == user.email


def test_upload_never_serializes_storage_key_or_sha256(session: Session) -> None:
    upload = make_upload(session, make_user(session))
    session.refresh(upload)
    dumped = Upload.model_validate(upload).model_dump(mode="json")
    assert "storage_key" not in dumped
    assert "sha256" not in dumped
    assert upload.storage_key is not None
    assert upload.storage_key not in json.dumps(dumped)
    assert upload.sha256 not in json.dumps(dumped)
    assert not {"storage_key", "sha256"} & set(Upload.model_fields)


def test_mock_upload_record_drops_the_internal_fields() -> None:
    record = {
        "id": "up_01",
        "user_id": "u_01",
        "filename": "seoul-subway-ridership.csv",
        "mime": "text/csv",
        "size": 1843200,
        "sha256": "9f2c…",
        "storage_key": "uploads/u_01/up_01",
        "page_count": None,
        "row_count": 4800,
        "status": "ready",
        "moderation": "passed",
        "created_at": "2026-10-25T09:00:00Z",
        "expires_at": "2026-10-26T09:00:00Z",
        "deleted_at": None,
    }
    dumped = Upload.model_validate(record).model_dump(mode="json")
    assert "storage_key" not in dumped
    assert "sha256" not in dumped


def test_run_from_database_rows_has_steps_and_report_id(session: Session) -> None:
    user = make_user(session)
    run = make_run(session, user)
    make_step(session, run, seq=2, key="dispatch")
    make_step(session, run, seq=1, key="plan")
    session.expire_all()
    parsed = Run.model_validate(run)
    assert [s.seq for s in parsed.steps] == [1, 2]
    assert parsed.steps[0].agent.value == "manager"
    assert parsed.report_id is None
    assert parsed.user_id == str(user.id)
