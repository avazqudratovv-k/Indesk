"""row-level grants for the app role

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-28 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "indesk_app"
MIGRATOR_ROLE = "indesk_migrator"


def upgrade() -> None:
    # Only when the roles exist (compose and production create them in the db container), so a
    # plain superuser setup, such as CI, keeps working and gets no grants.
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT USAGE ON SCHEMA public TO {APP_ROLE};
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};
            REVOKE ALL ON TABLE alembic_version FROM {APP_ROLE};
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{MIGRATOR_ROLE}') THEN
              ALTER DEFAULT PRIVILEGES FOR ROLE {MIGRATOR_ROLE} IN SCHEMA public
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};
            END IF;
          END IF;
        END
        $$
        """  # noqa: S608  # constant role names only
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{MIGRATOR_ROLE}') THEN
              ALTER DEFAULT PRIVILEGES FOR ROLE {MIGRATOR_ROLE} IN SCHEMA public
                REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE};
            END IF;
            REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM {APP_ROLE};
            REVOKE USAGE ON SCHEMA public FROM {APP_ROLE};
          END IF;
        END
        $$
        """  # noqa: S608  # constant role names only
    )
