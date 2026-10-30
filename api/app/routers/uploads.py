from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile

from app.core import clock, ratelimit
from app.core.errors import AppError, ErrorCode
from app.db.models import Upload as UploadRow
from app.routers.deps import AppSettings, CurrentUser, Db, IpHash, RedisDep
from app.schemas.users import Upload
from app.services import uploads as service
from app.storage import LocalDiskStorage, Storage

router = APIRouter(prefix="/uploads", tags=["uploads"])

CONSENT_VALUE = "true"


def get_storage(settings: AppSettings) -> Storage:
    return LocalDiskStorage(settings.storage_dir)


StorageDep = Annotated[Storage, Depends(get_storage)]


@router.post("", status_code=201, response_model=Upload)
def create_upload(
    db: Db,
    settings: AppSettings,
    storage: StorageDep,
    user: CurrentUser,
    ip_hash: IpHash,
    redis: RedisDep,
    file: Annotated[UploadFile, File()],
    consent: Annotated[str, Form()] = "",
) -> Upload:
    # Every attempt of a signed-in user counts, accepted or not. Redis down: refused (503).
    ratelimit.hit(
        redis, f"rl:upload:{user.id}", settings.limits.uploads_per_hour, ratelimit.UPLOAD_WINDOW
    )
    if consent != CONSENT_VALUE:
        raise AppError(422, ErrorCode.CONSENT_REQUIRED)
    upload = service.create_upload(
        db,
        storage,
        settings.limits,
        user,
        filename=file.filename,
        content_type=file.content_type,
        stream=file.file,
        ip_hash=ip_hash,
    )
    return _view(db, settings, [upload])[0]


def _view(db: Db, settings: AppSettings, rows: list[UploadRow]) -> list[Upload]:
    """The public shape of each upload, with pages_without_text filled in for PDFs."""
    counts = service.pages_without_text(db, rows, settings.limits)
    return [
        Upload.model_validate(u).model_copy(update={"pages_without_text": counts[u.id]})
        for u in rows
    ]


@router.get("", response_model=list[Upload])
def list_uploads(
    db: Db,
    settings: AppSettings,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    include_deleted: bool = False,
) -> list[Upload]:
    rows = service.list_uploads(
        db, user, clock.utcnow(), limit=limit, include_deleted=include_deleted
    )
    return _view(db, settings, rows)


@router.delete("/{upload_id}", status_code=204)
def delete_upload(upload_id: str, db: Db, storage: StorageDep, user: CurrentUser) -> Response:
    service.delete_upload(db, storage, user, upload_id, clock.utcnow())
    return Response(status_code=204)


@router.get("/{upload_id}", response_model=Upload)
def get_upload(upload_id: str, db: Db, settings: AppSettings, user: CurrentUser) -> Upload:
    return _view(db, settings, [service.get_upload(db, user, upload_id, clock.utcnow())])[0]
