"""The text of an uploaded PDF, kept for search (P14). Both tables belong to one upload and go
with it:
the sweep and the owner's delete remove these rows when they remove the file (the upload row stays,
so the cascade alone never fires). `chunks.embedding` is filled during a run (part 2), so it is NULL
at upload."""

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.db.base import Base, created_at_col, uuid_pk

# Vector size of chunks.embedding (owner answer to the P14 plan, Q1): 768, asked from the model with
# outputDimensionality. NOT VERIFIED against the live model; if it cannot return 768, a follow-up
# migration changes the column before any production data exists.
EMBEDDING_DIM = 768


class VectorType(UserDefinedType[list[float]]):
    """pgvector's `vector(N)` without the pgvector Python package (no new dependency yet: part 1
    never
        reads or writes a vector). Registered below so reflection and autogenerate know the type."""

    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dim})"


ischema_names["vector"] = VectorType


class DocumentPage(Base):
    """The text of one page, as stored (NFC, no control characters). Cat checks quotes on it."""

    __tablename__ = "document_pages"

    upload_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    page: Mapped[int] = mapped_column(primary_key=True)  # 1-based
    owner_id: Mapped[uuid.UUID]
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int]

    __table_args__ = (
        ForeignKeyConstraint(
            ["upload_id", "owner_id"], ["uploads.id", "uploads.user_id"], ondelete="CASCADE"
        ),
        CheckConstraint("page >= 1", name="page"),
        CheckConstraint("char_count = char_length(text)", name="char_count"),
    )


class Chunk(Base):
    """A slice of one page: text == page.text[char_start:char_end], never across a page."""

    __tablename__ = "chunks"

    id: Mapped[uuid_pk]
    upload_id: Mapped[uuid.UUID]
    owner_id: Mapped[uuid.UUID]
    page: Mapped[int]
    ord: Mapped[int]  # position in the whole document, from 0
    char_start: Mapped[int]
    char_end: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True)
    )
    embedding: Mapped[list[float] | None] = mapped_column(VectorType(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[created_at_col]

    __table_args__ = (
        ForeignKeyConstraint(
            ["upload_id", "owner_id"], ["uploads.id", "uploads.user_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["upload_id", "page"],
            ["document_pages.upload_id", "document_pages.page"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("upload_id", "ord", name="uq_chunks_upload_id_ord"),
        Index("ix_chunks_upload_id_page", "upload_id", "page"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        CheckConstraint("page >= 1 AND ord >= 0", name="position"),
        CheckConstraint(
            "char_start >= 0 AND char_end > char_start"
            " AND char_length(text) = char_end - char_start",
            name="span",
        ),
        CheckConstraint("(embedding IS NULL) = (embedding_model IS NULL)", name="embedding_pair"),
    )


__all__ = ["EMBEDDING_DIM", "Chunk", "DocumentPage", "VectorType"]
