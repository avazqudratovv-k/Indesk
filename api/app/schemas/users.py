from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.core.enums import DefaultView, Lang, Moderation, Plan, Theme, UploadMime, UploadStatus
from app.schemas.common import Id


class User(BaseModel):
    """What the API returns about the signed-in user. There is no password_hash field, and unknown
    attributes of the database row are ignored, so the hash cannot leak through this shape."""

    model_config = ConfigDict(from_attributes=True)

    id: Id
    email: str
    display_name: str
    handle: str
    discoverable: bool
    plan: Plan
    lang: Lang
    theme: Theme
    default_view: DefaultView
    notify: bool
    created_at: AwareDatetime
    deleted_at: AwareDatetime | None


class Upload(BaseModel):
    """File metadata for the owner. storage_key and sha256 are internal and are not fields here."""

    model_config = ConfigDict(from_attributes=True)

    id: Id
    user_id: Id
    filename: str
    mime: UploadMime
    size: int
    page_count: int | None
    row_count: int | None
    status: UploadStatus
    moderation: Moderation
    created_at: AwareDatetime
    expires_at: AwareDatetime
    deleted_at: AwareDatetime | None
