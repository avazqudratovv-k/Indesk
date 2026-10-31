"""refresh_tokens.session_started_at: the login time an absolute session limit counts from

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-30 12:00:00.000000

The column stays nullable (code treats NULL as created_at). Existing rows get the earliest
created_at of their family, which is the original login. A login older than the session limit
therefore cannot refresh after this migration: the user logs in again.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens", sa.Column("session_started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        """
        UPDATE refresh_tokens r
        SET session_started_at = f.started
        FROM (
          SELECT family_id, min(created_at) AS started FROM refresh_tokens GROUP BY family_id
        ) f
        WHERE r.family_id = f.family_id
        """
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "session_started_at")
