"""Create a run. Everything the client sends is checked here; user, language and limits are decided
on the server. One transaction: lock the user, replay an idempotent request, lock and check the
uploads, refuse a second active run, then insert the run, its files and the audit row.

Never logs a question or a filename."""

import hashlib
import json
import re
import uuid
from datetime import datetime
from typing import Final, NoReturn

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Limits
from app.core.enums import (
    CapDecision,
    FileRole,
    Moderation,
    Plan,
    RunMode,
    RunStatus,
    UploadMime,
    UploadStatus,
)
from app.core.errors import AppError, ErrorCode
from app.db.models import AuditLog, Run, RunFile, Upload, User
from app.runs import quota, store
from app.runs.lang import detect_lang
from app.schemas.runs import RunCreate

IDEMPOTENCY_TTL = 24 * 60 * 60
ACTIVE_INDEX: Final = "uq_runs_user_id_active"
_KEY_PATTERN: Final = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _fingerprint(body: RunCreate) -> str:
    """A hash of the request, so a reused key with a different request is caught. The hash is all
    Redis ever holds: never the question."""
    canonical = json.dumps(
        [
            body.mode.value,
            body.question,
            sorted((str(f.upload_id), f.role.value) for f in body.files),
        ]
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _idem_key(user_id: uuid.UUID, key: str) -> str:
    return f"idem:run:{user_id}:{key}"


def check_idempotency_key(key: str | None) -> str | None:
    if key is None:
        return None
    if not _KEY_PATTERN.match(key):
        raise AppError(422, ErrorCode.VALIDATION_ERROR)
    return key


def _check_body(body: RunCreate, limits: Limits) -> None:
    if body.mode is not RunMode.ASK:
        raise AppError(422, ErrorCode.MODE_NOT_AVAILABLE)
    if len(body.question) > limits.max_question_chars:
        raise AppError(422, ErrorCode.VALIDATION_ERROR)
    if len(body.files) > limits.files_per_slot["files"]:
        raise AppError(422, ErrorCode.TOO_MANY_FILES)


def _stored_role(requested: FileRole, position: int) -> FileRole:
    """The database allows ONE `subject` per run (a unique index on run_files) but an Ask request
    sends up to five files, all `subject` (RunCreate). In Ask the files are equals, so the first is
    stored as the subject and the rest as sources; the request contract is unchanged."""
    if requested is FileRole.SUBJECT and position > 0:
        return FileRole.SOURCE
    return requested


def _lock_uploads(db: Session, user: User, body: RunCreate, now: datetime) -> None:
    """Row-lock the uploads (the sweep skips locked rows) and check them. A missing, expired or
    foreign upload is one and the same 404."""
    ids = [f.upload_id for f in body.files]
    rows = list(
        db.scalars(
            select(Upload)
            .where(
                Upload.id.in_(ids),
                Upload.user_id == user.id,
                Upload.deleted_at.is_(None),
                Upload.expires_at > now,
            )
            .with_for_update(of=Upload)
        )
    )
    if len(rows) != len(ids):
        raise AppError(404, ErrorCode.NOT_FOUND)
    for upload in rows:
        if upload.mime != UploadMime.CSV:
            raise AppError(422, ErrorCode.UNSUPPORTED_TYPE)
        if (
            upload.status != UploadStatus.READY
            or upload.moderation == Moderation.BLOCKED
            or upload.storage_key is None
        ):
            raise AppError(409, ErrorCode.UPLOAD_NOT_READY)


def _run_active(run_id: uuid.UUID | None) -> AppError:
    """409 RUN_ACTIVE; the body names the run in the way, so the browser needs no local copy."""
    extra = {"run_id": str(run_id)} if run_id is not None else None
    return AppError(409, ErrorCode.RUN_ACTIVE, extra=extra)


def _refuse(db: Session, status: int, code: ErrorCode) -> NoReturn:
    """Roll back the whole admission (a counter bumped a moment ago goes with it), then refuse."""
    db.rollback()
    raise AppError(status, code)


def _admit(db: Session, limits: Limits, user: User, now: datetime) -> None:
    """The run-level gates, in order: the Free plan's total free runs, the daily run caps (user,
    then site), then a look at the model-call caps. Nothing is written unless all pass; the slot
    taken here is committed with the run itself, and given back if the run ends busy or capped."""
    if user.plan == Plan.FREE and quota.free_runs_used(db, user.id) >= limits.free_runs:
        _refuse(db, 403, ErrorCode.QUOTA_EXHAUSTED)
    day = clock.quota_day(now)
    reserved = quota.reserve_run(
        db,
        user_id=user.id,
        day=day,
        per_user=limits.daily_runs_per_user,
        per_day=limits.daily_runs_global,
    )
    if reserved is CapDecision.USER_CAP:
        _refuse(db, 429, ErrorCode.DAILY_CAP_USER)
    if reserved is CapDecision.GLOBAL_CAP:
        _refuse(db, 429, ErrorCode.DAILY_CAP_GLOBAL)
    calls = quota.calls_cap_reached(
        db,
        user_id=user.id,
        day=day,
        per_user=limits.daily_calls_per_user,
        per_day=limits.daily_calls_global,
    )
    if calls is CapDecision.USER_CAP:
        _refuse(db, 429, ErrorCode.DAILY_CAP_USER)
    if calls is CapDecision.GLOBAL_CAP:
        _refuse(db, 429, ErrorCode.DAILY_CAP_GLOBAL)


def _replay(db: Session, redis: Redis, user: User, key: str, body: RunCreate) -> Run | None:
    try:
        raw = redis.get(_idem_key(user.id, key))
    except (RedisError, OSError):
        raise AppError(503, ErrorCode.NOT_READY) from None
    if raw is None:
        return None
    stored = json.loads(raw)
    if stored["fp"] != _fingerprint(body):
        raise AppError(422, ErrorCode.VALIDATION_ERROR)
    return db.scalar(select(Run).where(Run.id == uuid.UUID(stored["run"]), Run.user_id == user.id))


def create_run(
    db: Session,
    redis: Redis,
    limits: Limits,
    user: User,
    body: RunCreate,
    *,
    idempotency_key: str | None,
    ip_hash: str,
) -> tuple[Run, bool]:
    """Returns (run, created). created is False when an idempotent request is replayed."""
    _check_body(body, limits)
    now = clock.utcnow()
    store.lock_user_runs(db, user.id)
    if idempotency_key is not None:
        replayed = _replay(db, redis, user, idempotency_key, body)
        if replayed is not None:
            db.rollback()
            return replayed, False
    _lock_uploads(db, user, body, now)
    active = store.active_run(db, user.id)
    if active is not None:
        active_id = active.id
        db.rollback()
        raise _run_active(active_id)
    _admit(db, limits, user, now)

    run = Run(
        created_at=now,  # the day of the run counter is taken from this, and given back on this day
        user_id=user.id,
        question=body.question,
        mode=body.mode,
        lang=detect_lang(body.question),
        status=RunStatus.QUEUED,
    )
    marker: str | None = None
    try:
        db.add(run)
        db.flush()
        for position, f in enumerate(body.files):
            db.add(
                RunFile(
                    run_id=run.id,
                    upload_id=f.upload_id,
                    owner_id=user.id,
                    role=_stored_role(f.role, position),
                )
            )
        db.add(
            AuditLog(
                user_id=user.id, action=store.AUDIT_RUN_CREATED, target=str(run.id), ip_hash=ip_hash
            )
        )
        db.flush()
        if idempotency_key is not None:
            # Set before the commit: a request waiting on the lock finds the key once we release it.
            marker = _idem_key(user.id, idempotency_key)
            value = json.dumps({"run": str(run.id), "fp": _fingerprint(body)})
            try:
                redis.set(marker, value, ex=IDEMPOTENCY_TTL, nx=True)
            except (RedisError, OSError):
                marker = None
                raise AppError(503, ErrorCode.NOT_READY) from None
        db.commit()
    except IntegrityError as error:
        db.rollback()
        _forget(redis, marker)
        if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == ACTIVE_INDEX:
            active = store.active_run(db, user.id)  # the winner of the race
            raise _run_active(active.id if active else None) from None
        raise
    except Exception:
        db.rollback()
        _forget(redis, marker)
        raise
    return run, True


def _forget(redis: Redis, marker: str | None) -> None:
    if marker is not None:
        try:
            redis.delete(marker)
        except (RedisError, OSError):
            pass


def get_run(db: Session, user: User, raw_id: str) -> Run:
    """Someone else's run, a missing one and a malformed id all give the same 404."""
    not_found = AppError(404, ErrorCode.NOT_FOUND)
    try:
        run_id = uuid.UUID(raw_id)
    except ValueError:
        raise not_found from None
    run = db.scalar(select(Run).where(Run.id == run_id, Run.user_id == user.id))
    if run is None:
        raise not_found
    return run


def get_active_run(db: Session, user: User) -> Run | None:
    """The caller's run that has not finished, if any."""
    return store.active_run(db, user.id)


def forget_key(redis: Redis, user_id: uuid.UUID, key: str | None) -> None:
    if key is not None:
        _forget(redis, _idem_key(user_id, key))
