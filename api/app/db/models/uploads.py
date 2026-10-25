import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Moderation, UploadMime, UploadStatus
from app.db.base import Base, Timestamp, created_at_col, enum_check, uuid_pk


class Upload(Base):
    """File metadata. storage_key and sha256 are internal: the API schema never exposes them.
    The row stays after the file is deleted (name, type, size); only storage_key is cleared."""

    __tablename__ = "uploads"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None]
    row_count: Mapped[int | None]
    status: Mapped[str] = mapped_column(
        Text, default=UploadStatus.UPLOADED, server_default=UploadStatus.UPLOADED.value
    )
    moderation: Mapped[str] = mapped_column(
        Text, default=Moderation.PENDING, server_default=Moderation.PENDING.value
    )
    created_at: Mapped[created_at_col]
    expires_at: Mapped[Timestamp]
    deleted_at: Mapped[Timestamp | None]

    __table_args__ = (
        # (id, user_id) lets run_files prove an upload and a run have the same owner.
        UniqueConstraint("id", "user_id", name="uq_uploads_id_user_id"),
        Index("ix_uploads_expires_at", "expires_at"),
        CheckConstraint("char_length(filename) BETWEEN 1 AND 255", name="filename"),
        CheckConstraint("size >= 0", name="size"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        CheckConstraint("page_count IS NULL OR page_count >= 0", name="page_count"),
        CheckConstraint("row_count IS NULL OR row_count >= 0", name="row_count"),
        enum_check("mime", UploadMime, "mime"),
        enum_check("status", UploadStatus, "status"),
        enum_check("moderation", Moderation, "moderation"),
    )
