from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core import clock, ratelimit
from app.core.errors import AppError, ErrorCode
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
    upload = service.create_csv_upload(
        db,
        storage,
        settings.limits,
        user,
        filename=file.filename,
        content_type=file.content_type,
        stream=file.file,
        ip_hash=ip_hash,
    )
    return Upload.model_validate(upload)


@router.get("", response_model=list[Upload])
def list_uploads(db: Db, user: CurrentUser) -> list[Upload]:
    return [Upload.model_validate(u) for u in service.list_uploads(db, user, clock.utcnow())]


@router.get("/{upload_id}", response_model=Upload)
def get_upload(upload_id: str, db: Db, user: CurrentUser) -> Upload:
    return Upload.model_validate(service.get_upload(db, user, upload_id, clock.utcnow()))
