import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DefaultView, EmailTokenPurpose, Lang, Plan, Theme
from app.db.base import Base, Timestamp, created_at_col, enum_check, uuid_pk


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid_pk]
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)  # Argon2; never leaves the server
    display_name: Mapped[str] = mapped_column(Text)
    handle: Mapped[str] = mapped_column(Text, unique=True)
    discoverable: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    plan: Mapped[str] = mapped_column(Text, default=Plan.FREE, server_default=Plan.FREE.value)
    lang: Mapped[str] = mapped_column(Text, default=Lang.EN, server_default=Lang.EN.value)
    theme: Mapped[str] = mapped_column(Text, default=Theme.LIGHT, server_default=Theme.LIGHT.value)
    default_view: Mapped[str] = mapped_column(
        Text, default=DefaultView.SIMPLE, server_default=DefaultView.SIMPLE.value
    )
    notify: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[created_at_col]
    deleted_at: Mapped[Timestamp | None]
    # Set when the address is proven (a verify link or a password reset). Existing accounts were
    # backfilled by migration 0007.
    email_verified_at: Mapped[Timestamp | None]
    # An access token issued before this moment is refused (set by a password reset).
    tokens_valid_after: Mapped[Timestamp | None]

    __table_args__ = (
        CheckConstraint(
            "email = lower(email) AND char_length(email) BETWEEN 3 AND 254", name="email"
        ),
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 60", name="display_name"),
        CheckConstraint(
            "handle = lower(handle) AND char_length(handle) BETWEEN 3 AND 30", name="handle"
        ),
        enum_check("plan", Plan, "plan"),
        enum_check("lang", Lang, "lang"),
        enum_check("theme", Theme, "theme"),
        enum_check("default_view", DefaultView, "default_view"),
    )


class RefreshToken(Base):
    """Only a hash of the token is stored. All tokens of one login share a family_id: reuse of
    an old token revokes the whole family."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )
    # Login time of this chain; rotated tokens copy it. NULL = a row from before migration 0006.
    session_started_at: Mapped[Timestamp | None]
    expires_at: Mapped[Timestamp]
    revoked_at: Mapped[Timestamp | None]
    created_at: Mapped[created_at_col]

    __table_args__ = (Index("ix_refresh_tokens_expires_at", "expires_at"),)


class EmailToken(Base):
    """A single-use link token for password reset or email verification. Only a hash is stored. A
    token of one purpose must never be accepted for the other."""

    __tablename__ = "email_tokens"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[Timestamp]
    used_at: Mapped[Timestamp | None]
    created_at: Mapped[created_at_col]

    __table_args__ = (
        enum_check("purpose", EmailTokenPurpose, "purpose"),
        Index("ix_email_tokens_user_id_purpose", "user_id", "purpose"),
        Index("ix_email_tokens_expires_at", "expires_at"),
    )
