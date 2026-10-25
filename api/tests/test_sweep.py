from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.enums import RunStatus, UploadStatus
from app.db.models import AuditLog, Upload
from app.services.uploads import sweep_expired_uploads
from app.storage import LocalDiskStorage, StorageError
from tests.factories import NOW, make_run, make_run_file, make_upload, make_user


@pytest.fixture
def storage(tmp_path: Path) -> LocalDiskStorage:
    return LocalDiskStorage(tmp_path / "uploads")


def stored_upload(
    session: Session, storage: LocalDiskStorage, user: object, **kw: object
) -> Upload:
    key = storage.put(b"a,b\n1,2\n")
    return make_upload(session, user, storage_key=key, **kw)  # type: ignore[arg-type]


def test_sweep_removes_only_expired_files_and_rows(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    old = stored_upload(session, storage, user, expires_at=NOW - timedelta(minutes=1))
    edge = stored_upload(session, storage, user, expires_at=NOW)
    fresh = stored_upload(session, storage, user, expires_at=NOW + timedelta(hours=1))
    old_key, fresh_key, edge_key = old.storage_key, fresh.storage_key, edge.storage_key
    assert old_key and fresh_key and edge_key

    result = sweep_expired_uploads(session, storage, NOW)
    assert (result.deleted, result.in_use, result.failed) == (2, 0, 0)  # expires_at <= now

    for gone in (old, edge):
        session.refresh(gone)
        assert gone.storage_key is None
        assert gone.status == UploadStatus.DELETED
        assert gone.deleted_at == NOW
        assert gone.filename and gone.size and gone.sha256  # the row keeps name, type and size
    with pytest.raises(StorageError):
        storage.get(old_key)
    with pytest.raises(StorageError):
        storage.get(edge_key)

    session.refresh(fresh)
    assert fresh.storage_key == fresh_key and fresh.deleted_at is None
    assert storage.get(fresh_key) == b"a,b\n1,2\n"


def test_sweep_twice_is_safe(session: Session, storage: LocalDiskStorage) -> None:
    user = make_user(session)
    stored_upload(session, storage, user, expires_at=NOW - timedelta(hours=1))
    assert sweep_expired_uploads(session, storage, NOW).deleted == 1
    again = sweep_expired_uploads(session, storage, NOW + timedelta(hours=1))
    assert (again.deleted, again.in_use, again.failed) == (0, 0, 0)
    assert (
        len(session.scalars(select(AuditLog).where(AuditLog.action == "upload_swept")).all()) == 1
    )


def test_a_file_that_is_already_gone_still_closes_the_row(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    upload = stored_upload(session, storage, user, expires_at=NOW - timedelta(hours=1))
    assert upload.storage_key
    storage.delete(upload.storage_key)
    assert sweep_expired_uploads(session, storage, NOW).deleted == 1
    session.refresh(upload)
    assert upload.status == UploadStatus.DELETED


def test_an_upload_used_by_an_unfinished_run_waits(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    waiting = stored_upload(session, storage, user, expires_at=NOW - timedelta(hours=1))
    running = stored_upload(session, storage, user, expires_at=NOW - timedelta(hours=1))
    finished = stored_upload(session, storage, user, expires_at=NOW - timedelta(hours=1))
    make_run_file(session, make_run(session, user, status=RunStatus.QUEUED), waiting)
    make_run_file(session, make_run(session, user, status=RunStatus.RUNNING), running)
    make_run_file(
        session, make_run(session, user, status=RunStatus.FINISHED, outcome="answered"), finished
    )

    result = sweep_expired_uploads(session, storage, NOW)
    assert (result.deleted, result.in_use) == (1, 2)
    for kept in (waiting, running):
        session.refresh(kept)
        assert kept.storage_key and kept.deleted_at is None
        assert storage.get(kept.storage_key)
    session.refresh(finished)
    assert finished.status == UploadStatus.DELETED

    # Once the run ends, the next sweep takes the rest.
    session.execute(text("UPDATE runs SET status = 'finished', outcome = 'failed'"))
    assert sweep_expired_uploads(session, storage, NOW).deleted == 2


def test_a_file_that_cannot_be_removed_stays_for_the_next_sweep(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    upload = stored_upload(session, storage, user, expires_at=NOW - timedelta(hours=1))

    class Broken:
        def delete(self, key: str) -> None:
            raise StorageError("disk")

    result = sweep_expired_uploads(session, Broken(), NOW)  # type: ignore[arg-type]
    assert (result.deleted, result.failed) == (0, 1)
    session.refresh(upload)
    assert upload.storage_key and upload.deleted_at is None
    assert sweep_expired_uploads(session, storage, NOW).deleted == 1


def test_the_audit_row_has_the_owner_and_the_id_only(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    upload = stored_upload(
        session, storage, user, expires_at=NOW - timedelta(hours=1), filename="secret-name.csv"
    )
    sweep_expired_uploads(session, storage, NOW)
    row = session.scalars(select(AuditLog).where(AuditLog.action == "upload_swept")).one()
    assert row.user_id == user.id and row.target == str(upload.id)
    assert "secret-name" not in f"{row.action}{row.target}{row.ip_hash}"
