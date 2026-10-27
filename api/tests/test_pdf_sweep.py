"""No orphan text or vectors (P14): the page texts and chunks go with the upload's file, whichever
way the upload ends (the 24 h sweep, the owner's delete), and also if one was missed. The upload
ROW stays after deletion (so the foreign key cascade never fires); these tests prove the explicit
deletes."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import RunStatus, UploadMime, UploadStatus
from app.db.models import Chunk, DocumentPage, Upload, User
from app.db.models.documents import EMBEDDING_DIM
from app.services.uploads import delete_upload, sweep_expired_uploads
from app.storage import LocalDiskStorage, StorageError
from tests.factories import NOW, make_run, make_run_file, make_upload, make_user


@pytest.fixture
def storage(tmp_path: Path) -> LocalDiskStorage:
    return LocalDiskStorage(tmp_path / "uploads")


def pdf_upload(
    session: Session, storage: LocalDiskStorage, user: User, *, vectors: bool = True, **kw: object
) -> Upload:
    upload = make_upload(
        session, user, mime=UploadMime.PDF, page_count=2, row_count=None,
        storage_key=storage.put(b"%PDF-1.4 fake"), **kw,
    )  # fmt: skip
    for page in (1, 2):
        session.add(
            DocumentPage(
                upload_id=upload.id, owner_id=user.id, page=page, text="abc def", char_count=7
            )
        )
    session.flush()
    for ord_, page in enumerate((1, 1, 2)):
        session.add(Chunk(upload_id=upload.id, owner_id=user.id, page=page, ord=ord_,
                          char_start=0, char_end=3, text="abc"))  # fmt: skip
    session.flush()
    if vectors:
        vector = "[" + ",".join(["0.5"] * EMBEDDING_DIM) + "]"
        session.execute(
            text("UPDATE chunks SET embedding = CAST(:v AS vector), embedding_model = 'm' "
                 "WHERE upload_id = :u"),
            {"v": vector, "u": upload.id},
        )  # fmt: skip
    return upload


def count(session: Session, upload: Upload) -> tuple[int, int]:
    chunks = session.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.upload_id == upload.id)
    )
    pages = session.scalar(select(func.count()).select_from(DocumentPage).where(
        DocumentPage.upload_id == upload.id))  # fmt: skip
    return chunks or 0, pages or 0


def test_the_sweep_removes_text_and_vectors_of_expired_uploads_only(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    old = pdf_upload(session, storage, user, expires_at=NOW - timedelta(minutes=1))
    fresh = pdf_upload(session, storage, user, expires_at=NOW + timedelta(hours=1))
    assert count(session, old) == (3, 2)

    result = sweep_expired_uploads(session, storage, NOW)

    assert (result.deleted, result.failed, result.orphan_chunks) == (1, 0, 0)
    assert count(session, old) == (0, 0)
    assert count(session, fresh) == (3, 2)  # untouched
    session.refresh(old)
    assert old.status == UploadStatus.DELETED  # the row stays; only its text and file are gone


def test_the_owner_delete_removes_text_and_vectors(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    upload = pdf_upload(session, storage, user, expires_at=NOW + timedelta(hours=1))
    other = pdf_upload(session, storage, user, expires_at=NOW + timedelta(hours=1))

    delete_upload(session, storage, user, str(upload.id), NOW)

    assert count(session, upload) == (0, 0)
    assert count(session, other) == (3, 2)


def test_a_running_run_keeps_its_text_until_it_ends(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    upload = pdf_upload(session, storage, user, expires_at=NOW - timedelta(minutes=1))
    run = make_run(session, user, status=RunStatus.RUNNING)
    make_run_file(session, run, upload)

    result = sweep_expired_uploads(session, storage, NOW)

    assert (result.deleted, result.in_use) == (0, 1)
    assert count(session, upload) == (3, 2)


def test_text_left_behind_by_a_deleted_upload_is_swept_up(
    session: Session, storage: LocalDiskStorage
) -> None:
    """The safety net: whatever went wrong earlier, an upload marked deleted has no text."""
    user = make_user(session)
    upload = pdf_upload(session, storage, user, expires_at=NOW + timedelta(hours=1))
    upload.status, upload.deleted_at, upload.storage_key = UploadStatus.DELETED, NOW, None
    session.flush()

    result = sweep_expired_uploads(session, storage, NOW)

    assert result.orphan_chunks == 3
    assert count(session, upload) == (0, 0)
    assert session.scalar(select(func.count()).select_from(Chunk)) == 0


def test_a_failed_file_delete_still_removes_the_text(
    session: Session, storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(session)
    upload = pdf_upload(session, storage, user, expires_at=NOW - timedelta(minutes=1))

    def broken(key: str) -> None:
        raise StorageError

    monkeypatch.setattr(storage, "delete", broken)
    result = sweep_expired_uploads(session, storage, NOW)

    assert (result.deleted, result.failed) == (0, 1)
    assert count(session, upload) == (0, 0)  # the text is the sensitive part and goes first
    session.refresh(upload)
    assert upload.storage_key is not None  # the file is retried by the next sweep


def test_deleting_the_upload_row_cascades(session: Session, storage: LocalDiskStorage) -> None:
    user = make_user(session)
    upload = pdf_upload(session, storage, user)
    session.execute(text("DELETE FROM uploads WHERE id = :u"), {"u": upload.id})
    assert count(session, upload) == (0, 0)


# ---- what the table itself refuses ----


def test_a_chunk_must_match_its_span(session: Session, storage: LocalDiskStorage) -> None:
    user = make_user(session)
    upload = pdf_upload(session, storage, user, vectors=False)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            Chunk(
                upload_id=upload.id,
                owner_id=user.id,
                page=1,
                ord=9,
                char_start=0,
                char_end=5,
                text="abc",
            )
        )  # 3 characters, span of 5
        session.flush()  # fmt: skip


def test_a_chunk_needs_its_page_and_its_owner(session: Session, storage: LocalDiskStorage) -> None:
    user, stranger = make_user(session), make_user(session)
    upload = pdf_upload(session, storage, user, vectors=False)
    with pytest.raises(IntegrityError), session.begin_nested():  # page 3 does not exist
        session.add(Chunk(upload_id=upload.id, owner_id=user.id, page=3, ord=9,
                          char_start=0, char_end=3, text="abc"))  # fmt: skip
        session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():  # another user's id on this upload
        session.add(Chunk(upload_id=upload.id, owner_id=stranger.id, page=1, ord=10,
                          char_start=0, char_end=3, text="abc"))  # fmt: skip
        session.flush()


def test_the_vector_has_768_dimensions_and_a_model_name(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    upload = pdf_upload(session, storage, user, vectors=False)
    with pytest.raises(Exception, match="768"), session.begin_nested():
        session.execute(
            text(
                "UPDATE chunks SET embedding = CAST('[1,2,3]' AS vector), embedding_model = 'm'"
                " WHERE upload_id = :u"
            ),
            {"u": upload.id},
        )
    with pytest.raises(IntegrityError), session.begin_nested():  # a vector without a model name
        vector = "[" + ",".join(["0.5"] * EMBEDDING_DIM) + "]"
        session.execute(
            text("UPDATE chunks SET embedding = CAST(:v AS vector) WHERE upload_id = :u"),
            {"v": vector, "u": upload.id},
        )


def test_the_text_search_column_is_filled_by_the_database(
    session: Session, storage: LocalDiskStorage
) -> None:
    user = make_user(session)
    pdf_upload(session, storage, user, vectors=False)
    hit = session.scalar(select(func.count()).select_from(Chunk).where(
        Chunk.tsv.op("@@")(func.plainto_tsquery("simple", "abc"))))  # fmt: skip
    assert hit == 3
