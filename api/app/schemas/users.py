from typing import Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    SerializerFunctionWrapHandler,
    model_serializer,
)

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
    # PDF only: pages with too little text to search (a scanned page), computed from the stored
    # pages. Additive: the key is left out of the response for a CSV (and when the text is gone).
    pages_without_text: int | None = None

    @model_serializer(mode="wrap")
    def _leave_out_empty_pages_without_text(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if data.get("pages_without_text") is None:
            data.pop("pages_without_text", None)
        return data

    status: UploadStatus
    moderation: Moderation
    created_at: AwareDatetime
    expires_at: AwareDatetime
    deleted_at: AwareDatetime | None
