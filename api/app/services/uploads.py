"""Create, list and read uploads, and the expiry sweep. Every function commits its own work.
Audit rows hold the user and the upload id only: no filename, no content."""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import BinaryIO

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from app import sandbox_client
from app.core import clock
from app.core.config import Limits
from app.core.enums import Moderation, RunStatus, SandboxErrorCode, UploadMime, UploadStatus
from app.core.errors import AppError, ErrorCode
from app.db.models import AuditLog, Chunk, DocumentPage, Run, RunFile, Upload, User
from app.services import chunking, csv_check
from app.storage import Storage, StorageError

logger = logging.getLogger("indesk.uploads")

AUDIT_UPLOAD_CREATED = "upload_created"
AUDIT_UPLOAD_SWEPT = "upload_swept"
AUDIT_UPLOAD_DELETED = "upload_deleted"

PDF_EXTENSION = "pdf"
PDF_MIMES = frozenset({"application/pdf", "application/x-pdf", ""})  # some browsers send nothing
_PDF_MAGIC = b"%PDF-"
_PDF_SCAN_BYTES = 1024  # a PDF may start with a few junk bytes before the magic number
# What the sandbox says about a PDF it would not read, as the code the client sees.
_PARSE_REFUSALS: dict[SandboxErrorCode, ErrorCode] = {
    SandboxErrorCode.ENCRYPTED: ErrorCode.PDF_ENCRYPTED,
    SandboxErrorCode.TOO_MANY_PAGES: ErrorCode.PDF_TOO_MANY_PAGES,
    SandboxErrorCode.TOO_MUCH_TEXT: ErrorCode.PDF_TOO_MUCH_TEXT,
}


def create_csv_upload(
    db: Session,
    storage: Storage,
    limits: Limits,
    user: User,
    *,
    filename: str | None,
    content_type: str | None,
    stream: BinaryIO,
    ip_hash: str,
) -> Upload:
    """Checks in order: header, size, empty, declared type, content sniff, encoding, CSV shape."""
    # Too many columns is refused here, before the rest of the body is read.
    head = csv_check.read_header(stream, limits)
    # Never the whole oversized body.
    data = head + stream.read(max(0, limits.max_file_bytes + 1 - len(head)))
    if len(data) > limits.max_file_bytes:
        raise AppError(413, ErrorCode.FILE_TOO_LARGE)
    if not data:
        raise AppError(422, ErrorCode.EMPTY_FILE)
    name = csv_check.sanitize_filename(filename, limits.max_filename_chars)
    csv_check.check_declared_type(name, content_type)
    checked = csv_check.check_csv(data, limits)

    try:
        key = storage.put(checked.utf8_bytes)
    except StorageError:
        logger.error("upload: storage write failed")
        raise AppError(500, ErrorCode.INTERNAL) from None
    now = clock.utcnow()
    upload = Upload(
        user_id=user.id,
        filename=name,
        mime=UploadMime.CSV,
        size=len(data),  # what the user sent; the stored copy may be longer after cp949 -> UTF-8
        sha256=hashlib.sha256(checked.utf8_bytes).hexdigest(),  # of the stored bytes
        storage_key=key,
        row_count=checked.row_count,
        status=UploadStatus.READY,  # structure checked
        moderation=Moderation.PENDING,  # no malware or content scan exists yet, so never "passed"
        created_at=now,
        expires_at=now + timedelta(hours=limits.upload_ttl_hours),
    )
    try:
        db.add(upload)
        db.flush()
        db.add(
            AuditLog(
                user_id=user.id, action=AUDIT_UPLOAD_CREATED, target=str(upload.id), ip_hash=ip_hash
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)  # no stored file without a row
        raise
    return upload


def create_upload(
    db: Session,
    storage: Storage,
    limits: Limits,
    user: User,
    *,
    filename: str | None,
    content_type: str | None,
    stream: BinaryIO,
    ip_hash: str,
) -> Upload:
    """A .pdf goes the PDF way, anything else the CSV way (which refuses what it does not take)."""
    name = csv_check.sanitize_filename(filename, limits.max_filename_chars)
    route = (
        create_pdf_upload if csv_check.extension_of(name) == PDF_EXTENSION else create_csv_upload
    )
    return route(
        db, storage, limits, user,
        filename=filename, content_type=content_type, stream=stream, ip_hash=ip_hash,
    )  # fmt: skip


def _check_pdf_type(name: str, declared_mime: str | None, data: bytes) -> None:
    if csv_check.normalize_mime(declared_mime) not in PDF_MIMES:
        raise AppError(415, ErrorCode.TYPE_MISMATCH)
    if _PDF_MAGIC not in data[:_PDF_SCAN_BYTES]:  # the headers are not trusted: the bytes decide
        raise AppError(415, ErrorCode.TYPE_MISMATCH)


def _pdf_pages(data: bytes, limits: Limits) -> list[str]:
    """Parse in the sandbox, then apply the page and text policy of limits.toml. Returns the cleaned
    text of each page. Every refusal is an AppError with a PDF code; nothing echoes the file."""
    parsed = sandbox_client.parse_pdf(
        data, max_pages=limits.max_pdf_pages, max_chars=limits.max_pdf_chars
    )
    if isinstance(parsed, sandbox_client.SandboxError):
        code = parsed.code
        if code == SandboxErrorCode.UNAVAILABLE:
            raise AppError(503, ErrorCode.PARSER_BUSY, headers={"Retry-After": "5"})
        raise AppError(422, _PARSE_REFUSALS.get(code, ErrorCode.PDF_UNREADABLE))
    pages = [chunking.clean_page_text(text) for text in parsed.parsed.pages]
    if len(pages) > limits.max_pdf_pages:
        raise AppError(422, ErrorCode.PDF_TOO_MANY_PAGES)
    total = sum(len(text) for text in pages)
    if total > limits.max_pdf_chars:
        raise AppError(422, ErrorCode.PDF_TOO_MUCH_TEXT)
    with_text = sum(1 for text in pages if len(text.strip()) >= limits.pdf_min_page_chars)
    if total < limits.pdf_min_text_chars or with_text * 2 < len(pages):
        raise AppError(422, ErrorCode.PDF_NO_TEXT)  # a scan or an empty file: nothing to search
    return pages


def create_pdf_upload(
    db: Session,
    storage: Storage,
    limits: Limits,
    user: User,
    *,
    filename: str | None,
    content_type: str | None,
    stream: BinaryIO,
    ip_hash: str,
) -> Upload:
    """Checks in order: size, empty, declared type, magic number, sandbox parse, page and text
    policy. The upload row, the page texts and the chunks (no vectors yet) go in one transaction."""
    data = stream.read(limits.max_file_bytes + 1)  # never the whole oversized body
    if len(data) > limits.max_file_bytes:
        raise AppError(413, ErrorCode.FILE_TOO_LARGE)
    if not data:
        raise AppError(422, ErrorCode.EMPTY_FILE)
    name = csv_check.sanitize_filename(filename, limits.max_filename_chars)
    _check_pdf_type(name, content_type, data)
    pages = _pdf_pages(data, limits)

    try:
        key = storage.put(data)
    except StorageError:
        logger.error("upload: storage write failed")
        raise AppError(500, ErrorCode.INTERNAL) from None
    now = clock.utcnow()
    upload = Upload(
        user_id=user.id,
        filename=name,
        mime=UploadMime.PDF,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=key,
        page_count=len(pages),
        status=UploadStatus.READY,
        moderation=Moderation.PENDING,  # no malware or content scan exists yet, so never "passed"
        created_at=now,
        expires_at=now + timedelta(hours=limits.upload_ttl_hours),
    )
    try:
        db.add(upload)
        db.flush()
        db.add_all(
            DocumentPage(
                upload_id=upload.id, owner_id=user.id, page=number, text=text, char_count=len(text)
            )
            for number, text in enumerate(pages, start=1)
        )
        db.flush()  # the pages first: a chunk's foreign key points at its page
        db.add_all(
            Chunk(
                upload_id=upload.id,
                owner_id=user.id,
                page=chunk.page,
                ord=chunk.ord,
                char_start=chunk.start,
                char_end=chunk.end,
                text=chunk.text,
            )  # fmt: skip
            for chunk in chunking.chunk_document(
                pages, limits.chunk_chars, limits.chunk_overlap_chars
            )
        )
        db.add(
            AuditLog(
                user_id=user.id, action=AUDIT_UPLOAD_CREATED, target=str(upload.id), ip_hash=ip_hash
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)  # no stored file without a row
        raise
    return upload


def pages_without_text(
    db: Session, uploads: list[Upload], limits: Limits
) -> dict[uuid.UUID, int | None]:
    """For each PDF upload: how many stored pages hold fewer than `pdf_min_page_chars` characters
    (a scanned page), the same line the upload policy draws. None for a CSV, or a PDF whose page
    text is gone. Computed from document_pages: nothing is stored for it."""
    ids = [u.id for u in uploads if u.mime == UploadMime.PDF]
    counts: dict[uuid.UUID, int | None] = {u.id: None for u in uploads}
    if not ids:
        return counts
    short = func.length(func.btrim(DocumentPage.text, " \n\t\r")) < limits.pdf_min_page_chars
    rows = db.execute(
        select(DocumentPage.upload_id, func.count(), func.count().filter(short))
        .where(DocumentPage.upload_id.in_(ids))
        .group_by(DocumentPage.upload_id)
    ).all()
    for upload_id, _total, without in rows:
        counts[upload_id] = int(without)
    return counts


def delete_document_text(db: Session, upload_ids: list[uuid.UUID] | None = None) -> int:
    """Delete the page texts and chunks (and so the vectors) of these uploads, or of every upload
    that is already marked deleted. Returns the chunks removed. The upload row is not touched."""
    if upload_ids is None:
        deleted_ids = select(Upload.id).where(Upload.deleted_at.is_not(None))
        condition_chunk, condition_page = (
            Chunk.upload_id.in_(deleted_ids),
            DocumentPage.upload_id.in_(deleted_ids),
        )
    else:
        condition_chunk = Chunk.upload_id.in_(upload_ids)
        condition_page = DocumentPage.upload_id.in_(upload_ids)
    removed = len(db.execute(delete(Chunk).where(condition_chunk).returning(Chunk.id)).all())
    db.execute(delete(DocumentPage).where(condition_page))
    return removed


def list_uploads(db: Session, user: User, now: datetime) -> list[Upload]:
    """The caller's own live uploads, newest first."""
    stmt = (
        select(Upload)
        .where(Upload.user_id == user.id, Upload.deleted_at.is_(None), Upload.expires_at > now)
        .order_by(Upload.created_at.desc(), Upload.id.desc())
    )
    return list(db.scalars(stmt))


def get_upload(db: Session, user: User, raw_id: str, now: datetime) -> Upload:
    """Someone else's upload, a missing one and a malformed id all give the same 404."""
    not_found = AppError(404, ErrorCode.NOT_FOUND)
    try:
        upload_id = uuid.UUID(raw_id)
    except ValueError:
        raise not_found from None
    upload = db.scalar(
        select(Upload).where(
            Upload.id == upload_id,
            Upload.user_id == user.id,
            Upload.deleted_at.is_(None),
            Upload.expires_at > now,
        )
    )
    if upload is None:
        raise not_found
    return upload


def delete_upload(db: Session, storage: Storage, user: User, raw_id: str, now: datetime) -> None:
    """The owner removes an upload. The stored file goes, the row stays (name, type, size) with
    status deleted, as for the sweep. Someone else's, a missing, an expired and a malformed id all
    give the same 404. The row is locked first, so a run being created at the same moment either
    sees the file gone or makes this answer 409."""
    not_found = AppError(404, ErrorCode.NOT_FOUND)
    try:
        upload_id = uuid.UUID(raw_id)
    except ValueError:
        raise not_found from None
    upload = db.scalar(
        select(Upload)
        .where(
            Upload.id == upload_id,
            Upload.user_id == user.id,
            Upload.deleted_at.is_(None),
            Upload.expires_at > now,
        )
        .with_for_update(of=Upload)
    )
    if upload is None:
        raise not_found
    running = exists().where(
        RunFile.upload_id == upload.id, RunFile.run_id == Run.id, Run.status != RunStatus.FINISHED
    )
    if db.scalar(select(running)):
        db.rollback()
        raise AppError(409, ErrorCode.UPLOAD_IN_USE)
    delete_document_text(
        db, [upload.id]
    )  # the derived text goes with the file, in this transaction
    try:
        if upload.storage_key is not None:
            storage.delete(upload.storage_key)
    except StorageError:
        db.rollback()
        logger.error("delete: could not delete the file of upload %s", upload.id)
        raise AppError(500, ErrorCode.INTERNAL) from None
    upload.storage_key = None
    upload.status = UploadStatus.DELETED
    upload.deleted_at = now
    db.add(AuditLog(user_id=user.id, action=AUDIT_UPLOAD_DELETED, target=str(upload.id)))
    db.commit()


@dataclass(frozen=True)
class SweepResult:
    deleted: int  # files removed and rows marked deleted
    in_use: int  # expired but attached to a run that has not finished: left for the next sweep
    failed: int  # the file could not be removed: left for the next sweep
    orphan_chunks: int = (
        0  # chunks that belonged to an upload already marked deleted (a safety net)
    )


def sweep_expired_uploads(db: Session, storage: Storage, now: datetime) -> SweepResult:
    """Delete the stored file of every upload past expires_at. The row stays (name, type, size) with
    status deleted, as DATA.md says. Safe to run twice and from two processes at once."""
    running = exists().where(
        RunFile.upload_id == Upload.id, RunFile.run_id == Run.id, Run.status != RunStatus.FINISHED
    )
    expired = (Upload.deleted_at.is_(None), Upload.expires_at <= now)
    in_use = len(db.scalars(select(Upload.id).where(*expired, running)).all())
    stmt = select(Upload).where(*expired, ~running).with_for_update(skip_locked=True, of=Upload)
    deleted = failed = 0
    for upload in db.scalars(stmt).all():
        delete_document_text(
            db, [upload.id]
        )  # first: the text is the sensitive part, the file is not
        try:
            if upload.storage_key is not None:
                storage.delete(upload.storage_key)
        except StorageError:
            logger.error("sweep: could not delete the file of upload %s", upload.id)
            failed += 1
            continue
        upload.storage_key = None
        upload.status = UploadStatus.DELETED
        upload.deleted_at = now
        db.add(AuditLog(user_id=upload.user_id, action=AUDIT_UPLOAD_SWEPT, target=str(upload.id)))
        deleted += 1
    # Safety net: an upload already marked deleted must have no text left (no orphan vectors).
    orphans = delete_document_text(db)
    db.commit()
    return SweepResult(deleted=deleted, in_use=in_use, failed=failed, orphan_chunks=orphans)
