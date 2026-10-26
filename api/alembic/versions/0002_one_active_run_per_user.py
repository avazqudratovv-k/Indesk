"""one active run per user

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Additive: an index only. A user can have at most one run that is not finished.
    op.create_index(
        "uq_runs_user_id_active",
        "runs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'finished'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_runs_user_id_active",
        table_name="runs",
        postgresql_where=sa.text("status <> 'finished'"),
    )
