"""10c API gaps: RUN_ACTIVE names the run, GET /runs/active, DELETE /uploads/{id}. Real API and
Postgres, fake queue, no model."""

import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, select

from app.core.config import Settings
from app.core.enums import RunOutcome, UploadStatus
from app.db.models import AuditLog, Upload
from tests.quota_helpers import Rig, make_rig_for
from tests.test_auth import MakeClient
from tests.test_runs_api import body, code, db_of, new_upload
from tests.test_uploads import settings_for, stored_files

NOT_FOUND = "NOT_FOUND"


@pytest.fixture
def rig(make_client: MakeClient, db_connection: Connection, tmp_path: Path) -> Rig:
    return make_rig_for(make_client, db_connection, tmp_path)


@pytest.fixture
def storage_settings(tmp_path: Path) -> Settings:
    return settings_for(tmp_path)


def run_active_body(response: Any) -> dict[str, Any]:
    assert response.status_code == 409, response.text
    error: dict[str, Any] = response.json()["error"]
    return error


# ---- RUN_ACTIVE carries the run id ----


def test_run_active_names_the_run_in_the_way(rig: Rig) -> None:
    first = rig.start_ok()
    second = rig.alice.post("/api/runs", json=body(new_upload(rig.alice)))
    assert run_active_body(second) == {"code": "RUN_ACTIVE", "run_id": first}


def test_run_active_never_names_another_users_run(rig: Rig) -> None:
    rig.start_ok(rig.bob)
    mine = rig.start_ok()
    again = rig.alice.post("/api/runs", json=body(new_upload(rig.alice)))
    assert run_active_body(again)["run_id"] == mine


def test_other_errors_gain_no_run_id(rig: Rig) -> None:
    code(rig.alice.post("/api/runs", json={"mode": "ask"}), 422, "VALIDATION_ERROR")


# ---- GET /runs/active ----


def test_no_active_run_is_204_with_no_body(rig: Rig) -> None:
    response = rig.alice.get("/api/runs/active")
    assert response.status_code == 204 and response.content == b""


def test_the_active_run_is_returned_as_a_run_view(rig: Rig) -> None:
    run_id = rig.start_ok()
    response = rig.alice.get("/api/runs/active")
    assert response.status_code == 200
    assert response.json() == rig.alice.get(f"/api/runs/{run_id}").json()
    assert response.json()["status"] == "queued"


def test_a_finished_run_is_not_active_and_other_users_are_not_shown(rig: Rig) -> None:
    run_id = rig.start_ok()
    rig.finish(run_id, RunOutcome.ANSWERED)
    assert rig.alice.get("/api/runs/active").status_code == 204
    rig.start_ok(rig.bob)
    assert rig.alice.get("/api/runs/active").status_code == 204


def test_the_active_run_route_needs_a_session(rig: Rig, make_client: MakeClient) -> None:
    anonymous = make_client(settings_for(Path("/nonexistent")))
    response = anonymous.get("/api/runs/active")
    code(response, 401, "UNAUTHENTICATED")


# ---- DELETE /uploads/{id} ----


def test_the_owner_deletes_an_upload(rig: Rig, db_connection: Connection, tmp_path: Path) -> None:
    upload_id = new_upload(rig.alice)
    settings = settings_for(tmp_path)
    assert len(stored_files(settings)) == 1
    response = rig.alice.delete(f"/api/uploads/{upload_id}")
    assert response.status_code == 204 and response.content == b""
    assert stored_files(settings) == []  # the stored object is gone
    with db_of(db_connection) as db:
        row = db.get(Upload, uuid.UUID(upload_id))
        assert row is not None  # the row is kept
        assert (row.status, row.storage_key) == (UploadStatus.DELETED, None)
        assert row.deleted_at is not None and row.filename
        actions = [
            a.action for a in db.scalars(select(AuditLog).where(AuditLog.target == upload_id))
        ]
        assert "upload_deleted" in actions
    code(rig.alice.get(f"/api/uploads/{upload_id}"), 404, NOT_FOUND)
    assert rig.alice.get("/api/uploads").json() == []


def test_deleting_twice_is_a_404(rig: Rig) -> None:
    upload_id = new_upload(rig.alice)
    assert rig.alice.delete(f"/api/uploads/{upload_id}").status_code == 204
    code(rig.alice.delete(f"/api/uploads/{upload_id}"), 404, NOT_FOUND)


def test_another_users_missing_and_malformed_ids_are_the_same_404(rig: Rig, tmp_path: Path) -> None:
    mine = new_upload(rig.alice)
    answers = [
        rig.bob.delete(f"/api/uploads/{mine}"),
        rig.bob.delete(f"/api/uploads/{uuid.uuid4()}"),
        rig.bob.delete("/api/uploads/not-a-uuid"),
    ]
    for response in answers:
        code(response, 404, NOT_FOUND)
    assert answers[0].content == answers[1].content == answers[2].content
    assert len(stored_files(settings_for(tmp_path))) == 1  # bob removed nothing
    assert rig.alice.get(f"/api/uploads/{mine}").status_code == 200


def test_an_upload_of_an_active_run_cannot_be_deleted(rig: Rig, tmp_path: Path) -> None:
    upload_id = new_upload(rig.alice)
    assert rig.alice.post("/api/runs", json=body(upload_id)).status_code == 202
    code(rig.alice.delete(f"/api/uploads/{upload_id}"), 409, "UPLOAD_IN_USE")
    assert len(stored_files(settings_for(tmp_path))) == 1
    assert rig.alice.get(f"/api/uploads/{upload_id}").status_code == 200


def test_an_upload_of_a_finished_run_can_be_deleted(rig: Rig) -> None:
    upload_id = new_upload(rig.alice)
    run_id = rig.alice.post("/api/runs", json=body(upload_id)).json()["id"]
    rig.finish(run_id, RunOutcome.ANSWERED)
    assert rig.alice.delete(f"/api/uploads/{upload_id}").status_code == 204


def test_a_deleted_upload_cannot_start_a_run(rig: Rig) -> None:
    upload_id = new_upload(rig.alice)
    rig.alice.delete(f"/api/uploads/{upload_id}")
    code(rig.alice.post("/api/runs", json=body(upload_id)), 404, NOT_FOUND)


def test_delete_needs_a_session_and_an_allowed_origin(
    rig: Rig, make_client: MakeClient, storage_settings: Settings
) -> None:
    upload_id = new_upload(rig.alice)
    anonymous = make_client(storage_settings, peer=("203.0.113.99", 50000))
    code(anonymous.delete(f"/api/uploads/{upload_id}"), 401, "UNAUTHENTICATED")
    evil = rig.alice.delete(f"/api/uploads/{upload_id}", headers={"Origin": "https://evil.example"})
    code(evil, 403, "ORIGIN_NOT_ALLOWED")
    assert rig.alice.get(f"/api/uploads/{upload_id}").status_code == 200


def test_a_failing_storage_delete_keeps_the_row_and_answers_500(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, db_connection: Connection
) -> None:
    from app.storage import LocalDiskStorage, StorageError  # noqa: PLC0415

    upload_id = new_upload(rig.alice)

    def broken(self: LocalDiskStorage, key: str) -> None:
        raise StorageError("disk")

    monkeypatch.setattr(LocalDiskStorage, "delete", broken)
    code(rig.alice.delete(f"/api/uploads/{upload_id}"), 500, "INTERNAL")
    with db_of(db_connection) as db:
        row = db.get(Upload, uuid.UUID(upload_id))
        assert row is not None and row.status == UploadStatus.READY and row.deleted_at is None
