"""email_tokens, users.email_verified_at (backfilled) and users.tokens_valid_after

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-02 09:00:00.000000

Password reset and sign-up verification (owner decisions 2026-11-02). Every account that exists when
this runs counts as verified: email_verified_at is set to the migration time and nothing else of
those rows changes. users.lang already exists since 0001, so it is not touched here.

Grants: migration 0004 set default privileges for tables the migrator creates, so indesk_app gets
row access to email_tokens by itself; the guarded GRANT below only repeats that explicitly.
Downgrade drops the table and both columns, which also forgets who was verified.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "indesk_app"


def upgrade() -> None:
    op.create_table(
        "email_tokens",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("purpose IN ('reset', 'verify')", name=op.f("ck_email_tokens_purpose")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_tokens_token_hash")),
    )
    op.create_index("ix_email_tokens_user_id_purpose", "email_tokens", ["user_id", "purpose"])
    op.create_index("ix_email_tokens_expires_at", "email_tokens", ["expires_at"])

    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("tokens_valid_after", sa.DateTime(timezone=True), nullable=True))
    # Existing accounts count as verified. Only this column changes.
    op.execute("UPDATE users SET email_verified_at = now() WHERE email_verified_at IS NULL")

    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE email_tokens TO {APP_ROLE};
          END IF;
        END
        $$
        """  # noqa: S608  # constant role name only
    )


def downgrade() -> None:
    op.drop_column("users", "tokens_valid_after")
    op.drop_column("users", "email_verified_at")
    op.drop_index("ix_email_tokens_expires_at", table_name="email_tokens")
    op.drop_index("ix_email_tokens_user_id_purpose", table_name="email_tokens")
    op.drop_table("email_tokens")
