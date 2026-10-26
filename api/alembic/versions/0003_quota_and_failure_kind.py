"""one quota row per run, and the failure kind of a model call

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of app.core.enums.FailureKind: a migration must not change when the enum does.
FAILURE_KINDS = (
    "http_400",
    "http_401",
    "http_403",
    "http_404",
    "http_4xx",
    "http_5xx",
    "transport",
    "bad_json",
    "too_large",
    "other",
)


def upgrade() -> None:
    # Additive. Nothing wrote `run` usage events before this revision, but if a database holds two
    # for one run, keep the first so the unique index can be built: no row of a different run goes.
    op.execute(
        """
        DELETE FROM usage_events AS later
        USING usage_events AS earlier
        WHERE later.kind = 'run' AND earlier.kind = 'run'
          AND later.run_id IS NOT NULL AND later.run_id = earlier.run_id
          AND (later.created_at, later.id) > (earlier.created_at, earlier.id)
        """
    )
    op.create_index(
        "uq_usage_events_run_id_run",
        "usage_events",
        ["run_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'run'"),
    )
    op.add_column("ai_calls", sa.Column("failure_kind", sa.Text(), nullable=True))
    values = ", ".join(f"'{kind}'" for kind in FAILURE_KINDS)
    op.create_check_constraint(
        op.f("ck_ai_calls_failure_kind"), "ai_calls", f"failure_kind IN ({values})"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_ai_calls_failure_kind"), "ai_calls", type_="check")
    op.drop_column("ai_calls", "failure_kind")
    op.drop_index(
        "uq_usage_events_run_id_run",
        table_name="usage_events",
        postgresql_where=sa.text("kind = 'run'"),
    )
