"""Create, list and read uploads, and the expiry sweep. Every function commits its own work.
Audit rows hold the user and the upload id only: no filename, no content."""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import BinaryIO

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Limits
from app.core.enums import Moderation, RunStatus, UploadMime, UploadStatus
from app.core.errors import AppError, ErrorCode
from app.db.models import AuditLog, Run, RunFile, Upload, User
from app.services import csv_check
from app.storage import Storage, StorageError

logger = logging.getLogger("indesk.uploads")

AUDIT_UPLOAD_CREATED = "upload_created"
AUDIT_UPLOAD_SWEPT = "upload_swept"


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
    """Checks in order: size, empty, declared type, content sniff, encoding, CSV shape."""
    data = stream.read(limits.max_file_bytes + 1)  # never the whole oversized body
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


@dataclass(frozen=True)
class SweepResult:
    deleted: int  # files removed and rows marked deleted
    in_use: int  # expired but attached to a run that has not finished: left for the next sweep
    failed: int  # the file could not be removed: left for the next sweep


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
    db.commit()
    return SweepResult(deleted=deleted, in_use=in_use, failed=failed)
