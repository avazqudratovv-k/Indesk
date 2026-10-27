"""SECURITY.md "superuser database role" (DECISIONS #118): the app role can read and write rows and
nothing else. The test makes the roles when the cluster has none (CI), migrates as the migrator and
then works as the app role. Both sessions are opened with `options=-c role=...`, so no password is
needed and the dev roles are left exactly as they are."""

from collections.abc import Iterator

import pytest
from alembic import command
from psycopg.errors import InsufficientPrivilege
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ProgrammingError

from tests.db_helpers import admin_url, alembic_config, recreate_database
from tests.factories import make_user

APP, MIGRATOR = "indesk_app", "indesk_migrator"
DATABASE = "indesk_test_roles"


def as_role(url: str, role: str) -> URL:
    return make_url(url).update_query_dict({"options": f"-c role={role}"})


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    admin = create_engine(admin_url().set(database="postgres"), isolation_level="AUTOCOMMIT")
    created: list[str] = []
    with admin.connect() as conn:
        for role in (MIGRATOR, APP):
            if not conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}
            ).first():
                conn.execute(text(f"CREATE ROLE {role} NOLOGIN"))  # noqa: S608
                created.append(role)
    url = recreate_database(DATABASE)
    with admin.connect() as conn:
        conn.execute(text(f"ALTER DATABASE {DATABASE} OWNER TO {MIGRATOR}"))  # noqa: S608
        conn.execute(text(f"GRANT CONNECT ON DATABASE {DATABASE} TO {APP}"))  # noqa: S608
    command.upgrade(
        alembic_config(as_role(url, MIGRATOR).render_as_string(hide_password=False)), "head"
    )
    yield url
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{DATABASE}" WITH (FORCE)'))
        for role in created:
            conn.execute(text(f"DROP ROLE {role}"))  # noqa: S608
    admin.dispose()


@pytest.fixture
def app_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(as_role(database_url, APP))
    yield engine
    engine.dispose()


@pytest.fixture
def migrator_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(as_role(database_url, MIGRATOR), isolation_level="AUTOCOMMIT")
    yield engine
    engine.dispose()


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TABLE users",
        "ALTER TABLE users ADD COLUMN sneaky text",
        "CREATE TABLE sneaky (id int)",
        "TRUNCATE users",
        "SELECT * FROM alembic_version",
        "UPDATE alembic_version SET version_num = 'x'",
    ],
)
def test_the_app_role_cannot_change_the_schema(app_engine: Engine, statement: str) -> None:
    with app_engine.connect() as conn, pytest.raises(ProgrammingError) as caught:
        conn.execute(text(statement))
    assert isinstance(caught.value.orig, InsufficientPrivilege)  # SQLSTATE 42501


def test_the_app_role_is_not_a_superuser_and_owns_nothing(app_engine: Engine) -> None:
    with app_engine.connect() as conn:
        assert conn.execute(text("SELECT current_user")).scalar() == APP
        assert (
            conn.execute(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            ).scalar()
            is False
        )
        owned = conn.execute(
            text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public' AND tableowner = :r"),
            {"r": APP},
        ).scalar()
    assert owned == 0


def test_the_app_role_can_read_and_write_rows(app_engine: Engine) -> None:
    from sqlalchemy.orm import Session  # noqa: PLC0415

    with Session(app_engine) as db:
        user = make_user(db)
        db.commit()
        email = user.email
    with app_engine.begin() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM users WHERE email = :e"), {"e": email}).scalar()
            == 1
        )
        conn.execute(
            text("UPDATE users SET display_name = 'Renamed' WHERE email = :e"), {"e": email}
        )
        conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
        assert (
            conn.execute(text("SELECT count(*) FROM users WHERE email = :e"), {"e": email}).scalar()
            == 0
        )


def test_a_table_the_migrator_adds_later_is_usable_by_the_app_role(
    migrator_engine: Engine, app_engine: Engine
) -> None:
    with migrator_engine.connect() as conn:
        conn.execute(text("CREATE TABLE later_table (id int PRIMARY KEY)"))
    with app_engine.begin() as conn:
        conn.execute(text("INSERT INTO later_table VALUES (1)"))
        assert conn.execute(text("SELECT count(*) FROM later_table")).scalar() == 1
    with app_engine.connect() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("DROP TABLE later_table"))
    with migrator_engine.connect() as conn:
        conn.execute(text("DROP TABLE later_table"))  # the migrator still can


def test_migration_0004_downgrades_and_upgrades_again(
    database_url: str, app_engine: Engine
) -> None:
    config = alembic_config(as_role(database_url, MIGRATOR).render_as_string(hide_password=False))
    command.downgrade(config, "0003")
    with app_engine.connect() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("SELECT count(*) FROM users"))
    command.upgrade(config, "head")
    with app_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users")).scalar() is not None


# ---- migration 0005: PDF text and vectors (P14a) ----


def test_the_app_role_can_use_the_pdf_tables_and_the_vector_type(app_engine: Engine) -> None:
    from sqlalchemy.orm import Session  # noqa: PLC0415

    vector = "[" + ",".join(["0.25"] * 768) + "]"
    with Session(app_engine) as db:
        user = make_user(db)
        upload = db.execute(
            text(
                "INSERT INTO uploads (user_id, filename, mime, size, sha256, expires_at)"
                " VALUES (:u, 'a.pdf', 'application/pdf', 10, :h, now() + interval '1 day')"
                " RETURNING id"
            ),
            {"u": user.id, "h": "a" * 64},
        ).scalar_one()
        db.execute(
            text(
                "INSERT INTO document_pages (upload_id, owner_id, page, text, char_count)"
                " VALUES (:i, :u, 1, 'abc def', 7)"
            ),
            {"i": upload, "u": user.id},
        )
        db.execute(
            text(
                "INSERT INTO chunks (upload_id, owner_id, page, ord, char_start, char_end, text)"
                " VALUES (:i, :u, 1, 0, 0, 7, 'abc def')"
            ),
            {"i": upload, "u": user.id},
        )
        db.execute(
            text("UPDATE chunks SET embedding = CAST(:v AS vector), embedding_model = 'm'"),
            {"v": vector},
        )
        nearest = db.execute(
            text(
                "SELECT count(*) FROM (SELECT 1 FROM chunks"
                " ORDER BY embedding <=> CAST(:v AS vector) LIMIT 1) q"
            ),
            {"v": vector},
        ).scalar_one()
        assert nearest == 1
        db.execute(text("DELETE FROM chunks"))
        db.execute(text("DELETE FROM document_pages"))
        db.rollback()


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TABLE chunks",
        "DROP TABLE document_pages",
        "ALTER TABLE chunks ADD COLUMN sneaky text",
        "CREATE INDEX sneaky ON chunks (page)",
        "DROP EXTENSION vector",
        "TRUNCATE chunks",
    ],
)
def test_the_app_role_cannot_change_the_pdf_tables_or_the_extension(
    app_engine: Engine, statement: str
) -> None:
    with app_engine.connect() as conn, pytest.raises(ProgrammingError) as caught:
        conn.execute(text(statement))
    assert isinstance(caught.value.orig, InsufficientPrivilege)


def test_the_tables_belong_to_the_migrator(migrator_engine: Engine) -> None:
    with migrator_engine.connect() as conn:
        owners: dict[str, str] = dict(
            conn.execute(
                text(
                    "SELECT tablename, tableowner FROM pg_tables"
                    " WHERE tablename IN ('chunks', 'document_pages')"
                )
            )
            .tuples()
            .all()
        )
    assert owners == {"chunks": MIGRATOR, "document_pages": MIGRATOR}


def test_a_missing_extension_stops_the_migration_with_a_clear_message(database_url: str) -> None:
    """The migrator cannot create pgvector (only a superuser can); the migration says what to do."""
    url = recreate_database("indesk_test_migrations", vector=False)
    admin = create_engine(admin_url().set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"ALTER DATABASE indesk_test_migrations OWNER TO {MIGRATOR}"))  # noqa: S608
    admin.dispose()
    config = alembic_config(as_role(url, MIGRATOR).render_as_string(hide_password=False))
    with pytest.raises(Exception, match="CREATE EXTENSION vector"):
        command.upgrade(config, "head")
