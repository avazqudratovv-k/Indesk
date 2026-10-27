"""document_pages and chunks for PDF search (P14a), with the pgvector extension

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-28 12:00:00.000000

The pgvector extension must exist. A superuser creates it once (db-init does on a fresh volume; on an
existing database run `CREATE EXTENSION vector;` as the superuser). `CREATE EXTENSION IF NOT EXISTS`
below is then a no-op. If it is missing and this role may not create it, the migration stops with a
clear message instead of a bare permission error.

No ANN index on chunks.embedding on purpose: every search is for one upload (at most a few hundred
rows) and an exact scan is both exact and fast; an HNSW index applied before a filter on upload_id
can return too few rows.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "indesk_app"
EMBEDDING_DIM = 768  # frozen copy of app.db.models.documents.EMBEDDING_DIM


class Vector(UserDefinedType[list[float]]):
    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dim})"


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          CREATE EXTENSION IF NOT EXISTS vector;
        EXCEPTION
          WHEN insufficient_privilege OR undefined_file OR feature_not_supported THEN
            RAISE EXCEPTION 'The pgvector extension is missing. A superuser must run once: CREATE EXTENSION vector;'
              USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.create_table(
        "document_pages",
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("page >= 1", name=op.f("ck_document_pages_page")),
        sa.CheckConstraint(
            "char_count = char_length(text)", name=op.f("ck_document_pages_char_count")
        ),
        sa.ForeignKeyConstraint(
            ["upload_id", "owner_id"],
            ["uploads.id", "uploads.user_id"],
            name=op.f("fk_document_pages_upload_id_uploads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("upload_id", "page", name=op.f("pk_document_pages")),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', text)", persisted=True),
            nullable=True,
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("page >= 1 AND ord >= 0", name=op.f("ck_chunks_position")),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start AND char_length(text) = char_end - char_start",
            name=op.f("ck_chunks_span"),
        ),
        sa.CheckConstraint(
            "(embedding IS NULL) = (embedding_model IS NULL)", name=op.f("ck_chunks_embedding_pair")
        ),
        sa.ForeignKeyConstraint(
            ["upload_id", "owner_id"],
            ["uploads.id", "uploads.user_id"],
            name=op.f("fk_chunks_upload_id_uploads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id", "page"],
            ["document_pages.upload_id", "document_pages.page"],
            name=op.f("fk_chunks_upload_id_document_pages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunks")),
        sa.UniqueConstraint("upload_id", "ord", name="uq_chunks_upload_id_ord"),
    )
    op.create_index("ix_chunks_upload_id_page", "chunks", ["upload_id", "page"])
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    # Migration 0004's default privileges already cover tables the migrator creates; this makes the
    # grant explicit for a database where those defaults were never set. Only when the role exists.
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON document_pages, chunks TO {APP_ROLE};
          END IF;
        END
        $$
        """  # noqa: S608  # constant role name only
    )


def downgrade() -> None:
    # The extension stays: other objects may use it, and a superuser created it.
    op.drop_index("ix_chunks_tsv", table_name="chunks")
    op.drop_index("ix_chunks_upload_id_page", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("document_pages")
