"""Absolute session length: a refresh chain ends at login + SESSION_MAX_SECONDS (default 6 h),
whatever the number of refreshes. Time moves through `clock.utcnow`; nothing sleeps."""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Settings
from app.db.models import RefreshToken
from tests.db_helpers import alembic_config, recreate_database
from tests.factories import make_user
from tests.test_auth import cookie_headers, login, refresh_value, signup, with_cookie

SIX_HOURS = timedelta(hours=6)


def max_age(line: str) -> int:
    match = re.search(r"Max-Age=(\d+)", line)
    assert match
    return int(match.group(1))


def move_to(monkeypatch: pytest.MonkeyPatch, at: datetime) -> None:
    monkeypatch.setattr(clock, "utcnow", lambda: at)


def rows(conn: Connection) -> list[RefreshToken]:
    with Session(bind=conn) as db:
        return list(db.scalars(select(RefreshToken).order_by(RefreshToken.created_at)).all())


def test_refresh_at_5h59_works_and_expiry_stays_at_login_plus_6h(
    auth_client: TestClient, db_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.utcnow()
    move_to(monkeypatch, start)  # frozen, so the login time is exactly `start`
    signup(auth_client)
    move_to(monkeypatch, start + timedelta(hours=5, minutes=59))
    assert auth_client.post("/api/auth/refresh").status_code == 204
    newest = rows(db_connection)[-1]
    assert newest.expires_at == start + SIX_HOURS  # not refresh time + 6 h
    assert newest.session_started_at == start


def test_refresh_at_6h01_is_401(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.utcnow()
    move_to(monkeypatch, start)  # frozen, so the login time is exactly `start`
    signup(auth_client)
    move_to(monkeypatch, start + SIX_HOURS + timedelta(minutes=1))
    assert auth_client.post("/api/auth/refresh").status_code == 401


def test_a_chain_of_refreshes_cannot_outlive_the_original_login(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.utcnow()
    move_to(monkeypatch, start)  # frozen, so the login time is exactly `start`
    signup(auth_client)
    for hour in (2, 4, 5):
        move_to(monkeypatch, start + timedelta(hours=hour))
        assert auth_client.post("/api/auth/refresh").status_code == 204
    move_to(monkeypatch, start + SIX_HOURS + timedelta(minutes=1))
    assert auth_client.post("/api/auth/refresh").status_code == 401


def test_rotated_token_inherits_session_started_at(
    auth_client: TestClient, db_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.utcnow()
    move_to(monkeypatch, start)  # frozen, so the login time is exactly `start`
    signup(auth_client)
    move_to(monkeypatch, start + timedelta(hours=3))
    assert auth_client.post("/api/auth/refresh").status_code == 204
    first, second = rows(db_connection)
    assert first.session_started_at == start
    assert second.session_started_at == first.session_started_at
    assert first.family_id == second.family_id


def test_cookie_max_ages_are_capped_by_the_remaining_session(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.utcnow()
    move_to(monkeypatch, start)  # frozen, so the login time is exactly `start`
    first = signup(auth_client)
    cookies = cookie_headers(first)
    assert max_age(cookies["indesk_access"]) == 900
    assert max_age(cookies["indesk_refresh"]) == 21600
    move_to(monkeypatch, start + timedelta(hours=2))
    cookies = cookie_headers(auth_client.post("/api/auth/refresh"))
    assert max_age(cookies["indesk_access"]) == 900
    assert max_age(cookies["indesk_refresh"]) == 4 * 3600
    move_to(monkeypatch, start + SIX_HOURS - timedelta(minutes=5))
    cookies = cookie_headers(auth_client.post("/api/auth/refresh"))
    assert max_age(cookies["indesk_access"]) == 300  # min(900, remaining)
    assert max_age(cookies["indesk_refresh"]) == 300


def test_login_starts_a_new_session_clock(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.utcnow()
    move_to(monkeypatch, start)  # frozen, so the login time is exactly `start`
    signup(auth_client)
    later = start + timedelta(hours=7)
    move_to(monkeypatch, later)
    assert auth_client.post("/api/auth/refresh").status_code == 401
    assert login(auth_client).status_code == 200
    move_to(monkeypatch, later + timedelta(hours=5, minutes=59))
    assert auth_client.post("/api/auth/refresh").status_code == 204


def test_env_override_changes_the_limit(
    make_client: Callable[..., TestClient],
    auth_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(auth_settings.model_copy(update={"session_max_seconds": 600}))
    start = clock.utcnow()
    move_to(monkeypatch, start)  # frozen, so the login time is exactly `start`
    cookies = cookie_headers(signup(client))
    assert max_age(cookies["indesk_refresh"]) == 600
    move_to(monkeypatch, start + timedelta(minutes=11))
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_still_ends_the_session(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    signup(auth_client)
    token = refresh_value(auth_client)
    response = auth_client.post("/api/auth/logout")
    assert response.status_code == 204
    assert max_age(cookie_headers(response)["indesk_refresh"]) == 0
    replay = auth_client.post("/api/auth/refresh", headers=with_cookie("indesk_refresh", token))
    assert replay.status_code == 401


def test_reuse_detection_still_revokes_the_family(
    auth_client: TestClient, db_connection: Connection
) -> None:
    signup(auth_client)
    old = refresh_value(auth_client)
    assert auth_client.post("/api/auth/refresh").status_code == 204
    newest = refresh_value(auth_client)
    assert auth_client.post(
        "/api/auth/refresh", headers=with_cookie("indesk_refresh", old)
    ).status_code == 401
    assert auth_client.post(
        "/api/auth/refresh", headers=with_cookie("indesk_refresh", newest)
    ).status_code == 401
    assert all(r.revoked_at is not None for r in rows(db_connection))


def test_row_without_session_started_at_counts_from_created_at(
    auth_client: TestClient, db_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row from before migration 0006 has NULL; created_at is its login time."""
    signup(auth_client)
    with Session(bind=db_connection) as db:
        db.execute(text("UPDATE refresh_tokens SET session_started_at = NULL"))
        created = db.scalars(select(RefreshToken.created_at)).one()
    move_to(monkeypatch, created + SIX_HOURS + timedelta(minutes=1))
    assert auth_client.post("/api/auth/refresh").status_code == 401


def test_backfill_uses_the_earliest_created_at_of_each_family() -> None:
    url = recreate_database("indesk_test_migrations")
    config = alembic_config(url)
    command.upgrade(config, "0005")
    engine = create_engine(url)
    t0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    with Session(engine) as db, db.begin():
        user = make_user(db)
        db.flush()
        for token, family, offset in [
            ("a1", "11111111-1111-1111-1111-111111111111", 0),
            ("a2", "11111111-1111-1111-1111-111111111111", 90),
            ("a3", "11111111-1111-1111-1111-111111111111", 200),
            ("b1", "22222222-2222-2222-2222-222222222222", 50),
        ]:
            db.execute(
                text(
                    "INSERT INTO refresh_tokens (user_id, family_id, token_hash, expires_at,"
                    " created_at) VALUES (:u, :f, :h, :e, :c)"
                ),
                {
                    "u": user.id,
                    "f": family,
                    "h": token,
                    "e": t0 + timedelta(days=30),
                    "c": t0 + timedelta(minutes=offset),
                },
            )
    command.upgrade(config, "0006")
    with engine.connect() as conn:
        found = {
            str(h): at
            for h, at in conn.execute(
                text("SELECT token_hash, session_started_at FROM refresh_tokens")
            ).tuples()
        }
    assert found["a1"] == found["a2"] == found["a3"] == t0
    assert found["b1"] == t0 + timedelta(minutes=50)
    command.downgrade(config, "0005")
    with engine.connect() as conn:
        columns = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'refresh_tokens'"
            )
        ).scalars().all()
    assert "session_started_at" not in columns
    command.upgrade(config, "head")
    engine.dispose()
